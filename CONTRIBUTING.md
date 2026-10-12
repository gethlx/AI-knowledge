# 协作规范（CONTRIBUTING）

本仓库由两方协作维护：

- **晶晶**（仓库所有者）：在本地 Mac 上工作，使用 Codex。
- **老邪**（AI 助手）：在独立的云端电脑上工作，使用 Codex CLI / Claude Code CLI。

两台机器文件互不可见，**GitHub 是唯一真源**；本地和云端各自保留工作副本，只通过 Git 同步。

## 1. 同步
- **交任务给老邪之前，先推送本地改动**：`git add <文件>` → `git commit -m "说明"` → `git push`。
- **至少每天推送一次**；未完成的工作（WIP）可以推到自己的分支。
- **开工前先同步最新 main**：`git fetch origin && git rebase origin/main`（或 `git pull --rebase`）。

## 2. 分支
- **一个任务一个分支**：晶晶用 `jingjing/xxx`，老邪用 `laoxie/xxx`。
- `main` 只接受 PR 合并，**PR 由晶晶审核后合并**；老邪不直接推 main、不自行合并。
- **不要两人同时改同一个分支**；一个任务只交给一个人。

## 3. 提交
- 小步、频繁提交，提交信息写清楚做了什么（例：`docs: 补充犬声研究条目`）。
- 建议让 Codex 在每个任务结束时自动 commit 并 push 到当前任务分支。

## 4. 需求与文档
- 任务需求、设计说明、待办写进仓库（`docs/`）或 GitHub Issue，不只留在聊天里——老邪看不到你本地的文件。
- 先读 `00-项目导航账本.md` 和 `PROJECT-BRIEF.md`；过程记录写入导航账本。
- 不提交可重建产物（`node_modules/`、`dist/`、`dist-ui/`）和 `.workbuddy/`。

## 5. 密钥
- **绝不提交密钥**：`.env`、API key、token、账号配置等。`.gitignore` 已忽略 `.env`。
- 需要时单独提供，老邪存放在云端环境变量中。

## 6. 冲突处理
1. `git fetch origin`，然后 `git rebase origin/main`。
2. 打开冲突文件，保留正确内容，删除 `<<<<<<<`/`=======`/`>>>>>>>` 标记。
3. `git add <文件>` → `git rebase --continue`；必要时 `git push --force-with-lease` **只推自己的任务分支**。
4. 拿不准就停下，在 PR 或 Issue 里说明，交给晶晶决定。**禁止强推 main。**
