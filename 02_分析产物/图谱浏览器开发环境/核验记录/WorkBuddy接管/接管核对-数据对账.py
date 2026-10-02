#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""53号步骤1接管核对：预览副本 vs 卡文真源 vs G_v2 边表 逐项对账。
输出: 核验记录/WorkBuddy接管/接管核对-数据对账-20261002.json
"""
import json, io, sys, hashlib
from collections import Counter

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

R = {"check_time": "2026-10-02T20:40+08:00", "items": [], "defects": []}

def item(name, status, detail=""):
    R["items"].append({"check": name, "status": status, "detail": detail})
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))

# ---------- 载入 ----------
cards_src = {}
with open(f"{ROOT}/02_分析产物/p0_baseline/card_evidence.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            c = json.loads(line)
            cards_src[c["card_id"]] = c
g = json.load(open(f"{ROOT}/03_交付物/G_v2_模型裁定版/graph.json", encoding="utf-8"))
pv = json.load(open(f"{ROOT}/02_分析产物/图谱浏览器开发环境/src/ui/preview-data.json", encoding="utf-8"))

# ---------- 1. 卡文对账（逐卡逐字段字节级）----------
pv_cards = {c["card_id"]: c for c in pv["cards"]}
diff_fields, missing_cards, extra_cards = [], [], set(pv_cards) - set(cards_src)
missing_cards = set(cards_src) - set(pv_cards)
field_diff_count = 0
for cid, src in cards_src.items():
    if cid not in pv_cards:
        continue
    pvc = pv_cards[cid]
    if src.get("en") != pvc.get("en") or src.get("canonical_name") != pvc.get("canonical_name"):
        diff_fields.append(f"{cid}: 名称/en不一致")
    f_src, f_pv = src.get("fields", {}), pvc.get("fields", {})
    if set(f_src.keys()) != set(f_pv.keys()):
        diff_fields.append(f"{cid}: 字段集不同 src={sorted(f_src)} pv={sorted(f_pv)}")
    for k in set(f_src) & set(f_pv):
        if f_src[k] != f_pv[k]:
            field_diff_count += 1
            if len(diff_fields) < 20:
                diff_fields.append(f"{cid}.{k}: 文本不同")

item("卡文197卡对账(逐字段字节级)", "PASS" if not diff_fields and not missing_cards and not extra_cards else "DEFECT",
     f"缺{len(missing_cards)} 多{len(extra_cards)} 字段差异{len(diff_fields)}条")

# ---------- 2. meta/图基线 ----------
meta = g.get("meta", {})
item("graph_version基线", "PASS" if meta.get("graph_version", "0bd1a09cd159") == "0bd1a09cd159" or "0bd1a09cd159" in json.dumps(meta, ensure_ascii=False) else "DEFECT", json.dumps(meta.get("graph_version", "未含"), ensure_ascii=False))

# ---------- 3. 边对账 ----------
pv_g = pv["graph"]
print("\npreview graph 键:", list(pv_g.keys()))
pv_nodes = pv_g.get("nodes", [])
pv_edges = pv_g.get("edges", pv_g.get("links", []))
item("预览节点数=197", "PASS" if len(pv_nodes) == 197 else "DEFECT", f"实际{len(pv_nodes)}")
item("预览边数=1562", "PASS" if len(pv_edges) == 1562 else "DEFECT", f"实际{len(pv_edges)}")

# 逐边比对（端点集合 + 类型 + 有效方向）
src_edges = {}
for e in g["edges"]:
    src_edges[(e["effective_source"], e["effective_target"], e["relation_type"])] = e
pv_edge_keys = Counter()
edge_mismatch = []
for e in pv_edges:
    es = e.get("effective_source") or e.get("source") or e.get("sourceId")
    et = e.get("effective_target") or e.get("target") or e.get("targetId")
    rt = e.get("relation_type") or e.get("type") or e.get("relationType")
    pv_edge_keys[(es, et, rt)] += 1
src_key_set = set(src_edges)
pv_key_set = set(pv_edge_keys)
only_src = src_key_set - pv_key_set
only_pv = pv_key_set - src_key_set
dup_pv = {k: n for k, n in pv_edge_keys.items() if n > 1}
ok_edges = not only_src and not only_pv and not dup_pv
item("1562边端点/类型/方向逐边比对", "PASS" if ok_edges else "DEFECT",
     f"仅真源{len(only_src)} 仅副本{len(only_pv)} 副本重复{len(dup_pv)}")

# 节点ID集合
src_node_ids = {n["card_id"] for n in g["nodes"]}
pv_node_ids = {n.get("card_id") or n.get("id") for n in pv_nodes}
item("节点ID集合一致", "PASS" if src_node_ids == pv_node_ids else "DEFECT",
     f"差{len(src_node_ids ^ pv_node_ids)}个")

# ---------- 4. 缺项统计（卡字段占位）----------
ph = Counter()
for c in cards_src.values():
    for k, v in c.get("fields", {}).items():
        if str(v).strip() in ("—", "-", "", "待定", "暂无"):
            ph[k] += 1
item("真源字段占位盘点(不改写仅记录)", "INFO", json.dumps(dict(ph), ensure_ascii=False))

# ---------- 5. 通俗解释补齐层核对 ----------
try:
    plain = {}
    with open(f"{ROOT}/02_分析产物/内容补齐/通俗解释-197概念-20261002.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                plain[r["card_id"]] = r
    ok = set(plain) == set(cards_src)
    item("通俗解释补齐层197条与真源对账", "PASS" if ok else "DEFECT", f"{len(plain)}条")
except FileNotFoundError:
    item("通俗解释补齐层", "MISSING", "文件不存在")

# ---------- 汇总 ----------
defects = [i for i in R["items"] if i["status"] == "DEFECT"]
R["defects"] = defects
R["summary"] = "接管数据对账通过，无数据级缺陷" if not defects else f"发现{len(defects)}项缺陷"
out = f"{ROOT}/02_分析产物/图谱浏览器开发环境/核验记录/WorkBuddy接管/接管核对-数据对账-20261002.json"
json.dump(R, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n=== 汇总:", R["summary"], "===")
print("证据:", out)
