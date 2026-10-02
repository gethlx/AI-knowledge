#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并金标准+六路分片，对账真源，跑去AI味机检，产出最终197条通俗解释。"""
import json, re, sys, io
from collections import Counter

ROOT = "/Users/larry/WorkBuddy/2026-09-13-14-09-47"
SPEC = f"{ROOT}/02_分析产物/内容补齐/写作规范与金标准-20261002.md"
SRC  = f"{ROOT}/02_分析产物/p0_baseline/card_evidence.jsonl"
OUT  = f"{ROOT}/02_分析产物/内容补齐/通俗解释-197概念-20261002.jsonl"
SHARDS = ["plain-K1-std", "plain-K1-rest", "plain-K2", "plain-K3", "plain-K4", "plain-K5", "plain-K6"]
SHARD_DIR = f"{ROOT}/02_分析产物/内容补齐"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ---------- 1. 从规范md解析金标准5条 ----------
spec_text = open(SPEC, encoding="utf-8").read()
gold = {}
for m in re.finditer(r"### (\d-\d+) ([^\n]+)\n(.*?)(?=\n### |\n## |\Z)", spec_text, re.S):
    cid, name, body = m.group(1), m.group(2).strip(), m.group(3).strip()
    body = body.replace("\\n", "\n")  # md里写的字面\n转真换行
    gold[cid] = {"card_id": cid, "name": name, "plain": body}
print(f"金标准解析: {len(gold)} 条 -> {sorted(gold)}")

# ---------- 2. 读真源 ----------
cards = {}
with open(SRC, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            c = json.loads(line)
            cards[c["card_id"]] = c
src_names = {cid: c["canonical_name"].split(" ", 1)[1] for cid, c in cards.items()}
print(f"真源卡数: {len(cards)}")

# ---------- 3. 合并 ----------
merged = {}
merged.update(gold)
for sh in SHARDS[1:]:
    path = f"{SHARD_DIR}/分片/{sh}.jsonl"
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r["card_id"] in merged:
                print(f"!! 重复card_id: {r['card_id']} ({sh})")
            merged[r["card_id"]] = r
            n += 1
    print(f"分片 {sh}: {n} 条")
print(f"合并总数: {len(merged)}")

# ---------- 4. 对账 ----------
errs, warns = [], []
missing = set(cards) - set(merged)
extra = set(merged) - set(cards)
if missing: errs.append(f"缺卡: {sorted(missing)}")
if extra: errs.append(f"多卡: {sorted(extra)}")

for cid, r in sorted(merged.items()):
    if cid not in cards: continue
    if r["name"] != src_names[cid]:
        errs.append(f"{cid} name不一致: '{r['name']}' != '{src_names[cid]}'")
    plain = r["plain"]
    n_chars = len(plain.replace("\n", ""))
    if not (180 <= n_chars <= 360):
        warns.append(f"{cid} 字数{n_chars}越界(180-360)")
    paras = plain.split("\n")
    if not (2 <= len(paras) <= 4):
        errs.append(f"{cid} 段数{len(paras)}异常")

# ---------- 5. 去AI味机检 ----------
BAN_WORDS = ["首先，", "其次，", "再次，", "最后，", "总而言之", "综上所述", "总的来说",
             "由此可见", "不难看出", "值得一提的是", "值得注意的是", "需要指出的是",
             "众所周知", "可以说，", "赋能", "抓手", "生态", "颗粒度", "降维打击",
             "底层逻辑", "强大", "卓越", "至关重要", "深远", "显著", "意义重大",
             "影响深远", "让我们", "在未来的", "发挥着重要作用", "起着重要作用"]
BAN_REGEX = [r"不仅.{0,15}更是", r"不仅.{0,15}也更是", r"既.{0,10}又.{0,10}更",
             r"无论是.{0,25}还是.{0,15}都", r"综上所述"]
hits = []
for cid, r in sorted(merged.items()):
    plain = r["plain"]
    for w in BAN_WORDS:
        if w in plain:
            hits.append(f"{cid} 禁词'{w}'")
    for rx in BAN_REGEX:
        if re.search(rx, plain):
            hits.append(f"{cid} 禁式'{rx}'")
    # 破折号≤2
    n_dash = plain.count("——")
    if n_dash > 2:
        warns.append(f"{cid} 破折号{n_dash}处(>2)")
    # 全角数字开头异常等略

# 开头句式重复检查
openers = Counter()
for r in merged.values():
    openers[r["plain"][:6]] += 1
for op, n in openers.items():
    if n >= 3:
        warns.append(f"开头'{op}'重复{n}次")

# ---------- 6. 输出 ----------
if errs:
    print("\n=== 错误（阻断）===")
    for e in errs: print(" ", e)
    sys.exit(1)
if hits:
    print("\n=== 禁词命中（需人工裁决/返工）===")
    for h in hits: print(" ", h)
else:
    print("\n禁词机检: 0命中")
if warns:
    print("\n=== 警告 ===")
    for w in warns: print(" ", w)
else:
    print("警告: 无")

with open(OUT, "w", encoding="utf-8") as f:
    for cid in sorted(merged, key=lambda x: (int(x.split("-")[0]), int(x.split("-")[1]))):
        f.write(json.dumps(merged[cid], ensure_ascii=False) + "\n")
print(f"\n已写出: {OUT} ({len(merged)}条)")
lens = [len(r["plain"].replace("\n","")) for r in merged.values()]
print(f"字数: min{min(lens)} / max{max(lens)} / avg{sum(lens)//len(lens)}")
