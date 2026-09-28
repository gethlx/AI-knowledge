#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P6 例外式复核确认器
====================
背景（14号裁定 §3.1 的执行口径，写入 17号报告）：
- luna 判 no_relation 的候选对走【例外式批量复核】：三路评审员只对"不同意 no_relation"
  的对输出意见文件（reviews_inbox_full/<pair>/reviewer_*.json），静默 = 确认；
- 本脚本收口：
  1) 任一评审路有异议的对 → 追加进 full_pairs_review2.jsonl（进入标准三路逐对评审管线）；
  2) 三路全静默的对 → 写 REJECTED_MODEL_ADJUDICATED 决策记录（luna no_relation +
     三路复核静默确认），存 light_confirmed_rejected.jsonl，不进 multi_model_review。

用法：python3 p6_light_confirm.py
"""
import json
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
P5 = BASE / "02_分析产物/p5_review"
INBOX = P5 / "reviews_inbox_full"
PROPOSALS = BASE / "02_分析产物/p5_candidates/proposals"
OUT_DISPUTE = P5 / "full_pairs_review2.jsonl"
OUT_CONFIRMED = P5 / "light_confirmed_rejected.jsonl"
REVIEWERS = ("reviewer_glm", "reviewer_deepseek", "reviewer_hy4")


def main():
    light = [json.loads(l) for l in (P5 / "light_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    disputes, confirmed, broken = [], [], []
    for p in light:
        pid = p["pair_id"]
        flags = []
        for rv in REVIEWERS:
            f = INBOX / pid / f"{rv}.json"
            if f.is_file():
                try:
                    flags.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    broken.append(f"{pid}/{rv}.json 不可解析")
        if flags:
            disputes.append({"pair_id": pid, "flaggers": [f["reviewer_id"] for f in flags],
                             "flag_types": [f["relation_type"] for f in flags]})
        else:
            pr = json.loads((PROPOSALS / f"{pid}.json").read_text(encoding="utf-8"))
            confirmed.append({
                "pair_id": pid, "source": p["source"], "target": p["target"],
                "final_status": "REJECTED_MODEL_ADJUDICATED",
                "mechanism": "luna no_relation + 三路例外式复核静默确认",
                "luna_rationale": pr.get("rationale", ""),
                "reviewer_silence": list(REVIEWERS),
                "decided_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
                "schema_version": "p1-contract-v1",
                "boundary": "模型裁定，未人工逐条核验",
            })

    with OUT_DISPUTE.open("w", encoding="utf-8") as f:
        for d in disputes:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with OUT_CONFIRMED.open("w", encoding="utf-8") as f:
        for c in confirmed:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"[LIGHT-CONFIRM] 复核对象 {len(light)} | 有异议→完整评审 {len(disputes)} | 静默确认拒绝 {len(confirmed)} | 坏文件 {len(broken)}")
    for b in broken[:5]:
        print("  ⚠", b)


if __name__ == "__main__":
    main()
