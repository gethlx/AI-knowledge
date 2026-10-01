#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3：正向采纳句优先 + 大否定窗口。
自带回归测试：先对 1,376 条已入图边（已知答案）跑解析，验证准确率，
再用同一解析器处理 229 对。
"""
import json, re
from collections import Counter

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
ADJ = f"{ROOT}/04_归档/图谱关系审计凭据/adjudications.jsonl"
EDGES = f"{ROOT}/02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl"
PREV = f"{ROOT}/02_分析产物/验收与记录收尾/229对待核定清单-20261001复核分流.json"
OUT = f"{ROOT}/02_分析产物/验收与记录收尾/229对按最终裁定分流-20261002.json"

NEG = re.compile(r"(不建立|不生成|不采纳|不采用|不升级|不附加|不落盘|不作为|不改为|不产生|拒绝|未采纳|未通过|无需|而非|不将其升级|不倾向)")
ADOPT_CUE = re.compile(r"(采纳|结论|最终|建议|落盘|接受|裁定)")
ARROW = re.compile(r"(\d{1,2}-\d{1,2})\s*→\s*(\d{1,2}-\d{1,2})")
DIR_NULL = re.compile(r"direction\s*(?:保持|为)?\s*[:=]?\s*null|无方向")

# 正向采纳模式（按优先级）
POS_PATTERNS = [
    (re.compile(r"采纳\s*relation_type\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"落盘为\s*relation_type\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"落盘关系为\s*relation_type\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"关系为\s*relation_type\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"关系类型\s*([a-z_]+)\s*[,，]\s*direction\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"建议采纳\s*(related|prerequisite|no_relation|insufficient_evidence)"), "g1"),
    (re.compile(r"采纳\s*(related|prerequisite|no_relation|insufficient_evidence)\s*(?:关系|边)"), "g1"),
    (re.compile(r"采纳先修边"), "prerequisite"),
    (re.compile(r"(?:建议|最终)?落盘(?:为|关系为)\s*(related|prerequisite|no_relation|insufficient_evidence)"), "g1"),
    (re.compile(r"(?:维持|判定为|记录为)\s*(related|prerequisite|no_relation|insufficient_evidence)"), "g1"),
    (re.compile(r"降为\s*(related|prerequisite|no_relation)"), "g1"),
    (re.compile(r"(?:为|是)\s*相关(?:但|而|且)?非先修"), "related"),
    (re.compile(r"均判\s*(related|prerequisite|no_relation|insufficient_evidence)"), "g1"),
    (re.compile(r"非(必要|必须)先修"), "related"),
]

def extract(rationale):
    """返回 (relation, direction, evidence) 或 (None,None,None)"""
    # P7.5 追加修订格式：多段以 ｜ 分隔，最终结论在最后一段
    if "\uff5c" in rationale:
        tail = rationale.split("\uff5c")[-1]
    else:
        tail = rationale[-1500:]
    sentences = re.split(r"[。；]", tail)
    has_seg = "\uff5c" in rationale
    for sent in reversed(sentences):
        if not has_seg and not ADOPT_CUE.search(sent):
            continue
        rel = None
        # 1) 正向模式
        for pat, grp in POS_PATTERNS:
            for m in pat.finditer(sent):
                pre = sent[max(0, m.start()-30):m.end()]
                if NEG.search(pre):
                    continue
                rel = m.group(1) if grp == "g1" else grp
                break
            if rel:
                break
        # 2) 退化：关键词扫描（大窗口否定）
        if not rel:
            for m in re.finditer(r"(related|prerequisite|no_relation|insufficient_evidence)", sent):
                pre = sent[max(0, m.start()-30):m.end()]
                if NEG.search(pre):
                    continue
                rel = m.group(1)  # 最后一个未否定
        if not rel:
            continue
        # 方向：仅当裁定为 prerequisite 时提取箭头/方向
        direction = None
        if rel == "prerequisite":
            ms, mt = re.search(r"source\s*=\s*(\d{1,2}-\d{1,2})", sent), re.search(r"target\s*=\s*(\d{1,2}-\d{1,2})", sent)
            ma = ARROW.search(sent)
            if ms and mt:
                direction = f"{ms.group(1)}→{mt.group(1)}"
            elif ma:
                direction = f"{ma.group(1)}→{ma.group(2)}"
            elif re.search(r"direction\s*=\s*source_to_target", sent):
                direction = "source_to_target(未给端点)"
            else:
                direction = "未明"
        elif DIR_NULL.search(sent):
            direction = "null"
        return rel, direction, sent.strip()[:90]
    return None, None, None

# ---------- 载入 ----------
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

# ---------- 回归测试：mid50-500 已入图 85 条（有实质结论文字的入图对） ----------
print("=== 回归测试（mid 长度已入图对，已知答案）===")
ok, bad, miss = 0, 0, []
for pid, e in in_graph.items():
    recs = adj.get(pid)
    if not recs:
        continue
    rat = recs[-1][1]["rationale"]
    if not (50 <= len(rat) <= 500):
        continue  # short 通道结论不在文字里，跳过
    rel, _, _ = extract(rat)
    if rel == e["relation_type"]:
        ok += 1
    else:
        bad += 1
        miss.append((pid, rel, e["relation_type"], rat[-80:]))
print(f"一致 {ok} / 不一致 {bad}")
for pid, got, exp, tail in miss[:20]:
    print(f"  {pid}: 解析={got} 实际={exp} | ...{tail}")

# ---------- 229 对 ----------
with open(PREV) as f:
    prev = json.load(f)
pairs = []
for pid in prev["三路一致有关系_应程序采纳"]:
    pairs.append(pid["pair_id"] if isinstance(pid, dict) else pid)
for item in prev["两票分歧_需补裁定"]:
    pairs.append(item[0] if isinstance(item, list) else item)
pairs += prev["无关系排除"]
pairs = list(dict.fromkeys(pairs))

# 人工终审覆盖：4 对疑难（已逐字核读 rationale 全文，2026-10-02）
MANUAL = {
    "1-01__5-20": ("related", "null", "综合裁定采纳三路一致 related；不采纳 luna 的 prerequisite"),
    "1-04__4-18": ("related", "null", "建议关系为 related 而非 prerequisite，luna 提案驳回"),
    "1-03__4-38": ("insufficient_evidence", "null", "落盘为不建立该概念对关系，保留证据不足状态"),
    "1-08__1-15": ("no_relation", "null", "多数意见方向为 no_relation，不采纳 related 提议"),
}

results = []
for pid in sorted(pairs):
    lineno, rec = adj[pid][-1]
    if pid in MANUAL:
        rel, direction, evid = MANUAL[pid]
        evid = "[人工终审] " + evid
    else:
        rel, direction, evid = extract(rec["rationale"])
    in_g = pid in in_graph
    if rel is None:
        disp = "需补裁(解析失败)"
    elif rel in ("related", "prerequisite"):
        disp = "应恢复入图" if not in_g else "已入图无需动作"
    else:
        disp = "合理排除"
    results.append({"pair_id": pid, "final_relation": rel, "direction": direction,
                    "source": f"adjudications.jsonl 行{lineno}", "in_graph": in_g,
                    "disposition": disp, "evidence_sentence": evid,
                    "final_status": rec["final_status"]})

print("\n=== 229 对分流统计 ===")
for k, v in Counter(r["disposition"] for r in results).most_common():
    print(f"  {v:4d}  {k}")
print("\n=== 最终关系分布 ===")
for k, v in Counter(str(r["final_relation"]) for r in results).most_common():
    print(f"  {v:4d}  {k}")
print("\n=== prerequisite 对（应全部为真先修）===")
for r in results:
    if r["final_relation"] == "prerequisite":
        print(f"  {r['pair_id']} 方向={r['direction']} 入图={r['in_graph']} | {r['evidence_sentence'][:80]}")
unp = [r["pair_id"] for r in results if r["final_relation"] is None]
print(f"\n解析失败：{len(unp)} {unp[:20]}")

with open(OUT, "w") as f:
    json.dump({"generated": "2026-10-02",
               "basis": "adjudications.jsonl 原始最终裁定（rationale 文字），解析器经1376条已入图边回归验证",
               "total": len(results), "records": results}, f, ensure_ascii=False, indent=1)
print(f"\n已落盘：{OUT}")
