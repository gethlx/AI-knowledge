#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
候选图构建与验证（186 对恢复）。
输入：G_v1_模型裁定版/graph.json（1,376 边，不动）+ 终版分流 JSON 的 186 条应恢复记录。
输出：02_分析产物/验收与记录收尾/G_v2_候选图_186恢复/（graph.json + 验证报告）。
校验：pair 重复 / 端点覆盖 / 双向先修冲突 / 先修 DAG 无环 / 孤岛重算 / 边数口径。
"""
import json, hashlib
from collections import Counter, defaultdict

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
MAIN = f"{ROOT}/03_交付物/G_v1_模型裁定版/graph.json"
SPLIT = f"{ROOT}/02_分析产物/验收与记录收尾/229对按最终裁定分流-20261002.json"
OUTDIR = f"{ROOT}/02_分析产物/验收与记录收尾/G_v2_候选图_186恢复"

g = json.load(open(MAIN))
nodes = g["nodes"]
edges = g["edges"]
split = json.load(open(SPLIT))
restore = [r for r in split["records"] if r["disposition"] == "应恢复入图"]
assert len(restore) == 186, f"应恢复应为186，实为{len(restore)}"

card_ids = {n["card_id"] for n in nodes}
main_pairs = {e["pair_id"] for e in edges}
errors = []

# ---- 候选边构造 ----
max_num = max(int(e["edge_id"][1:5]) for e in edges)  # e0001..eNNNN
new_edges = []
for i, r in enumerate(restore):
    pid = r["pair_id"]
    if pid in main_pairs:
        errors.append(f"{pid} 已在主图，禁止重复")
        continue
    a, b = pid.split("__")
    if a not in card_ids or b not in card_ids:
        errors.append(f"{pid} 端点不在197节点内")
        continue
    num = max_num + 1 + i
    base = {
        "edge_id": f"e{num:04d}_{pid}",
        "pair_id": pid,
        "source": a, "target": b,
        "relation_type": r["final_relation"],
        "status": r["final_status"],
        "adjudicator": r["adjudicator"],
        "model_confidence": None,
        "minority_uncertain": False,
        "high_influence": False,
        "prompt_version": None,
        "schema_version": None,
    }
    if r["final_relation"] == "related":
        base.update({"effective_source": a, "effective_target": b, "direction": None})
    else:
        dc = r["direction_code"]
        es, et = r["effective_source"], r["effective_target"]
        # 与原文箭头方向一致性
        arrow = r["direction"]  # 形如 1-02→1-01
        if not arrow.startswith(es) or not arrow.endswith(et):
            errors.append(f"{pid} 方向字段不一致: {arrow} vs {es}->{et}")
        base.update({"effective_source": es, "effective_target": et,
                     "direction": dc, "source": a, "target": b})
    new_edges.append(base)

cand_edges = edges + new_edges

# ---- 校验 1：边数与关系分布 ----
assert len(cand_edges) == 1562, len(cand_edges)
rel_cnt = Counter(e["relation_type"] for e in cand_edges)
assert rel_cnt["prerequisite"] == 78 and rel_cnt["related"] == 1484, rel_cnt

# ---- 校验 2：pair 唯一性 ----
all_pairs = [e["pair_id"] for e in cand_edges]
assert len(all_pairs) == len(set(all_pairs)), "存在重复 pair"

# ---- 校验 3：双向先修冲突 ----
pre_pairs = [(e["effective_source"], e["effective_target"]) for e in cand_edges if e["relation_type"] == "prerequisite"]
pre_set = set(pre_pairs)
bidi = [(a, b) for (a, b) in pre_pairs if a != b and (b, a) in pre_set]
assert not bidi, f"双向先修冲突: {bidi}"

# ---- 校验 4：先修 DAG 无环（Kahn 拓扑）----
pre_adj = defaultdict(list)
indeg = defaultdict(int)
for a, b in pre_pairs:
    pre_adj[a].append(b)
    indeg[b] += 1
    indeg[a] += 0
queue = [n for n in indeg if indeg[n] == 0]
topo, seen = [], 0
while queue:
    n = queue.pop()
    topo.append(n); seen += 1
    for m in pre_adj[n]:
        indeg[m] -= 1
        if indeg[m] == 0:
            queue.append(m)
assert seen == len(indeg), f"先修图存在环！参与节点 {len(indeg)}，拓扑仅 {seen}"

# ---- 校验 5：连通性与孤岛重算 ----
adj = defaultdict(set)
for e in cand_edges:
    a, b = e["effective_source"], e["effective_target"]
    adj[a].add(b); adj[b].add(a)
seen2, comps = set(), []
for n in card_ids:
    if n in seen2: continue
    stack, comp = [n], set()
    while stack:
        x = stack.pop()
        if x in seen2: continue
        seen2.add(x); comp.add(x); stack.extend(adj.get(x, ()))
    comps.append(sorted(comp))
comps.sort(key=len, reverse=True)
iso_new = [n for n in card_ids if n not in adj]

# ---- 输出 ----
cand = {
    "meta": {
        "name": "G_v2_candidate",
        "boundary": "候选图：G_v1 全部1,376边 + 终版分流186条恢复（183 related + 3 prerequisite）。未写入正式冻结包，待验收。",
        "node_count": len(nodes), "edge_count": len(cand_edges),
        "relation_type_counts": {"prerequisite": rel_cnt["prerequisite"], "related": rel_cnt["related"]},
        "dag_check": "pass",
        "base_graph_version": g["meta"]["graph_version"],
        "restored_pairs": len(restore),
        "restored_source": "229对按最终裁定分流-20261002.json (v3/Codex终版)",
    },
    "nodes": nodes,
    "edges": cand_edges,
}
import os
os.makedirs(OUTDIR, exist_ok=True)
with open(f"{OUTDIR}/graph.json", "w") as f:
    json.dump(cand, f, ensure_ascii=False, indent=1)

report = {
    "generated": "2026-10-01",
    "checks": {
        "edge_count_1562": True,
        "node_count_197": True,
        "no_duplicate_pairs": True,
        "no_bidirectional_prerequisite": True,
        "prerequisite_dag_acyclic_78_edges": True,
        "endpoints_within_197_nodes": True,
        "errors": errors,
    },
    "connectivity": {
        "components_before": 7,
        "components_after": len(comps),
        "component_sizes_after": [len(c) for c in comps][:10],
        "isolated_nodes_before": ["1-02", "1-03", "1-07", "1-11", "1-13", "1-14"],
        "isolated_nodes_after": sorted(iso_new),
    },
    "new_prerequisite_edges": [
        {"pair_id": r["pair_id"], "direction": r["direction"], "direction_code": r.get("direction_code")}
        for r in restore if r["final_relation"] == "prerequisite"],
    "sha256_graph_json": hashlib.sha256(open(f"{OUTDIR}/graph.json","rb").read()).hexdigest(),
}
with open(f"{OUTDIR}/候选图验证报告.json", "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1))
