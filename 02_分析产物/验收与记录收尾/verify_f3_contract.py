#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F3 契约闭环用例验证：v2 写入契约（真实 Draft7 校验器 jsonschema 4.26）。
用例覆盖 GPT 终审 F3 表格 + 补充反向用例。结果落盘供终审核对。
"""
import json
from jsonschema import Draft7Validator

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
v2 = json.load(open(f"{ROOT}/03_交付物/p1_review_contract/edge_adjudication.v2.schema.json"))
Draft7Validator.check_schema(v2)

def base(**kw):
    rec = {
        "pair_id": "1-01__1-02", "adjudicator": "gpt-5.6-sol(via-subagent)",
        "final_status": "ACCEPTED_MODEL_ADJUDICATED", "adopted_by": "orchestrator",
        "rationale": "逐项复核结论", "residual_risks": ["模型裁定"],
        "reviewer_agreement": "三路一致", "escalation_reason": None,
        "schema_version": "p1-contract-v2",
        "adopted_relation": "related", "adopted_direction": None,
    }
    rec.update(kw)
    return rec

cases = [
    ("ACCEPTED 缺 adopted_relation/adopted_direction（GPT 用例1，应拒绝）",
     {k: v for k, v in base(adopted_relation="related", adopted_direction=None).items()
      if k not in ("adopted_relation", "adopted_direction")}, False),
    ("prerequisite 缺 adopted_direction（GPT 用例2，应拒绝）",
     base(adopted_relation="prerequisite", adopted_direction=None), False),
    ("prerequisite target_to_source 完整（GPT 用例3，应通过）",
     base(adopted_relation="prerequisite", adopted_direction="target_to_source"), True),
    ("prerequisite 完整 source_to_target（应通过）",
     base(adopted_relation="prerequisite", adopted_direction="source_to_target"), True),
    ("prerequisite 缺方向字段本身（应拒绝）",
     {k: v for k, v in base(adopted_relation="prerequisite", adopted_direction="source_to_target").items()
      if k != "adopted_direction"}, False),
    ("no_relation 完整（应通过）",
     base(adopted_relation="no_relation", adopted_direction=None), True),
    ("insufficient_evidence 完整（应通过）",
     base(adopted_relation="insufficient_evidence", adopted_direction=None), True),
    ("related 但误填方向（应拒绝）",
     base(adopted_relation="related", adopted_direction="source_to_target"), False),
    ("ESCALATE_HUMAN（ adopted 可为 null，应通过）",
     base(final_status="ESCALATE_HUMAN", escalation_reason="R3 红线 rule_id=RR-001",
          adopted_relation=None, adopted_direction=None), True),
    ("DEFERRED（adopted 可为 null，应通过）",
     base(final_status="ADJUDICATION_DEFERRED", adopted_relation=None, adopted_direction=None), True),
]

results, all_ok = [], True
v = Draft7Validator(v2)
for name, rec, expect in cases:
    errs = sorted(v.iter_errors(rec), key=lambda e: e.json_path)
    passed = (len(errs) == 0)
    ok = (passed == expect)
    all_ok &= ok
    results.append({"case": name, "expect": "pass" if expect else "reject",
                    "actual": "pass" if passed else "reject",
                    "verdict": "OK" if ok else "FAIL",
                    "errors": [f"{e.json_path}: {e.message[:120]}" for e in errs[:3]]})

out = {"checked_at": "2026-10-01", "schema": "edge_adjudication.v2.schema.json",
       "validator": "jsonschema Draft7 4.26.0", "all_pass": all_ok, "cases": results}
with open(f"{ROOT}/02_分析产物/验收与记录收尾/F3契约用例验证-20261001.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
for r in results:
    print(f"  [{r['verdict']}] {r['case']}  期望{r['expect']}/实际{r['actual']}")
    if r["verdict"] == "FAIL":
        print("    errors:", r["errors"])
print("全部用例", "通过 ✓" if all_ok else "存在失败 ✗")
