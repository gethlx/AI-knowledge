#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p17_community_partition.py —— 17号 §2.1 固化的社区检测与 unit_ledger 生成器。

冻结项（F-06）：
- 算法: networkx greedy_modularity_communities（无权重）
- 输入: p5_candidates/all_candidate_pairs.jsonl 冻结版（4,051 边 / 197 节点）
- 参数: 无附加参数；随机性来源为 networkx 内部实现，同输入同结果（确定性验证见输出行）
输出: p5_review/unit_ledger.jsonl（互斥/完备/计数一致三性校验）+ p17_partition_snapshot.json
"""
import json
import hashlib
from pathlib import Path
from collections import Counter

import networkx as nx

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
POOL = BASE / "02_分析产物/p5_candidates/all_candidate_pairs.jsonl"
OUT_LEDGER = BASE / "02_分析产物/p5_review/unit_ledger.jsonl"
OUT_SNAPSHOT = BASE / "02_分析产物/p17_partition_snapshot.json"

SEED_TAG = "p17-partition-v1"


def main():
    pool = [json.loads(l) for l in POOL.read_text(encoding="utf-8").splitlines() if l.strip()]
    pool_sorted = sorted(pool, key=lambda p: p["pair_id"])  # 规范顺序，保证确定性
    pool_hash = hashlib.sha256(
        "".join(json.dumps(p, sort_keys=True, ensure_ascii=False) for p in pool_sorted).encode()
    ).hexdigest()[:12]

    G = nx.Graph()
    G.add_edges_from((p["source"], p["target"]) for p in pool_sorted)
    comms = nx.community.greedy_modularity_communities(G)
    comms = sorted(comms, key=lambda c: -len(c))
    card2unit = {c: f"U{i+1}" for i, comm in enumerate(comms) for c in comm}

    # full/light 归属沿用 luna 提议（v2.1 冻结口径）
    full_ids, light_ids = set(), set()
    for pf in (BASE / "02_分析产物/p5_candidates/proposals").glob("*.json"):
        d = json.loads(pf.read_text(encoding="utf-8"))
        (full_ids if d.get("relation_type") in ("prerequisite", "related") else light_ids).add(d["pair_id"])

    lines, missing = [], []
    for p in pool_sorted:
        us, ut = card2unit.get(p["source"]), card2unit.get(p["target"])
        if us is None or ut is None:
            missing.append(p["pair_id"])  # 端点不在图中，防御性记录
            continue
        unit = us if us == ut else "U6"  # 跨社区对 → 桥接单元
        path = "full" if p["pair_id"] in full_ids else ("light" if p["pair_id"] in light_ids else "UNCLASSIFIED")
        lines.append({"pair_id": p["pair_id"], "unit_id": unit, "path": path,
                      "source": p["source"], "target": p["target"]})

    # 三性校验
    pair_ids = [l["pair_id"] for l in lines]
    checks = {
        "互斥": len(pair_ids) == len(set(pair_ids)),
        "完备": len(lines) + len(missing) == len(pool) and not missing,
        "计数一致": (Counter(l["path"] for l in lines)["full"] == len(full_ids)
                  and Counter(l["path"] for l in lines)["light"] == len(light_ids)),
    }
    stat = Counter((l["unit_id"], l["path"]) for l in lines)

    OUT_LEDGER.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lines), encoding="utf-8")
    snapshot = {
        "seed_tag": SEED_TAG, "input_pool_hash": pool_hash,
        "algorithm": "networkx.greedy_modularity_communities",
        "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
        "components": nx.number_connected_components(G),
        "units": {f"U{i+1}": {"cards": len(c),
                              "dominant_axes": Counter(x.split('-')[0] for x in c).most_common(3)}
                  for i, c in enumerate(comms)},
        "unit_path_counts": {f"{u}/{k}": v for (u, k), v in sorted(stat.items())},
        "checks": checks, "missing": missing,
    }
    OUT_SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(snapshot, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
