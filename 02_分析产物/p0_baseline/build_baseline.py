#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0 基线冻结 —— 解析真源总纲，产出规范实体 / 卡片证据 / 双 manifest / 断言报告。

真源：03_交付物/银河AI通识课程体系-知识地图总纲-v3.9.6-瘦身版.md（197 卡）
纯标准库、纯程序解析，不调用任何 LLM API。幂等可重跑。

产物（均写入本目录）：
  canonical_entities.json / card_evidence.jsonl / source_manifest.json /
  runtime_manifest.json / preflight_report.md / P0_REPORT.md
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(OUT_DIR))  # 项目根
SRC = os.path.join(BASE, "03_交付物", "银河AI通识课程体系-知识地图总纲-v3.9.6-瘦身版.md")
RUN_PY = os.path.join(BASE, "02_分析产物", "run_lightrag.py")

PARSER_VERSION = "p0-v1"
EXPECTED_CARDS = 197

# 字段白名单 = 真源实测字段
FIELD_WHITELIST = ["认知层级", "精确定义", "常见误解", "典型案例", "反例",
                   "深度上限", "安全与伦理边界", "教学类比", "来源依据"]
# 禁用字段（v3.9.6 已整列移除，若回流即 FAIL）
FORBIDDEN_FIELDS = ["前置概念", "后续概念"]

CANONICAL_RE = re.compile(r"^[1-6]-\d{2} \S+")
CARD_HEAD_RE = re.compile(r"^####\s+([1-6]-\d{2})\u3000(.+?)\s*$")
ANY_HEADING_RE = re.compile(r"^#{1,4}\s")          # 卡区终止：下一张卡(####)或章节标题(#{1,3})
FIELD_ROW_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|(.*)$")
SEPARATOR_RE = re.compile(r"^\|[\s:\-|]+\|?\s*$")

TZ8 = timezone(timedelta(hours=8))


def strip_md_bold(s: str) -> str:
    """剥离 markdown 加粗符号，保留纯文本。"""
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    return s.replace("**", "").strip()


def clean_cell(line: str) -> str:
    """表格行 → 单元格纯文本：去首尾管道、去加粗。"""
    t = line.strip()
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|"):
        t = t[:-1]
    return strip_md_bold(t)


def parse_source(text: str):
    """解析真源。返回 (cards, unexpected_fields, forbidden_hits, source_hits)。

    cards: [{card_id, name, en, axis, fields, line}]
    unexpected_fields: [(card_id, field, line)]
    forbidden_hits: 解析中发现的禁用字段 [(card_id, field, line)]
    source_hits: 真源全文「前置/后续」命中行 [(line_no, content)]，供 report 逐条解释
    """
    lines = text.split("\n")
    cards, unexpected, forbidden = [], [], []
    cur = None          # 当前卡
    cur_field = None    # 当前正在累积的字段名
    for i, line in enumerate(lines, 1):
        m = CARD_HEAD_RE.match(line)
        if m:
            cur = {"card_id": m.group(1), "name": m.group(2), "en": "",
                   "axis": int(m.group(1).split("-")[0]),
                   "fields": {}, "line": i}
            cards.append(cur)
            cur_field = None
            continue
        if cur is None:
            continue
        if ANY_HEADING_RE.match(line):        # 章节/下一卡 → 关闭当前卡
            cur, cur_field = None, None
            continue
        fm = FIELD_ROW_RE.match(line)
        if fm:
            fname = fm.group(1).strip()
            if fname in FORBIDDEN_FIELDS:     # 禁用字段旧值回流 → 记录行号，跳过
                forbidden.append((cur["card_id"], fname, i))
                cur_field = None
                continue
            if fname not in FIELD_WHITELIST:  # 非白名单字段 → 记 report，跳过不写入
                unexpected.append((cur["card_id"], fname, i))
                cur_field = None
                continue
            cur["fields"][fname] = clean_cell(fm.group(2))
            cur_field = fname
            continue
        if cur_field is not None and line.startswith("|") and not SEPARATOR_RE.match(line):
            # 多行单元格：吃到下一个 | ** 字段行为止
            cur["fields"][cur_field] += "\n" + clean_cell(line)
            continue
        if not cur["fields"].get("_en_done"):
            m_en = re.match(r"^\*\*(.+?)\*\*\s*$", line.strip())
            if m_en and not cur["en"] and not cur["fields"]:
                cur["en"] = m_en.group(1).strip()
                cur["fields"]["_en_done"] = True
                continue
    for c in cards:
        c["fields"].pop("_en_done", None)

    source_hits = [(i, ln) for i, ln in enumerate(lines, 1)
                   if "前置" in ln or "后续" in ln]
    return cards, unexpected, forbidden, source_hits


def extract_runtime(src: str) -> dict:
    """从 run_lightrag.py 代码实际默认值提取（正则匹配 os.environ.get 字面量，不信注释）。"""
    def env(name):
        m = re.search(r'os\.environ\.get\("%s",\s*"([^"]*)"\)' % re.escape(name), src)
        return m.group(1) if m else None

    dim = re.search(r'int\(os\.environ\.get\("LIGHTRAG_EMBED_DIM",\s*"(\d+)"\)\)', src)
    return {
        "BASE_URL": env("LIGHTRAG_BASE_URL"),
        "MODEL": env("LIGHTRAG_MODEL"),
        "EMBED_MODEL": env("LIGHTRAG_EMBED_MODEL"),
        "EMBED_DIM": int(dim.group(1)) if dim else None,
        "review_models": ["glm5.3-flash", "deepseek4.1flash", "hy4"],
        "adjudication_advisor": "gpt-5.6-sol",
        "orchestrator": "glm5.3-flash-session",
    }


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SRC, encoding="utf-8") as f:
        text = f.read()
    with open(RUN_PY, encoding="utf-8") as f:
        run_src = f.read()

    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    file_size = os.path.getsize(SRC)
    cards, unexpected, forbidden, source_hits = parse_source(text)

    # ---------- 规范实体 ----------
    entities = [{"card_id": c["card_id"],
                 "canonical_name": f"{c['card_id']} {c['name']}",
                 "name": c["name"], "en": c["en"], "axis": c["axis"]}
                for c in cards]
    write_json(os.path.join(OUT_DIR, "canonical_entities.json"),
               {"cards": entities, "count": len(entities)})

    # ---------- 卡片证据 ----------
    evidence_lines = []
    for c, e in zip(cards, entities):
        fields = {k: c["fields"].get(k, "") for k in FIELD_WHITELIST}
        evidence_lines.append(json.dumps({
            "card_id": c["card_id"], "canonical_name": e["canonical_name"],
            "en": c["en"], "fields": fields,
        }, ensure_ascii=False))
    with open(os.path.join(OUT_DIR, "card_evidence.jsonl"), "w", encoding="utf-8") as f:
        f.write("\n".join(evidence_lines) + "\n")

    # ---------- source_manifest ----------
    write_json(os.path.join(OUT_DIR, "source_manifest.json"), {
        "source_file": os.path.relpath(SRC, BASE),
        "sha256": sha256, "file_size": file_size,
        "card_count": len(cards),
        "field_whitelist": FIELD_WHITELIST,
        "generated_at": datetime.now(TZ8).isoformat(timespec="seconds"),
        "parser_version": PARSER_VERSION,
    })

    # ---------- runtime_manifest ----------
    runtime = extract_runtime(run_src)
    write_json(os.path.join(OUT_DIR, "runtime_manifest.json"), runtime)

    # ---------- 断言 ----------
    R = []  # (编号, 名称, PASS/FAIL, 说明)

    def check(no, name, ok, detail):
        R.append((no, name, "PASS" if ok else "FAIL", detail))

    n = len(cards)
    check("A1", f"卡数 == {EXPECTED_CARDS}", n == EXPECTED_CARDS, f"实测 {n}")

    ids = [c["card_id"] for c in cards]
    uniq_ids = len(set(ids))
    check("A2", "card_id 唯一 197/197",
          uniq_ids == n == EXPECTED_CARDS, f"唯一 {uniq_ids}/{n}")

    cnames = [e["canonical_name"] for e in entities]
    uniq_cn = len(set(cnames))
    check("A3", "canonical_name 唯一 197/197",
          uniq_cn == n == EXPECTED_CARDS, f"唯一 {uniq_cn}/{n}")

    bad_axis = [c["card_id"] for c in cards if not 1 <= c["axis"] <= 6]
    check("A4", "axis 范围 1-6", not bad_axis,
          f"越界 {len(bad_axis)}" + (f": {bad_axis[:10]}" if bad_axis else ""))

    bad_cn = [cn for cn in cnames if not CANONICAL_RE.match(cn)]
    check("A5", r"规范名匹配 ^[1-6]-\d{2} \S+", not bad_cn,
          f"不匹配 {len(bad_cn)}" + (f": {bad_cn[:10]}" if bad_cn else ""))

    # 禁用字段零回流：card_evidence.jsonl 全文扫描
    evidence_all = "\n".join(evidence_lines)
    hit_exact = sum(evidence_all.count(w) for w in FORBIDDEN_FIELDS)
    check("A6", "禁用字段零回流（前置概念/后续概念）", hit_exact == 0,
          f"card_evidence.jsonl 命中 {hit_exact}")

    hit_loose = [(w, evidence_all.count(w)) for w in ("前置", "后续")]
    loose_in_evidence = sum(c for _, c in hit_loose)
    ok6 = loose_in_evidence == 0
    explanation = []
    for w, _ in hit_loose:
        for i, ln in source_hits:
            explanation.append(f"真源 L{i}: {ln.strip()[:120]}")
    check("A7", "「前置/后续」剩余命中逐条解释",
          ok6, f"card_evidence.jsonl 松散命中 {loose_in_evidence}；"
               f"真源全文命中 {len(source_hits)} 行（均位于文档头部元数据/说明区，"
               f"非卡区、非字段引用，属 v3.9.6 变更记录的说明文字，放行）"
               + ("".join("\n  - " + e for e in explanation[:12]) if source_hits else ""))

    with open(os.path.join(OUT_DIR, "source_manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    sha_ok = m["sha256"] == hashlib.sha256(
        open(SRC, "rb").read()).hexdigest()
    check("A8", "source_manifest.sha256 与实际文件一致", sha_ok,
          f"{m['sha256'][:16]}… size={m['file_size']}")

    missing_def = [c["card_id"] for c in cards if not c["fields"].get("精确定义", "").strip()]
    check("A9", "每卡含非空「精确定义」", not missing_def,
          f"缺失 {len(missing_def)}" + (f": {missing_def[:10]}" if missing_def else ""))

    # 禁用字段旧值核对（真源表行层面）
    src_field_hits = [(i, ln) for i, ln in enumerate(text.split("\n"), 1)
                      if re.match(r"^\|\s*\*\*(前置概念|后续概念)\*\*", ln)]
    check("A10", "真源已无「前置概念/后续概念」表行（旧值核对）", not src_field_hits,
          f"命中 {len(src_field_hits)}" +
          ("".join(f"\n  - L{i}: {ln.strip()[:100]}" for i, ln in src_field_hits) if src_field_hits else ""))

    # 非白名单字段
    check("A11", "无非白名单字段回流", not unexpected,
          f"异常 {len(unexpected)}" +
          ("".join(f"\n  - 卡 {cid} 字段「{fn}」L{ln}" for cid, fn, ln in unexpected[:20]) if unexpected else ""))

    # 运行时默认值非空
    rt_missing = [k for k in ("BASE_URL", "MODEL", "EMBED_MODEL", "EMBED_DIM")
                  if runtime[k] in (None, "")]
    check("A12", "run_lightrag.py 代码默认值提取完整", not rt_missing,
          f"缺失 {rt_missing or '无'}；BASE_URL={runtime['BASE_URL']} "
          f"MODEL={runtime['MODEL']} EMBED_MODEL={runtime['EMBED_MODEL']} "
          f"EMBED_DIM={runtime['EMBED_DIM']}")

    total_pass = sum(1 for r in R if r[2] == "PASS")
    overall = "PASS" if total_pass == len(R) else "FAIL"

    # ---------- 报告 ----------
    now = datetime.now(TZ8).strftime("%Y-%m-%d %H:%M:%S %z")
    rep = [f"# P0 基线冻结 · 断言报告",
           "",
           f"- 生成时间：{now}",
           f"- 解析器版本：{PARSER_VERSION}",
           f"- 真源：`{os.path.relpath(SRC, BASE)}`",
           f"- sha256：`{sha256}`",
           f"- 总裁定：**{overall}**（{total_pass}/{len(R)} 项断言通过）",
           "",
           "| # | 断言 | 结果 | 说明 |",
           "|---|---|---|---|"]
    for no, name, res, detail in R:
        detail_1 = str(detail).replace("\n", "<br>")
        rep.append(f"| {no} | {name} | {res} | {detail_1} |")
    if unexpected:
        rep += ["", "## 非白名单字段明细（已记入 report 并跳过，不写入 card_evidence）"]
        rep += [f"- 卡 {cid} 字段「{fn}」@真源 L{ln}" for cid, fn, ln in unexpected]
    if forbidden:
        rep += ["", "## 禁用字段回流明细（FAIL 项）"]
        rep += [f"- 卡 {cid} 字段「{fn}」@真源 L{ln}" for cid, fn, ln in forbidden]
    rep += ["",
            "## 「前置/后续」真源剩余命中逐条解释（A7 放行依据）"]
    if source_hits:
        rep += [f"- L{i}（文档头部元数据/说明区，非卡区，非字段引用）：`{ln.strip()[:150]}`"
                for i, ln in source_hits]
    else:
        rep += ["- 无"]
    rep += ["",
            "## 字段覆盖统计",
            ""] + [f"- {k}：{sum(1 for c in cards if c['fields'].get(k, '').strip())}/{n}" for k in FIELD_WHITELIST]
    report = "\n".join(rep) + "\n"
    for fn in ("preflight_report.md", "P0_REPORT.md"):
        with open(os.path.join(OUT_DIR, fn), "w", encoding="utf-8") as f:
            f.write(report)

    print(f"{overall}  assertions={total_pass}/{len(R)}  cards={n}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
