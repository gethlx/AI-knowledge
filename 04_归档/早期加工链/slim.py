#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.9.4 → v3.9.5（瘦身版）
清理：历史版本备注 / 废弃的六主轴-四阶段编排结构 / 审计过程痕迹 / 散落的母版引用 / 图谱线表述
产出：03_交付物/银河AI通识课程体系-知识地图总纲-v3.9.5-瘦身版.md

【状态：过程档案，已不可运行】
输入源 v3.9.4 已按「甲案」清除，v3.9.5 为唯一真源，本脚本不再需要执行。
保留它仅为记录瘦身逻辑（哪一处被改成什么）；人可读对照见《07-瘦身对照清单》。
若要重跑：先取回输入文件，再把下方 SRC 指回该文件。
"""
import re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scenario_data as sd

ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "03_交付物/银河AI通识课程体系-知识地图总纲-v3.9.4-修正版.md")
DST = os.path.join(ROOT, "03_交付物/银河AI通识课程体系-知识地图总纲-v3.9.5-瘦身版.md")

lines = open(SRC, encoding="utf-8").read().split("\n")
log = []


def find(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise ValueError("NOT FOUND")


def sub(pred, new, tag):
    i = find(pred)
    old = lines[i]
    lines[i] = new
    log.append(f"[{tag}] 改写 L{i+1}：{old[:46]}… → {new[:46]}…")


# ============ 1. 删除 §1.2 概念生命周期总表 + §1.3 四阶段知识重心 ============
a = find(lambda l: l.startswith("### 1.2 概念生命周期总表"))
b = find(lambda l: l.startswith("## 二、"))
n = b - a
del lines[a:b]
log.append(f"[A1/A2] 删除 §1.2+§1.3 废弃编排结构：{n} 行")

# ============ 2. 头部元信息 ============
sub(lambda l: l.startswith("| **文档版本** |"),
    "| **文档版本** | v3.9.5（瘦身版 · 清理历史备注与废弃结构） |", "B1")
sub(lambda l: l.startswith("| **文档定位** |"),
    "| **文档定位** | 母版 §3.1 知识主轴的展开实现；补足母版明确标注的「知识骨架尚未逐课覆盖」缺口 |", "B1")
sub(lambda l: l.startswith("| **覆盖范围** |"),
    "| **覆盖范围** | 197 条统一编号概念卡（知识标签 K1–K6 × 学习场景 S1–S7）；**只含概念、原理与基础知识，不含任何实操、工具操作与任务卡** |", "B1")
sub(lambda l: l.startswith("| **概念总量** |"),
    "| **概念总量** | **197** 条（统一编号：原稳定层 162 ＋ 演进层并入 35；按知识标签连续编号，无独立前沿区） |", "B1")
sub(lambda l: l.startswith("| **本版变更** |"),
    "| **本版变更** | v3.9.5 瘦身版：清理历史版本备注、废弃的六主轴/四阶段编排结构、审计过程痕迹；散落的母版条款引用归并至章末统一说明。六条主轴正式降格为知识标签 K1–K6，与学习场景标签 S1–S7 并列。v3.9–v3.9.4 各版修正记录见《00-审核校验报告》与《07-瘦身对照清单》 |", "A3")
sub(lambda l: l.startswith("> **本文件与母版的关系**"),
    "> **本文件与母版的关系**：本文件是母版的**下游产物**，不修改、不替代母版任何条款。母版 §3.1 已声明「六条主轴是 v5.0-r4 的目标知识骨架，不代表当前116课已经完整覆盖」，本文件即为补齐该骨架的知识侧总纲。凡与母版冲突之处，以母版为准；本文件中的概念深度一律**不得超过**母版 §3.4 规定的深度上限。", "B1")

# ============ 3. §0 使用说明 ============
a = find(lambda l: l.startswith("### 0.2"))
b = find(lambda l: l.startswith("### 0.3"))
NEW02 = ["### 0.2 覆盖范围", "",
         "本文件只承载**知识侧**内容：197 条概念卡，统一编号、统一字段、扁平化组织（正文只有「知识标签 → 概念卡」两层）。", "",
         "平台、入口、界面、价格、操作步骤等**动态工具与案例层**内容不在本文件范围内，属任务卡与动态附件。", ""]
lines[a:b] = NEW02
log.append(f"[B3] §0.2 精简为「覆盖范围」：{b-a} 行 → {len(NEW02)} 行（删母版三层映射表 + 「演进层并入」叙述）")

# ============ 4. §1.1 六条主轴 → 知识标签 ============
sub(lambda l: l.startswith("### 1.1 六条主轴的定位"),
    "### 1.1 知识标签的定位与概念分布", "B4")
i11 = find(lambda l: l.startswith("| # | 知识主轴 |"))
lines[i11] = "| # | 知识标签 | 概念总数 |"
lines[i11 + 1] = "|---|---|---|"
k = i11 + 2
while lines[k].startswith("|"):
    cells = [c.strip() for c in lines[k].strip().strip("|").split("|")]
    lines[k] = f"| {cells[0]} | {cells[1]} | {cells[2]} |"
    k += 1
log.append(f"[B4] §1.1 表删「其中演进层并入」「母版对应」两列：{k - i11 - 2} 行 → 3 列")
sub(lambda l: l.startswith("> **需要重点提示**"),
    "> **需要重点提示**：母版 §3.1 明确指出「**算法、模型与学习**」（K3）是当前最大缺口，必须在后续逐课审计中核对深度、前置关系和学习活动，必要时通过修订或新增课位补足。本文件已按标准深度补齐（40 条，含 v2.0 新增的技术主干），并在每条标注「待补课位」类信息，供课位审计参考。", "B4")
sub(lambda l: l.startswith("> **本版定位变更（v3.9.3 起）**"),
    "> **组织维度（v3.9.5 起）**：六条主轴已正式降格为「知识标签」K1–K6，与「学习场景标签」（S1–S7）双轨并存——一条概念卡同时携带 `K#`（学科归属，用于检索、定位与母版对齐）与 `S#`（学习场景，用于教学编排与分组）。详见《01-场景化归类总表》《02-边界联系与触发条件》。", "B4")

# ============ 5. §三 标题与结构说明 ============
sub(lambda l: l.startswith("## 三、概念卡总目录"),
    "## 三、概念卡总目录：197 条统一编号概念卡", "B5")
sub(lambda l: l.startswith("> **结构说明（扁平化"),
    "> **结构说明（扁平化 · 原子化）**：正文只有「知识标签 → 概念卡」两层，不设更深的分组层级。每条概念卡为**原子化知识单元**，统一包含字段：**精确定义、常见误解、前置概念、后续概念、典型案例、反例、深度上限、安全伦理边界、来源依据**（教学类比另列）。**「前置概念」「后续概念」两字段记录概念间的引用与依赖**（前置 → 本卡），配合统一编号即可追溯全部概念的前后关系。", "B5/E4")
sub(lambda l: l.startswith("> 认知层级为「待定」的 35 条"),
    "> 认知层级为「待定」的 35 条为演进层并入卡。这 35 条的「前置概念」「后续概念」引用**已补齐**；其**认知层级仍为「待定」**。", "B5/E3")

# ============ 6. §3.1–3.6 标题：主轴N → 知识标签 KN ============
for k in range(1, 7):
    pref = f"### 3.{k} 主轴{k}："
    i = find(lambda l, p=pref: l.startswith(p))
    old = lines[i]
    lines[i] = old.replace(f"主轴{k}：", f"知识标签 K{k}：")
    log.append(f"[B6] 章标题 L{i+1}：{old} → {lines[i]}")

cnt = 0
for i, l in enumerate(lines):
    if l.startswith("> **四阶段递进**："):
        lines[i] = l.replace("> **四阶段递进**：", "> **概念递进**：")
        cnt += 1
log.append(f"[B6] 「四阶段递进」→「概念递进」：{cnt} 处")

cnt = 0
for i, l in enumerate(lines):
    if l.startswith("本轴共"):
        lines[i] = l.replace("本轴共", "本标签组共")
        cnt += 1
log.append(f"[B6] 「本轴共」→「本标签组共」：{cnt} 处")

# ============ 7. §二 标题 ============
sub(lambda l: l.startswith("## 二、跨阶段深度边界"),
    "## 二、深度边界（硬约束）", "C2")

# ============ 8. §4.1 改造为「场景 × 伦理锚点」 ============
ETH = ["2-08", "2-10", "2-11", "2-14", "4-10", "4-13", "4-15", "4-19", "4-21",
       "5-05", "5-10", "5-11", "6-02", "6-03", "6-04", "6-05", "6-06", "6-07",
       "6-08", "6-09", "6-10"]
NAME = {}
for l in lines:
    m = re.match(r'^#### (\d+-\d+)　(.+)$', l)
    if m:
        NAME[m.group(1)] = m.group(2)

groups = {f"S{k}": [] for k in range(1, 8)}
for cid in ETH:
    s = sd.P.get(cid, ("S?", ""))[0]
    groups.setdefault(s, []).append(cid)

FOCUS = {
    "S1": "本场景不单设伦理锚点——隐私与可靠性判断首次在 S3 出现",
    "S2": "说清用法与边界：不把提示词当作全部 AI 能力，不越界代劳",
    "S3": "依据在哪、能不能信：先查后写、区分来源可靠性、标明不确定",
    "S4": "谁主导、归谁、标不标：人主导创作、署名与 AI 参与说明",
    "S5": "素材本身的成色：数据质量与偏差是结果可靠性的根",
    "S6": "敢不敢发、谁能用：人工决定点、发布条件与用户责任",
    "S7": "边界、代价与选择：公平、隐私、安全、责任与治理制度",
}
SNAME = {k: f"{k} {sd.SCENARIOS[k]['name']}" for k in sd.SCENARIOS}

rows = []
for k in range(1, 8):
    sk = f"S{k}"
    ids = groups.get(sk, [])
    cell = "、".join(f"{c} {NAME.get(c, '')}" for c in ids) if ids else "—"
    rows.append(f"| **{SNAME[sk]}** | {cell} | {FOCUS[sk]} |")

NEW41 = ["### 4.1 场景 × 伦理锚点", "",
         "> **伦理锚点**指概念卡中承载「在哪里停下来、由谁负责、要向谁说明」的知识点。下表按学习场景（S1–S7）归组，便于随场景大纲定位伦理承担点。", "",
         "| 主场景 | 承载概念（本文件编号） | 该场景的伦理侧重 |",
         "|---|---|---|"] + rows + [
         "",
         "> **深度边界**：以上锚点一律只要求学生做「识别—选择—说明理由」层的判断；不讲法律例外与判例细节、不涉及正式数据治理与统计公平性、不扩展为合规体系或宏观政策分析。", ""]

a = find(lambda l: l.startswith("### 4.1 四阶段伦理锚点"))
b = find(lambda l: l.startswith("### 4.2 高风险领域边界"))
lines[a:b] = NEW41
log.append(f"[C1] §4.1 改造为「场景 × 伦理锚点」：{b-a} 行 → {len(NEW41)} 行，锚点 {len(ETH)} 个按 S1–S7 重组")

# ============ 9. §五 接口 ============
sub(lambda l: l.startswith("## 五、与后续场景化大纲及知识图谱的接口"),
    "## 五、与下游大纲的接口", "C3")

# 9b. 删除 §5.3「知识图谱制作接口」整节，§5.4 重编号为 §5.3
_a = find(lambda l: l.startswith("### 5.3 知识图谱制作接口"))
_b = find(lambda l: l.startswith("### 5.4 版本治理建议"))
del lines[_a:_b]
log.append(f"[C4] 删除 §5.3「知识图谱制作接口」整节：{_b-_a} 行")
sub(lambda l: l.startswith("### 5.4 版本治理建议"), "### 5.3 版本治理建议", "C4")

sub(lambda l: l.startswith("- 「阶段目标、学习前置"),
    "- 「学习前置、全课程统一表达基准及认知复杂度」→ 第一部分 1.1 与第二部分深度边界；", "B7")
sub(lambda l: l.startswith("- 「每阶段显性伦理锚点"),
    "- 「显性伦理锚点的承载课位或项目节点」→ 第四部分 4.1（待课位审计后回填具体课位编号）。", "B7")
sub(lambda l: l.startswith("4. 重点核对主轴3"),
    "4. 重点核对知识标签 K3（算法、模型与学习）的 40 条概念，母版已点名此轴需补足。", "B8")


def repl_in_line(pred, old, new, tag):
    i = find(pred)
    before = lines[i]
    lines[i] = lines[i].replace(old, new)
    log.append(f"[{tag}] L{i+1}：{old} → {new}")
    assert before != lines[i], "no-op replace"


sub(lambda l: l.startswith("| 演进层并入卡确定层级与阶段 |"),
    "| 演进层并入卡确定认知层级 | 统一补齐 35 条「待定」卡的教学字段与引用边，升级为完整概念卡 |", "B9")

# ============ 10. 附录A 列改造 ============
ih = find(lambda l: l.startswith("| 编号 | 概念 | 主轴 | 首次阶段"))
lines[ih] = "| 编号 | 概念 | 知识标签 | 主场景 | 认知层级 | 层级 |"
ib = find(lambda l: l.startswith("## 附录B"), ih)
m_cnt = 0
for k in range(ih + 2, ib):
    l = lines[k]
    if not l.startswith("|"):
        continue
    cells = [c.strip() for c in l.strip().strip("|").split("|")]
    if len(cells) != 7:
        log.append(f"!! 附录A 列数异常 L{k+1}: {l}")
        continue
    cid, name, axis, _f, _d, lvl, layer = cells
    s = sd.P.get(cid, ("—",))[0]
    lines[k] = f"| {cid} | {name} | {axis} | {s} | {lvl} | {layer} |"
    m_cnt += 1
log.append(f"[B10] 附录A 列改造：删「首次阶段/最深阶段」，主轴→知识标签，新增「主场景」；{m_cnt} 行重构")

# ============ 11. 附录B ============
a = find(lambda l: l.startswith("### B.1"))
b = find(lambda l: l.startswith("### B.2"))
NEWB1 = ["### B.1 需你确认的编辑问题", "",
         "| # | 问题 | 当前处理 |",
         "|---|---|---|",
         "| 1 | 「算法、模型与学习」（K3）与「社会、伦理与未来」（K6）的补齐是否符合课程定位 | 已按母版标准补齐（K3 40 条 / K6 41 条），待审 |",
         "| 2 | 认知层级四级（识记/理解/应用/分析评价）替代母版五层是否可接受 | 已按此处理，理由见 0.3 |",
         "| 3 | 35 条演进层并入卡的认知层级如何确定 | 引用边已补齐；认知层级待定 |", ""]
lines[a:b] = NEWB1
log.append(f"[A4] 附录B.1 清理已完成历史条目：{b-a} 行 → {len(NEWB1)} 行")

i = find(lambda l: l.startswith("> 注：原「生成式UI"))
del lines[i]
if lines[i] == "" and lines[i - 1] == "":
    del lines[i]
log.append("[A5] 删除附录B 旧编号注释（F-D04/F-D08/F-F04）")

# ============ 12. 尾部：母版引用统一说明 ============
i = find(lambda l: l.startswith("**文档结束**"))
lines[i] = "**文档结束**　|　版本 v3.9.5（瘦身版）　|　生成日期 2026-09-13　|　状态：待人工确认"
j = find(lambda l: l == "---", max(0, i - 8))
lines[j:j] = ["---", "", "**母版引用统一说明**", "",
              "> 本文件所有深度边界对齐母版 §3.4，伦理锚点对齐母版 §6.3，术语取舍对齐母版 §2.4，知识主轴对齐母版 §3.1。v3.9.5 瘦身时已清理散落的逐处条款引用；如需追溯具体条款，按对应章节编号查阅母版原文。", ""]
log.append("[A6/E1] 尾部旧版本行更新 + 新增《母版引用统一说明》")

# ============ 13. 卡字段清理 ============
DROP = ["审计缺口", "审计盲区", "盲审缺口", "升入稳定层", "演进层并入（原 F-",
        "（用户确认全收）", "（用户点名的缺口）", "（衍生概念保留）", "（深度重校准后保留）",
        "（FLOPS 单位已砍掉）", "（最高严重度）", "（用户已确认", "（教育视角）",
        "（学习视角）", "（用户明确要求不能缺）", "（缺口"]

n_lvl = n_lim = n_src = n_src_clean = n_src_empty = 0
for i, l in enumerate(lines):
    # 认知层级：只留层级
    m = re.match(r'^\| \*\*认知层级\*\* \| (.+?) \|$', l)
    if m:
        n_lvl += 1
        v = m.group(1)
        m2 = re.search(r'；\*\*(.+?)\*\*\s*$', v)
        if m2:
            lines[i] = f"| **认知层级** | **{m2.group(1)}** |"
        else:
            log.append(f"!! 认知层级未匹配 L{i+1}: {l}")
        continue
    # 深度上限：去阶段前缀 + 去母版尾注 + 演进卡待定表述
    if re.match(r'^\| \*\*深度上限\*\* \|', l):
        n_lim += 1
        v = l[len("| **深度上限** |"):].strip()
        if v.endswith("|"):
            v = v[:-1].strip()
        v0 = v
        v = v.replace("认知层级与起始阶段待定（演进层并入，分层阶段统一确定）",
                      "认知层级待定（演进层并入）")
        v = re.sub(r'^第[一二三四]阶段', '', v)
        v = re.sub(r'（母版[^）]*）', '', v)
        v = v.replace('低阶段用任务指南与可替换模板；中高阶段发展为工作模块与Skill，不绑定单一平台',
                      '从任务指南与可替换模板起步，发展为工作模块与 Skill，不绑定单一平台')
        v = re.sub(r'主轴(\d)', r'K\1', v)
        v = v.strip() or "—"
        if v != v0:
            lines[i] = f"| **深度上限** | {v} |"
        continue
    # 安全与伦理边界：主轴→K 标签 + 去阶段残留
    if re.match(r'^\| \*\*安全与伦理边界\*\* \|', l):
        v = l[len("| **安全与伦理边界** |"):].strip()
        if v.endswith("|"):
            v = v[:-1].strip()
        v0 = v
        v = re.sub(r'（母版§3\.4 限低阶段不讲密钥管理，本卡限于高阶段的安全教育视角，不涉及编程。）',
                   '（本卡限于安全教育视角，不涉及编程。）', v)
        v = v.replace('属于高阶段价值讨论，避免断言与恐慌。', '属于价值讨论，避免断言与恐慌。')
        v = re.sub(r'主轴(\d)', r'K\1', v)
        if v != v0:
            lines[i] = f"| **安全与伦理边界** | {v} |"
        continue
    # 来源依据：清审计痕迹
    if re.match(r'^\| \*\*来源依据\*\* \|', l):
        n_src += 1
        v = l[len("| **来源依据** |"):].strip()
        if v.endswith("|"):
            v = v[:-1].strip()
        segs = [s.strip() for s in re.split(r'[；;]', v) if s.strip()]
        keep = [s for s in segs if not any(k in s for k in DROP)]
        # 母版锚点去阶段定位词；「母版主轴N」统一映射为 K 标签
        keep = [re.sub(r'第[一二三四]阶段', '', s) for s in keep]
        keep = [re.sub(r'母版§3\.1主轴(\d)', r'母版§3.1 K\1', s) for s in keep]
        keep = [re.sub(r'母版§3\.2主轴(\d)', r'母版§3.2 K\1', s) for s in keep]
        keep = [re.sub(r'母版主轴(\d)', r'母版§3.1 K\1', s) for s in keep]
        if len(keep) < len(segs):
            n_src_clean += 1
        if not keep:
            n_src_empty += 1
            log.append(f"   来源依据清理后为空（填「行业通行」）L{i+1}: {v}")
            keep = ["行业通行"]
        nv = "；".join(keep)
        if nv != v:
            lines[i] = f"| **来源依据** | {nv} |"
        continue

log.append(f"[D1] 认知层级字段规范化：{n_lvl} 条只留层级")
log.append(f"[F1] 深度上限字段：{n_lim} 条，去阶段前缀与母版尾注")
log.append(f"[D2] 来源依据字段：{n_src} 条，清理审计痕迹 {n_src_clean} 条，清理后为空 {n_src_empty} 条")

# ============ 14. 残余编排痕迹清理 ============
REPL = [
    ("低阶段以可观察事实和生活案例为主；中高阶段再讨论系统关系与社会影响",
     "起步时以可观察事实和生活案例为主，进阶后讨论系统关系与社会影响"),
    ("高阶段可增加技术深度，但必须区分教学简化与真实系统",
     "进阶后可增加技术深度，但必须区分教学简化与真实系统"),
    ("低阶段重在输入、输出和核查，中高阶段才引入系统组件、自动执行和失败处理",
     "起步时重在输入、输出和核查，进阶后才引入系统组件、自动执行和失败处理"),
    ("- 「六条知识主轴的范围、核心概念、前置关系及识别、解释、使用、评价或创造层教学深度」→ 第三部分全部概念卡；",
     "- 「K1–K6 知识标签的范围、核心概念、前置关系及识别、解释、使用、评价或创造层教学深度」→ 第三部分全部概念卡；"),
    ("| 母版 §3.1 知识主轴或 §3.4 深度边界变更 |",
     "| 母版 §3.1 知识标签映射或 §3.4 深度边界变更 |"),
]
for old, new in REPL:
    hit = 0
    for i, l in enumerate(lines):
        if old in l:
            lines[i] = l.replace(old, new)
            hit += 1
    log.append(f"[E2] 残余清理（{hit} 处）：{old[:32]}… → {new[:32]}…")

out = "\n".join(lines)
open(DST, "w", encoding="utf-8").write(out)

print("\n".join(log))
print(f"\n源：{SRC}\n新：{DST}")
print(f"行数 {len(open(SRC, encoding='utf-8').read().split(chr(10)))} → {len(lines)}")
print(f"字符 {len(open(SRC, encoding='utf-8').read())} → {len(out)}")
