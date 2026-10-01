#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_f3_pipeline_loop.py —— F3 程序闭环端到端验证（32号"剩余修正范围"验收）。

全部本地假数据，不调用模型、不读 1,907 份原件、不改任何落盘数据。

覆盖（32号逐条对应）：
  T1 生成端拒绝：sol_api_bridge.validate 对 ACCEPTED 缺关系/缺方向、prerequisite 方向 null 拒绝
  T2 合法 v2 通过：sol_api_bridge.validate 与 multi_model_review.validate_adjudication_schema
     对合法完整 v2 记录通过（32号：消费端此前 additionalProperties 误拒 adopted_*）
  T3 反向先修 1-02→1-01：pair 1-01__1-02 + adopted_direction=target_to_source
     → build_edge_from_adjudication → build_graph.normalize → 生效端点 (1-02, 1-01)
  T4 相关入边：related → 边生成、direction=None
  T5 两类无边排除：no_relation / insufficient_evidence → 不生成边（附原因）
  T6 dry-run provider 端到端：假 bundle → adjudicate（v2）→ 校验 → 入边 → normalize/dag_check
  T7 方向一致性防御：direction 与 adopted_direction 不一致的边被 build_graph.normalize 拒绝
  T8 存量边界：v1 记录仍走 v1 手写校验（合法 v1 过、带 batch_mode 的历史形态按原规则拒）
  T9 停用护栏：p6_batch/p6_mega 无 P6_LEGACY_CONFIRM 时 exit 2
  T10 提示词：sol_api_bridge.build_prompt 输出 p1-contract-v2 与结构化字段要求
"""
import json
import subprocess
import sys
from pathlib import Path

PROG = Path(__file__).resolve().parent.parent  # 02_分析产物
sys.path.insert(0, str(PROG))

import adjudication_contract as contract
import sol_api_bridge as bridge
import multi_model_review as mmr
import build_graph

RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append((name, "PASS", ""))
        print(f"  ✓ {name}")
    except Exception as exc:
        RESULTS.append((name, "FAIL", str(exc)))
        print(f"  ✗ {name}: {exc}")


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


BASE_ADJ = {
    "pair_id": "1-01__1-02",
    "adjudicator": "gpt-5.6-sol(via-subagent)",
    "final_status": "ACCEPTED_MODEL_ADJUDICATED",
    "adopted_relation": "prerequisite",
    "adopted_direction": "target_to_source",
    "adopted_by": "orchestrator",
    "rationale": "逐项复核三路意见，证据逐字命中；尾句：采纳 prerequisite，方向 target_to_source。",
    "residual_risks": ["模型裁定，未人工逐条核验"],
    "reviewer_agreement": "三路一致 prerequisite target_to_source",
    "escalation_reason": None,
    "schema_version": "p1-contract-v2",
}


def v2_accept(**over):
    adj = dict(BASE_ADJ)
    adj.update(over)
    return adj


# ---- T1 生成端拒绝 ----
def t1_missing_relation():
    adj = v2_accept()
    del adj["adopted_relation"]
    errs = bridge.validate(adj, "1-01__1-02")
    expect(errs, "ACCEPTED 缺 adopted_relation 应被拒绝")
def t1_missing_direction():
    adj = v2_accept(adopted_relation="prerequisite", adopted_direction=None)
    errs = bridge.validate(adj, "1-01__1-02")
    expect(errs, "prerequisite 方向 null 应被拒绝")
def t1_wrong_version():
    adj = v2_accept(schema_version="p1-contract-v1")
    expect(bridge.validate(adj, "1-01__1-02"), "错版本应被拒绝")


# ---- T2 合法 v2 通过 ----
def t2_bridge_ok():
    adj = v2_accept(adopted_relation="prerequisite", adopted_direction="target_to_source")
    expect(bridge.validate(adj, "1-01__1-02") == [], f"应通过: {bridge.validate(adj, '1-01__1-02')}")
def t2_mmr_ok():
    adj = v2_accept(adopted_relation="related", adopted_direction=None)
    errs = mmr.validate_adjudication_schema(adj)
    expect(errs == [], f"消费端应通过合法 v2（32号：此前 additionalProperties 误拒）: {errs}")


# ---- T3 反向先修 1-02→1-01 ----
def t3_reverse_prerequisite():
    adj = v2_accept(adopted_relation="prerequisite", adopted_direction="target_to_source")
    expect(mmr.validate_adjudication_schema(adj) == [], "v2 校验应通过")
    edge, reason = contract.build_edge_from_adjudication(adj, "1-01", "1-02")
    expect(edge is not None, f"应生成边: {reason}")
    expect(edge["direction"] == "target_to_source", "direction 应=adopted_direction")
    expect(edge["adopted_direction"] == "target_to_source", "adopted_direction 应保留")
    s, t = build_graph.normalize(edge)
    expect((s, t) == ("1-02", "1-01"), f"生效端点应为 (1-02, 1-01)，实际 {(s, t)}")


# ---- T4 相关入边 ----
def t4_related_edge():
    adj = v2_accept(adopted_relation="related", adopted_direction=None)
    edge, reason = contract.build_edge_from_adjudication(adj, "1-01", "1-02")
    expect(edge is not None, f"related 应生成边: {reason}")
    expect(edge["relation_type"] == "related" and edge["direction"] is None, "related 边方向应为 null")
    expect(edge["schema_version"] == "p1-contract-v2", "边应记录来源契约版本")


# ---- T5 两类无边排除 ----
def t5_no_edge():
    for rel in ("no_relation", "insufficient_evidence"):
        adj = v2_accept(adopted_relation=rel, adopted_direction=None)
        edge, reason = contract.build_edge_from_adjudication(adj, "1-01", "1-02")
        expect(edge is None, f"{rel} 不得生成边")
        expect(rel in (reason or ""), f"{rel} 的跳过原因应说明: {reason}")


# ---- T6 dry-run provider 端到端 ----
def _fake_eval(rel, direction, confidence=0.8):
    raw = {"pair_id": "1-01__1-02", "reviewer_id": "reviewer_glm",
           "relation_type": rel, "direction": direction, "evidence": [],
           "reason": "假数据", "confidence": confidence, "input_card_hash": "x",
           "prompt_hash": "x", "status": "OK"}
    return mmr.OpinionEval(reviewer_id="reviewer_glm", raw=raw, valid=True,
                           invalid_reasons=[], redline_hits=[])

def t6_dryrun_e2e():
    provider = mmr.DryRunAdjudicationProvider()
    class _P:  # 最小 PairTask 桩
        pair_id = "1-01__1-02"; source = "1-01"; target = "1-02"; high_influence = False
    bundle = {"opinions": [_fake_eval("prerequisite", "target_to_source")] * 3,
              "redline_hits": []}
    adj = provider.adjudicate(_P(), bundle, None)  # graph_state 未用到
    errs = mmr.validate_adjudication_schema(adj)
    expect(errs == [], f"dry-run 产出的 v2 应通过校验: {errs}")
    expect(adj["adopted_relation"] == "prerequisite"
           and adj["adopted_direction"] == "target_to_source", "dry-run 应给结构化结论")
    edge, reason = contract.build_edge_from_adjudication(adj, "1-01", "1-02")
    expect(edge is not None, f"端到端应生成边: {reason}")
    s, t = build_graph.normalize(edge)
    expect((s, t) == ("1-02", "1-01"), f"端到端生效端点应 (1-02, 1-01)，实际 {(s, t)}")
    expect(build_graph.dag_check([edge]) == [], "单条反向先修边应无环")

def t6_dryrun_no_relation():
    provider = mmr.DryRunAdjudicationProvider()
    class _P:
        pair_id = "1-01__1-02"; source = "1-01"; target = "1-02"; high_influence = False
    bundle = {"opinions": [_fake_eval("no_relation", None)] * 3, "redline_hits": []}
    adj = provider.adjudicate(_P(), bundle, None)
    expect(adj["final_status"] == mmr.ST_REJECTED, "三路一致 no_relation 应为 REJECTED")
    expect(adj["adopted_relation"] == "no_relation", "应给结构化结论 no_relation")
    edge, reason = contract.build_edge_from_adjudication(adj, "1-01", "1-02")
    expect(edge is None, "no_relation 采纳后仍不得生成边")


# ---- T7 方向一致性防御 ----
def t7_direction_mismatch():
    bad = {"edge_id": "e_x", "pair_id": "1-01__1-02", "source": "1-01", "target": "1-02",
           "relation_type": "prerequisite", "direction": "source_to_target",
           "adopted_direction": "target_to_source"}
    try:
        build_graph.normalize(bad)
        raise AssertionError("direction≠adopted_direction 应被拒绝")
    except ValueError:
        pass


# ---- T8 存量 v1 边界 ----
def t8_v1_compat():
    v1_ok = {"pair_id": "1-01__1-02", "adjudicator": "gpt-5.6-sol(via-subagent)",
             "final_status": "ACCEPTED_MODEL_ADJUDICATED", "adopted_by": "orchestrator",
             "rationale": "r", "residual_risks": ["x"], "reviewer_agreement": "a",
             "escalation_reason": None, "schema_version": "p1-contract-v1"}
    expect(mmr.validate_adjudication_schema(v1_ok) == [], "合法 v1 存量应走 v1 路径通过")
    v1_extra = dict(v1_ok, batch_mode="tier2-matrix")
    expect(mmr.validate_adjudication_schema(v1_extra), "v1 带 batch_mode 应按原规则拒绝（历史行为不变）")


# ---- T9 停用护栏 ----
def t9_deprecated_guard():
    for script in ("p6_batch_adjudicator.py", "p6_mega_adjudicator.py"):
        r = subprocess.run([sys.executable, str(PROG / script)], capture_output=True, text=True)
        expect(r.returncode == 2, f"{script} 无确认时应 exit 2，实际 {r.returncode}")
        expect("DEPRECATED" in r.stdout + r.stderr, f"{script} 应输出停用声明")


# ---- T10 提示词 v2 ----
def t10_prompt_v2():
    cards = {"1-01": {"canonical_name": "1-01 人工智能", "fields": {"精确定义": "x"}},
             "1-02": {"canonical_name": "1-02 智能", "fields": {"精确定义": "y"}}}
    prompt = bridge.build_prompt("1-01__1-02", cards)
    expect("p1-contract-v2" in prompt, "实际生成提示词应输出 v2 版本标记")
    expect("adopted_relation" in prompt and "adopted_direction" in prompt,
           "实际生成提示词应要求结构化结论字段")
    expect("P9 教训" in prompt, "应包含 P9 教训警示")


ALL = [
    ("T1a ACCEPTED缺adopted_relation拒绝", t1_missing_relation),
    ("T1b prerequisite方向null拒绝", t1_missing_direction),
    ("T1c 错版本拒绝", t1_wrong_version),
    ("T2a 生成端合法v2通过", t2_bridge_ok),
    ("T2b 消费端合法v2通过(原additionalProperties误拒)", t2_mmr_ok),
    ("T3 反向先修1-02→1-01全链路", t3_reverse_prerequisite),
    ("T4 相关入边", t4_related_edge),
    ("T5 两类无边排除", t5_no_edge),
    ("T6a dry-run端到端(反向先修)", t6_dryrun_e2e),
    ("T6b dry-run no_relation不产边", t6_dryrun_no_relation),
    ("T7 direction≠adopted_direction拒绝", t7_direction_mismatch),
    ("T8 存量v1边界不变", t8_v1_compat),
    ("T9 旧批量入口停用护栏", t9_deprecated_guard),
    ("T10 实际提示词v2化", t10_prompt_v2),
]

if __name__ == "__main__":
    print(f"== F3 程序闭环端到端验证（{len(ALL)} 项，本地假数据，零模型调用）==")
    for name, fn in ALL:
        check(name, fn)
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    print(f"\n结果：{len(RESULTS) - len(fails)}/{len(RESULTS)} 通过")
    if fails:
        for n, _, e in fails:
            print(f"  FAIL {n}: {e}")
        sys.exit(1)
    print("F3 程序闭环 ✓：生成端拒绝缺字段、消费端接受合法 v2、入边取结构化结论、"
          "无关系/证据不足不产边、方向映射受校验、旧批量入口停用。")
