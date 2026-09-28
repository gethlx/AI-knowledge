#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p17_closing_pass.py —— P5 收口三合一（幂等，可重复跑）：

1. prehash   : 给意见文件批量回填 input_card_hash / prompt_hash（仅填 PENDING，
               哈希口径沿用 17号 §2.3 已核实定义：input_card_hash=对作用域两卡内容哈希，
               prompt_hash=按(kind+route)规则头模板哈希；各取 sha256 前 16 位）。
2. converge  : light 争议汇聚（仅 Schema 校验通过 + 证据逐字核验通过的意见计为有效争议，
               §2.5.1），产出需并入 full 流的 pair 清单 light_disputed_pairs.json。
3. audit     : 全库对账（full 终态 / light 覆盖 / 待补清单），输出 closing_audit.json。

用法：python3 p17_closing_pass.py prehash | converge | audit
"""
import json
import hashlib
import glob
import os
import sys
from pathlib import Path
from collections import defaultdict, Counter

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
P5 = BASE / "02_分析产物/p5_review"
FULL = P5 / "reviews_inbox_full"
LIGHT = P5 / "reviews_inbox_light"
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
LEDGER = P5 / "unit_ledger.jsonl"

VALID_RT = {"prerequisite", "related", "no_relation", "insufficient_evidence"}
LIGHT_RT = {"prerequisite", "related", "insufficient_evidence"}

_cards = {}
def cards():
    if not _cards:
        for line in open(CARDS_FILE, encoding="utf-8"):
            if line.strip():
                c = json.loads(line)
                _cards[c["card_id"]] = c
    return _cards

def card_hash(pid):
    a, b = pid.split("__")
    cs = cards()
    ha = hashlib.sha256(json.dumps(cs[a], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    hb = hashlib.sha256(json.dumps(cs[b], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    return hashlib.sha256(f"{min(ha,hb)}:{max(ha,hb)}".encode()).hexdigest()[:16]

PROMPT_TEMPLATES = {
    ("full", "reviewer_glm"): "full-glm-v1", ("full", "reviewer_deepseek"): "full-ds-v1",
    ("full", "reviewer_hy4"): "full-hy4-v1", ("light", "reviewer_glm"): "light-glm-v1",
    ("light", "reviewer_deepseek"): "light-ds-v1", ("light", "reviewer_hy4"): "light-hy4-v1",
}
def prompt_hash(kind, route):
    return hashlib.sha256(PROMPT_TEMPLATES[(kind, route)].encode()).hexdigest()[:16]

def validate_opinion(j, pid, route, kind):
    """返回 None=有效，否则错误字符串。校验 schema 核心 + 证据逐字（§2.5.1 争议有效性标准）。"""
    try:
        if j.get("pair_id") != pid: return "pair_id mismatch"
        if j.get("reviewer_id") != route: return "reviewer_id mismatch"
        if j.get("status") != "REVIEW_COMPLETED": return "status"
        if j.get("relation_type") not in VALID_RT: return "relation_type"
        if j.get("relation_type") == "prerequisite" and j.get("direction") not in ("source_to_target", "target_to_source"):
            return "direction"
        if j.get("relation_type") != "prerequisite" and j.get("direction") is not None:
            return "direction-not-null"
        ev = j.get("evidence") or []
        if j.get("relation_type") in ("prerequisite", "related"):
            if not ev: return "empty evidence"
        cs = cards()
        for e in ev:
            cid, fld, quote = e.get("card_id"), e.get("field"), e.get("quote", "")
            if cid not in cs: return f"bad card_id {cid}"
            text = cs[cid]["fields"].get(fld)
            if text is None: return f"bad field {cid}.{fld}"
            if quote not in text: return "quote not verbatim"
        return None
    except Exception as ex:
        return f"exception {ex}"

def cmd_prehash():
    n = 0
    for kind, inbox in (("full", FULL), ("light", LIGHT)):
        for f in glob.glob(str(inbox / "*" / "reviewer_*.json")):
            route = Path(f).stem
            j = json.load(open(f, encoding="utf-8"))
            pid = Path(f).parent.name
            changed = False
            if j.get("input_card_hash") == "PENDING":
                j["input_card_hash"] = card_hash(pid); changed = True
            if j.get("prompt_hash") == "PENDING":
                j["prompt_hash"] = prompt_hash(kind, route); changed = True
            if changed:
                tmp = f + ".tmp"
                open(tmp, "w", encoding="utf-8").write(json.dumps(j, ensure_ascii=False, indent=1))
                os.replace(tmp, f); n += 1
    print(f"prehash: {n} files updated")

def cmd_converge():
    disputed, invalid = {}, Counter()
    for f in glob.glob(str(LIGHT / "*" / "reviewer_*.json")):
        route = Path(f).stem
        pid = Path(f).parent.name
        j = json.load(open(f, encoding="utf-8"))
        err = validate_opinion(j, pid, route, "light")
        if err:
            invalid[err] += 1; continue
        if j.get("relation_type") in LIGHT_RT:
            disputed.setdefault(pid, {})[route] = j["relation_type"]
    out = {
        "total_valid_disputed_pairs": len(disputed),
        "pairs": {p: v for p, v in sorted(disputed.items())},
        "invalid_files": dict(invalid),
        "note": "有效争议对需按 §2.5.1 并入 full 评审流（三路 full 意见照常收取）",
    }
    (P5 / "light_disputed_pairs.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"converge: {len(disputed)} valid disputed pairs -> light_disputed_pairs.json")
    print(f"invalid light files: {dict(invalid) or 'none'}")

def cmd_audit():
    ledger = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    full_pairs = {j["pair_id"] for j in ledger if j["path"] == "full"}
    light_pairs = {j["pair_id"] for j in ledger if j["path"] == "light"}
    routes = ["reviewer_glm", "reviewer_deepseek", "reviewer_hy4"]
    rep = {"full": {}, "light": {}}
    miss_full = defaultdict(list)
    for r in routes:
        ok = 0
        for pid in full_pairs:
            try:
                j = json.load(open(FULL / pid / f"{r}.json", encoding="utf-8"))
                assert j["status"] == "REVIEW_COMPLETED" and j["relation_type"] in VALID_RT
                ok += 1
            except Exception:
                miss_full[r].append(pid)
        rep["full"][r] = {"ok": ok, "missing": len(miss_full[r])}
    # v1-inherited coverage check: ledger full pairs not in v2 sessions rely on v1 opinions
    rep["full"]["missing_detail"] = {r: v[:20] for r, v in miss_full.items()}
    # light coverage: per route, count light pairs with a valid dispute OR fall in silent set (cannot verify silence w/o session completion log)
    for r in routes:
        n = sum(1 for pid in light_pairs if (LIGHT / pid / f"{r}.json").is_file())
        rep["light"][r] = {"dispute_files": n, "silent_unverified": len(light_pairs) - n}
    rep["light"]["total_pairs"] = len(light_pairs)
    (P5 / "closing_audit.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:2000])

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    {"prehash": cmd_prehash, "converge": cmd_converge, "audit": cmd_audit}[cmd]()
