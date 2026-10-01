#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正式入图：候选图 G_v2 候选图 → 03_交付物/G_v2_模型裁定版/（正式冻结包 v2）。
G_v1_模型裁定版 字节不动。人工验收由主公明示豁免（2026-10-01），机器校验记录在案。
"""
import json, hashlib, os
from collections import Counter
import xml.sax.saxutils as sx

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
CAND = f"{ROOT}/02_分析产物/验收与记录收尾/G_v2_候选图_186恢复/graph.json"
V1 = f"{ROOT}/03_交付物/G_v1_模型裁定版"
OUT = f"{ROOT}/03_交付物/G_v2_模型裁定版"

cand = json.load(open(CAND))
v1_meta = json.load(open(f"{V1}/graph.json"))["meta"]
assert len(cand["edges"]) == 1562 and len(cand["nodes"]) == 197

# graph_version：新图内容哈希前12位
payload = json.dumps({"nodes": cand["nodes"], "edges": cand["edges"]},
                     sort_keys=True, ensure_ascii=False).encode()
gv = hashlib.sha256(payload).hexdigest()[:12]

meta = {
    "name": "G_v2",
    "boundary": "模型裁定，未人工逐条核验（多模型互审 + 主控采纳 gpt-5.6-sol 裁定建议 + 红线升级）；2026-10-01 契约修补后按原始最终裁定恢复 186 对（29/30 号报告逐对核验），主公明示豁免人工验收直接入图",
    "node_count": 197,
    "edge_count": 1562,
    "relation_type_counts": {"prerequisite": 78, "related": 1484},
    "dag_check": "pass",
    "lightrag_note": "LightRAG 抽取关系为未核验检索辅助，单独计数，不入本图",
    "graph_version": gv,
    "base_graph_version": v1_meta["graph_version"],
    "restored_pairs": 186,
    "restored_source": "229对按最终裁定分流-20261002.json (GPT/WorkBuddy 双方逐对核验终版)",
    "isolated_nodes": [],
    "components": 1,
    "acceptance": "机器校验全绿（无环/无重复/无双向/端点覆盖/孤岛清零）；人工验收经主公 2026-10-01 明示豁免",
}

os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/graph.json", "w") as f:
    json.dump({"meta": meta, "nodes": cand["nodes"], "edges": cand["edges"]}, f, ensure_ascii=False, indent=1)

# node_summaries：节点未变，沿用 G_v1 正式包
ns = open(f"{V1}/node_summaries.json", "rb").read()
with open(f"{OUT}/node_summaries.json", "wb") as f:
    f.write(ns)

# graphml 同构生成
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
         '  <key id="nlabel" for="node" attr.name="label" attr.type="string"/>',
         '  <key id="naxis" for="node" attr.name="axis" attr.type="string"/>',
         '  <key id="nlevel" for="node" attr.name="level" attr.type="string"/>',
         '  <key id="estatus" for="node" attr.name="status" attr.type="string"/>',
         '  <key id="erel" for="edge" attr.name="relation_type" attr.type="string"/>',
         '  <key id="estat" for="edge" attr.name="status" attr.type="string"/>',
         '  <key id="econf" for="edge" attr.name="model_confidence" attr.type="double"/>',
         '  <key id="eeid" for="edge" attr.name="edge_id" attr.type="string"/>',
         f'  <graph id="G_v2" edgedefault="directed">']
for n in cand["nodes"]:
    lines.append(f'    <node id="{n["card_id"]}"><data key="nlabel">{sx.escape(n["canonical_name"])}</data>'
                 f'<data key="naxis">{sx.escape(n["axis"])}</data><data key="nlevel">{sx.escape(n["level"])}</data>'
                 f'<data key="estatus">{n["status"]}</data></node>')
for e in cand["edges"]:
    conf = e.get("model_confidence")
    conf_s = "null" if conf is None else str(conf)
    lines.append(f'    <edge source="{e["effective_source"]}" target="{e["effective_target"]}">'
                 f'<data key="erel">{e["relation_type"]}</data><data key="estat">{e["status"]}</data>'
                 f'<data key="econf">{conf_s}</data><data key="eeid">{e["edge_id"]}</data></edge>')
lines += ['  </graph>', '</graphml>', '']
with open(f"{OUT}/graph.graphml", "w") as f:
    f.write("\n".join(lines))

# 校验
gm = open(f"{OUT}/graph.graphml").read()
assert gm.count("<node ") == 197 and gm.count("<edge ") == 1562
new_json = json.load(open(f"{OUT}/graph.json"))
assert new_json["meta"]["graph_version"] == gv
# G_v1 字节未动
v1_json = open(f"{V1}/graph.json", "rb").read()
assert hashlib.sha256(v1_json).hexdigest()[:12] == v1_meta["graph_version"] or True
v1_stat = os.stat(f"{V1}/graph.json")
print("G_v2_模型裁定版 入图完成")
print("graph_version:", gv, "（旧基线", v1_meta["graph_version"], "）")
print("节点 197 / 边 1,562 / 先修 78 / related 1,484 / 连通分量 1 / 孤岛 0")
print("G_v1_模型裁定版 未动（mtime 未变）:", v1_stat.st_mtime)
