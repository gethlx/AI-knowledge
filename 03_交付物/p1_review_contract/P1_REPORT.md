# P1 契约落地报告

- 阶段：P1（准则、Schema、互审 Prompt、升级规则）
- 交付目录：`03_交付物/p1_review_contract/`
- 上位依据：`03_交付物/14-知识图谱实施规划最终裁定版.md`（第一节状态表、3.1 主控换防、3.2 输入隔离、3.3 裁定规则、8.4 接口与 ReviewOpinion、8.5 sol 稳定性协议）
- 参考样例：`02_分析产物/lightrag_input/小样K1-20卡-摄入版.md`（1-01 至 1-20 卡）
- 生成日期：2026-09-26

## 一、产出清单（8 个文件，均为新增，未改动任何既有文件）

| # | 文件 | 内容 |
|---|---|---|
| 1 | `annotation_guidelines.md` | 标注准则 v1.0.0：五类判定（prerequisite A→B / prerequisite B→A / related / no_relation / insufficient_evidence）；先修唯一定义「不理解A会实质阻断对B的理解或应用」；五类各含 2 正例 1 反例（全部取自 1-01～1-20 真实卡名，卡文原句逐字引用）；证据逐字规则；禁令清单；认知层级「只提示、非证据」；兜底规则「无法确定选 insufficient_evidence」 |
| 2 | `edge_review.schema.json` | ReviewOpinion JSON Schema（draft-07）：pair_id、reviewer_id（枚举 reviewer_glm/reviewer_deepseek/reviewer_hy4）、model_requested、model_returned、relation_type、direction、evidence[]（card_id/field/quote 必填）、reason、confidence(0-1)、input_card_hash、prompt_hash、status（枚举 REVIEW_COMPLETED/REVIEW_FAILED/REVIEW_INCOMPLETE）；required 覆盖全部 12 个关键键；additionalProperties=false；allOf 条件约束（prerequisite 必须给方向、非 prerequisite 方向必须 null） |
| 3 | `edge_adjudication.schema.json` | Adjudication JSON Schema（draft-07）：pair_id、adjudicator(const "gpt-5.6-sol(via-subagent)")、final_status（枚举 ACCEPTED_MODEL_ADJUDICATED/REJECTED_MODEL_ADJUDICATED/ESCALATE_HUMAN/ADJUDICATION_DEFERRED）、adopted_by(const "orchestrator")、rationale、residual_risks、reviewer_agreement、escalation_reason（ESCALATE_HUMAN 时条件必填，其余状态必须为 null）、schema_version；additionalProperties=false |
| 4 | `edge_proposal_prompt.md` | 三路评审统一 Prompt 模板（评审员通用）：角色定位、输入（两卡允许字段全文）、关系定义与反例、输出 JSON Schema、禁令清单（外部知识/第三方实体/改写名/旧字段/引用不存在的内容）、insufficient_evidence 使用条件；占位符 {{CARD_A}}、{{CARD_B}}、{{PAIR_ID}}、{{GUIDELINE_VERSION}} |
| 5 | `edge_adjudication_prompt.md` | sol 裁定建议 Prompt 模板：输入 review_bundle（三路意见+程序校验结果+原始卡文+GRAPH_STATE）；逐项复核清单（多数/少数意见、证据命中、影响范围、红线、DAG）；输出 Adjudication JSON；明确「不得简单多数票」「两路一致一路明确反对默认 ESCALATE_HUMAN」「记录反对理由」；占位符 {{REVIEW_BUNDLE}}、{{CARD_A_FIELDS}}、{{CARD_B_FIELDS}}、{{GRAPH_STATE}} |
| 6 | `redline_rules.json` | 红线规则机读版 R1–R10：R1 安全伦理→ESCALATE_HUMAN；R2 卡文矛盾→ESCALATE_HUMAN；R3 先修环/DAG冲突→ESCALATE_HUMAN；R4 双向边→ESCALATE_HUMAN；R5 自引用→REJECT_PAIR；R6 证据逐字校验失败→INVALIDATE_OPINION；R7 表外实体→ESCALATE_HUMAN；R8 旧字段回流（前置概念/后续概念）→ESCALATE_HUMAN；R9 高影响项→SOL_RECHECK_REQUIRED；R10 sol 不可用→ADJUDICATION_DEFERRED（120s 超时、0/30/60s 退避 3 次重试、连续 10 个熔断上报，全部写入规则描述） |
| 7 | `prompt_test_cases.jsonl` | 测试用例 13 条（每行一个 JSON 对象），覆盖 12 项要求场景（见第三节） |
| 8 | `P1_REPORT.md` | 本报告 |

## 二、模型角色写入确认（与规划 3.1/8.1 一致，未偏离）

- 三路独立盲评：glm5.3-flash（reviewer_glm）、deepseek4.1flash（reviewer_deepseek）、hy4（reviewer_hy4）——并行、对等、互不可见；写入 annotation_guidelines.md、edge_proposal_prompt.md、edge_review.schema.json（reviewer_id 枚举）；
- 编排主控：当前会话模型（glm5.3-flash 编排层）——只推流程、做程序校验、采纳裁定建议落盘，绝不自行裁定；写入 edge_adjudication.schema.json（adopted_by const "orchestrator"）、edge_adjudication_prompt.md、redline_rules.json R10 描述；
- 综合裁定建议：gpt-5.6-sol，经 subagent 按需拉起，受 8.5 稳定性协议（120s 超时、3 次重试 0/30/60s 退避、失败进 ADJUDICATION_DEFERRED、连续 10 个熔断上报）；写入 edge_adjudication.schema.json（adjudicator const "gpt-5.6-sol(via-subagent)"、final_status 枚举含 ADJUDICATION_DEFERRED）、edge_adjudication_prompt.md、redline_rules.json R10。

## 三、测试用例覆盖矩阵（13 条）

| case_id | 场景 | expected_relation_type | expected_status |
|---|---|---|---|
| PREREQ_POSITIVE_01 | 明确先修正例 | prerequisite | ACCEPTED_MODEL_ADJUDICATED |
| PREREQ_REVERSED_02 | 方向反转 | prerequisite（target_to_source） | ACCEPTED_MODEL_ADJUDICATED |
| RELATED_CONFUSABLE_03 | 易混 related | related | ACCEPTED_MODEL_ADJUDICATED |
| NO_RELATION_SILENT_04 | 无关（卡文零交集） | no_relation | REJECTED_MODEL_ADJUDICATED |
| NO_RELATION_COOCUR_05 | 无关（同主题/共现陷阱） | no_relation | REJECTED_MODEL_ADJUDICATED |
| INSUFFICIENT_VAGUE_06 | 证据不足 | insufficient_evidence | ESCALATE_HUMAN |
| FORGED_QUOTE_07 | 伪造引文（逐字校验拒绝） | prerequisite（无效意见） | ESCALATE_HUMAN |
| THIRD_PARTY_LURE_08 | 第三方实体诱导 | no_relation | REJECTED_MODEL_ADJUDICATED |
| LEGACY_FIELD_LURE_09 | 旧字段诱导（前置概念/后续概念） | insufficient_evidence | ESCALATE_HUMAN |
| NAME_VARIANT_LURE_10 | 同名变体诱导（应拒绝改写名） | related | ESCALATE_HUMAN |
| HIERARCHY_INVERT_11 | 层级倒挂（层级非证据） | related | ESCALATE_HUMAN |
| TRIPLE_CONSENSUS_12 | 三路一致接受 | prerequisite | ACCEPTED_MODEL_ADJUDICATED |
| TWO_VS_ONE_13 | 两对一反对升级 | prerequisite（存争议） | ESCALATE_HUMAN |

## 四、自检说明

1. **Schema 合法性**：`edge_review.schema.json` 与 `edge_adjudication.schema.json`、`redline_rules.json` 均通过 `json.load` 解析验证为合法 JSON；Schema 语法为 draft-07（$schema 声明、type/enum/required/additionalProperties/allOf-if-then 均为标准关键字）；
2. **JSONL 校验**：`prompt_test_cases.jsonl` 共 13 行，每行均为可独立 `json.loads` 的合法 JSON 对象，含全部 6 个约定字段（case_id/pair_type/input_summary/expected_relation_type/expected_status/notes）；
3. **字段对齐**：ReviewOpinion 字段与规划 8.4 示例逐一对齐；Adjudication 状态枚举与规划第一节状态表、3.3 裁定规则对齐；
4. **口径一致性**：五类判定、先修定义、禁令、insufficient_evidence 兜底在 guidelines、两份 Prompt、测试用例间口径一致；红线 R1–R10 与规划 3.3 裁定表、8.5 稳定性协议对齐；
5. **隔离边界**：三路盲评 Prompt 唯一差异为模型来源；sol Prompt 明确其建议属性与主控"只采纳不裁定"的独立性红线；任何模型不得读取 `04_归档/前置后续-作废字段归档.csv`（R8 落地）；
6. **版本联动**：guidelines v1.0.0 ↔ 两份 Prompt v1.0.0 ↔ 红线规则 v1.0.0 ↔ 测试用例，变更须统一升版本并触发重评估。

## 五、P1 闸门对照（规划第四节）

- 五类判断：guidelines 第 3 节完整定义并配正反例 ✅
- 状态机：ReviewOpinion.status（单路）+ Adjudication.final_status（裁定）两级状态，与第一节状态表对齐 ✅
- 红线规则：R1–R10 机读化，action 可执行 ✅
- 测试：13 条用例覆盖正常流、对抗流、升级流 ✅
