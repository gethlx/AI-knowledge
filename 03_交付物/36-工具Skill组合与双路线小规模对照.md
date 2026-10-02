# 36 · 工具与Skill组合、双路线小规模对照

2026-10-02｜用户已授权记录选型并制作小规模对照。选型为候选组合，尚未安装新增Skill或确定正式产品路线。34号是功能提案，35号是扩充候选；本文件澄清两条路线均保留，不把暂缓重复安装解释为否定图先行。

## 工具与Skill组合

| 路线/角色 | 建议组合 | 本轮实际使用 |
|---|---|---|
| A：视觉图先行 | imagegen生成设计图；img-to-frontend候选组织出图→用户选图→转码→截图对照；已有product-design:image-to-code可负责选图后的还原 | imagegen内置工具生成一张真实内容桌面设计图；尚未选图，不进入A路线转码 |
| B：HTML先行 | qiaomu-design候选组织可运行方向预览；现有HTML/前端工具直接实现并检验阅读、导航 | HTML、html-prototype及design-artifact现有Skill制作独立单文件预览 |
| 两路线共同评审 | Impeccable候选负责专项评审与打磨，浏览器工具验证真实内容和交互 | Playwright验证B预览；A图文人工检查，机器检查范围另记 |
| 后期动效 | emil-design-eng按具体问题择机引入 | 未引入 |

新增安装候选：qiaomu-design、Impeccable；img-to-frontend恢复为A路线主要候选，是否新增安装取决于图先行工作流的实际选择。已有工具可完成本轮对照，但本轮不构成这些未安装Skill的效果评测。taste-skill已有版排除密集product UI，不整套启用；UI UX Pro Max、web-design-engineer留作备选；图转码同名市场包未核对包内容，不重复安装。

社区证据与边界：
- [qiaomu官方正文](https://github.com/joeseesun/qiaomu-design/blob/main/SKILL.md)覆盖中文、阅读器和功能UI；[安装反馈#14](https://github.com/joeseesun/qiaomu-design/issues/14)报告参考目录遗漏，正式安装须核对完整目录，不能只看SKILL.md存在。
- [Impeccable官方正文](https://github.com/pbakaus/impeccable/blob/main/plugin/skills/impeccable/SKILL.md)区分Read/Operate；[独立开发者实测](https://dev.classmethod.jp/en/articles/claude-code-impeccable-skill-ai-slop-removal/)提供具体对比度修正例；[漏检#884](https://github.com/pbakaus/impeccable/issues/884)和[误报#882](https://github.com/pbakaus/impeccable/issues/882)说明检测不替代浏览器验收。
- [img-to-frontend正文](https://github.com/am-will/codex-skills/blob/main/skills/img-to-frontend/SKILL.md)要求四张图与人工选图。本轮不调用该Skill，用户授权的小规模一图对照优先，不冒充完整四阶段执行。
- [七款横评](https://www.cnblogs.com/itech/p/21618703)发表于2026-07-18、测试SaaS官网，不将其排名或“零bug”外推为知识图册效果。市场平台通道不自动证明与上游版本同等或无hook行为。

## 对照设计

同一节点：4-03“大语言模型”；同一真源：`02_分析产物/p0_baseline/card_evidence.jsonl`与G_v2正式graph.json，版本0bd1a09cd159。节点九项字段原文不改，原文缺项不补造；41条关系中先修3、相关38。先修有效方向：3-04模型→4-03；3-21下一个词预测与自回归生成→4-03；4-03→4-05微调与指令微调。

共用视觉brief：作者/教师研究、桌面优先只是当前试作假设；现代知识图册，深蓝导航、白色阅读面、青绿强调；目录＋宽卡文＋局部关系辅栏。控制内容和视觉气质相近，观察不同生产路线的表现，不把颜色偏好当路线效果。

| 产物 | 比较问题 | 边界 |
|---|---|---|
| A静态设计图 | 整体审美、阅读层级、视觉构图能否先讲清楚 | 无真实交互；中文生成可能失真；未转码，不能评估还原成本/偏差 |
| B可运行HTML | 真文是否可读、邻居跳转/返回、关系方向、搜索与窄屏是否成立 | 小规模候选预览，不是正式产品；不代表qiaomu/Impeccable试作成绩 |

B目录范围为4-03及其41个邻居共42张卡，搜索仅这些样本；冻结197卡及全图关系嵌入用于节点原文和完整邻接核对。局部图仅画6条，显示总数与图示数，全部关系可从清单访问。生成图只作视觉参考，图中的内容与关系不取代冻结数据。

先交付一张图与一个真实HTML预览，待用户比较后再决定：保留图先行并选择参考图进行还原；保留HTML先行继续打磨；或结合两者。安装、正式开发和课程编排均不由本轮对照自动启动。

## 交付入口与核验

- [打开对照入口](图谱浏览器小规模对照-20261002/index.html)
- [B：可运行HTML预览](图谱浏览器小规模对照-20261002/route-b.html)
- A设计图、完整生图提示词、真源快照说明及本轮验证结果均放在上述独立对照目录。状态与具体结果完成后补记。

## 本轮实际结果

A已生成初稿并修正一次：去掉虚构分类、部分相关线换为虚线，但仍残留LLM→AIGC→微调的错误先修链、“先理解”3条误标；原文标点/空格等不能保证逐字一致。因此A仅供审美比较，关系语义未通过，不作转码数据来源。初稿与修正稿均保存，统一入口突出披露。

B已完成：冻结卡文九项字段一致，41条清单、先修3条及相关38条、局部6条、搜索及空结果、邻居跳转与返回、键盘操作、390px无横向溢出、减弱动效模式及无脚本错误，共14项浏览器检查通过。桌面1440×1000、窄屏390×844截图已检查。搜索LLM可同时命中包含该缩写的其他节点，不强行限定唯一匹配。

本次只检验上述核心样本，不宣称全197卡逐节点功能验收或全面无障碍认证。A转码还未开展，无法比较还原成本与偏差；未安装qiaomu-design、Impeccable或img-to-frontend，不能将结果写成这些Skill的横评。当前不选定胜者，待用户看实际产物。正式四件工件哈希未变，无提交、推送或发布。
