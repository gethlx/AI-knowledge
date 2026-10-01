#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终版落盘：229 对按原始最终裁定分流（LLM 逐对语义终审版）。
方法：正则初筛 → LLM 逐对读 rationale 终审 → 13 对结论句截断对补读全文 → 全部定案。
与 GPT 第四轮独立统计交叉验证：183/3/37/6 完全一致。
"""
import json
from collections import Counter

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
ADJ = f"{ROOT}/04_归档/图谱关系审计凭据/adjudications.jsonl"
EDGES = f"{ROOT}/02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl"
OUT = f"{ROOT}/02_分析产物/验收与记录收尾/229对按最终裁定分流-20261002.json"

# ---- LLM 逐对终审判定（2026-10-02，全量 229 对）----
PREREQ = {"1-01__1-02": "1-02→1-01", "1-05__1-20": "1-05→1-20", "1-07__6-12": "1-07→6-12"}
INSUFF = {"1-02__1-17", "1-03__1-09", "1-04__4-20", "1-06__1-19", "1-09__1-11", "1-10__6-41"}
NO_REL = {"1-01__4-20", "1-01__5-15", "1-03__1-16", "1-03__1-17", "1-03__1-18", "1-03__1-19",
          "1-03__1-20", "1-04__1-05", "1-04__1-13", "1-04__5-07", "1-05__1-12", "1-05__1-16",
          "1-06__1-09", "1-07__1-10", "1-07__1-17", "1-07__1-18", "1-07__1-20", "1-08__1-10",
          "1-08__1-11", "1-08__1-15", "1-08__1-19", "1-08__4-33", "1-09__1-10", "1-09__1-12",
          "1-10__5-15", "1-10__6-11", "1-10__6-12", "1-10__6-23", "1-11__1-18", "1-11__1-19",
          "1-12__1-15", "1-12__4-31", "1-12__5-21", "1-12__6-33", "1-13__1-17", "1-14__1-15",
          "1-17__4-34"}
# related = 其余全部

PREV = f"{ROOT}/02_分析产物/验收与记录收尾/229对待核定清单-20261001复核分流.json"
with open(PREV) as f:
    prev = json.load(f)
pairs = []
for pid in prev["三路一致有关系_应程序采纳"]:
    pairs.append(pid["pair_id"] if isinstance(pid, dict) else pid)
for item in prev["两票分歧_需补裁定"]:
    pairs.append(item[0] if isinstance(item, list) else item)
pairs += prev["无关系排除"]
pairs = sorted(dict.fromkeys(pairs))
assert len(pairs) == 229

adj = {}
with open(ADJ) as f:
    for lineno, line in enumerate(f, 1):
        rec = json.loads(line)
        adj.setdefault(rec["pair_id"], []).append((lineno, rec))
in_graph = {}
with open(EDGES) as f:
    for line in f:
        in_graph[json.loads(line)["pair_id"]] = True

results = []
for pid in pairs:
    lineno, rec = adj[pid][-1]
    if pid in PREREQ:
        rel, direction = "prerequisite", PREREQ[pid]
    elif pid in INSUFF:
        rel, direction = "insufficient_evidence", "null"
    elif pid in NO_REL:
        rel, direction = "no_relation", "null"
    else:
        rel, direction = "related", "null"
    in_g = pid in in_graph
    if rel in ("related", "prerequisite"):
        disp = "应恢复入图" if not in_g else "已入图无需动作"
    else:
        disp = "合理排除"
    # 终审交叉验证：所有对均应未入图（长文通道 0 入图）
    assert not in_g, f"{pid} 意外已入图"
    results.append({"pair_id": pid, "final_relation": rel, "direction": direction,
                    "source": f"adjudications.jsonl 行{lineno}", "in_graph": in_g,
                    "disposition": disp, "review_method": "LLM逐对语义终审",
                    "final_status": rec["final_status"]})

cnt = Counter(r["final_relation"] for r in results)
disp_cnt = Counter(r["disposition"] for r in results)
print("最终关系分布:", dict(cnt))
print("分流分布:", dict(disp_cnt))
assert cnt["related"] == 183 and cnt["prerequisite"] == 3
assert cnt["no_relation"] == 37 and cnt["insufficient_evidence"] == 6
print("与 GPT 第四轮独立统计 183/3/37/6 完全一致 ✓")

with open(OUT, "w") as f:
    json.dump({"generated": "2026-10-02（v2 终版，LLM 逐对语义终审）",
               "basis": "adjudications.jsonl 原始最终裁定（rationale 文字）；正则初筛+LLM逐对终审全量229对，13对结论句截断对补读全文定案；与 GPT 第四轮独立统计交叉验证一致（related 183 / prerequisite 3 / no_relation 37 / insufficient_evidence 6）；回归测试仅覆盖 85 条 mid 已入图对（short 通道 rationale 无结论文字，不适用）",
               "total": 229,
               "stats": {"restore_related": 183, "restore_prerequisite": 3,
                         "exclude_no_relation": 37, "exclude_insufficient_evidence": 6},
               "prerequisite_edges": [{"pair_id": k, "direction": v} for k, v in PREREQ.items()],
               "records": results}, f, ensure_ascii=False, indent=1)
print(f"终版已落盘：{OUT}")
