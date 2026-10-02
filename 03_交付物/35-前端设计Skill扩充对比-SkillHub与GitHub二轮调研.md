# 35 · 前端设计 Skill 扩充对比（SkillHub + GitHub 二轮调研）

> 2026-10-01｜主公要求在 34 号三候选基础上扩充对比池。本轮：SkillHub（WorkBuddy 市场）三路检索 + GitHub/实测榜单二轮检索，共新增 6 个有效候选、排除 5 类噪音。**仍未安装任何 Skill、未试作**。
> 适用场景不变：银河AI知识图册 = 中文长文卡文阅读 + 密集关系图 + 知识查阅（product UI，非 landing page）。

## 一句话结论

**推荐组合更新为"两主一试一补"**：Impeccable（SkillHub 现成 v2.0.0）与 qiaomu-design（中文排版 + 风格试衣间）并列主候选做试作对比；emil-design-eng 留作后期动效打磨；本机已有的 taste-skill 取其反 AI 味规则作补充规则集，**不当主框架**——它自己声明不适合 product UI。

## SkillHub（WorkBuddy 市场）检索结果

三路关键词（前端设计 / frontend design / UI design）去重后，与本任务相关的新发现：

| 候选 | skillId | 版本 | 能力 | 对本项目的判断 |
|---|---|---|---|---|
| **impeccable（市场版）** | `skill_2053082862415904768` | 2.0.0 | 与 GitHub 版同源：23 命令、59 条确定性检测规则、设计系统生成 | **重要发现**：市场有现成包，安装走平台通道，**规避 34 号披露的 npx 写入 hook 风险与 Socket LOW 告警疑虑**。主候选地位不变，安装方式升级 |
| **web-design-engineer** | `skill_2095057993326362624` | 2.0.0 | 网页/仪表盘/原型/数据可视化；**设计评审 + 浏览器验收**（GitHub 源：ConardLi/garden-skills，11K stars，MIT） | 备选。其"浏览器验收"流程与本项目发布教训（发布 HTML 工件须过浏览器冒烟）同构，值得在试点阶段对照 |
| design-taste-plus | `skill_2095292000804139008` | 1.0.0 | "先读 brief，再选真实设计基础"的反模板技能 | **疑似本机已有 taste-skill（design-taste-frontend）的市场同源版**，不重复引入 |
| apple-design | `skill_2095572066616803328` | 1.0.0 | 苹果流体交互：弹簧参数、拖拽手势、毛玻璃 | 边缘。动效思想可参考，与知识阅读主场景相关性低 |
| awesome-design-md | `skill_2053081374617444352` | 1.0.0 | 54 个知名网站设计系统模板 | 资料库型，与 UI UX Pro Max 定位重叠，不优先 |
| design-ui-designer / frontend-ui-engineering / image-to-code / figma / gemdesign | — | — | 设计令牌组件规格 / 工程实践 / 图生码 / Figma / 原型平台 | 排除：或平台绑定，或与本任务工作流不符 |

## GitHub 与实测榜单二轮检索

### 关键发现 1：cnblogs 七款实测横评（2026-09）

来源：cnblogs.com/itech/p/21618703（实测 7 款 AI 网页设计 Skill 横向对比）。核心结论：**Star 数与质量几乎无关**——162K stars 的官方 frontend-design 效果不如无 star 数的第三方；29.2K stars 的 Vercel 官方 Web Design Guidelines 直接翻车（实测 2 分，排除）。

| 实测排名 | Skill | 实测综合 | 说明 |
|---|---|---|---|
| 1 | **design-taste-frontend**（taste-skill） | 9.5/10 | 视觉 10 / 细节 10 / 响应式 10 / 0 bug。**本机 `~/.workbuddy/skills/taste-skill/` 已装，与上游 main 分支 sha256 逐字节相同（`aa194351b246b8b4`，2026-10-01 实测）＝上游 v2 原样** |
| 2 | **qiaomu-design**（joeseesun，向阳乔木） | 8.5/10 | 创意 10。创意项目、叙事型单页 |
| 3 | emil-design-eng（emilkowalski） | 8/10 | 动效 10。ex-Vercel/Linear，Sonner/Vaul 作者 |
| 4 | Impeccable | 8/10 | 细节 9 / 响应式 9 / 0 bug，创意 6 |
| 5 | UI UX Pro Max | 7.5/10 | 团队协作、B 端、兜底 |
| 6 | Frontend Design（Anthropic 官方） | 7/10 | 创意 10 但 bug 多、细节 6，"预留返工时间" |
| 7 | Web Design Guidelines（Vercel） | **2/10** | **排除** |

### 关键发现 2：taste-skill 的适用边界（对本项目致命）

本机版 SKILL.md 开头自声明：**"Not dashboards, not data tables, not multi-step product UI"**。图谱浏览器 = 多步 product UI + 数据可视化，恰好落在其声明的不适用区。结论：**取其反 AI 味禁令（字体/紫渐变/em-dash/三连卡片）与 pre-flight check 作为补充规则集，不作为知识图册的主设计框架**。上游 v2 仍在迭代（tasteskill.dev），本机版可择机升级。

### 关键发现 3：qiaomu-design（"偏执型设计顾问" v3.9）

GitHub：joeseesun/qiaomu-design。工作流："读懂场景 → 看见方向 → 明确选择 → 真实实现 → 浏览器验收"——**与 34 号推进顺序（视觉方向稿 → 试点 → 浏览器验收）几乎同构**。对本项目的四个针对性能力：

1. **风格试衣间**：一句话生成 4 个设计 Demo，本地预览服务器交互式选择——正好覆盖 34 号"方向 A/B 视觉稿对比"需求，且比两张稿多两个方向；
2. **中文排版规范**——海外 Skill 普遍不重视，本项目 197 卡全中文长文，这是硬需求；
3. **58 套真实网站 DESIGN.md 库**（Stripe/Linear/Apple 等），可"参考 XX 的克制感"注入设计 DNA；
4. **打磨模式六动作**（Audit/Critique/Polish/Animate/Harden/Live）+ preflight 交付门禁 + 自进化偏好账本。

局限：创意型定位，长文知识阅读场景需自行验证；依赖 GLM 5.2 / Claude 级模型执行（作者自述）。

### 其他新候选

- **emil-design-eng**（emilkowalski/skills，32.8K stars / 全家桶 967K 安装）：缓动决策流程图、时长表、44px 命中区。**留给第 3 步"最终审美打磨"阶段引入**，首版不需要。
- **better-\* suite**（jakubkrehel/skills，83K 安装）：review 工作流，与 Impeccable 的 audit 重叠，不优先。
- **designer-skills**（Owl-Listener，63 skills + 27 命令）：全流程太重，单任务项目用不动。
- **MengTo/Skills**：WebGL 广度型，超需求。
- 各类 frontend-design 复刻 fork（binjuhor、BuilderIO、davila7 等）：Anthropic 变体，不重复计数。

## 统一候选池（替代 34 号"推荐组合"节；2026-10-01 主公要求图转码类并入统一待选）

前端视觉稿→实现是一条流水线，候选按角色分两组，**待选共 11 个**：

**A · 设计规则类（决定"长得好不好"）——5 个**

| # | Skill | 角色 | 来源/状态 |
|---|---|---|---|
| 1 | **Impeccable** v2.0.0 | 主候选甲：59 条确定性规则可程序化验收，实测细节/响应式最强、0 bug | SkillHub 现成包，未装 |
| 2 | **qiaomu-design** v3.9 | 主候选乙：中文排版规范＋风格试衣间＋浏览器验收闭环，与项目内容形态最契合 | GitHub，未装 |
| 3 | taste-skill（design-taste-frontend） | 补充规则集：反 AI 味禁令＋pre-flight；自声明不适合 product UI，不当主框架 | 本机已装（与上游逐字节一致） |
| 4 | emil-design-eng | 后期动效打磨（第 3 步收敛阶段引入） | GitHub，未装 |
| 5 | web-design-engineer v2.0.0 | 备选：设计评审＋浏览器验收工作流对照 | SkillHub，未装 |

**B · 图转代码类（决定"从图到码"）——6 个**

| # | Skill | 角色 | 来源/状态 |
|---|---|---|---|
| 6 | **img-to-frontend** | **首选试作**：4 张设计图→用户选→实现提示词→构建→截图迭代逼近参考图，与 34 号第 1 步同构 | GitHub（am-will/codex-skills 系），未装 |
| 7 | image-to-code（taste-skill 仓库子技能） | 已知方向后的高保真还原：生图→深度分析→实现，9 项拨盘 | GitHub，未装（与 #3 同仓库） |
| 8 | image-to-code（市场版） | 同 #7，走 SkillHub 平台通道安装 | SkillHub，未装 |
| 9 | screenshot-to-code | 已有截图→React/Vue/HTML 转码 | GitHub（OneWave-AI），未装 |
| 10 | design-to-code | 截图/Figma→JSON 设计令牌→组件，token 提取思路可借鉴 | GitHub，未装 |
| 11 | image-to-code（plugin87） | 设计系统还原＋对比度/渲染验证门禁，"还原系统非像素复制" | GitHub，未装 |

**另：已调研未推荐 2 个**——UI UX Pro Max（实测 7.5 分，兜底/资料库）、Anthropic frontend-design（实测 7 分，bug 多，仅轻量场景）。排除项见上文各节。

**推荐打法**：A 组选 1-2 个定"审美规则"，B 组选 1 个跑"视觉稿→实现"——第 1 步用 #6 img-to-frontend（或 #2 qiaomu 试衣间直接出可交互 Demo）出方向稿，选中方向后用 #7/#8 高保真还原，全程用 #1 Impeccable audit 交叉验收。A/B 两组互为对方的质检器，不是二选一。

## 边界声明

- 安装量/Stars/实测评分均为 2026-10-01 检索快照，不是审美效果或安全性的最终证明；
- cnblogs 实测的测试对象是营销页/落地页类任务，与本项目的知识阅读场景存在偏差，其排名只作参考不作结论；
- 本轮仍未安装、未试作——所有判断保持 34 号的"适配判断"性质，最终以真实卡文试作对比为准；
- 安装前按平台规程做安全审计（尤其 qiaomu-design 含本地预览服务器脚本）。

## 附：图到代码方向详细分析（索引已并入上文统一候选池 6-11 号）

主公问"有没有还原视觉设计图实现前端网页 UI 的 skill"——有，该方向独立成类，候选如下：

| 候选 | 来源 | 工作流 | 对本项目的判断 |
|---|---|---|---|
| **img-to-frontend** | GitHub `am-will/codex-skills`（经 thedixitjain/the-mega-skill-library 收录，安全扫描 A/100） | 强制四阶段：$imagegen 生成 **4 张互异设计图** → 停下让用户选 → 只把选中图翻译成精确实现提示词 → 构建真实页面并**截图迭代逼近参考图** | **流程与 34 号第 1 步（A/B 视觉方向稿 → 选定 → 实现）完全同构**，且"4 方向"比 2 方向多两个候选；首选试作对象 |
| **image-to-code**（taste-skill 仓库子技能，install name `image-to-code`） | GitHub `Leonxlnx/taste-skill`（skills/image-to-code-skill/，35.9KB） | IMAGE-FIRST 铁律：先生成设计图 → 深度分析 → 实现前端；9 项拨盘基线（VARIANCE 8 / CLARITY 9 / EAGERNESS 10 等） | 与主技能同仓库可一并装；适合已知方向后做高保真还原 |
| **image-to-code**（市场版） | SkillHub `skill_2095482829206953984` | "先生成并分析设计图，再据此实现高保真前端页面" | 描述与 taste-skill 系同源疑似，装市场版可走平台通道 |
| **screenshot-to-code** | GitHub `OneWave-AI/claude-skills`（997 安装 / 287 stars，安全审计 2/3 通过） | 已有截图 → 布局/组件/色值/间距分析 → React+Tailwind（默认）/Vue/HTML 产出 | 适合"已有设计图"场景，本项目需先产出设计图，用途次之 |
| **design-to-code** | GitHub `majiayu000/claude-skill-registry`（163 stars） | 截图/Figma 导出 → 视觉 AI 提取 JSON 设计令牌 → 像素级 React 组件 | token 提取思路可借鉴，单体技能价值一般 |
| **image-to-code**（plugin87 系） | GitHub `plugin87/ux-ui-agent-skills` | 参考图 → 推断设计系统 → 三级 DTCG token → 对比度/渲染验证门禁；诚实声明"还原系统非像素复制" | 其"验证门禁"思想值得并入验收流程 |

**共同边界**：此类技能还原的是设计**系统**（色板/字阶/间距语言），非像素级复刻；本项目知识图册的中文长文排版、密集关系图在"设计图生成"阶段的中文渲染质量必须实测（AI 生图中文易出错字）；密集边、先修方向等图谱语义仍须读 G_v2 数据，设计图不承载关系真源。

**对 34 号第 1 步的落地建议**：视觉方向稿可用 img-to-frontend（4 图选 1）或 qiaomu-design 试衣间（4 方向可交互 Demo）二选一跑——前者产静态设计图后转码，后者直接产代码 Demo；两者都跑则互为对照。
