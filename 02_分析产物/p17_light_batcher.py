#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p17_light_batcher.py —— 17号 §2.5.1 light 例外复核批次生成器。

设计（依据 17号 v2.4 §2.5/§2.5.1 生效条款）：
- 输入与 full 送审同构：规则头 + 本班次卡文快照 + 本班次 light 对清单；三路独立会话互不可见。
- 仅争议输出（deviation ZB-20260927-01 授权）：评审员仅在认为该对不是 no_relation 时
  输出意见（relation_type ∈ {prerequisite, related, insufficient_evidence}）；
  认可 no_relation → 不写任何文件（静默）。
- 意见落盘到独立收件箱 reviews_inbox_light/<pair_id>/reviewer_X.json（与 full 收件箱物理隔离）。
- 班次规模 350 对/班次（light 预期输出稀疏，可大于 full 的 60/120）；
  pair 按共卡聚类排序后切块，最小化每班次卡文渲染量。
- 失败终态：班次死亡且补跑耗尽 → 该单元 light 对记 LIGHT_REVIEW_INCOMPLETE（挂起待补跑），
  由主控按 relay log 判定，不在本脚本内判定。

输出：p5_review/unit_sessions_light/<route>/U{n}-s{i}.md + .pairs.jsonl + .meta.json
      p5_review/light_manifest.json
"""
import json
import hashlib
from pathlib import Path
from collections import defaultdict

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
P5 = BASE / "02_分析产物/p5_review"
LEDGER = P5 / "unit_ledger.jsonl"
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
OUT = P5 / "unit_sessions_light"

SESSION_CAP = 350          # 每班次 pair 上限
CARD_CAP = 110             # 每班次渲染卡文上限（防 U6 桥接单元单班次 173KB 输入压挤上下文）
ROUTES = ["reviewer_glm", "reviewer_deepseek", "reviewer_hy4"]

HEADER = """# P5 light 例外复核输入（{unit} · 会话{i} · 证据唯一来源 = 本文卡文快照）

> 配套契约：03_交付物/p1_review_contract/（annotation_guidelines v1.0.1 / edge_review.schema.json）
> 评审路标识：{route}
> 依据：17号升级案 §2.5/§2.5.1（终批记录 ZB-20260927-01 授权的明示偏差）

## 评审规则（light 例外复核专用，与 full 同证据标准）

1. 本清单为召回侧判定"大概率无关系"的 light 候选对。你的任务：**只输出争议意见**。
2. 逐对核对卡文快照。若你认为某对**不是** no_relation（即存在先修/相关/证据不足的实质依据）→ 输出意见文件，relation_type 限 {{prerequisite, related, insufficient_evidence}}。
3. 若你认可该对为 no_relation → **不输出任何文件**（静默即认可）。
4. 证据标准与 full 完全一致：evidence.quote 必须是本文卡文快照的**逐字子串**（禁止改写/拼接/翻译/修标点），写明 card_id 与 field；prerequisite/related 两卡各引至少 1 条。
5. 先修唯一定义：**不理解 A 会实质阻断对 B 的理解或应用**（缺失即卡住、卡文可证、方向唯一合理）。有帮助但非必需、同主题、共现、教学编排顺序、分类包含——都不是先修。
6. direction：prerequisite 时 source_to_target 或 target_to_source；related/insufficient_evidence 时 direction=null。
7. 禁止引用【知识标签】【学习场景】等卡中不存在的字段（作废字段当不存在）。
8. 无法确定是否相关 → 输出 insufficient_evidence 并在 reason 写明缺口（宁可争议，不可放过）。

## 输出方式（与 full 不同：只写争议对）

- 意见文件写到：`02_分析产物/p5_review/reviews_inbox_light/<pair_id>/{route}.json`
- 注意是 **reviews_inbox_light**（不是 reviews_inbox_full）；先写 `.tmp` 再原子重命名。
- 字段：pair_id, reviewer_id="{route}", model_requested="{model}", model_returned="{model}", relation_type, direction, evidence, reason, confidence, input_card_hash="PENDING", prompt_hash="PENDING", status="REVIEW_COMPLETED"。
- 不越界处理清单外 pair。完成后必须附磁盘核账输出（本清单 pair 中实际输出意见数 + 逐个 json.load 校验），不许空口宣称完成。

## 本班次 pair 清单（共 {npairs} 对）

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

    # light pairs per unit
    unit_pairs = defaultdict(list)
    for line in open(LEDGER, encoding="utf-8"):
        if not line.strip():
            continue
        j = json.loads(line)
        if j["path"] == "light":
            unit_pairs[j["unit_id"]].append(j["pair_id"])

    model_map = {
        "reviewer_glm": "glm5.3-flash",
        "reviewer_deepseek": "deepseek4.1flash",
        "reviewer_hy4": "hy4",
    }

    manifest = {"kind": "light", "session_cap": SESSION_CAP, "sessions": []}
    total_pairs = 0
    for unit in sorted(unit_pairs):
        pairs = sorted(unit_pairs[unit])
        total_pairs += len(pairs)
        # cluster by shared cards: sort by (source_card, target_card)
        pairs_sorted = sorted(pairs, key=lambda p: (p.split("__")[0], p.split("__")[1]))
        # chunk with card-affinity: greedy accumulate while caps hold
        chunks, cur, cur_cards = [], [], set()
        for pid in pairs_sorted:
            a, b = pid.split("__")
            new_cards = {a, b} - cur_cards
            if cur and (len(cur) + 1 > SESSION_CAP or len(cur_cards | new_cards) > CARD_CAP):
                chunks.append((cur, cur_cards))
                cur, cur_cards = [], set()
            cur.append(pid)
            cur_cards |= {a, b}
        if cur:
            chunks.append((cur, cur_cards))

        for route in ROUTES:
            for i, (chunk, _) in enumerate(chunks, 1):
                label = f"{unit}-s{i}"
                sess_dir = OUT / route
                sess_dir.mkdir(parents=True, exist_ok=True)
                md = HEADER.format(unit=unit, i=i, route=route,
                                   model=model_map[route], npairs=len(chunk))
                md += "\n".join(pair_label(p, names) for p in chunk)
                md += BODY_PAIRS + "\n"
                used = sorted({c for p in chunk for c in p.split("__")})
                for cid in used:
                    md += card_md(cards[cid]) + "\n"
                (sess_dir / f"{label}.md").write_text(md, encoding="utf-8")
                with open(sess_dir / f"{label}.pairs.jsonl", "w", encoding="utf-8") as f:
                    for p in chunk:
                        f.write(json.dumps({"pair_id": p}, ensure_ascii=False) + "\n")
                meta = {"route": route, "unit": unit, "session": i,
                        "pairs": len(chunk), "cards": len(used), "kind": "light"}
                (sess_dir / f"{label}.meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                manifest["sessions"].append(meta)

    manifest["total_light_pairs"] = total_pairs
    manifest["total_sessions"] = len(manifest["sessions"])
    (P5 / "light_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"light pairs: {total_pairs}; sessions: {manifest['total_sessions']}")
    for s in manifest["sessions"]:
        print(f"  {s['route']:>18} {s['unit']}-s{s['session']}: {s['pairs']} pairs / {s['cards']} cards")


if __name__ == "__main__":
    main()
