#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析《银河AI通识课程体系-知识地图总纲-v3.9》概念卡为结构化 JSON。"""
import re, json, os, sys

SRC = (sys.argv[1] if len(sys.argv) > 1
       else "/Users/larry/WorkBuddy/2026-09-13-14-09-47/01_素材输入/银河AI通识课程体系-知识地图总纲-v3.9.md")
OUT = (sys.argv[2] if len(sys.argv) > 2
       else "/Users/larry/WorkBuddy/2026-09-13-14-09-47/02_分析产物/cards.json")

FIELDS = ["认知层级", "精确定义", "常见误解", "前置概念", "后续概念", "典型案例",
          "反例", "深度上限", "安全与伦理边界", "教学类比", "来源依据"]

def main():
    with open(SRC, encoding="utf-8") as f:
        lines = f.read().split("\n")

    cards = []
    cur = None
    cur_field = None
    axis_of_section = None

    card_re = re.compile(r"^####\s+(\d+)-(\d+)\s*\u3000?\s*(.+?)\s*$")
    axis_re = re.compile(r"^###\s+3\.\d+\s+(?:主轴|知识标签 K)(\d+)")
    field_re = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.*)$")

    for ln in lines:
        m_axis = axis_re.match(ln)
        if m_axis:
            axis_of_section = int(m_axis.group(1))
            if cur:
                cards.append(cur); cur = None; cur_field = None
            continue
        # 章节标题边界（#/##/###，不含 #### 卡片标题）：关闭当前卡，防止最后一张卡越界吞掉后续章节
        if re.match(r"^#{1,3}\s", ln):
            if cur:
                cards.append(cur); cur = None; cur_field = None
            continue
        m_card = card_re.match(ln)
        if m_card:
            if cur:
                cards.append(cur)
            cid = f"{m_card.group(1)}-{m_card.group(2)}"
            cur = {"id": cid, "axis": int(m_card.group(1)), "name": m_card.group(3).strip(),
                   "en": "", "raw_stage_level": "", "fields": {}}
            cur_field = None
            continue
        if cur is None:
            continue
        # 英文名行：卡标题后紧跟的 **English**
        if not cur["en"]:
            m_en = re.match(r"^\*\*(.+?)\*\*\s*$", ln)
            if m_en:
                cur["en"] = m_en.group(1).strip()
                continue
        m_f = field_re.match(ln)
        if m_f:
            key = m_f.group(1).strip()
            val = m_f.group(2).strip()
            if key == "字段":
                continue
            cur_field = key
            cur["fields"].setdefault(key, [])
            cur["fields"][key].append(val)
            continue
        # 续行（多行单元格）
        if cur_field and ln.strip():
            if ln.strip() == "---":
                continue
            cur["fields"][cur_field].append(ln.strip())
        if cur_field and ln.strip():
            pass
    if cur:
        cards.append(cur)

    # 清理：去掉表格行尾竖线
    for c in cards:
        for k, v in c["fields"].items():
            txt = "\n".join(x for x in v if x not in ("", "|"))
            txt = re.sub(r"\|+$", "", txt).strip()
            c["fields"][k] = txt
        c["raw_stage_level"] = c["fields"].get("认知层级", "")
        c["definition"] = c["fields"].get("精确定义", "")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=1)

    print(f"解析完成：{len(cards)} 张卡 -> {OUT}")
    from collections import Counter
    print("按主轴：", dict(sorted(Counter(c['axis'] for c in cards).items())))
    no_pre = [c["id"] for c in cards if c["fields"].get("前置概念", "—") in ("—", "")]
    print(f"无前置卡数：{len(no_pre)}")
    no_en = [c["id"] for c in cards if not c["en"]]
    print(f"缺英文名：{no_en}")

if __name__ == "__main__":
    main()
