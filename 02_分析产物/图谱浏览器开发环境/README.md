# 神奇科学AI知识图册 · 前端工程

这是本地开发与GitHub在线图册共用的源码。首页为index.html，包含197个概念、1562条关系、定义与解释、搜索和相邻概念原位阅读。默认展开关系网与解释说明；手机实机体验仍需结合真实设备复测。

## 安装与启动

安装Node.js 22.12或更高版本（含npm），在本目录执行：

```bash
npm ci
npm run dev
```

打开终端显示的根地址，默认是 http://127.0.0.1:41839/ 。端口被占用时会明确报错。浏览期间保留终端运行；不能直接双击源码HTML运行。

## 构建和预览

```bash
npm run build
npm run preview
```

构建输出为dist-ui/，首页是index.html。预览默认仍用41839端口，需要先停止开发服务，或以 `npm run preview -- --port 41840` 指定其他端口。托管时上传整个dist-ui目录。默认相对资源路径支持放到子目录；固定部署路径可用 `npm run build -- --base=/你的子路径/`。

GitHub Pages执行同一个build命令，只附加/AI-knowledge/路径。开发、构建、预览与在线发布共用根vite.config.js，无需另外复制或拼装首页。旧的src/ui/vite.config.js仅转导该配置，兼容以前的构建命令。

## 入口与数据

- `/`：唯一产品首页，读取src/ui/atlas-preview.js和src/ui/preview-data.json。
- `/atlas.html`：旧链接兼容跳转，保留查询参数和概念hash；开发及构建后均可用。
- `/tests/smoke/`：仅开发模式提供的早期三节点安装测试，不进入产品构建。
- 原始卡文与G_v2关系包是知识权威来源，preview-data.json是运行副本；本次入口统一不改知识数据。
- 页面行为、接口及历史验收记录见src/ui/README.md，项目当前进度见仓库根导航账本；历史交接文档不是当前启动指引。

## 可选维护工具

普通使用和构建只需要Node.js及npm，不需要Codex、WorkBuddy、Skill或本机共享目录。tools.sh仅为可选命令包装器，不包含个人电脑路径：`./tools.sh npm run dev`与标准npm命令等价。

设计检查和浏览器工具如需使用，应自行安装并加入PATH，或通过IMPECCABLE_BIN、PLAYWRIGHT_CLI指定可执行程序。它们缺失不影响图册运行。不提交node_modules或dist-ui；构建的大包提示不代表图册构建失败。
