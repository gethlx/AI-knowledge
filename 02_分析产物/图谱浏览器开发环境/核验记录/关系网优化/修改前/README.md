# Codex HTML视觉还原与WorkBuddy接口交接

当前入口：`http://127.0.0.1:41839/atlas.html`。默认阅读大语言模型，`?view=explore`直接进入探索，`#card_id`可用于内部深链；内部编号不展示给读者。这是44号确认稿的可运行视觉还原，原安装测试index.html/smoke.js未覆盖。

## 视觉基准与组件

确认基准：44号两张状态稿；搜索42号03-search-suggestions，目录41号03-directory。读者为手机学习者，默认正文优先；没有单独桌面设计，宽屏继续使用480px以内的阅读壳。背景浅暖纸，宋体字形，少量鼠尾草绿与琥珀色强调；不用整张设计图作背景。

- 背景/前景/弱文字/线：#f8f6f1 / #172a35 / #585c5b / #d9d5cb。
- 正文字体：本地AtlasSerif（Noto Serif SC字符子集），16px/1.95；主标题27–36px，节标题21px，英文14px，徽标13px。窄手机标题可自然换行，不截断知识名。
- 页面宽度上限480px，390px左右边距20px；320px边距14px。顶部72px。正文图标40px，文字区间隔15px；窄屏34px/12px。
- 阅读：标题与125×195px关系网缩略并排，正文按实际内容自然延长。更多说明和来源原地折叠。相邻词条全量，次要折叠。
- 探索：同一WebGL容器移到上方，图谱高度约35svh、下限225px，底部同一个详情面板变成定义预览。上拉手柄或按钮进入阅读，不先进入邻居页。
- 顶部新增固定可见的关系网/正文切换按钮，便于在正文滚动后切换并恢复位置；这是用户允许HTML阶段调整的细节。点击标签不做按钮位移，否则会偏离锚点。
- 所有普通按钮最小44px；纸面样式图标来自已安装Phosphor，不用字符/emoji。手柄以Pointer Events支持上拉及取消，正文保持原生滚动。减少动态偏好下不播放入场动画，图谱初始不自动旋转。

## 文件边界

- `atlas.html`：唯一统一页面、搜索/目录浏览层和操作说明。
- `src/styles/atlas.css`：视觉token和手机响应式。
- `src/ui/atlas-preview.js`：可替换的预览控制器。包含真源副本读取、详情渲染、六节点空间演示、少量浏览历史。不是最终src/data、src/graph、src/state或src/main.js。
- `src/ui/preview-data.json`：冻结197卡与1562边的只读JSON副本；为视觉样本提供真实内容与完整邻居。生产整合时换成WB的数据适配器，不能把此副本变成新权威或回写真源。
- `public/assets/`：本地字体子集与许可、独立生成的纸山背景。原字体下载保存在核验记录/HTML还原，未放入生产静态目录。
- `src/ui/vite.config.js`：仅为独立预览配置atlas.html入口，构建到dist-ui；不改变默认安装测试构建或package scripts。

## 当前预览接口

window.atlasUI提供：

| 接口 | 用途 |
|---|---|
| selectConcept(id) | 直接更新正文和高亮；不变图谱焦点/视角；同ID不置顶、不加历史 |
| setMode('reading' / 'explore') | 同一面板切换，保留正文位置；不销毁/重建场景 |
| focusSelected() | 明确请求后才聚焦关系，当前预览取真实邻居中的至多5项 |
| getState() | selected / focus / mode / graphReady / visible / camera |
| readCard(id)、getNeighbors(id) | 真源副本卡文与before/after/related分组，仅供当前预览 |
| graph() | 当前ForceGraph对象，便于技术验证/交接，不是生产场景契约的必需API |

document事件atlas:selection的detail.id和atlas:mode的detail.mode可用作整合监听入口。场景容器#webgl、绑定标签层#node-labels在#graph-surface内，共同移动到#thumbnail-graph或#expanded-graph；不能分别按两套坐标布置节点/线/标签。标签投影使用graph2ScreenCoords，镜头change和resize同步刷新，不在页面坐标中伪造连线。

WB可保留HTML/CSS/资产与控件语义，替换预览控制器为正式数据、场景和状态模块；原样保留selectConcept与focusSelected的行为差异。当前焦点与阅读概念不同，顶部提示“图谱聚焦：…”。

## 明确待接入

当前六节点布局是为复现图稿而固定的三维坐标，有真实旋转、球体点击和有效方向箭头；不是197节点力导向场景。没有全图按钮冒充197节点渲染。正文/搜索/目录与邻居清单可读取全部197卡/1562边，但正式全图、密集标签避让、相机/过滤完整历史、WebGL故障回退的运行证据、手机实机性能仍由WB整合验收。不要在替换预览前删掉“样式预览”范围说明。

WB下一步直接参考44号语义、45号还原报告及本文件；保持冻结输入、所有方向/类型、缺项和待定状态。无需为每个卡生成视觉稿；同一模板可套197卡。不新增服务器、账号或课程编排。

## 运行

开发：在工程目录执行`./tools.sh npm run dev`，打开/atlas.html。

还原专用构建：`./tools.sh npm exec vite build -- --config src/ui/vite.config.js`，输出dist-ui。该输出使用Web服务打开，不直接双击模块HTML。
