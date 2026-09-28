#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P5 候选召回工具（14号裁定版）
================================
三路召回（高召回、后裁决）：
  R1 语义近邻路   ：glm-embedding-3-pro 向量，每卡 Top-K 近邻（双向并集）
  R2 标签邻域路   ：v3.9.6 卡文无知识标签/学习场景（红线 R8：当不存在），
                    用真实存在的字段替代 → 同轴（卡号前缀）且认知层级相同/相邻
                    （识记<理解<应用<分析评价；待定 = 同轴内通配）
  R3 跨域补漏路   ：每卡跨轴 Top-3 高相似对 + 固定种子分层随机抽样

全量无序对 19,306 不送模型；本脚本产出 all_candidate_pairs.jsonl（候选池）。
若提供 --k1-ledger（K1 已裁定边），额外输出 recall_curve.json 用于定 Top-K。

用法：
  python3 p5_candidate_recall.py --stage embed            # 只做向量化（幂等，有缓存）
  python3 p5_candidate_recall.py --stage recall --k 8     # 只做召回（用已有向量）
  python3 p5_candidate_recall.py --stage all --k 8 \
      --k1-ledger ../03_交付物/p2_k1_run/accepted_model_adjudicated_edges.jsonl
"""
import json
import hashlib
import math
import os
import random
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
MODELS_JSON = Path.home() / ".workbuddy" / "models.json"
OUT_DIR = BASE / "02_分析产物/p5_candidates"
EMBED_FILE = OUT_DIR / "embeddings_glm-embedding-3-pro.json"
PAIRS_FILE = OUT_DIR / "all_candidate_pairs.jsonl"
STATS_FILE = OUT_DIR / "recall_stats.json"
CURVE_FILE = OUT_DIR / "recall_curve.json"

EMBED_MODEL = "glm-embedding-3-pro"
EMBED_DIM = 4096
EMBED_BATCH = 8
PROMPT_VERSION = "p5-recall-v2"
MAX_LEVEL_DIFF = 2  # K1 校准定稿（见 16号报告）

LEVEL_SCALE = {"识记": 0, "理解": 1, "应用": 2, "分析评价": 3}
EMBED_FIELDS = ["认知层级", "精确定义", "常见误解", "典型案例", "反例",
                "深度上限", "安全与伦理边界", "教学类比"]  # 来源依据是出处信息，不进语义向量


def load_router_key() -> str:
    models = json.loads(MODELS_JSON.read_text(encoding="utf-8"))
    for m in models:
        if m.get("id") == "gpt-5.6-sol":
            return m["apiKey"]
    return models[0]["apiKey"]


def load_cards():
    cards = {}
    for line in CARDS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        cards[c["card_id"]] = c
    assert len(cards) == 197, f"卡数 {len(cards)} != 197"
    return cards


def embed_text(card: dict) -> str:
    parts = [f"{card['canonical_name']}（{card.get('en','')}）"]
    for f in EMBED_FIELDS:
        v = card["fields"].get(f, "")
        if v:
            parts.append(f"【{f}】{v}")
    return "\n".join(parts)


def call_embeddings(texts, key):
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        "https://router.vimox.cn/v1/embeddings", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    items = sorted(data["data"], key=lambda x: x["index"])
    return [it["embedding"] for it in items]


def stage_embed(cards):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = {}
    if EMBED_FILE.is_file():
        cache = json.loads(EMBED_FILE.read_text(encoding="utf-8"))
        print(f"[EMBED] 载入缓存 {len(cache)} 条")
    key = load_router_key()
    todo = []
    for cid, c in cards.items():
        text = embed_text(c)
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if cid not in cache or cache[cid].get("hash") != h:
            todo.append((cid, text, h))
    print(f"[EMBED] 待向量化 {len(todo)} / {len(cards)}")
    t0 = time.time()
    for i in range(0, len(todo), EMBED_BATCH):
        batch = todo[i:i + EMBED_BATCH]
        vecs = call_embeddings([b[1] for b in batch], key)
        for (cid, text, h), v in zip(batch, vecs):
            assert len(v) == EMBED_DIM, f"{cid} 维度 {len(v)} != {EMBED_DIM}"
            cache[cid] = {"hash": h, "vec": v}
        done = min(i + EMBED_BATCH, len(todo))
        print(f"[EMBED] {done}/{len(todo)} 累计耗时 {time.time()-t0:.1f}s")
        EMBED_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    EMBED_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"[EMBED] 完成：{len(cache)} 条向量 → {EMBED_FILE.name}")


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def level_of(card):
    lv = card["fields"].get("认知层级", "待定")
    return LEVEL_SCALE.get(lv, None)  # None = 待定（通配）


def axis_of(cid):
    return cid.split("-")[0]


def stage_recall(cards, k, k1_ledger):
    if not EMBED_FILE.is_file():
        print("⛔ 无向量缓存，先跑 --stage embed"); sys.exit(2)
    cache = json.loads(EMBED_FILE.read_text(encoding="utf-8"))
    cids = sorted(cards)
    vecs = {cid: cache[cid]["vec"] for cid in cids}

    # 全对相似度（197x197 上三角）
    print("[SIM] 计算全对余弦相似度 …")
    t0 = time.time()
    sim = {}
    for i, a in enumerate(cids):
        for b in cids[i + 1:]:
            sim[(a, b)] = cosine(vecs[a], vecs[b])
    print(f"[SIM] {len(sim)} 对，耗时 {time.time()-t0:.1f}s")

    def key(a, b):
        return (a, b) if a < b else (b, a)

    sources = defaultdict(set)

    # R1 语义近邻：每卡 Top-K（双向并集）
    for a in cids:
        others = sorted(
            ((b, sim[key(a, b)]) for b in cids if b != a),
            key=lambda x: -x[1])
        for b, _ in others[:k]:
            sources[key(a, b)].add("R1_semantic_topk")

    # R2 标签邻域（替代口径）：同轴 且 层级差 ≤2 / 含待定（K1 校准定稿：diff≤2 时 64 条 K1 真边覆盖 100%）
    for i, a in enumerate(cids):
        la = level_of(cards[a])
        for b in cids[i + 1:]:
            if axis_of(a) != axis_of(b):
                continue
            lb = level_of(cards[b])
            if la is None or lb is None or abs(la - lb) <= MAX_LEVEL_DIFF:
                sources[key(a, b)].add("R2_axis_level")

    # R3a 跨域补漏：每卡跨轴 Top-3
    for a in cids:
        cross = sorted(
            ((b, sim[key(a, b)]) for b in cids if axis_of(b) != axis_of(a)),
            key=lambda x: -x[1])
        for b, _ in cross[:3]:
            sources[key(a, b)].add("R3_cross_top3")

    # R3b 分层随机抽样：15 个轴对桶 × 8 对 = 120 对（固定种子可复现）
    rng = random.Random(20260926)
    axis_pairs = [(x, y) for i, x in enumerate("123456") for y in "123456"[i + 1:]]
    by_axis = {ax: [c for c in cids if axis_of(c) == ax] for ax in "123456"}
    for ax1, ax2 in axis_pairs:
        candidates = []
        for a in by_axis[ax1]:
            for b in by_axis[ax2]:
                candidates.append((a, b))
        if candidates:
            for a, b in rng.sample(candidates, min(8, len(candidates))):
                sources[key(a, b)].add("R3_random_sample")

    with PAIRS_FILE.open("w", encoding="utf-8") as f:
        for (a, b) in sorted(sources):
            f.write(json.dumps({
                "pair_id": f"{a}__{b}",
                "source": a, "target": b,
                "sim": round(sim[(a, b)], 4),
                "recall_sources": sorted(sources[(a, b)]),
                "status": "CANDIDATE",
                "prompt_version": PROMPT_VERSION,
            }, ensure_ascii=False) + "\n")

    road_cnt = defaultdict(int)
    for srcs in sources.values():
        for s in srcs:
            road_cnt[s] += 1
    stats = {
        "k": k, "total_pairs_19306": 19306,
        "candidate_pool": len(sources),
        "road_counts": dict(road_cnt),
        "embed_model": EMBED_MODEL, "embed_dim": EMBED_DIM,
        "r2_note": "v3.9.6 无知识标签/学习场景字段，按红线R8以 同轴+认知层级(相同/相邻/待定通配) 替代",
    }
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[RECALL] 候选池 {len(sources)} 对（Top-K={k}）→ {PAIRS_FILE.name}")

    # K1 召回曲线：已裁定边是否被候选池覆盖（含各路单独覆盖）
    if k1_ledger:
        edges = []
        for p in k1_ledger:
            e = json.loads(p) if isinstance(p, str) else p
            eid = e.get("pair_id") or f"{e.get('source','?')}__{e.get('target','?')}"
            edges.append(eid)
        covered = [e for e in edges if e in sources]
        # 各路单独召回
        per_road = {}
        for road in ["R1_semantic_topk", "R2_axis_level", "R3_cross_top3", "R3_random_sample"]:
            hit = sum(1 for e in edges if road in sources.get(e, set()))
            per_road[road] = {"hits": hit, "recall": round(hit / len(edges), 3) if edges else None}
        # Top-K 扫描 1..15
        curve = []
        for kk in range(1, 16):
            s = set()
            for a in cids:
                others = sorted(((b, sim[key(a, b)]) for b in cids if b != a),
                                key=lambda x: -x[1])
                for b, _ in others[:kk]:
                    s.add(key(a, b))
            hit = sum(1 for e in edges if e in s)
            curve.append({"k": kk, "recall": round(hit / len(edges), 3) if edges else None})
        CURVE_FILE.write_text(json.dumps({
            "k1_edges": len(edges), "pool_covered": len(covered),
            "pool_recall": round(len(covered) / len(edges), 3) if edges else None,
            "per_road": per_road, "topk_curve": curve,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[CURVE] K1 已裁定边 {len(edges)}，候选池覆盖 {len(covered)} → {CURVE_FILE.name}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["embed", "recall", "all"], default="all")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--k1-ledger", default="")
    ap.add_argument("--max-level-diff", type=int, default=None, help="覆盖 MAX_LEVEL_DIFF")
    args = ap.parse_args()

    cards = load_cards()
    if args.stage in ("embed", "all"):
        stage_embed(cards)
    if args.stage in ("recall", "all"):
        ledger = []
        if args.k1_ledger and Path(args.k1_ledger).is_file():
            ledger = Path(args.k1_ledger).read_text(encoding="utf-8").splitlines()
            ledger = [l for l in ledger if l.strip()]
        global MAX_LEVEL_DIFF
        if args.max_level_diff is not None:
            MAX_LEVEL_DIFF = args.max_level_diff
        stage_recall(cards, args.k, ledger)


if __name__ == "__main__":
    main()
