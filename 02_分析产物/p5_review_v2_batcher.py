#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P5 评审批次生成器 v2
====================
改进点（针对 v1 跨批冗余）：
1. 只为【缺失的意见槽位】生成会话（pair × 路由 粒度，幂等）；
2. 按卡聚类分会（BFS 共卡扩张）：同一张卡的候选边进同一会话，
   会话卡并集从 ~197 压到典型 30-60，输入体积降数倍；
3. 会话规模由实测存活上限定界（glm/hy4=60 对，deepseek=120 对），不由输入定界；
4. 同卡同会话 = 同标尺，缓解跨批漂移。

输出：p5_review/v2_sessions/<route>/sessN.md + sessN.pairs.jsonl + v2_manifest.json
"""
import json
from collections import deque
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
P5 = BASE / "02_分析产物/p5_review"
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
INBOX = P5 / "reviews_inbox_full"
OUT = P5 / "v2_sessions"

ROUTE_CAP = {"reviewer_glm": 60, "reviewer_hy4": 60, "reviewer_deepseek": 120}
CARD_CAP = 90
REVIEWERS = ["reviewer_glm", "reviewer_deepseek", "reviewer_hy4"]

HEADER = """# P5 评审输入（v2 会话 {label} · 证据唯一来源 = 本文卡文快照）

> 配套契约：03_交付物/p1_review_contract/（annotation_guidelines v1.0.1 / edge_review.schema.json）
> 你的评审路标识：{route}（三路评审员输入同构、互相不可见）

## 评审规则（浓缩版，与准则冲突时以准则原文为准）

1. 五类判定：prerequisite / related / no_relation / insufficient_evidence / 安全或伦理问题（触发红线即按准则上报）。
2. 先修唯一定义：**不理解 A 会实质阻断对 B 的理解或应用**（缺失即卡住、卡文可证、方向唯一合理）。有帮助但非必需、同主题、共现、教学编排顺序、分类包含——都不是先修。
3. evidence.quote 必须是本文卡文快照的**逐字子串**（禁止改写/拼接/翻译/修标点），并写明 card_id 与 field。判 prerequisite/related 建议两卡各引至少 1 条。
4. 无法确定时一律 insufficient_evidence，并在 reason 写明缺口。
5. direction：source_to_target（A→B）或 target_to_source；related/no_relation/insufficient_evidence 时 direction=null。
6. 禁止引用【知识标签】【学习场景】等卡中不存在的字段（作废字段当不存在）。
7. 只输出符合 edge_review.schema.json 的 JSON 对象；input_card_hash / prompt_hash 先填 "PENDING"（编排主控会统一发放官方哈希）。

## 输出方式

每个 pair 一个 JSON 文件，写到：`02_分析产物/p5_review/reviews_inbox_full/<pair_id>/{route}.json`
内容为单个 JSON 对象。完成后必须附磁盘核账输出（实际落盘文件数），不许空口宣称完成。

## 本会话 pair 清单（共 {npairs} 对）
"""

BODY_PAIRS = "\n## 本会话涉及的卡文快照（每卡仅渲染一次；证据只能引自此处）\n"


def card_md(c):
    lines = [f"## {c['card_id']} {c['canonical_name']}"]
    for k, v in c["fields"].items():
        lines.append(f"- **{k}**：{v}")
    return "\n".join(lines)


def valid_opinion(pid, route):
    f = INBOX / pid / f"{route}.json"
    if not f.exists():
        return False
    try:
        json.load(open(f, encoding="utf-8"))
        return True
    except Exception:
        return False


def cluster(pairs, cap):
    """BFS 共卡聚类：种子对出发，沿共卡边扩张，直到会话满。"""
    card2pairs = {}
    for p in pairs:
        for cid in (p["source"], p["target"]):
            card2pairs.setdefault(cid, []).append(p["pair_id"])
    remaining = {p["pair_id"]: p for p in pairs}
    sessions = []
    while remaining:
        seed_pid = next(iter(remaining))
        seed = remaining.pop(seed_pid)
        sess = [seed]
        cards = {seed["source"], seed["target"]}
        queue = deque([seed])
        while queue and len(sess) < cap:
            cur = queue.popleft()
            for cid in (cur["source"], cur["target"]):
                for pid in card2pairs.get(cid, []):
                    if pid not in remaining:
                        continue
                    q = remaining[pid]
                    nc = cards | {q["source"], q["target"]}
                    if len(nc) > CARD_CAP:
                        continue
                    cards = nc
                    sess.append(remaining.pop(pid))
                    queue.append(q)
                    if len(sess) >= cap:
                        break
        sessions.append(sess)
    return sessions


def main():
    full = [json.loads(l) for l in (P5 / "full_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    cards = {}
    for l in CARDS_FILE.read_text(encoding="utf-8").splitlines():
        if l.strip():
            c = json.loads(l)
            cards[c["card_id"]] = c

    manifest = {"sessions": [], "totals": {}}
    OUT.mkdir(parents=True, exist_ok=True)

    for route in REVIEWERS:
        missing = [p for p in full if not valid_opinion(p["pair_id"], route)]
        missing.sort(key=lambda p: p["pair_id"])
        sess_list = cluster(missing, ROUTE_CAP[route])
        rdir = OUT / route
        rdir.mkdir(parents=True, exist_ok=True)
        manifest["totals"][route] = {"missing": len(missing), "sessions": len(sess_list)}
        for i, sess in enumerate(sess_list, 1):
            need = sorted({c for p in sess for c in (p["source"], p["target"])})
            label = f"{route.replace('reviewer_', '')}-s{i}"
            body = [HEADER.replace("{label}", label).replace("{route}", route).replace("{npairs}", str(len(sess)))]
            for p in sess:
                body.append(f"- `{p['pair_id']}`（{cards[p['source']]['canonical_name']} × {cards[p['target']]['canonical_name']}，召回={'+'.join(p['recall_sources'])}）")
            body.append(BODY_PAIRS)
            for cid in need:
                body.append(card_md(cards[cid]))
            md = "\n".join(body)
            fn = rdir / f"sess{i}.md"
            fn.write_text(md, encoding="utf-8")
            pf = rdir / f"sess{i}.pairs.jsonl"
            pf.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in sess), encoding="utf-8")
            manifest["sessions"].append({"route": route, "session": i, "file": str(fn.relative_to(BASE)),
                                         "pairs": len(sess), "cards": len(need), "input_chars": len(md)})
            print(f"[SESS] {label}: {len(sess)} 对, {len(need)} 卡, {len(md)} chars")

    (OUT / "v2_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[DONE] totals={json.dumps(manifest['totals'], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
