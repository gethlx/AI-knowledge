#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multi_model_review.py 端到端测试（直接 import 调函数，不调真实 LLM API）。

场景：
  a) 三路一致+证据命中+无红线 → ACCEPTED_MODEL_ADJUDICATED
  b) 两路一致一路明确反对 → ESCALATE_HUMAN
  c) 一路证据 quote 不在卡文 → 该路无效（invalid opinion），按剩余意见裁定
  d) sol 三次失败 → ADJUDICATION_DEFERRED 且不写 accepted
  e) 连续 10 个 deferred → 熔断退出码 3
  f) 表外实体意见被拒（R7：意见无效 + pair 升级人工）
  g) 旧字段回流意见触发 R8 → ESCALATE_HUMAN
  h) dry-run 全流程跑通 + 重跑幂等（第二次 0 新增）
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import multi_model_review as mmr

BASELINE_DIR = Path(__file__).resolve().parent / "p0_baseline"
CARDS = mmr.load_card_evidence(BASELINE_DIR)
CANONICAL_IDS = mmr.load_canonical_ids(BASELINE_DIR)


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------

def verbatim_quote(cid: str) -> dict[str, str]:
    return {"card_id": cid, "field": "精确定义", "quote": CARDS[cid]["fields"]["精确定义"]}


def make_opinion(pair_id: str, reviewer_id: str, relation_type: str, direction: str | None,
                 reason: str = "两卡卡文的精确定义显示其关系，依据卡文判断。",
                 evidence: list[dict[str, str]] | None = None) -> dict:
    if evidence is None:
        src, tgt = pair_id.split("__", 1)
        evidence = [verbatim_quote(src), verbatim_quote(tgt)]
    return {
        "pair_id": pair_id,
        "reviewer_id": reviewer_id,
        "model_requested": mmr.REVIEWER_MODELS[reviewer_id],
        "model_returned": mmr.REVIEWER_MODELS[reviewer_id],
        "relation_type": relation_type,
        "direction": direction,
        "evidence": evidence,
        "reason": reason,
        "confidence": 0.9,
        "input_card_hash": "FILLED_AT_CALL_TIME",
        "prompt_hash": "FILLED_AT_CALL_TIME",
        "status": "REVIEW_COMPLETED",
    }


class CannedReviewProvider(mmr.ReviewProvider):
    """按 pair_id 提供预制意见模板；template_fn(pair) 返回 None 表示缺文件。"""

    def __init__(self, reviewer_id: str, template_fn):
        self.reviewer_id = reviewer_id
        self.model_requested = mmr.REVIEWER_MODELS[reviewer_id]
        self.template_fn = template_fn

    def get_opinion(self, pair, bundle):
        tpl = self.template_fn(pair, self.reviewer_id)
        if tpl is None:
            return None
        op = copy.deepcopy(tpl)
        op["input_card_hash"] = bundle["card_content_hash"]
        op["prompt_hash"] = bundle["prompt_hash"]
        return op


def unanimous_provider_set(pair_id: str, relation_type: str, direction: str | None,
                           mutate=None) -> list[mmr.ReviewProvider]:
    """三路一致意见；mutate(reviewer_id, opinion) 可对单路意见做修改。"""
    def fn(pair, reviewer_id: str):
        op = make_opinion(pair_id, reviewer_id, relation_type, direction)
        if mutate is not None:
            op = mutate(reviewer_id, op)
        return op
    return [CannedReviewProvider(r, fn) for r in mmr.REVIEWERS]


class FailingSolProvider(mmr.AdjudicationProvider):
    """模拟 gpt-5.6-sol 不可用（8.5：超时/非法返回视同失败，计入重试）。"""

    def adjudicate(self, pair, bundle, graph_state):
        raise mmr.SolUnavailableError(f"模拟超时（>{mmr.SOL_TIMEOUT_SECONDS}s）")


class BreakerReport(Exception):
    pass


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def build_orch(workdir: Path, reviewers, adjudicator) -> mmr.Orchestrator:
    return mmr.Orchestrator(
        workdir=workdir, cards=CARDS, canonical_ids=CANONICAL_IDS,
        review_providers=reviewers, adjudication_provider=adjudicator,
        retry_delays=(0, 30, 60), sleep_fn=None,  # 不真实 sleep，仅记录协议参数
    )


def make_pair(pair_id: str) -> mmr.PairTask:
    src, tgt = pair_id.split("__", 1)
    return mmr.PairTask(pair_id=pair_id, source=src, target=tgt)


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------

def test_a_three_way_consistent_accept(tmp: Path) -> None:
    orch = build_orch(tmp / "a", unanimous_provider_set("1-01__1-02", "prerequisite", "source_to_target"),
                      mmr.DryRunAdjudicationProvider())
    summary = orch.run([make_pair("1-01__1-02")])
    decisions = read_jsonl(orch.paths["decisions"])
    assert len(decisions) == 1
    d = decisions[0]
    assert d["final_status"] == mmr.ST_ACCEPTED, d
    assert d["adjudication"]["adjudicator"] == mmr.ADJUDICATOR_ID
    assert d["adjudication"]["adopted_by"] == "orchestrator"
    accepted = read_jsonl(orch.paths["accepted"])
    assert len(accepted) == 1
    edge = accepted[0]
    assert edge["relation_type"] == "prerequisite" and edge["direction"] == "source_to_target"
    assert edge["status"] == mmr.ST_ACCEPTED
    assert edge["evidence_match"] is True
    assert len(edge["cache_key"]) == 64  # sha256
    assert edge["review_independence"]["model_sources"] == [
        "glm5.3-flash", "deepseek4.1flash", "hy4"]
    assert summary["dag_violations"] == []
    print("  a) 三路一致 → ACCEPTED_MODEL_ADJUDICATED ✓")


def test_b_two_vs_one_explicit_oppose(tmp: Path) -> None:
    pair_id = "1-02__1-03"

    def fn(pair, reviewer_id: str):
        if reviewer_id == "reviewer_hy4":
            return make_opinion(pair_id, reviewer_id, "no_relation", None,
                                reason="两卡卡文的精确定义分别描述不同对象，卡文未体现直接关系。")
        return make_opinion(pair_id, reviewer_id, "related", None)

    orch = build_orch(tmp / "b", [CannedReviewProvider(r, fn) for r in mmr.REVIEWERS],
                      mmr.DryRunAdjudicationProvider())
    summary = orch.run([make_pair(pair_id)])
    d = read_jsonl(orch.paths["decisions"])[0]
    assert d["final_status"] == mmr.ST_ESCALATE, d
    esc = read_jsonl(orch.paths["escalation"])
    assert len(esc) == 1
    assert "反对" in esc[0]["escalation_reason"]
    assert esc[0]["adjudication"]["reviewer_agreement"]  # sol 必须记录反对理由
    assert read_jsonl(orch.paths["accepted"]) == []
    assert summary[mmr.ST_ESCALATE] == 1
    print("  b) 两对一明确反对 → ESCALATE_HUMAN ✓")


def test_c_bad_quote_invalidates_opinion(tmp: Path) -> None:
    pair_id = "1-01__1-02"

    def mutate(reviewer_id: str, op: dict):
        if reviewer_id == "reviewer_hy4":
            op = copy.deepcopy(op)
            op["evidence"][0]["quote"] = op["evidence"][0]["quote"] + "（改写版本，非逐字）"
        return op

    orch = build_orch(tmp / "c", unanimous_provider_set(pair_id, "prerequisite", "source_to_target", mutate),
                      mmr.DryRunAdjudicationProvider())
    orch.run([make_pair(pair_id)])
    d = read_jsonl(orch.paths["decisions"])[0]
    assert d["final_status"] == mmr.ST_ACCEPTED, d  # 按剩余两路一致意见裁定
    hy4 = [r for r in d["reviewers"] if r["reviewer_id"] == "reviewer_hy4"][0]
    assert hy4["valid"] is False
    assert any("R6" in h["rule_id"] for h in hy4["redline_hits"])
    accepted = read_jsonl(orch.paths["accepted"])
    assert len(accepted) == 1  # 剩余两路一致仍可接受
    print("  c) R6 逐字校验失败 → 意见无效，按剩余意见裁定 ✓")


def test_d_sol_three_failures_deferred(tmp: Path) -> None:
    orch = build_orch(tmp / "d", unanimous_provider_set("1-02__1-03", "related", None),
                      FailingSolProvider())
    summary = orch.run([make_pair("1-02__1-03")])
    d = read_jsonl(orch.paths["decisions"])[0]
    assert d["final_status"] == mmr.ST_DEFERRED, d
    assert len(d["sol_attempts"]) == mmr.SOL_MAX_RETRIES  # 3 次重试计数
    assert [a["delay_before_seconds"] for a in d["sol_attempts"]] == [0, 30, 60]
    deferred = read_jsonl(orch.paths["deferred"])
    assert len(deferred) == 1 and deferred[0]["pair_id"] == "1-02__1-03"
    assert read_jsonl(orch.paths["accepted"]) == []  # 不写 accepted
    assert summary[mmr.ST_DEFERRED] == 1
    print("  d) sol 三次失败 → ADJUDICATION_DEFERRED，不写 accepted ✓")


def test_e_circuit_breaker_after_ten_deferred(tmp: Path) -> None:
    # 12 个互不相同的 pair，三路一致 related，sol 全部失败 → 第 10 个触发熔断
    pairs = []
    axis1 = sorted(cid for cid in CANONICAL_IDS if cid.startswith("1-"))[:13]
    for i in range(12):
        pairs.append(f"{axis1[i]}__{axis1[i + 1]}")

    def fn(pair, reviewer_id: str):
        return make_opinion(pair.pair_id, reviewer_id, "related", None)

    reviewers = [CannedReviewProvider(r, fn) for r in mmr.REVIEWERS]
    orch = build_orch(tmp / "e", reviewers, FailingSolProvider())
    breaker_report = None
    try:
        orch.run([make_pair(p) for p in pairs])
        raise BreakerReport("未触发熔断")
    except mmr.CircuitBreakerError as exc:
        breaker_report = exc.report
        assert breaker_report["processed"] == 10
        assert breaker_report["breaker_triggered"] is True
        assert len(breaker_report["breaker_report"]["deferred_pairs"]) == 10
    decisions = read_jsonl(orch.paths["decisions"])
    assert len(decisions) == 10  # 第 11、12 个 pair 未处理
    assert all(d["final_status"] == mmr.ST_DEFERRED for d in decisions)
    assert read_jsonl(orch.paths["accepted"]) == []

    # 端到端验证熔断退出码 3：经 CLI main() 走同一路径
    pairs_file = tmp / "e" / "pairs.jsonl"
    pairs_file.write_text("\n".join(json.dumps({"pair_id": p}) for p in pairs) + "\n",
                          encoding="utf-8")
    orig_build = mmr.build_providers
    mmr.build_providers = lambda mode, reviews_dir: (reviewers, FailingSolProvider())
    try:
        rc = mmr.main(["--mode", "dry-run", "--pairs", str(pairs_file),
                       "--workdir", str(tmp / "e" / "cli_workdir")])
    finally:
        mmr.build_providers = orig_build
    assert rc == 3, f"熔断应返回退出码 3，实际 {rc}"
    print("  e) 连续 10 个 deferred → 熔断，CLI 退出码 3 ✓")


def test_f_off_registry_entity_rejected(tmp: Path) -> None:
    pair_id = "1-01__1-02"

    def mutate(reviewer_id: str, op: dict):
        if reviewer_id == "reviewer_deepseek":
            op = copy.deepcopy(op)
            op["evidence"].append({"card_id": "9-99", "field": "精确定义", "quote": "不在任何规范卡中的引用"})
        return op

    orch = build_orch(tmp / "f", unanimous_provider_set(pair_id, "prerequisite", "source_to_target", mutate),
                      mmr.DryRunAdjudicationProvider())
    summary = orch.run([make_pair(pair_id)])
    d = read_jsonl(orch.paths["decisions"])[0]
    assert d["final_status"] == mmr.ST_ESCALATE, d  # R7：表外实体一律不得入图
    ds = [r for r in d["reviewers"] if r["reviewer_id"] == "reviewer_deepseek"][0]
    assert ds["valid"] is False and any(h["rule_id"] == "R7" for h in ds["redline_hits"])
    assert "R7" in d["adjudication"]["escalation_reason"]
    assert read_jsonl(orch.paths["accepted"]) == []
    assert summary[mmr.ST_ESCALATE] == 1
    print("  f) 表外实体（R7）→ 意见被拒 + 升级人工 ✓")


def test_g_legacy_field_backflow_r8(tmp: Path) -> None:
    pair_id = "1-02__1-03"

    def mutate(reviewer_id: str, op: dict):
        if reviewer_id == "reviewer_glm":
            op = copy.deepcopy(op)
            op["reason"] = "该卡在『前置概念』中已列出『后续概念』，故判断为 related。"  # 作废字段回流
        return op

    orch = build_orch(tmp / "g", unanimous_provider_set(pair_id, "related", None, mutate),
                      mmr.DryRunAdjudicationProvider())
    orch.run([make_pair(pair_id)])
    d = read_jsonl(orch.paths["decisions"])[0]
    assert d["final_status"] == mmr.ST_ESCALATE, d
    assert any(h["rule_id"] == "R8" for h in d["redline_hits"])
    assert "R8" in d["adjudication"]["escalation_reason"]
    assert read_jsonl(orch.paths["accepted"]) == []
    print("  g) 旧字段回流（R8）→ ESCALATE_HUMAN ✓")


def test_h_dry_run_end_to_end_and_idempotent(tmp: Path) -> None:
    workdir = tmp / "h" / "p1_review_run"
    argv = ["--mode", "dry-run", "--workdir", str(workdir)]
    rc1 = mmr.main(argv)
    assert rc1 == 0
    files = ["accepted_model_adjudicated_edges.jsonl", "rejected_model_adjudicated.jsonl",
             "escalation_queue.jsonl", "deferred_queue.jsonl",
             "review_incomplete_queue.jsonl", "decisions.jsonl"]
    for f in files:
        assert (workdir / f).is_file(), f"缺少产物 {f}"
    decisions1 = read_jsonl(workdir / "decisions.jsonl")
    accepted1 = read_jsonl(workdir / "accepted_model_adjudicated_edges.jsonl")
    rejected1 = read_jsonl(workdir / "rejected_model_adjudicated.jsonl")
    escalated1 = read_jsonl(workdir / "escalation_queue.jsonl")
    assert len(decisions1) == 5  # K1 前 5 对演示
    status_counts: dict[str, int] = {}
    for d in decisions1:
        status_counts[d["final_status"]] = status_counts.get(d["final_status"], 0) + 1
    assert status_counts == {mmr.ST_ACCEPTED: 3, mmr.ST_REJECTED: 1, mmr.ST_ESCALATE: 1}, status_counts
    assert len(accepted1) == 3 and len(rejected1) == 1 and len(escalated1) == 1

    # 重跑：幂等，第二次运行 0 新增
    rc2 = mmr.main(argv)
    assert rc2 == 0
    decisions2 = read_jsonl(workdir / "decisions.jsonl")
    accepted2 = read_jsonl(workdir / "accepted_model_adjudicated_edges.jsonl")
    rejected2 = read_jsonl(workdir / "rejected_model_adjudicated.jsonl")
    escalated2 = read_jsonl(workdir / "escalation_queue.jsonl")
    assert len(decisions2) == len(decisions1) == 5
    assert len(accepted2) == len(accepted1)
    assert len(rejected2) == len(rejected1)
    assert len(escalated2) == len(escalated1)
    # 断点续跑语义：accepted 先修边回灌 graph_state 后 DAG 校验依然无环
    print("  h) dry-run 全流程 + 幂等重跑（第二次 0 新增）✓")


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        test_a_three_way_consistent_accept,
        test_b_two_vs_one_explicit_oppose,
        test_c_bad_quote_invalidates_opinion,
        test_d_sol_three_failures_deferred,
        test_e_circuit_breaker_after_ten_deferred,
        test_f_off_registry_entity_rejected,
        test_g_legacy_field_backflow_r8,
        test_h_dry_run_end_to_end_and_idempotent,
    ]
    passed = 0
    with tempfile.TemporaryDirectory(prefix="p1_orch_test_") as td:
        tmp = Path(td)
        for t in tests:
            try:
                t(tmp)
                passed += 1
            except Exception as exc:  # noqa: BLE001
                import traceback
                print(f"FAIL {t.__name__}: {exc}")
                traceback.print_exc()
                return 1
    print(f"全部 {passed}/{len(tests)} 个场景 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
