#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p6_mega_adjudicator.py —— 主公批准的"一口气"大调用批量裁定。

剩余待裁对全部打进一次 sol 调用：
- 输入：极简判定矩阵（pair|g:rt|d:rt|h:rt|luna）+ 卡名录精简版；
- 输出：极简 JSON 对象 {pair_id: [采纳rt, direction或null, 20字理由或""]}；
- 截断容错：解析已返回的合法前缀，未覆盖对自动并入下一次调用（最多 5 次）。
用法：python3 p6_mega_adjudicator.py        # 跑到全量完成或 5 次调用用尽
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path("/Users/larry/WorkBuddy/2026-09-13-14-09-47")
P5 = BASE / "02_分析产物/p5_review"
INBOX = P5 / "reviews_inbox_full"
BASELINE = BASE / "02_分析产物/p0_baseline"
PROPOSALS = BASE / "02_分析产物/p5_candidates/proposals"
from sol_api_bridge import load_sol_config

plan = json.loads((P5 / "p6_tier_plan.json").read_text(encoding="utf-8"))
ALL = plan["all_pairs"]; MATRIX = plan["matrix"]
cards = {}
for line in open(BASELINE / "card_evidence.jsonl", encoding="utf-8"):
    if line.strip():
        c = json.loads(line)
        cards[c["card_id"]] = c

HEADER = """你是知识图谱项目的概念对批量裁定模型。以下每行一个概念对：pair_id|g:glm判定|d:deepseek判定|h:hy4判定|l:luna提议（ prerequisite 对附 (方向,置信度)，related/no_relation 附 (置信度)；*- 表示该路此信息缺失）。

裁定规则：
1. 三路一致 → 照准；有分歧 → 按多数+置信度独立裁定；分歧过大/疑似红线 → ESCALATE。
2. 先修唯一定义：不理解 A 会实质阻断对 B 的理解或应用。相关但非必需 = related。
3. 输出 JSON 对象（无 markdown 包裹）：{"pair_id": ["采纳的relation_type或ESCALATE", "direction或null", "≤20字理由(ACCEPTED-related可给\"\")"]}
   - relation_type ∈ prerequisite/related/no_relation/insufficient_evidence/ESCALATE
   - direction 仅 prerequisite 需要（source_to_target=A→B / target_to_source），其余 null
4. 只输出 JSON 对象本身。

卡名录（id 名称：定义前40字）：
"""

RT_ALIAS = {"p": "prerequisite", "r": "related", "n": "no_relation", "i": "insufficient_evidence"}


def row(pid):
    r = MATRIX[pid]
    a, b = pid.split("__")

    def fmt(route, tag):
        rt, d, cf = r[route]
        s = RT_ALIAS.get(tag, tag)  # 展示用简称
        if rt == "prerequisite":
            return f"{tag}:p({d[0] if d else '?'},{cf})"
        return f"{tag}:{ {'prerequisite':'p','related':'r','no_relation':'n','insufficient_evidence':'i'}[rt] }({cf})"
    lr = PROPOSALS / f"{pid}.json"
    lt = "-"
    if lr.exists():
        try:
            x = json.loads(lr.read_text(encoding="utf-8")).get("relation_type")
            lt = {"prerequisite": "p", "related": "r", "no_relation": "n", "insufficient_evidence": "i"}.get(x, "-")
        except Exception:
            pass
    return f"{pid}|{fmt('reviewer_glm','g')}|{fmt('reviewer_deepseek','d')}|{fmt('reviewer_hy4','h')}|l:{lt}"


def catalog():
    return "\n".join(f"{cid} {c['canonical_name']}：{str(c['fields'].get('精确定义',''))[:40]}"
                     for cid, c in sorted(cards.items()))


def remaining():
    return [p for p in ALL if not (INBOX / p / "adjudication.json").exists() and p in MATRIX]


def call_sol_once(prompt, max_tokens=65000):
    cfg = load_sol_config()
    body = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.2, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(cfg["url"], data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"[MEGA-CALL] 耗时={time.time()-t0:.0f}s 返回 {len(data['choices'][0]['message']['content'])} 字符 "
          f"finish={data['choices'][0].get('finish_reason')}", flush=True)
    return data["choices"][0]["message"]["content"]


def save(pid, rt, direction, reason, escalate=None):
    status = "ESCALATE_HUMAN" if rt == "ESCALATE" else "ACCEPTED_MODEL_ADJUDICATED"
    out = {"pair_id": pid, "adjudicator": "gpt-5.6-sol(via-subagent)",
           "final_status": status,
           "adopted_relation": None if rt in ("ESCALATE", "no_relation", "insufficient_evidence") else rt,
           "direction": direction if rt == "prerequisite" else None,
           "adopted_by": "orchestrator",
           "rationale": f"[大调用批量裁定] {reason}",
           "residual_risks": ["大调用批量裁定（主公批准）：非逐对实质复核"],
           "reviewer_agreement": "见判定矩阵",
           "escalation_reason": reason if rt == "ESCALATE" else None,
           "schema_version": "p1-contract-v1", "batch_mode": "mega"}
    f = INBOX / pid / "adjudication.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.rename(f)


def parse_obj(content):
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return None
    txt = m.group(0)
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        # 截断容错：逐步回退到最后一个完整 "pid":[...] 记录
        for cut in range(len(txt) - 1, 1, -1):
            frag = txt[:cut].rstrip().rstrip(",")
            try:
                return json.loads(frag + "}")
            except json.JSONDecodeError:
                continue
    return None


def main():
    CHUNK = 150  # 实测：sol 面对 1000+ 对会"躺平"只输出 1 条；150 对时输出纪律正常
    cfg_round = 0
    while cfg_round < 5:
        todo = remaining()[:CHUNK]
        total = len(remaining())
        print(f"[MEGA] 第{cfg_round+1}次调用，本批 {len(todo)} 对（总剩余 {total}）", flush=True)
        if not todo:
            print("[MEGA] 全量完成", flush=True)
            return
        rows = "\n".join(row(p) for p in todo)
        prompt = HEADER + catalog() + f"\n\n## 待裁矩阵（{len(todo)} 对）\n" + rows
        print(f"[MEGA] prompt {len(prompt)} 字符", flush=True)
        try:
            content = call_sol_once(prompt)
        except Exception as e:
            print(f"[MEGA] 调用失败 {type(e).__name__}: {str(e)[:120]}，30s 后重试", flush=True)
            time.sleep(30)
            cfg_round += 1
            continue
        obj = parse_obj(content)
        if not obj:
            print("[MEGA] 返回无法解析，30s 后重试", flush=True)
            time.sleep(30)
            cfg_round += 1
            continue
        ok = bad = 0
        for pid, v in obj.items():
            if pid not in MATRIX:
                bad += 1; continue
            rt, d, reason = (v + [None, ""])[:3] if isinstance(v, list) else (None, None, str(v))
            if rt not in ("prerequisite", "related", "no_relation", "insufficient_evidence", "ESCALATE"):
                bad += 1; continue
            if rt == "prerequisite" and d not in ("source_to_target", "target_to_source"):
                bad += 1; continue
            save(pid, rt, d, reason)
            ok += 1
        print(f"[MEGA] 本轮落盘 {ok}，非法 {bad}；喂 {len(todo)} 对 vs 返回 {len(obj)} 条", flush=True)
        if ok == 0:
            cfg_round += 1
        else:
            cfg_round = 0
    print("[MEGA] 达到连续失败上限，交还主控", flush=True)


if __name__ == "__main__":
    main()
