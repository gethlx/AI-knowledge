# 图谱浏览器开发环境

本目录是Codex / WorkBuddy共用的本地工程环境。atlas.html已实现完整197卡、197节点/1562边及真实三维浏览；50号交互与52号视觉已获用户确认。index.html只保留3节点安装测试。当前等待WorkBuddy工程核对、补缺及手机验收，不代表正式工程已验收。正式G_v2及卡文保持只读。

当前任务入口：../../03_交付物/53-已确认浏览器交接与WorkBuddy后续任务.md；页面行为与接口：src/ui/README.md。

## 已锁定工具

- Node v24.14.0 / npm 11.9.0（复用本机现有运行时，未全局重装）。
- Vite 8.3.2：本地开发及构建。
- 3d-force-graph 1.80.1：真实Three.js/WebGL三维关系图；Three 0.186.1由锁文件固定。
- @phosphor-icons/web 2.1.2：真实图标库。本安装测试用regular字体；正式界面按选定视觉稿选择匹配图标与加载方式。
- Playwright CLI 0.1.22：复用现有Skill脚本；同一脚本也已挂到WorkBuddy。

## 双方使用

在本目录执行 `./tools.sh npm run dev`；默认本地地址为 `http://127.0.0.1:41839/`，端口占用时明确报错。产品专用构建：`./tools.sh npm exec vite build -- --config src/ui/vite.config.js`，输出dist-ui；`npm run build`仅构建原安装测试。`./tools.sh npm ci --ignore-scripts`可按锁文件重装当前依赖。包装器固定本机Node真实路径，避免两端PATH不同。当前安装和构建无需运行依赖包生命周期脚本。不要把node_modules或dist提交到仓库。

`./tools.sh impeccable context --target index.html` 读取当前目标背景；`./tools.sh impeccable detect --json index.html` 手动检测。相对目标以本目录为基准，也可以传绝对路径。这个包装器使用共享池固定引擎，关闭该入口的更新检查和选型遥测；没有安装自动编辑hook。Impeccable检测结果不能替代截图对照和真实交互验收。

`./tools.sh browser --help`使用现有Playwright CLI。两端挂载的Skill目录需刷新或新开对话才会被客户端索引；当前已核对两端文件及命令入口可达，不宣称替WorkBuddy执行过智能体任务。

新Skill真身：`~/AI-Tools/shared/skills/img-to-frontend/`、`~/AI-Tools/shared/skills/impeccable/`。两端入口均为软链，不要用各端安装器覆盖软链；升级应在独立目录审查后替换共享池，不能直接使用upstream update覆盖正在读取的Skill。

当前任务与验收入口见53号；38号为安装来源及早期分工。核验记录在 `核验记录/`。

## 当前边界

安装测试无外部模型/API调用，未新生成视觉稿。运行依赖的已知漏洞查询为0，不代表完整安全审计。构建有三维JS包体超过500kB的提示；正式产品由WorkBuddy检查按需加载和手机实机表现，当前完整图浏览器预览已通过既有核验，手机实机性能仍未验证。

## 2026-10-02 HTML还原入口

打开http://127.0.0.1:41839/atlas.html。源码、视觉尺寸与WorkBuddy接口见src/ui/README.md；当前视觉52号、交接53号，45号为早期还原记录。专用构建：./tools.sh npm exec vite build -- --config src/ui/vite.config.js，输出dist-ui。原安装测试保留不覆盖；当前已为完整197/1562预览，仍需53号工程验收。
