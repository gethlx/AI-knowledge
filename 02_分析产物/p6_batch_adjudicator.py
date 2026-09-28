#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p6_batch_adjudicator.py —— P6 分层批量裁定（主公 2026-09-27 批准的明示偏差）。

偏差依据：14号 §8.4"逐对实质复核"在批量层降为判定矩阵速裁，焦点对仍在层3逐对全量复核。
- 批量层（tier_batch）：1,767 对无先修争议的对，150 对/批打包判定矩阵，sol 一次批裁；
- 焦点层（tier3）：140 对（任一路判 prerequisite / 方向冲突 / 引文 FLAGGED），
  沿用 sol_api_bridge 的逐对 full prompt（三路意见全文 + 卡文全文 + 红线）。

用法（前台短跑适配沙箱，单次调用 2-4 分钟）：
  python3 p6_batch_adjudicator.py batch <批号1..N>     # 跑批量层第 N 批
  python3 p6_batch_adjudicator.py focus <起:止>        # 跑焦点层第 a..b 个（切片）
  python3 p6_batch_adjudicator.py plan                 # 显示计划与完成度

幂等：adjudication.json 已存在即跳过。
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
P5 = BASE / "02_分析产物/p5_review"
INBOX = P5 / "reviews_inbox_full"
BASELINE = BASE / "02_分析产物/p0_baseline"
PROPOSALS = BASE / "02_分析产物/p5_candidates/proposals"
sys.path.insert(0, str(BASE / "02_分析产物"))
from sol_api_bridge import load_sol_config, call_sol, validate, load_redlines_text, build_prompt

BATCH_CAP = 20
TIMEOUT_RETRY = 3

plan = json.loads((P5 / "p6_tier_plan.json").read_text(encoding="utf-8"))
ALL = plan["all_pairs"]; TIER3 = plan["tier3"]; TIER_B = plan["tier_batch"]; MATRIX = plan["matrix"]

cards = {}
for line in open(BASELINE / "card_evidence.jsonl", encoding="utf-8"):
    if line.strip():
        c = json.loads(line)
        cards[c["card_id"]] = c


def card_line(cid):
    c = cards[cid]
    d = str(c["fields"].get("精确定义", ""))[:50]
    return f"{cid} {c['canonical_name']}：{d}"


def luna_rt(pid):
    f = PROPOSALS / f"{pid}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8")).get("relation_type")
        except Exception:
            return None
    return None


def mat_row(pid):
    row = MATRIX[pid]
    a, b = pid.split("__")
    parts = [f"{pid} | {cards[a]['canonical_name']} × {cards[b]['canonical_name']}"]
    for r in ("reviewer_glm", "reviewer_deepseek", "reviewer_hy4"):
        rt, d, cf = row[r]
        parts.append(f"{r.replace('reviewer_','')}:{rt}" + (f"({d},conf{cf})" if rt == "prerequisite" else f"(conf{cf})"))
    lr = luna_rt(pid)
    parts.append(f"luna:{lr}" if lr else "luna:-")
    return " | ".join(parts)


BATCH_HEADER = """你是知识图谱项目（银河AI通识课程体系）的概念对批量综合裁定模型。以下 %d 个概念对已完成三路独立盲评，每行给出：pair_id | 两卡名 | 三路判定（g=glm, d=deepseek, h=hy4，prerequisite 附方向与置信度）| luna 召回侧提议。

## 裁定规则
1. 逐对给出裁定：三路一致 → 照准（ACCEPTED）或否决（REJECTED，需理由）；有分歧 → 按多数与置信度倾向裁定，independent 判断，不盲从多数；分歧过大或疑似红线 → ESCALATE_HUMAN。
2. 先修唯一定义：不理解 A 会实质阻断对 B 的理解或应用。相关但非必需 = related，不是 prerequisite。
3. ACCEPTED 且 relation_type=prerequisite 必须给 direction（source_to_target=A→B 或 target_to_source）；related/insufficient_evidence/no_relation 的 direction=null。relation_type 填你采纳的判定（ACCEPTED 时）；REJECTED/ESCALATE_HUMAN 时填 null。
4. 卡名录（附后）供参考；本批不涉及红线议题对（安全伦理类已单列复核），无需红线核对。
5. 只输出 JSON 数组（无 markdown 包裹、无解释文字），每对一条：
[{"pair_id":"...","final_status":"ACCEPTED_MODEL_ADJUDICATED|REJECTED_MODEL_ADJUDICATED|ESCALATE_HUMAN","relation_type":"prerequisite|related|no_relation|insufficient_evidence|null","direction":"source_to_target|target_to_source|null","brief_reason":"≤40字","confidence":0.0}]

## 卡名录（id 名称：精确定义前50字）
%s

## 批量判定矩阵（%d 对）
""" # .format(n, 卡名录, n)


def run_batch(idx: int):
    chunks = [TIER_B[i:i+BATCH_CAP] for i in range(0, len(TIER_B), BATCH_CAP)]
    chunk = chunks[idx - 1]
    todo = [p for p in chunk if not (INBOX / p / "adjudication.json").exists()]
    print(f"[BATCH {idx}/{len(chunks)}] 批内 {len(chunk)} 对，待裁 {len(todo)}", flush=True)
    if not todo:
        print("[BATCH] 全部已有裁定，跳过", flush=True)
        return
    # 重算本批卡名录（只列本批涉及的卡）
    used_cards = sorted({c for p in todo for c in p.split("__")})
    catalog = "\n".join(card_line(c) for c in used_cards)
    rows = "\n".join(mat_row(p) for p in todo)
    prompt = BATCH_HEADER % (len(todo), catalog, len(todo)) + rows
    print(f"[BATCH] prompt {len(prompt)} 字符", flush=True)
    cfg = load_sol_config()
    body = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.2}).encode()
    adj_map = None
    for attempt in range(1, 3):
        try:
            req = urllib.request.Request(cfg["url"], data=body, method="POST",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=240) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            print(f"[SOL-CALL] batch{idx} 耗时={time.time()-t0:.0f}s 返回 {len(content)} 字符", flush=True)
            import re
            m = re.search(r"\[.*\]", content, re.S)
            adj_map = json.loads(m.group(0))
            break
        except Exception as e:
            print(f"[RETRY {attempt}] 批量失败 {type(e).__name__}: {str(e)[:100]}", flush=True)
            time.sleep(20 * attempt)
    if adj_map is None:
        print("[BATCH] 3 次失败，本批挂起", flush=True)
        return
    ok, bad = 0, []
    for adj in adj_map:
        pid = adj.get("pair_id")
        if pid not in todo:
            bad.append(f"越界:{pid}"); continue
        rt = adj.get("relation_type")
        d = adj.get("direction")
        if adj["final_status"] == "ACCEPTED_MODEL_ADJUDICATED":
            if rt == "prerequisite" and d not in ("source_to_target", "target_to_source"):
                bad.append(f"{pid}:prerequisite缺方向"); continue
            if rt != "prerequisite" and d is not None:
                adj["direction"] = None
        out = {"pair_id": pid, "adjudicator": "gpt-5.6-sol(via-subagent)",
               "final_status": adj["final_status"],
               "adopted_relation": rt if adj["final_status"] == "ACCEPTED_MODEL_ADJUDICATED" else None,
               "direction": adj.get("direction"),
               "adopted_by": "orchestrator",
               "rationale": f"[批量层判定矩阵速裁] {adj.get('brief_reason','')}",
               "residual_risks": ["批量裁定（主公批准的明示偏差）：未逐对实质复核引文"],
               "reviewer_agreement": "见判定矩阵",
               "escalation_reason": adj.get("brief_reason") if adj["final_status"] == "ESCALATE_HUMAN" else None,
               "schema_version": "p1-contract-v1", "batch_mode": "tier2-matrix"}
        out_f = INBOX / pid / "adjudication.json"
        tmp = out_f.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.rename(out_f)
        ok += 1
    print(f"[BATCH {idx}] 落盘 {ok}，异常 {len(bad)} {bad[:5]}", flush=True)


def run_focus(a: int, b: int):
    todo = [p for p in TIER3 if not (INBOX / p / "adjudication.json").exists()][a:b]
    cfg = load_sol_config()
    redlines = load_redlines_text()
    print(f"[FOCUS {a}:{b}] 待裁 {len(todo)}", flush=True)
    for pid in todo:
        prompt = build_prompt(pid, cards, None, None)
        got = False
        for attempt in range(1, TIMEOUT_RETRY + 1):
            try:
                body = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}],
                                   "temperature": 0.2}).encode()
                req = urllib.request.Request(cfg["url"], data=body, method="POST",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})
                with urllib.request.urlopen(req, timeout=180) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                import re
                m = re.search(r"\{.*\}", data["choices"][0]["message"]["content"], re.S)
                adj = json.loads(m.group(0))
                errs = validate(adj, pid)
                if errs:
                    print(f"[FOCUS] {pid} Schema 不合 {errs}", flush=True); continue
                adj["batch_mode"] = "tier3-focus"
                out_f = INBOX / pid / "adjudication.json"
                tmp = out_f.with_suffix(".tmp")
                tmp.write_text(json.dumps(adj, ensure_ascii=False, indent=1), encoding="utf-8")
                tmp.rename(out_f)
                print(f"[FOCUS] {pid} → {adj['final_status']}", flush=True)
                got = True
                break
            except Exception as e:
                print(f"[FOCUS] {pid} RETRY{attempt} {type(e).__name__}: {str(e)[:80]}", flush=True)
                time.sleep(15 * attempt)
        if not got:
            print(f"[FOCUS] {pid} 3 次失败，挂起", flush=True)


def show_plan():
    done = {d.parent.name for d in INBOX.glob("*/adjudication.json")}
    b_todo = [p for p in TIER_B if p not in done]
    f_todo = [p for p in TIER3 if p not in done]
    print(f"全量 {len(ALL)} | 已裁定 {len(done & set(ALL))} | 批量层待裁 {len(b_todo)}（{(len(b_todo)+BATCH_CAP-1)//BATCH_CAP} 批）| 焦点层待裁 {len(f_todo)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        show_plan()
    elif cmd == "auto":
        # 自动找第一个有活的批跑完即返回（供外层限时循环调用）
        nch = (len(TIER_B) + BATCH_CAP - 1) // BATCH_CAP
        done = {d.parent.name for d in INBOX.glob("*/adjudication.json")}
        for i in range(1, nch + 1):
            chunk = TIER_B[(i - 1) * BATCH_CAP: i * BATCH_CAP]
            if any(p not in done for p in chunk):
                run_batch(i)
                sys.exit(0)
        print("[AUTO] 批量层全部完成", flush=True)
    elif cmd == "batch":
        run_batch(int(sys.argv[2]))
    elif cmd == "focus":
        a, b = (sys.argv[2].split(":") + [""])[:2]
        run_focus(int(a), int(b) if b else None)
    else:
        print(__doc__)
