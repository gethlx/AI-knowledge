#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把197条通俗解释注入 preview-data.json 的 cards[].fields["通俗解释"]。
真源: 02_分析产物/内容补齐/通俗解释-197概念-20261002.jsonl（不变）
本脚本可重跑（幂等）；preview-data.json 的卡文/边表其余部分零改动。
"""
import json, io, sys, hashlib

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
SRC = f"{ROOT}/02_分析产物/内容补齐/通俗解释-197概念-20261002.jsonl"
DST = f"{ROOT}/02_分析产物/图谱浏览器开发环境/src/ui/preview-data.json"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

plain = {}
with open(SRC, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            r = json.loads(line)
            plain[r["card_id"]] = r["plain"]
assert len(plain) == 197, f"补齐层应197条, 实际{len(plain)}"

pv = json.load(open(DST, encoding="utf-8"))
assert len(pv["cards"]) == 197

n_inject = 0
for c in pv["cards"]:
    cid = c["card_id"]
    assert cid in plain, f"缺 {cid} 的通俗解释"
    if c["fields"].get("通俗解释") != plain[cid]:
        c["fields"]["通俗解释"] = plain[cid]
        n_inject += 1

with open(DST, "w", encoding="utf-8") as f:
    json.dump(pv, f, ensure_ascii=False, separators=(",", ":"))

h = hashlib.sha256(open(DST, "rb").read()).hexdigest()
print(f"注入完成: {n_inject}条更新 / 197卡。新哈希: {h[:16]}…")
