#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p17_disputed_rebatcher.py —— 17号 §2.5.1 有效争议对并入 full 流的补审批次生成器。

输入：p5_review/light_disputed_pairs.json（138 个有效争议对）
输出：p5_review/unit_sessions_disputed/<route>/DS-s{i}.md + .pairs.jsonl + .meta.json
      p5_review/disputed_manifest.json

规则：
- 意见落 reviews_inbox_full/<pair_id>/reviewer_X.json（与常规 full 同箱同标准）；
- 规则头 = full 浓缩版（五类判定），证据标准与 full 完全一致；
- CARD_CAP=110：138 对涉 127 张卡，按共卡聚类切 2 班/路；
- 派发为每路 1 个大 agent 顺序消化其 2 个班次文件（响应"不要搞出太多班次"）。
"""
import json
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
P5 = BASE / "02_分析产物/p5_review"
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
DISPUTED = P5 / "light_disputed_pairs.json"
OUT = P5 / "unit_sessions_disputed"

CARD_CAP = 110
ROUTES = ["reviewer_glm", "reviewer_deepseek", "reviewer_hy4"]

HEADER = """# P5 争议对 full 补审输入（{unit} · 会话{i} · 证据唯一来源 = 本文卡文快照）

> 配套契约：03_交付物/p1_review_contract/（annotation_guidelines v1.0.1 / edge_review.schema.json）
> 评审路标识：{route}
> 依据：17号升级案 §2.5.1——light 例外复核产生的有效争议对并入 full 评审流（三路 full 意见照常收取）。

## 评审规则（full 浓缩版，与准则冲突时以准则原文为准）

1. 五类判定：prerequisite / related / no_relation / insufficient_evidence / 安全或伦理问题（触发红线即按准则上报）。
2. 先修唯一定义：**不理解 A 会实质阻断对 B 的理解或应用**（缺失即卡住、卡文可证、方向唯一合理）。有帮助但非必需、同主题、共现、教学编排顺序、分类包含——都不是先修。
3. evidence.quote 必须是本文卡文快照的**逐字子串**（禁止改写/拼接/翻译/修标点），并写明 card_id 与 field。判 prerequisite/related 两卡各引至少 1 条。
4. 无法确定时一律 insufficient_evidence，并在 reason 写明缺口。
5. direction：source_to_target（A→B）或 target_to_source；related/no_relation/insufficient_evidence 时 direction=null。
6. 禁止引用【知识标签】【学习场景】等卡中不存在的字段（作废字段当不存在）。
7. 只输出符合 edge_review.schema.json 的 JSON 对象；input_card_hash / prompt_hash 先填 "PENDING"。

## 领取与落盘（防重复）

- 领取槽位前检查：`02_分析产物/p5_review/reviews_inbox_full/<pair_id>/{route}.json` 已存在且合法 → 跳过；
- 意见文件先写 `.tmp` 再原子重命名到正式名；
- 必须写到 **reviews_inbox_full** 目录（不是 reviews_inbox_light，不是工作区根目录，不建嵌套目录）；
- 只处理本清单 pair，不越界。完成后必须附磁盘核账输出（本清单 pair 的实际落盘数 + 逐个 json.load 校验），不许空口宣称完成。

## 输出方式

写到：`02_分析产物/p5_review/reviews_inbox_full/<pair_id>/{route}.json`

## 本班次 pair 清单（共 {npairs} 对；本批全部来自 light 争议升级，默认倾向"有关"，但请独立判定，勿被 light 判定锚定）

"""

BODY_PAIRS = "\n## 本班次涉及的卡文快照（每卡仅渲染一次；证据只能引自此处）\n"


def card_md(c):
    lines = [f"## {c['card_id']} {c['canonical_name']}"]
    for k, v in c["fields"].items():
        lines.append(f"- **{k}**：{v}")
    return "\n".join(lines)


def pair_label(pid, names):
    a, b = pid.split("__")
    return f"- `{pid}`（{names.get(a, a)} × {names.get(b, b)}）"


def main():
    cards = {}
    for line in open(CARDS_FILE, encoding="utf-8"):
        if line.strip():
            c = json.loads(line)
            cards[c["card_id"]] = c
    names = {cid: c["canonical_name"] for cid, c in cards.items()}

    disputed = json.load(open(DISPUTED, encoding="utf-8"))
    pairs = sorted(disputed["pairs"])
    assert len(pairs) == disputed["total_valid_disputed_pairs"], "清单数不一致"

    # 共卡聚类切块
    chunks, cur, cur_cards = [], [], set()
    for pid in pairs:
        a, b = pid.split("__")
        new_cards = {a, b} - cur_cards
        if cur and len(cur_cards | new_cards) > CARD_CAP:
            chunks.append((cur, cur_cards))
            cur, cur_cards = [], set()
        cur.append(pid)
        cur_cards |= {a, b}
    if cur:
        chunks.append((cur, cur_cards))

    manifest = {"kind": "disputed_full", "source": "light_disputed_pairs.json",
                "total_pairs": len(pairs), "sessions": []}
    for route in ROUTES:
        for i, (chunk, _) in enumerate(chunks, 1):
            label = f"DS-s{i}"
            sess_dir = OUT / route
            sess_dir.mkdir(parents=True, exist_ok=True)
            md = HEADER.format(unit="DS(争议对)", i=i, route=route, npairs=len(chunk))
            md += "\n".join(pair_label(p, names) for p in chunk)
            md += BODY_PAIRS + "\n"
            used = sorted({c for p in chunk for c in p.split("__")})
            for cid in used:
                md += card_md(cards[cid]) + "\n"
            (sess_dir / f"{label}.md").write_text(md, encoding="utf-8")
            with open(sess_dir / f"{label}.pairs.jsonl", "w", encoding="utf-8") as f:
                for p in chunk:
                    f.write(json.dumps({"pair_id": p}, ensure_ascii=False) + "\n")
            meta = {"route": route, "unit": "DS", "session": i,
                    "pairs": len(chunk), "cards": len(used), "kind": "disputed_full"}
            (sess_dir / f"{label}.meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            manifest["sessions"].append(meta)

    (P5 / "disputed_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"disputed pairs: {len(pairs)}; sessions/route: {len(chunks)}")
    for s in manifest["sessions"]:
        print(f"  {s['route']:>18} DS-s{s['session']}: {s['pairs']} pairs / {s['cards']} cards")


if __name__ == "__main__":
    main()
