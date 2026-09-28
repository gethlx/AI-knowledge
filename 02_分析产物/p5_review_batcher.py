#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P5 评审批次生成器
=================
输入：定稿候选池 all_candidate_pairs.jsonl + luna 提议 proposals/*.json
输出：p5_review/
  full_pairs.jsonl        —— luna 提议了关系的对（逐对三路评审）
  light_pairs.jsonl       —— luna 判 no_relation 的对（例外式批量复核）
  reviewer_input_full_batchN.md   —— 三路评审员共用输入（同 Prompt 同卡文快照）
  reviewer_input_light_batchN.md  —— 例外式复核输入
  batch_manifest.json

独立性规则（14号裁定 §3.1/3.2）：
- 三路评审员收到完全相同的输入，互相不可见；
- 评审员【看不到】luna 提议（防锚定，四路独立）；luna 提议只进 sol 的裁定 bundle；
- 评审意见占位 hash 由编排主控事后统一发放（hash_dispense.py）。

用法：
  python3 p5_review_batcher.py --full-batch 120 --light-batch 150
"""
import json
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
POOL = BASE / "02_分析产物/p5_candidates/all_candidate_pairs.jsonl"
PROPOSALS = BASE / "02_分析产物/p5_candidates/proposals"
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
OUT = BASE / "02_分析产物/p5_review"

HEADER_RULES = """# P5 评审输入（批次 {batch} · 证据唯一来源 = 本文卡文快照）

> 配套契约：03_交付物/p1_review_contract/（annotation_guidelines v1.0.0 / edge_review.schema.json）
> 评审路标识：reviewer_glm / reviewer_deepseek / reviewer_hy4 三路之一（三路收到完全相同输入，互相不可见）

## 评审规则（浓缩版，与准则冲突时以准则原文为准）

1. 五类判定：prerequisite / related / no_relation / insufficient_evidence / 安全或伦理问题（触发红线即按准则上报）。
2. 先修唯一定义：**不理解 A 会实质阻断对 B 的理解或应用**（缺失即卡住、卡文可证、方向唯一合理）。有帮助但非必需、同主题、共现、教学编排顺序、分类包含——都不是先修。
3. evidence.quote 必须是本文卡文快照的**逐字子串**（禁止改写/拼接/翻译/修标点），并写明 card_id 与 field。判 prerequisite/related 建议两卡各引至少 1 条。
4. 无法确定时一律 insufficient_evidence，并在 reason 写明缺口。
5. direction：source_to_target（A→B）或 target_to_source；related/no_relation/insufficient_evidence 时 direction=null。
6. 禁止引用【知识标签】【学习场景】等卡中不存在的字段（作废字段当不存在）。
7. 只输出符合 edge_review.schema.json 的 JSON 对象；input_card_hash / prompt_hash 先填 "PENDING"（编排主控会统一发放官方哈希）。

## 输出方式

每个 pair 一个 JSON 文件，写到：`02_分析产物/p5_review/reviews_inbox_full/<pair_id>/{reviewer}.json`
（{reviewer} 为你的评审路标识。）文件名即 pair_id，内容为单个 JSON 对象。
"""

HEADER_LIGHT = """# P5 例外式复核输入（批次 {batch} · no_relation 复核）

> 背景：luna 提议器对下列候选对判了 no_relation（卡文层面无教学关联依据）。
> 你的任务【不是】重新逐对详评，而是**例外式复核**：凭本文卡文快照，只对【你认为存在
> 对照/易混/延伸/先修关系且有逐字证据】的对输出意见；同意 no_relation 的对**不要**输出文件。

## 输出方式（仅对不同意 no_relation 的对）

写到：`02_分析产物/p5_review/reviews_inbox_full/<pair_id>/{reviewer}.json`
JSON 同 edge_review.schema.json：relation_type=prerequisite|related|insufficient_evidence，
evidence.quote 必须是本文卡文快照逐字子串；input_card_hash / prompt_hash 先填 "PENDING"。

## 规则提醒

- 先修=不理解 A 会实质阻断对 B 的理解或应用；有帮助但非必需、共现、同主题都不是先修。
- 疑似有关但证据不够 → 写 insufficient_evidence 意见（也会触发该对进入完整评审）。
- 静默 = 确认 no_relation（会被记录为三路复核无异议）。
"""


def card_md(c):
    lines = [f"## {c['card_id']} {c['canonical_name']}"]
    for k, v in c["fields"].items():
        lines.append(f"- **{k}**：{v}")
    return "\n".join(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-batch", type=int, default=120)
    ap.add_argument("--light-batch", type=int, default=150)
    args = ap.parse_args()

    pool = [json.loads(l) for l in POOL.read_text(encoding="utf-8").splitlines() if l.strip()]
    proposals = {}
    for pf in PROPOSALS.glob("*.json"):
        d = json.loads(pf.read_text(encoding="utf-8"))
        proposals[d["pair_id"]] = d

    full, light = [], []
    for p in pool:
        pr = proposals.get(p["pair_id"])
        if pr and pr.get("relation_type") in ("prerequisite", "related"):
            full.append(p)
        elif pr and pr.get("relation_type") == "no_relation":
            light.append(p)
        # 提议缺失的对（luna 失败/未跑）另列，不进批次
    missing = [p["pair_id"] for p in pool if p["pair_id"] not in proposals]

    cards = {}
    for l in CARDS_FILE.read_text(encoding="utf-8").splitlines():
        if l.strip():
            c = json.loads(l)
            cards[c["card_id"]] = c

    if not OUT.is_dir():
        OUT.mkdir(parents=True)
    inbox_full = OUT / "reviews_inbox_full"
    if not inbox_full.is_dir():
        inbox_full.mkdir(parents=True)
    with (OUT / "full_pairs.jsonl").open("w", encoding="utf-8") as f:
        for p in full:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with (OUT / "light_pairs.jsonl").open("w", encoding="utf-8") as f:
        for p in light:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    manifest = {"full_total": len(full), "light_total": len(light),
                "missing_proposals": len(missing), "batches": []}

    def write_batches(pairs, size, kind):
        for i in range(0, len(pairs), size):
            batch = pairs[i:i + size]
            n = i // size + 1
            need = sorted({x for p in batch for x in (p["source"], p["target"])})
            body = ["\n## 本批 pair 清单"]
            for p in batch:
                body.append(f"- `{p['pair_id']}`（{cards[p['source']]['canonical_name']} × {cards[p['target']]['canonical_name']}，召回={'+'.join(p['recall_sources'])}）")
            body.append("\n## 卡文快照（证据唯一来源）")
            for cid in need:
                body.append(card_md(cards[cid]))
            header = (HEADER_RULES if kind == "full" else HEADER_LIGHT).replace(
                "{batch}", str(n))
            fn = OUT / f"reviewer_input_{kind}_batch{n}.md"
            fn.write_text(header + "\n".join(body), encoding="utf-8")
            manifest["batches"].append({"kind": kind, "file": fn.name, "pairs": len(batch)})
            print(f"[BATCH] {fn.name}: {len(batch)} 对, {len(need)} 卡")

    write_batches(full, args.full_batch, "full")
    write_batches(light, args.light_batch, "light")
    (OUT / "batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[DONE] full={len(full)} light={len(light)} missing_proposals={len(missing)}")


if __name__ == "__main__":
    main()
