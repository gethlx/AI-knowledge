# 项目说明 · 银河AI通识课程体系知识图谱

> 更新：2026-10-01｜**G_v2 已正式入图（主公明示豁免人工验收）；数据与记录链闭合，待外部 AI 终审验收**。渲染展示层待按 G_v2 重建。

## 项目与当前阶段

把 197 张 AI 通识概念卡转换为模型裁定关系图。**当前冻结基线：`G_v2_模型裁定版`，graph_version `0bd1a09cd159`：197 节点、1,562 边（related 1,484 + prerequisite 78），先修 DAG pass，连通分量 1，孤岛 0。** 旧基线 G_v1（`6031421d9f22`，1,376 边）字节原样保留，版本链 G_K1 → G_v1 → G_v2 可追溯。

2026-10-01 主线：229 份缺结构化字段的历史裁定（rationale 长文逐项复核通道）完成逐对结论恢复分流——**186 对恢复（183 related + 3 prerequisite 带方向）、43 对排除（37 no_relation + 6 insufficient_evidence）**，GPT 与 WorkBuddy 双方逐对核验交叉一致（29 号 v3、30 号报告），随后候选图机器校验全绿，主公明示豁免人工验收，正式入图。

## 位置与先读文件

- 本地根目录：`/Users/larry/WorkBuddy/2026-09-13-14-09-47/`
- 仓库：`origin → git@github.com:gethlx/AI-knowledge.git`，main 分支，最新 commit `e074263`
- 导航：`00-项目导航账本.md`（内含"外部 AI 终审验收入口"速查节，**终审从此读起**）
- 验收历史链：25 号（验收收尾）→ 27 号（三处质疑）→ 28 号（全量分流六问）→ 29 号（按原始裁定重做，v3）→ 30 号（终审材料直接修正）

## 关键文件

| 用途 | 项目内路径 |
|---|---|
| **正式冻结包（当前基线）** | `03_交付物/G_v2_模型裁定版/`（graph.json + graph.graphml + node_summaries.json） |
| 旧基线（保留追溯） | `03_交付物/G_v1_模型裁定版/`（字节未动） |
| 展示层（未重建） | `03_交付物/G_v1_展示修正版/`（仍渲染旧 1,376 边，待按 G_v2 重建） |
| 186 对恢复依据 | `02_分析产物/验收与记录收尾/229对按最终裁定分流-20261002.json`（五元组+证据句+rationale哈希）＋ `229对裁定结论复核证据-20261001.json` ＋ `229对终审材料-20261002.txt`（全文 rationale） |
| 入图机器校验 | `02_分析产物/验收与记录收尾/G_v2_候选图_186恢复/候选图验证报告.json` ＋ `promote_candidate_to_v2.py` |
| 防呆脚本 | `02_分析产物/验收与记录收尾/finalize_229_review.py`（缺项/哈希变化/未知关系报错；默认只读，--write 重建） |
| 全部 197 卡内容 | `02_分析产物/p0_baseline/card_evidence.jsonl` |
| P1-P8 阶段边台账 | `02_分析产物/p5_review/accepted_model_adjudicated_edges.jsonl`（1,376 条） |
| 永久审计凭据 | `04_归档/图谱关系审计凭据/`（7,895 份评审 JSON 压缩包、1,907 条裁定 JSONL 及保全清单） |
| 契约（已修补） | `03_交付物/p1_review_contract/edge_adjudication.schema.json`（新增 adopted_relation/adopted_direction，存量向后兼容） |

## 接手必须知道的事实

1. 全部关系为模型裁定（多模型互审+主控采纳），未人工逐条核验；**人工验收由主公 2026-10-01 明示豁免**。
2. 229 对恢复的结论均取自 adjudications.jsonl rationale 原文（非三路票数、非正则推断）；其中 5+2 处先后错分均被对方 AI 核出并修正，全过程留痕于 27-30 号报告。
3. 43 对排除含 6 对 insufficient_evidence——证据不足≠证明无关系；210 条批量速裁 ACCEPTED 未入图对中 132 条 rationale 为空，其"无关系"结论依赖 verdict_matrix 佐证链。
4. 六孤岛已消除（恢复前后对比见候选图验证报告）；"孤岛系课程设计留白"为已被推翻的旧表述。
5. 待删除区（13,539 文件/83M）未动，终审验收完毕后由主公下令整体清除；永久凭据不在其中。
6. p6.guardian.plist（9-30 幽灵定时任务）已归档停用，可恢复；114 次 sol 调用费用待主公侧 Vimox 账单核实。

## 终审建议核对清单

1. 抽样核验 186 对恢复边的 rationale 原文（分流 JSON 给出逐对行号+证据句+哈希）。
2. 复跑 `finalize_229_review.py`（只读检查）与 `promote_candidate_to_v2.py` 断言。
3. 核对 G_v2 graph.json 与候选图一致性、graph_version 哈希、G_v1 字节未动。
4. 43 对排除逐对复核（尤其 6 对 insufficient_evidence）。
5. 展示层重建与浏览器验收为后续独立工作，不属本轮数据终审范围。
