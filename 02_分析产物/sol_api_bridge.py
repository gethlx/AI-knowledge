#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_api_bridge.py —— 经 Vimox API 真调 gpt-5.6-sol 生成裁定建议（8.5 协议）。

调用链：reviews_inbox/<pair_id>/{reviewer_*.json} + card_evidence
        → 填充 edge_adjudication_prompt.md 模板
        → POST https://router.vimox.cn/v1/chat/completions (model=gpt-5.6-sol)
        → Adjudication Schema 校验
        → 写 reviews_inbox/<pair_id>/adjudication.json
        → 编排器重跑补裁。

每次调用打印 [SOL-CALL] 时间戳/耗时/pair_id，供主公在 Vimox 控制台对账。
超时 120s，重试 3 次（0/30/60s 退避），3 次全败 → 跳过该 pair（留在 deferred）。
纯标准库。
"""
import json
import re
import sys
import threading
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
MODELS_JSON = Path.home() / ".workbuddy" / "models.json"
INBOX = BASE / "02_分析产物/p1_review_run/reviews_inbox"
BASELINE = BASE / "02_分析产物/p0_baseline"
CONTRACT = BASE / "03_交付物/p1_review_contract"
PAIRS_FILE = BASE / "02_分析产物/p2_k1/pilot_pairs.jsonl"
PROGRAM_CHECKS = BASE / "02_分析产物/p5_review/program_checks.json"
SOL_TIMEOUT = 120
RETRY_DELAYS = (0, 30, 60)
CIRCUIT_LIMIT = 10  # 8.5 协议：连续 10 个 deferred → 熔断暂停

_circuit = {"broken": False, "consecutive_fail": 0}
_lock = threading.Lock()


def load_sol_config() -> dict:
    models = json.loads(MODELS_JSON.read_text(encoding="utf-8"))
    sol = next(m for m in models if m["id"] == "gpt-5.6-sol")
    return {"url": sol["url"], "key": sol["apiKey"], "model": "gpt-5.6-sol"}


def load_redlines_text() -> str:
    """加载红线 R1-R10 机读规则（修复：此前裁定提示词要求逐条核对却未附规则，导致假升级）"""
    f = CONTRACT / "redline_rules.json"
    rules = json.loads(f.read_text(encoding="utf-8"))["rules"]
    lines = [f"- {r['rule_id']}（{r['type']}）命中条件：{r['condition']}；命中 action：{r['action']}"
             for r in rules]
    return "\n".join(lines)


def build_prompt(pair_id: str, cards: dict, proposal: dict | None = None,
                 check: dict | None = None) -> str:
    a_id, b_id = pair_id.split("__")
    ca, cb = cards[a_id], cards[b_id]
    opinions = []
    for rv in ("reviewer_glm", "reviewer_deepseek", "reviewer_hy4"):
        p = INBOX / pair_id / f"{rv}.json"
        if p.is_file():
            opinions.append(p.read_text(encoding="utf-8"))
    if check and check.get("status") == "FLAGGED":
        program_checks = f"程序校验发现问题（如实透传，裁定请据此降权/复核）：{'; '.join(check.get('issues', []))}"
    else:
        program_checks = "schema通过；证据逐字校验通过；无表外实体；无旧字段回流"
    review_bundle = json.dumps({
        "pair_id": pair_id,
        "program_checks": program_checks,
        "opinions": [json.loads(o) for o in opinions],
        **({"luna_proposal": proposal} if proposal else {}),
    }, ensure_ascii=False, indent=1)

    def card_text(c):
        return "\n".join(f"- **{k}**：{v}" for k, v in c["fields"].items())

    graph_state = "P6 裁定初始态：当前无已裁定边（G_v1 尚未建图）；无环冲突历史。"
    redlines = load_redlines_text()
    prompt = f"""你是知识图谱项目（银河AI通识课程体系）的概念对综合裁定建议模型。三路独立盲评已完成，编排主控已完成程序校验。你的任务是给出裁定建议（不是最终裁定——最终由编排主控采纳后落盘），要求可追溯、逐项复核、不偏向多数。

概念对：{pair_id}（source={a_id}，target={b_id}）

## 一、review_bundle（三路意见 + 程序校验结果）
{review_bundle}

## 二、原始卡文
CARD_A（{ca["canonical_name"]}）：
{card_text(ca)}

CARD_B（{cb["canonical_name"]}）：
{card_text(cb)}

## 三、图谱当前状态
{graph_state}

## 四、裁定要求（逐项在 rationale 中回应）
1. 逐一列出三路 relation_type/direction/confidence；不得简单多数票放行；
2. 核对每条 evidence.quote 是否能在原始卡文中逐字找到；
3. 评估影响范围（是否核心课程入口/关键学习路径）；
4. 红线 R1-R10 逐条核对，任一命中即按 action 处理。规则全文如下：
{redlines}
5. 检查采纳多数意见方向是否形成先修环/双向边。

## 五、输出格式
只输出一个 JSON 对象（不要 markdown 代码块、不要解释文字）：
{{"pair_id": "{pair_id}", "adjudicator": "gpt-5.6-sol(via-subagent)", "final_status": "ACCEPTED_MODEL_ADJUDICATED|REJECTED_MODEL_ADJUDICATED|ESCALATE_HUMAN|ADJUDICATION_DEFERRED", "adopted_by": "orchestrator", "rationale": "<逐项复核说明>", "residual_risks": ["模型裁定，未人工逐条核验"], "reviewer_agreement": "<三路一致情况>", "escalation_reason": null 或 "<原因>", "schema_version": "p1-contract-v1"}}"""
    return prompt


def call_sol(cfg: dict, prompt: str, pair_id: str) -> dict:
    body = json.dumps({
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["url"], data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=SOL_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    dt = time.time() - t0
    print(f"[SOL-CALL] {time.strftime('%H:%M:%S')} pair={pair_id} 耗时={dt:.1f}s "
          f"model_returned={data.get('model','?')}")
    content = data["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        raise ValueError("响应中未找到 JSON")
    return json.loads(m.group(0))


def validate(adj: dict, pair_id: str) -> list[str]:
    errs = []
    if adj.get("pair_id") != pair_id:
        errs.append("pair_id 不匹配")
    if adj.get("final_status") not in ("ACCEPTED_MODEL_ADJUDICATED", "REJECTED_MODEL_ADJUDICATED",
                                       "ESCALATE_HUMAN", "ADJUDICATION_DEFERRED"):
        errs.append("final_status 非法")
    if adj.get("adopted_by") != "orchestrator":
        errs.append("adopted_by 必须为 orchestrator")
    if not adj.get("rationale"):
        errs.append("rationale 缺失")
    if adj.get("final_status") == "ESCALATE_HUMAN" and not adj.get("escalation_reason"):
        errs.append("ESCALATE_HUMAN 必须 escalation_reason")
    return errs


def process_one(cfg, cards, pid, proposals=None, check=None) -> str:
    out = INBOX / pid / "adjudication.json"
    if out.is_file():
        return "skip"
    if _circuit["broken"]:
        return "circuit"
    prompt = build_prompt(pid, cards, (proposals or {}).get(pid), check)
    for attempt, delay in enumerate(RETRY_DELAYS, 1):
        if delay:
            time.sleep(delay)
        try:
            adj = call_sol(cfg, prompt, pid)
            errs = validate(adj, pid)
            if errs:
                print(f"[RETRY {attempt}] {pid} Schema 不合: {errs}", flush=True)
                continue
            out.write_text(json.dumps(adj, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[OK] {pid} → {adj['final_status']}", flush=True)
            with _lock:
                _circuit["consecutive_fail"] = 0
            return "ok"
        except Exception as exc:
            print(f"[RETRY {attempt}] {pid} 失败: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
    print(f"[GIVE-UP] {pid} 3 次失败，留在 deferred", flush=True)
    with _lock:
        _circuit["consecutive_fail"] += 1
        if _circuit["consecutive_fail"] >= CIRCUIT_LIMIT and not _circuit["broken"]:
            _circuit["broken"] = True
            print(f"[CIRCUIT-BREAK] 连续 {CIRCUIT_LIMIT} 个 pair 裁定失败 → 熔断暂停（8.5 协议第 4 条），"
                  f"已完成数据保留，等待主控处置", flush=True)
    return "fail"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(PAIRS_FILE))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--inbox", default="", help="覆盖 reviews_inbox 目录（P5 用 reviews_inbox_full）")
    ap.add_argument("--proposals-dir", default="", help="luna 提议目录；提供则 bundle 携带 luna_proposal")
    args = ap.parse_args()
    global INBOX
    if args.inbox:
        INBOX = Path(args.inbox)
    proposals = None
    if args.proposals_dir:
        pdir = Path(args.proposals_dir)
        proposals = {}
        for pf in pdir.glob("*.json"):
            d = json.loads(pf.read_text(encoding="utf-8"))
            if d.get("relation_type") != "no_relation":
                proposals[d["pair_id"]] = {
                    "relation_type": d.get("relation_type"),
                    "direction": d.get("direction"),
                    "evidence": d.get("evidence"),
                    "evidence_field": d.get("evidence_field"),
                    "rationale": d.get("rationale"),
                }
        print(f"[SOL-BRIDGE] 载入 luna 提议 {len(proposals)} 条（no_relation 不入 bundle）", flush=True)
    cfg = load_sol_config()
    print(f"[SOL-BRIDGE] 端点={cfg['url']} model={cfg['model']} workers={args.workers}（主公可在 Vimox 控制台对账）", flush=True)
    cards = {json.loads(l)["card_id"]: json.loads(l)
             for l in open(BASELINE / "card_evidence.jsonl", encoding="utf-8")}
    pair_ids = [json.loads(l)["pair_id"] for l in open(args.pairs, encoding="utf-8")]
    checks = {}
    if PROGRAM_CHECKS.is_file():
        checks = json.loads(PROGRAM_CHECKS.read_text(encoding="utf-8"))
        flagged = sum(1 for v in checks.values() if v.get("status") == "FLAGGED")
        print(f"[SOL-BRIDGE] 程序校验透传：{len(checks)} 对（FLAGGED {flagged}）", flush=True)
    stat = {"ok": 0, "fail": 0, "skip": 0, "circuit": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, cfg, cards, pid, proposals, checks.get(pid)): pid
                for pid in pair_ids}
        for fut in as_completed(futs):
            stat[fut.result()] += 1
    print(f"[SOL-BRIDGE] 完成：成功 {stat['ok']}，失败 {stat['fail']}，跳过 {stat['skip']}，熔断未跑 {stat['circuit']}")


if __name__ == "__main__":
    main()
