#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2：句级负向感知解析 rationale 最终裁定"""
import json, re
from collections import Counter

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
ADJ = f"{ROOT}/04_归档/图谱关系审计凭据/adjudications.jsonl"
PREV = f"{ROOT}/02_分析产物/验收与记录收尾/229对待核定清单-20261001复核分流.json"
OUT = f"{ROOT}/02_分析产物/验收与记录收尾/229对按最终裁定分流-20261002.json"
EDGES = f"{ROOT}/02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl"

with open(PREV) as f:
    prev = json.load(f)
pairs = []
for pid in prev["三路一致有关系_应程序采纳"]:
    pairs.append(pid["pair_id"] if isinstance(pid, dict) else pid)
for item in prev["两票分歧_需补裁定"]:
    pairs.append(item[0] if isinstance(item, list) else item)
pairs += prev["无关系排除"]
pairs = list(dict.fromkeys(pairs))

adj = {}
with open(ADJ) as f:
    for lineno, line in enumerate(f, 1):
        rec = json.loads(line)
        adj.setdefault(rec["pair_id"], []).append((lineno, rec))

in_graph = {}
with open(EDGES) as f:
    for line in f:
        e = json.loads(line)
        in_graph[e["pair_id"]] = e

NEG = re.compile(r"(不建立|不生成|不采纳|不采用|不升级|拒绝|未采纳|不将其升级|无需建立|无需采纳|不产生)")
REL_KW = re.compile(r"(related|prerequisite|no_relation|insufficient_evidence)")
ADOPT_CUE = re.compile(r"(采纳|结论|最终|建议|落盘|接受)")
DIR_ARROW = re.compile(r"(?:方向为|方向：)?(\d{1,2}-\d{1,2})\s*→\s*(\d{1,2}-\d{1,2})")
DIR_NULL = re.compile(r"direction\s*(?:保持|为)?\s*[:=]?\s*null|无方向|双向关系|无先修方向")

def extract(rationale):
    tail = rationale[-1500:]
    sentences = re.split(r"[。；]", tail)
    # 从尾部往前找第一个同时含"采纳线索"+"关系关键词"的句子
    for sent in reversed([s for s in sentences if s.strip()]):
        if not ADOPT_CUE.search(sent):
            continue
        # 收集句中关系提及，带否定标记
        adopted = None
        for m in REL_KW.finditer(sent):
            pre = sent[max(0, m.start()-14):m.start()]
            if NEG.search(pre):
                continue
            adopted = m.group(1)  # 取最后一个未被否定的
        if adopted is None:
            continue
        # 方向
        direction = None
        ma = DIR_ARROW.search(sent)
        mn = DIR_NULL.search(sent)
        if ma:
            direction = f"{ma.group(1)}→{ma.group(2)}"
        elif mn:
            direction = "null"
        # 方向未在本句：向相邻句找
        if direction is None:
            idx = sentences.index(sent)
            for nb in [sentences[idx+1] if idx+1 < len(sentences) else "",
                       sentences[idx-1] if idx-1 >= 0 else ""]:
                ma2 = DIR_ARROW.search(nb)
                mn2 = DIR_NULL.search(nb)
                if ma2:
                    direction = f"{ma2.group(1)}→{ma2.group(2)}"; break
                if mn2:
                    direction = "null"; break
        return adopted, direction, sent.strip()[:80]
    return None, None, None

results = []
for pid in sorted(pairs):
    recs = adj.get(pid, [])
    lineno, rec = recs[-1]
    rel, direction, evid = extract(rec["rationale"])
    in_g = pid in in_graph
    if rel is None:
        disp = "结论含混无法解析→需补裁"
    elif rel in ("related", "prerequisite"):
        disp = "应恢复入图" if not in_g else "已入图无需动作"
    elif rel in ("no_relation", "insufficient_evidence"):
        disp = "合理排除"
    else:
        disp = "异常关系类型→人工核对"
    results.append({"pair_id": pid, "final_relation": rel, "direction": direction,
                    "source": f"行{lineno}", "in_graph": in_g, "disposition": disp,
                    "evidence_sentence": evid, "final_status": rec["final_status"]})

cnt = Counter(r["disposition"] for r in results)
print("=== 分流统计 ===")
for k, v in cnt.most_common():
    print(f"  {v:4d}  {k}")
rel_cnt = Counter(r["final_relation"] for r in results)
print("\n=== 最终关系分布 ===")
for k, v in rel_cnt.most_common():
    print(f"  {v:4d}  {k}")

unparsed = [r for r in results if r["final_relation"] is None]
print(f"\n未解析：{len(unparsed)}")
for r in unparsed[:10]:
    print("  ", r["pair_id"])

# 方向分布（prerequisite 对）
prereqs = [r for r in results if r["final_relation"] == "prerequisite"]
print(f"\n最终裁定 prerequisite 共 {len(prereqs)} 对")
with open(OUT, "w") as f:
    json.dump({"generated": "2026-10-02", "basis": "adjudications.jsonl 原始最终裁定（rationale 文字）",
               "total": len(results), "stats": dict(cnt), "relation_dist": dict(rel_cnt),
               "records": results}, f, ensure_ascii=False, indent=1)
print(f"已落盘：{OUT}")
