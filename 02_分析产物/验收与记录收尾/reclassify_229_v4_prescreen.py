#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v4：分流收尾。正则仅作初筛，产出全量审查材料供逐对语义终审。
已确认误判 5 对直接改判（GPT 第四轮，原文已核）；全量 229 对输出
「pair_id | 初筛结果 | rationale 尾部」供 LLM 终审。
"""
import json, re
from collections import Counter

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
ADJ = f"{ROOT}/04_归档/图谱关系审计凭据/adjudications.jsonl"
EDGES = f"{ROOT}/02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl"
PREV = f"{ROOT}/02_分析产物/验收与记录收尾/229对待核定清单-20261001复核分流.json"
OUT_REVIEW = f"{ROOT}/02_分析产物/验收与记录收尾/229对初筛参考材料-20261002.txt"

# GPT 第四轮确认的 5 处误判（原文已逐条核对），直接改判
GPT_FIX = {
    "1-01__5-15": ("no_relation", "采纳 no_relation、无方向，驳回 related 延伸解释"),
    "1-02__1-17": ("insufficient_evidence", "luna 虽建议 related，其证据未证明应落图关系，故不采纳该提案"),
    "1-05__1-16": ("no_relation", "luna_proposal 提出的 related 仅宽泛背景延伸，故不采纳"),
    "1-09__1-12": ("no_relation", "综合语义独立复核，建议将该对裁定为 no_relation，direction=null"),
    "1-10__6-41": ("insufficient_evidence", "不采纳 related 建议，也不直接断言 no_relation，保留为证据不足"),
}

NEG = re.compile(r"(不建立|不生成|不采纳|不采用|不升级|不附加|不落盘|不落边|不作为|不改为|不产生|不直接断言|不视作|不当作|不倾向|拒绝|驳回|否决|未采纳|未通过|无需|而非|不将其升级)")
ADOPT_CUE = re.compile(r"(采纳|结论|最终|建议|落盘|接受|裁定)")
POS_PATTERNS = [
    (re.compile(r"(?:建议(?:将该对)?|综合裁定(?:建议)?[:：]?|最终(?:建议)?|结论[:：]?)?(?:采纳|裁定为|判定为|维持)\s*(?:关系为\s*)?(?:relation_type\s*=\s*)?(related|prerequisite|no_relation|insufficient_evidence)"), "g1"),
    (re.compile(r"采纳\s*relation_type\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"落盘(?:为|关系为)\s*relation_type\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"关系类型\s*([a-z_]+)\s*[,，]\s*direction\s*=\s*([a-z_]+)"), "g1"),
    (re.compile(r"采纳先修边"), "prerequisite"),
    (re.compile(r"降为\s*(related|prerequisite|no_relation)"), "g1"),
    (re.compile(r"(?:为|是)\s*相关(?:但|而|且)?非先修"), "related"),
    (re.compile(r"均判\s*(related|prerequisite|no_relation|insufficient_evidence)"), "g1"),
    (re.compile(r"非(必要|必须)先修"), "related"),
]

def prescreen(rationale):
    """正则初筛，返回 (rel, 结论句)。仅供终审参考。"""
    has_seg = "\uff5c" in rationale
    tail = rationale.split("\uff5c")[-1] if has_seg else rationale[-1500:]
    for sent in reversed(re.split(r"[。；]", tail)):
        if not has_seg and not ADOPT_CUE.search(sent):
            continue
        rel = None
        for pat, grp in POS_PATTERNS:
            for m in pat.finditer(sent):
                ctx = sent[max(0, m.start()-30):m.end()+40]  # 前后双向否定检测
                if NEG.search(ctx):
                    continue
                rel = m.group(1) if grp == "g1" else grp
                break
            if rel:
                break
        if rel:
            return rel, sent.strip()[:90]
    return None, None

adj = {}
with open(ADJ) as f:
    for lineno, line in enumerate(f, 1):
        rec = json.loads(line)
        adj.setdefault(rec["pair_id"], []).append((lineno, rec))
in_graph = set()
with open(EDGES) as f:
    for line in f:
        in_graph.add(json.loads(line)["pair_id"])
with open(PREV) as f:
    prev = json.load(f)
pairs = []
for pid in prev["三路一致有关系_应程序采纳"]:
    pairs.append(pid["pair_id"] if isinstance(pid, dict) else pid)
for item in prev["两票分歧_需补裁定"]:
    pairs.append(item[0] if isinstance(item, list) else item)
pairs += prev["无关系排除"]
pairs = sorted(dict.fromkeys(pairs))

# 产出终审材料
with open(OUT_REVIEW, "w") as f:
    for i, pid in enumerate(pairs, 1):
        lineno, rec = adj[pid][-1]
        rel, evid = prescreen(rec["rationale"])
        if pid in GPT_FIX:
            rel = GPT_FIX[pid][0]
        flag = "★GPT改判" if pid in GPT_FIX else ""
        f.write(f"### {i:3d}/229 {pid} 行{lineno} 初筛={rel} {flag}\n")
        f.write(rec["rationale"].replace("\n", " ") + "\n\n")
print(f"初筛参考材料已产出（不得作为最终裁定）：{OUT_REVIEW}")
cnt = Counter(prescreen(adj[p][-1][1]["rationale"])[0] for p in pairs)
print("初筛分布（含 GPT 5 对改判前口径差异，仅供参考）：", dict(cnt))
