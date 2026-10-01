#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按原始最终裁定（adjudications.jsonl rationale 文字）重做 229 对分流。
只读复核：不重跑模型、不修改图谱数据。
输出五元组：最终关系、方向、出处（adjudications.jsonl 行号）、当前是否入图、处置理由。
"""
import json, re, sys
from collections import Counter, defaultdict

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
ADJ = f"{ROOT}/04_归档/图谱关系审计凭据/adjudications.jsonl"
EDGES = f"{ROOT}/02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl"
PREV = f"{ROOT}/02_分析产物/验收与记录收尾/229对待核定清单-20261001复核分流.json"
OUT = f"{ROOT}/02_分析产物/验收与记录收尾/229对按最终裁定分流-20261002.json"

# ---------- 1. 载入 229 对清单（对集合本身沿用，分类重做） ----------
with open(PREV) as f:
    prev = json.load(f)
pairs = []
for pid in prev.get("三路一致有关系_应程序采纳", []):
    pairs.append(pid["pair_id"] if isinstance(pid, dict) else pid)
for item in prev.get("两票分歧_需补裁定", []):
    pairs.append(item[0] if isinstance(item, list) else item)
for pid in prev.get("无关系排除", []):
    pairs.append(pid)
pairs = list(dict.fromkeys(pairs))
print(f"229 对清单载入：{len(pairs)} 对（去重后）")

# ---------- 2. 载入裁定记录（一对可能多条，保留全部行号） ----------
adj_by_pair = defaultdict(list)
with open(ADJ) as f:
    for lineno, line in enumerate(f, 1):
        rec = json.loads(line)
        adj_by_pair[rec["pair_id"]].append((lineno, rec))
print(f"adjudications.jsonl 共 {sum(len(v) for v in adj_by_pair.values())} 条 / {len(adj_by_pair)} 对")

# ---------- 3. 载入入图边 ----------
in_graph = {}
with open(EDGES) as f:
    for line in f:
        e = json.loads(line)
        in_graph[e["pair_id"]] = e
print(f"入图边真源：{len(in_graph)} 条")

# ---------- 4. rationale 结论提取 ----------
# 已验证句式（1-02__2-03 / 1-16__1-18）：
#  A. "结论为接受模型裁定：关系类型X，direction=Y"
#  B. "采纳 relation_type=X、direction=Y"
# 其他可能变体一并尝试；全部失败则判"含混需人工"。
PAT_A = re.compile(r"结论为(?:接受模型裁定|采纳模型裁定)?[:：]?\s*关系类型\s*([a-z_]+)\s*[,，]\s*direction\s*=\s*([a-z_]+)")
PAT_B = re.compile(r"采纳\s*relation_type\s*=\s*([a-z_]+)\s*[,，、]\s*direction\s*=\s*([a-z_]+)")
PAT_C = re.compile(r"最终(?:裁定|采纳)[:：]?\s*relation_type\s*=\s*([a-z_]+)\s*[,，、]\s*direction\s*=\s*([a-z_]+)")
PAT_D = re.compile(r"关系类型\s*([a-z_]+)\s*[,，]\s*direction\s*=\s*([a-z_]+)[^。]*。[^。]*(?:采纳|接受)")

def extract(rationale):
    """返回 (relation, direction, 句式标签)"""
    tail = rationale[-1200:]  # 结论位于尾部
    for pat, tag in [(PAT_A, "A:结论为接受模型裁定"), (PAT_B, "B:采纳relation_type"),
                     (PAT_C, "C:最终裁定"), (PAT_D, "D:变体")]:
        m = pat.search(tail)
        if m:
            return m.group(1), m.group(2), tag
    return None, None, "UNPARSED"

# ---------- 5. 逐对五元组 ----------
results = []
unparsed = []
for pid in sorted(pairs):
    recs = adj_by_pair.get(pid, [])
    if not recs:
        results.append({"pair_id": pid, "final_relation": None, "direction": None,
                        "source": None, "in_graph": pid in in_graph,
                        "disposition": "无裁定记录→需补裁", "pattern": "NO_RECORD",
                        "final_status": None, "prev_group": None})
        unparsed.append(pid)
        continue
    # 取最后一条裁定（多轮时以最末为准；同时记录全部行号）
    lineno, rec = recs[-1]
    rel, direction, tag = extract(rec["rationale"])
    status = rec.get("final_status")
    in_g = pid in in_graph
    # 分类
    if rel is None:
        disp = "结论含混无法解析→需补裁"
        unparsed.append(pid)
    elif rel in ("related", "prerequisite"):
        disp = "最终裁定有关系→应恢复入图" if not in_g else "最终裁定有关系且已入图→无需动作"
    elif rel in ("no_relation", "insufficient_evidence"):
        disp = "最终裁定无关系/证据不足→合理排除"
    else:
        disp = f"未识别的关系类型 {rel}→需人工核对"
        unparsed.append(pid)
    results.append({
        "pair_id": pid,
        "final_relation": rel,
        "direction": direction,
        "source": f"adjudications.jsonl 行{lineno}" + (f"（另有行{','.join(str(l) for l,_ in recs[:-1])}）" if len(recs) > 1 else ""),
        "in_graph": in_g,
        "disposition": disp,
        "pattern": tag,
        "final_status": status,
        "adjudicator": rec.get("adjudicator"),
    })

# ---------- 6. 统计 ----------
cnt = Counter(r["disposition"] for r in results)
print("\n=== 分流统计 ===")
for k, v in cnt.most_common():
    print(f"  {v:4d}  {k}")
pat_cnt = Counter(r["pattern"] for r in results)
print("\n=== 句式命中 ===")
for k, v in pat_cnt.most_common():
    print(f"  {v:4d}  {k}")
print(f"\n需人工/补裁对数：{len(set(unparsed))}")

# 交叉核对：三路意见 vs 最终裁定不一致的对（GPT 指出的类别）
rel_set = {r["pair_id"] for r in results if r["final_relation"] in ("related", "prerequisite")}
prev_no_rel = set(prev.get("无关系排除", []))
overlap = rel_set & prev_no_rel
print(f"\n[关键交叉] 旧分类'无关系排除'中按最终裁定实为有关系的对：{len(overlap)}")
if overlap:
    for pid in sorted(overlap):
        r = next(x for x in results if x["pair_id"] == pid)
        print(f"  {pid}: {r['final_relation']} (行{r['source']})")

prev_div = {item[0] if isinstance(item, list) else item for item in prev.get("两票分歧_需补裁定", [])}
overlap2 = rel_set & prev_div
print(f"[关键交叉] 旧分类'两票分歧'中按最终裁定已裁为有关系的对：{len(overlap2)}")

with open(OUT, "w") as f:
    json.dump({"generated": "2026-10-02",
               "basis": "adjudications.jsonl 原始最终裁定（rationale 文字结论），非三路意见",
               "total": len(results),
               "stats": dict(cnt),
               "records": results}, f, ensure_ascii=False, indent=1)
print(f"\n已落盘：{OUT}")
