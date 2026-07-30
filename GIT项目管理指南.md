# 🐙 Git & GitHub 项目管理指南

> 适用项目：**data-agent（掌柜问数）** | 远程仓库：`git@github.com:kkx414/data-agent.git`\
> 编写日期：2026-07-30

---

## 目录

1. [前置概念：Git 工作流三要素](#1-前置概念git-工作流三要素)
2. [日常开发循环（最常用）](#2-日常开发循环最常用)
3. [分支管理策略](#3-分支管理策略)
4. [提交规范（Commit Message）](#4-提交规范commit-message)
5. [多电脑同步工作流](#5-多电脑同步工作流)
6. [回滚与撤销操作](#6-回滚与撤销操作)
7. [.gitignore 配置](#7-gitignore-配置)
8. [标签与版本发布](#8-标签与版本发布)
9. [协作场景——Pull Request 流程](#9-协作场景pull-request-流程)
10. [常见问题速查](#10-常见问题速查)
11. [推荐 Git 配置](#11-推荐-git-配置)
12. [常用命令速查表](#12-常用命令速查表)

---

## 1. 前置概念：Git 工作流三要素

在你开始操作之前，先理解这三个"区域"：

```
┌──────────────┐    git add    ┌──────────────┐   git commit   ┌──────────────┐
│   工作目录     │  ──────────▶  │   暂存区      │  ──────────▶   │   本地仓库     │
│  (Working     │              │  (Staging)    │               │  (Local Repo) │
│   Directory)  │              │               │               │               │
└──────────────┘              └──────────────┘               └───────┬───────┘
                                                                     │
                                                            git push  │  git pull
                                                                     │
                                                              ┌──────▼──────┐
                                                              │   远程仓库    │
                                                              │  (GitHub)    │
                                                              └─────────────┘
```

| 概念 | 是什么 | 类比 |
|------|--------|------|
| **工作目录** | 你电脑上的项目文件夹，改代码的地方 | 你的办公桌 |
| **暂存区** | `git add` 后的临时区域，选择哪些文件要提交 | 把文件放进信封 |
| **本地仓库** | `git commit` 后保存在本地的版本历史 | 你自己的档案柜 |
| **远程仓库** | GitHub 上的仓库，用于备份和同步 | 公司的中央档案室 |

---

## 2. 日常开发循环（最常用）

每一天写代码的标准流程，记住这 **5 个步骤**：

### 步骤一：开始工作前——拉取最新代码

```bash
# 每次坐到电脑前，先执行这一步
git pull origin main
```

> **为什么？** 如果你在另一台电脑上推送过代码，pull 会把那些更新同步到当前电脑。如果没有更新，它会告诉你 `Already up to date.`，放心继续。

### 步骤二：写代码，然后检查状态

```bash
# 看看你改了哪些文件
git status
```

输出解读：

```
Changes not staged for commit:   ← 修改了已有文件，还没暂存
  modified:   app/core/log.py

Untracked files:                 ← 新建了文件，Git 还没跟踪
  app/services/new_service.py
```

### 步骤三：暂存改动

```bash
# 方式 A：逐个添加（推荐新手使用，精确控制）
git add app/core/log.py

# 方式 B：添加某个目录下所有改动
git add app/services/

# 方式 C：添加所有改动（最常用，但要确认 .gitignore 已配好）
git add .
```

> **重要习惯**：`git add .` 之前先用 `git status` 看一眼，确保不会误把日志文件、临时文件提交上去。

### 步骤四：提交到本地仓库

```bash
git commit -m "feat: 新增日志模块的请求耗时统计功能"
```

提交信息怎么写？→ 见 [第 4 节：提交规范](#4-提交规范commit-message)。

### 步骤五：推送到 GitHub

```bash
git push origin main
```

> **完成！** 现在你的代码已经安全地备份在 GitHub 上了，换一台电脑也能拉到。

---

## 3. 分支管理策略

### 推荐策略：轻量级 Feature Branch

对于个人项目，不需要过于复杂的 Git Flow。推荐这样：

```
main ─────────────────────────────●────●────●── （稳定版本）
       \                         /    /
        feature-xxx ───────────●────●──         （开发新功能）
                                 \
                                  fix-xxx ──●──  （修 bug）
```

### 创建分支开发新功能

```bash
# 1. 确保 main 是最新的
git checkout main
git pull origin main

# 2. 创建并切换到新分支
git checkout -b feature/智能问数优化

# 3. 在新分支上开发，正常 add + commit
git add .
git commit -m "feat: 优化自然语言转SQL的提示词模板"

# 4. 开发完成后，切回 main 合并
git checkout main
git merge feature/智能问数优化

# 5. 推送 main 到远端
git push origin main

# 6. （可选）删除已合并的本地分支
git branch -d feature/智能问数优化
```

### 分支命名建议

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能 | `feature/add-es-search` |
| `fix/` | 修 Bug | `fix/mysql-connection-leak` |
| `refactor/` | 重构 | `refactor/repository-pattern` |
| `docs/` | 文档 | `docs/api-readme` |
| `test/` | 测试 | `test/add-unit-tests` |

---

## 4. 提交规范（Commit Message）

### 格式

```
<type>: <简短描述>

[可选的详细说明]
```

### type 类型速查

| type | 含义 | 本项目的例子 |
|------|------|-------------|
| `feat` | 新功能 | `feat: 新增 Elasticsearch 向量检索接口` |
| `fix` | 修 Bug | `fix: 修复 MySQL 连接池耗尽导致的超时问题` |
| `refactor` | 重构（不改功能） | `refactor: 抽取 repository 公共基类` |
| `docs` | 文档 | `docs: 补充 API 接口文档` |
| `style` | 格式（空格、换行等） | `style: 统一代码缩进为 4 空格` |
| `chore` | 杂项/工具配置 | `chore: 添加 .gitignore 文件` |
| `test` | 测试 | `test: 添加 dw_mysql_repository 单元测试` |

### 好 vs 坏的提交信息

```bash
# ❌ 坏
git commit -m "改了东西"
git commit -m "update"
git commit -m "fix bug"

# ✅ 好
git commit -m "feat: 新增 column_info 实体的 Qdrant 向量同步功能"
git commit -m "fix: 修复 ES 客户端在空查询时抛出 KeyError 的问题"
git commit -m "docs: 新增 Git 项目管理指南"
```

---

## 5. 多电脑同步工作流

这是你最初使用 Git 的核心场景——在两台电脑之间切换开发。

### 电脑 A 上完成工作后

```bash
# 确保所有改动已提交
git status                     # 应该显示 "nothing to commit, working tree clean"

# 推送到 GitHub
git push origin main
```

### 换到电脑 B 时

```bash
# 1. 第一次使用：克隆整个项目（只需一次）
git clone git@github.com:kkx414/data-agent.git
cd data-agent

# 2. 之后每次：拉取最新代码
git pull origin main
```

### ⚠️ 换电脑前必须做的事

```
         电脑 A                           电脑 B
    ┌─────────────┐                 ┌─────────────┐
    │  写代码...    │                 │             │
    │  git add     │                 │             │
    │  git commit  │                 │             │
    │  git push  ──│──── GitHub ────▶│  git pull   │
    │  ✅ 完成！   │                 │  继续开发    │
    └─────────────┘                 └─────────────┘
```

> **铁律**：从电脑 A 离开之前，必须 `git push`。否则代码只存在电脑 A 的本地仓库里，电脑 B 拉不到。

---

## 6. 回滚与撤销操作

### 场景一：改了文件但还没 add（撤销工作区改动）

```bash
# 撤销某个文件的修改
git restore app/core/log.py

# 撤销所有修改
git restore .
```

### 场景二：已经 add 了但还没 commit（撤销暂存）

```bash
# 把文件从暂存区撤回工作区（保留你的修改）
git restore --staged app/core/log.py

# 撤回所有
git restore --staged .
```

### 场景三：已经 commit 了但还没 push（撤销提交）

```bash
# 撤销最近一次 commit，改动回到暂存区
git reset --soft HEAD~1

# 撤销最近一次 commit，改动回到工作区
git reset --mixed HEAD~1

# 彻底丢弃最近一次 commit 的所有改动（⚠️ 谨慎！）
git reset --hard HEAD~1
```

### 场景四：已经 push 到 GitHub 了

```bash
# 方法：创建一个反向提交来"撤销"
git revert HEAD                 # 撤销最近一次提交
git push origin main            # 推送这个撤销
```

### 场景五：紧急丢弃所有本地改动，回到远端最新状态

```bash
git fetch origin
git reset --hard origin/main
```

> 各场景的操作总结图：
>
> ```
> 还是工作区？         → git restore <file>
> 已经 add 了？        → git restore --staged <file>
> 已经 commit 了？     → git reset --soft HEAD~1
> 已经 push 了？       → git revert HEAD
> 完全搞乱了想重来？    → git reset --hard origin/main
> ```

---

## 7. .gitignore 配置

你的项目目前**没有 `.gitignore` 文件**，这意味着 `__pycache__`、`.idea`、日志文件等都会被 Git 跟踪。这会带来两个问题：

1. 每次 `git status` 都有一堆无关文件干扰视线
2. 换电脑后这些本地文件可能冲突

### 立即创建 .gitignore

在项目根目录创建 `.gitignore` 文件：

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyc
*.pyo
*.egg-info/
dist/
build/
.venv/
venv/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# 日志
logs/
*.log

# 环境变量（敏感信息）
.env
.env.local
.env.*.local

# Docker
docker-compose.override.yml

# 操作系统
.DS_Store
Thumbs.db
Desktop.ini

# 项目特定
.workbuddy/
```

### 如果有些文件已经被 Git 跟踪了

```bash
# 1. 先创建 .gitignore（用上面的内容）
# 2. 从 Git 追踪中移除（但不删除本地文件）
git rm --cached -r __pycache__/
git rm --cached -r .idea/
git rm --cached -r logs/

# 3. 提交这个清理
git add .gitignore
git commit -m "chore: 添加 .gitignore 并清理不应追踪的文件"
git push origin main
```

---

## 8. 标签与版本发布

当你的项目到了一个有意义的里程碑时，打一个标签（Tag）。

```bash
# 打一个轻量标签
git tag v1.0.0

# 打一个带说明的标签（推荐）
git tag -a v1.0.0 -m "v1.0.0: 完成核心问数流程，支持 MySQL + ES + Qdrant"

# 推送标签到 GitHub
git push origin v1.0.0

# 推送所有本地标签
git push origin --tags

# 查看所有标签
git tag -l

# 切回到某个标签版本查看代码
git checkout v1.0.0
```

### 推荐的版本号规则（语义化版本）

```
v<主版本号>.<次版本号>.<修订号>

主版本号：不兼容的 API 修改        → v2.0.0
次版本号：向下兼容的功能新增        → v1.1.0
修订号：  向下兼容的 Bug 修复       → v1.0.1
```

---

## 9. 协作场景——Pull Request 流程

当你需要别人 review 代码，或者想在自己的分支上实验而不影响 main：

### Step-by-step

```bash
# 1. 从最新的 main 创建功能分支
git checkout main
git pull origin main
git checkout -b feature/qdrant-hybrid-search

# 2. 开发并多次提交
git add app/repositories/qdrant/
git commit -m "feat: 新增 Qdrant 混合检索（向量+关键词）"

git add app/clients/qdrant_client_manager.py
git commit -m "feat: Qdrant 客户端增加稀疏向量支持"

# 3. 第一次推送分支到 GitHub
git push -u origin feature/qdrant-hybrid-search
#    ↑ -u 参数：建立本地分支与远程分支的追踪关系，之后只需 git push

# 4. 去 GitHub 网页上 → Pull Requests 标签 → New Pull Request
#    base: main  ← compare: feature/qdrant-hybrid-search
#    填写 PR 描述，点击 Create Pull Request

# 5. 代码审查通过后，在 GitHub 网页上点击 Merge

# 6. 回到本地，更新 main
git checkout main
git pull origin main

# 7. 删除已合并的功能分支
git branch -d feature/qdrant-hybrid-search
```

---

## 10. 常见问题速查

### Q1：`git push` 时报 `rejected` 错误

```
! [rejected]  main -> main (fetch first)
```

**原因**：GitHub 上的代码比你本地的更新（比如你在另一台电脑上推送过）。

**解决**：

```bash
git pull origin main        # 先拉取远程更新，合并
# 如果有冲突，解决冲突后：
git add .
git commit -m "merge: 合并远程更新"
git push origin main
```

### Q2：合并时出现冲突（CONFLICT）

Git 会标记冲突文件，打开后会看到：

```
<<<<<<< HEAD
你当前分支的代码
=======
远程分支的代码
>>>>>>> origin/main
```

**解决**：手动编辑文件，保留正确的代码，删除 `<<<<<<<`、`=======`、`>>>>>>>` 这些标记，然后：

```bash
git add <冲突文件>
git commit -m "merge: 解决合并冲突"
git push origin main
```

### Q3：不小心在 main 上直接开发了，想挪到新分支

```bash
# 你的改动还没 commit 的情况下
git stash                    # 暂存当前改动
git checkout -b feature/xxx  # 创建并切换到新分支
git stash pop                # 恢复改动到新分支
```

```bash
# 已经 commit 了
git checkout -b feature/xxx  # 从当前状态创建新分支（改动会带过去）
git checkout main            # 切回 main
git reset --hard HEAD~3      # main 回退 3 个提交（改成你实际的提交数）
```

### Q4：想查看某次提交改了哪些文件

```bash
git show <commit-hash>       # 查看某次提交的详细信息
git log --oneline            # 列出简洁的提交历史
git log --oneline -10        # 只看最近 10 条
```

### Q5：`git status` 里看到一堆不想要的 `__pycache__` 文件

这说明你还没配置 `.gitignore`，请参考 [第 7 节](#7-gitignore-配置)。

---

## 11. 推荐 Git 配置

在终端中执行以下命令，让你的 Git 更好用：

```bash
# 设置用户名和邮箱（GitHub 会以此识别提交者）
git config --global user.name "kkx414"
git config --global user.email "你的邮箱@example.com"

# 设置默认分支名为 main（GitHub 新标准）
git config --global init.defaultBranch main

# 启用彩色输出（更好看）
git config --global color.ui auto

# 设置别名（少打字）
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.lg "log --oneline --graph --all"

# 之后可以用 git st 代替 git status，git lg 查看漂亮的提交图
```

---

## 12. 常用命令速查表

| 命令 | 作用 |
|------|------|
| `git status` | 查看当前改动了哪些文件 |
| `git add <file>` | 把文件加入暂存区 |
| `git add .` | 把当前目录所有改动加入暂存区 |
| `git commit -m "msg"` | 提交到本地仓库 |
| `git push origin main` | 推送到 GitHub |
| `git pull origin main` | 从 GitHub 拉取最新代码 |
| `git log --oneline` | 查看提交历史（简洁版） |
| `git diff` | 查看具体改了什么（还未暂存的） |
| `git diff --staged` | 查看已暂存的改动 |
| `git branch` | 查看本地分支列表 |
| `git branch -a` | 查看所有分支（包括远程） |
| `git checkout -b <name>` | 创建并切换到新分支 |
| `git checkout <branch>` | 切换到已有分支 |
| `git merge <branch>` | 把指定分支合并到当前分支 |
| `git stash` | 暂时保存当前改动，清理工作区 |
| `git stash pop` | 恢复最近一次 stash 的改动 |
| `git remote -v` | 查看远程仓库地址 |
| `git clone <url>` | 克隆远程仓库到本地 |

---

## 📋 你的快速上手清单

按顺序完成以下操作，你就掌握了个人项目 Git 管理的基础：

- [ ] **1.** 配置 Git 用户名和邮箱（[第 11 节](#11-推荐-git-配置)）
- [ ] **2.** 创建 `.gitignore` 文件（[第 7 节](#7-gitignore-配置)）
- [ ] **3.** 清理已被 Git 跟踪的无用文件（`__pycache__`、`.idea` 等）
- [ ] **4.** 提交并推送 `.gitignore`
- [ ] **5.** 从另一台电脑 `git clone` 项目，验证同步流程
- [ ] **6.** 下次写新功能时，尝试用分支开发（[第 3 节](#3-分支管理策略)）
- [ ] **7.** 项目达到里程碑时打一个版本标签（[第 8 节](#8-标签与版本发布)）

---

> 💡 **记住这句话**：\
> **add → commit → push** 是你的肌肉记忆。\
> **status → pull** 是打开电脑的第一件事。\
> 养成这两个习惯，Git 就不会给你带来麻烦，只会帮你省时间。
