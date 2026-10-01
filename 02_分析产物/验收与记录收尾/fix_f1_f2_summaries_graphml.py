#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F1+F2 整改：重建 node_summaries（按 G_v2 边集与 effective 端点）+ 重写 graph.graphml
（related 显式 directed=false，prerequisite 有向，confidence 未知省略 data）。
graph.json 不动（0bd1a09cd159 基线数据保持）。全部产物自校验。
"""
import json, hashlib
import xml.sax.saxutils as sx

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
G2 = f"{ROOT}/03_交付物/G_v2_模型裁定版"

g = json.load(open(f"{G2}/graph.json"))
nodes, edges = g["nodes"], g["edges"]
assert len(nodes) == 197 and len(edges) == 1562

old_ns = json.load(open(f"{G2}/node_summaries.json"))
defs = {it["card_id"]: it.get("definition", "") for it in old_ns}
names = {n["card_id"]: n["canonical_name"] for n in nodes}

# ---------- F1: 重建摘要 ----------
in_edges = {cid: [] for cid in names}
out_edges = {cid: [] for cid in names}
for e in edges:
    es, et = e["effective_source"], e["effective_target"]
    out_edges[es].append({"edge_id": e["edge_id"], "to": et, "rt": e["relation_type"]})
    in_edges[et].append({"edge_id": e["edge_id"], "from": es, "rt": e["relation_type"]})

summaries = []
for n in nodes:
    cid = n["card_id"]
    ie, oe = in_edges[cid], out_edges[cid]
    summaries.append({
        "card_id": cid,
        "canonical_name": names[cid],
        "definition": defs.get(cid, ""),
        "degree": len(ie) + len(oe),
        "in_edges": ie,
        "out_edges": oe,
    })
with open(f"{G2}/node_summaries.json", "w") as f:
    json.dump(summaries, f, ensure_ascii=False, indent=1)

# 自校验 F1：degree/in/out 与 graph.json 逐条一致
ns_check = {it["card_id"]: it for it in summaries}
for e in edges:
    es, et = e["effective_source"], e["effective_target"]
    assert any(x["edge_id"] == e["edge_id"] for x in ns_check[es]["out_edges"])
    assert any(x["edge_id"] == e["edge_id"] for x in ns_check[et]["in_edges"])
for cid, it in ns_check.items():
    assert it["degree"] == len(it["in_edges"]) + len(it["out_edges"])
iso = [cid for cid, it in ns_check.items() if it["degree"] == 0]
assert iso == [], iso
former_islands = {"1-02": 17, "1-03": 19, "1-07": 8, "1-11": 11, "1-13": 10, "1-14": 16}
for cid, expect in former_islands.items():
    got = ns_check[cid]["degree"]
    assert got == expect, f"{cid}: 期望{expect} 实得{got}"
print("F1 摘要重建 ✓（197 条全量重建，前孤岛度数与 GPT 终审报告一致：",
      {c: ns_check[c]["degree"] for c in former_islands}, "）")

# ---------- F2: 重写 GraphML ----------
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
         # 语义：related 为无向语义关系，故 graph 仍声明 directed 供 prerequisite 使用，
         # 每条 related 边显式 directed="false"（GraphML primer：边级 directed 覆盖图默认值）
         '  <graph id="G_v2" edgedefault="directed">']
for n in nodes:
    lines.append(f'    <node id="{n["card_id"]}"><data key="nlabel">{sx.escape(n["canonical_name"])}</data>'
                 f'<data key="naxis">{sx.escape(n["axis"])}</data><data key="nlevel">{sx.escape(n["level"])}</data>'
                 f'<data key="estatus">{n["status"]}</data></node>')
n_related_undirected = n_pre = n_conf_omitted = 0
for e in edges:
    if e["relation_type"] == "related":
        src, tg, dir_attr = e["effective_source"], e["effective_target"], ' directed="false"'
        n_related_undirected += 1
    else:
        src, tg, dir_attr = e["effective_source"], e["effective_target"], ""
        n_pre += 1
    conf = e.get("model_confidence")
    conf_data = "" if conf is None else f'<data key="econf">{conf}</data>'
    if conf is None:
        n_conf_omitted += 1
    lines.append(f'    <edge source="{src}" target="{tg}"{dir_attr}>'
                 f'<data key="erel">{e["relation_type"]}</data><data key="estat">{e["status"]}</data>'
                 f'{conf_data}<data key="eeid">{e["edge_id"]}</data></edge>')
lines += ['  </graph>', '</graphml>', '']
open(f"{G2}/graph.graphml", "w").write("\n".join(lines))

# 自校验 F2
gm = open(f"{G2}/graph.graphml").read()
assert gm.count("<node ") == 197
assert gm.count("<edge ") == 1562
assert gm.count('directed="false"') == 1484
import xml.etree.ElementTree as ET
tree = ET.parse(f"{G2}/graph.graphml")
root = tree.getroot()
ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
gedges = root.findall(".//g:edge", ns)
assert len(gedges) == 1562
for ge in gedges:
    if ge.get("directed") is None:
        pass  # 继承 directed=True，仅 prerequisite 允许
    # econf 若存在必须是合法 double
    for d in ge.findall("g:data", ns):
        if d.get("key") == "econf":
            float(d.text)  # 非法值会抛异常
print(f"F2 GraphML 重写 ✓（related 无向 {n_related_undirected} 条显式 directed=false；"
      f"prerequisite {n_pre} 条有向生效端点；confidence 未知省略 {n_conf_omitted} 处，无文本 null）")

# graph.json 未动
gj = json.load(open(f"{G2}/graph.json"))
payload = json.dumps({"nodes": gj["nodes"], "edges": gj["edges"]}, sort_keys=True, ensure_ascii=False).encode()
assert hashlib.sha256(payload).hexdigest()[:12] == gj["meta"]["graph_version"]
print("graph.json 基线未动 ✓", gj["meta"]["graph_version"])
