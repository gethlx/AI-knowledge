#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
luna 提议桥（P5：候选对 → 关系提议，冻结选型 gpt-5.6-luna via Vimox）
=====================================================================
角色（14号裁定）：luna 只做候选关系提议器，不是裁决者。
  输出一个候选对（两卡全字段）→ 输出 JSON：
  {pair_id, relation_type: prerequisite|related|no_relation,
   direction, evidence, evidence_field, rationale}

幂等：p5_candidates/proposals/<pair_id>.json 存在且 input_hash 一致 → 跳过。
程序校验：JSON 可解析、relation_type 合法、端点为规范 197 卡、
         evidence 必须在两卡之一的全文中逐字命中（不命中标 INVALID_EVIDENCE 重试一次）。
日志：每调用打 [LUNA-CALL] 时间/耗时/返回模型，供主公在 Vimox 控制台对账。

用法：
  python3 luna_proposal_bridge.py --pairs p5_candidates/all_candidate_pairs.jsonl --workers 3
"""
import hashlib
import json
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
CARDS_FILE = BASE / "02_分析产物/p0_baseline/card_evidence.jsonl"
MODELS_JSON = Path.home() / ".workbuddy" / "models.json"
OUT_DIR = BASE / "02_分析产物/p5_candidates/proposals"
PROMPT_VERSION = "luna-proposal-v1"
TIMEOUT = 180
PRINT_LOCK = threading.Lock()


def log(msg):
    with PRINT_LOCK:
        print(msg, flush=True)


def load_config() -> dict:
    models = json.loads(MODELS_JSON.read_text(encoding="utf-8"))
    m = next(m for m in models if m["id"] == "gpt-5.6-luna")
    return {"url": m["url"], "key": m["apiKey"], "model": "gpt-5.6-luna"}


def load_cards():
    cards = {}
    for line in CARDS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            cards[c["card_id"]] = c
    return cards


def card_full_text(c):
    parts = [c["canonical_name"]]
    for k, v in c["fields"].items():
        parts.append(f"【{k}】{v}")
    return "\n".join(parts)


PROMPT_TMPL = """你是知识图谱项目（银河AI通识课程体系，197 张冻结概念卡）的候选关系提议器。你只提议，不裁决；不使用任何外部知识，只依据下面给出的两卡原文。

概念对：{pair_id}
- source = {sa}：{na}
- target = {sb}：{nb}

## 卡 A 全文（{sa}）
{ta}

## 卡 B 全文（{sb}）
{tb}

## 关系定义（只允许以下判断）
- "prerequisite"（先修）：学生需先理解一方，才可能理解另一方；依据只能是卡文中的教学逻辑（定义依赖、原理依赖、认知层级递进），不得凭常识臆测。
- "related"（相关）：两卡在教学中存在对照、易混或延伸关系，但无先后依赖。
- "no_relation"：卡文中找不到任何可逐字引用的教学关联依据。宁缺毋滥：没有证据就输出 no_relation。

## 硬性规则
1. evidence 必须是从卡 A 或卡 B 原文中逐字复制的原句，并注明 evidence_field（来自哪个字段）。
2. 禁止输出除 source/target 之外的第三个实体；禁止改写实体名；禁止引用【知识标签】【学习场景】等卡中不存在的字段。
3. prerequisite 必须给出 direction（"source_to_target" 表示先修 A→B，或 "target_to_source"）。
4. 只输出一个 JSON 对象，不要任何其他文字：
{{"pair_id":"{pair_id}","relation_type":"prerequisite|related|no_relation","direction":"source_to_target|target_to_source|null","evidence":"逐字原句","evidence_field":"字段名","rationale":"≤60字理由"}}

无依赖时 direction 填 null。no_relation 时 evidence 可为空字符串。
"""


def call_luna(cfg, prompt):
    body = json.dumps({"model": cfg["model"], "temperature": 0.2,
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(cfg["url"], data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {cfg['key']}"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    dur = time.time() - t0
    text = data["choices"][0]["message"]["content"]
    returned = data.get("model", cfg["model"])
    log(f"[LUNA-CALL] {time.strftime('%H:%M:%S')} 耗时={dur:.1f}s model_returned={returned}")
    return text


def extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("无 JSON")
    return json.loads(m.group(0))


def process_one(pair, cards, cfg):
    pid = pair["pair_id"]
    sa, sb = pid.split("__")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"{pid}.json"

    ta, tb = card_full_text(cards[sa]), card_full_text(cards[sb])
    input_hash = hashlib.sha256(
        (PROMPT_VERSION + "|" + ta + "|" + tb).encode("utf-8")).hexdigest()

    if out_file.is_file():
        old = json.loads(out_file.read_text(encoding="utf-8"))
        if old.get("input_hash") == input_hash and old.get("status") in (
                "PROPOSED_UNVERIFIED", "NO_RELATION_PROPOSED"):
            return "skip"

    prompt = PROMPT_TMPL.format(
        pair_id=pid, sa=sa, sb=sb,
        na=cards[sa]["canonical_name"], nb=cards[sb]["canonical_name"],
        ta=ta, tb=tb)

    last_err = None
    for attempt in (1, 2):
        try:
            raw = call_luna(cfg, prompt)
            obj = extract_json(raw)
            rt = obj.get("relation_type")
            if rt not in ("prerequisite", "related", "no_relation"):
                raise ValueError(f"relation_type 非法: {rt}")
            # 逐字证据校验
            ev = obj.get("evidence", "") or ""
            ok_ev = (not rt == "no_relation") and bool(ev) and (ev in ta or ev in tb)
            if rt != "no_relation" and not ok_ev:
                raise ValueError("evidence 未逐字命中两卡原文")
            record = {
                "pair_id": pid, "prompt_version": PROMPT_VERSION,
                "input_hash": input_hash,
                "source": sa, "target": sb,
                "relation_type": rt,
                "direction": obj.get("direction") if rt == "prerequisite" else None,
                "evidence": ev if rt != "no_relation" else "",
                "evidence_field": obj.get("evidence_field", ""),
                "rationale": obj.get("rationale", ""),
                "raw_model": "gpt-5.6-luna",
                "status": "PROPOSED_UNVERIFIED" if rt != "no_relation" else "NO_RELATION_PROPOSED",
            }
            out_file.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                encoding="utf-8")
            return "ok"
        except Exception as e:
            last_err = e
            time.sleep(5 * attempt)
    log(f"[GIVE-UP] {pid}: {last_err}")
    return "fail"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(BASE / "02_分析产物/p5_candidates/all_candidate_pairs.jsonl"))
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    cfg = load_config()
    cards = load_cards()
    pairs = [json.loads(l) for l in Path(args.pairs).read_text(encoding="utf-8").splitlines() if l.strip()]
    log(f"[LUNA-BRIDGE] 端点={cfg['url']} model={cfg['model']} workers={args.workers} 候选={len(pairs)}（主公可在 Vimox 控制台对账）")

    stats = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_one, p, cards, cfg): p["pair_id"] for p in pairs}
        for i, fut in enumerate(as_completed(futs), 1):
            stats[fut.result()] += 1
            if i % 50 == 0:
                log(f"[LUNA-BRIDGE] 进度 {i}/{len(pairs)} {stats}")
    log(f"[LUNA-BRIDGE] 完成：{stats}")


if __name__ == "__main__":
    main()
