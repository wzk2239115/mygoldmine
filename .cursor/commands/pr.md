
# 创建 Pull Request

> 生成 PR 描述并创建 Pull Request

## 任务

为当前分支创建 Pull Request，自动生成规范的 PR 描述，支持自动检测、模板化、多平台集成等功能。

## 使用方式

### Cursor
在 Cursor 中通过命令面板（`Cmd+Shift+P` / `Ctrl+Shift+P`）或快捷键调用此命令。

### Cursor
在 Cursor 中通过斜杠命令 `/pr` 或参数提示调用此命令。

## 执行步骤

### 0. 前置检查

在执行前进行环境检查：

```bash
# 检查是否为 Git 仓库
git rev-parse --git-dir > /dev/null 2>&1 || { echo "错误: 当前目录不是 Git 仓库"; exit 1; }

# 检查当前分支
CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
  echo "错误: 无法获取当前分支，可能处于 detached HEAD 状态"
  exit 1
fi

# 检查是否有未提交的更改
if [ -n "$(git status --porcelain)" ]; then
  echo "警告: 检测到未提交的更改"
  echo "建议: 先提交或暂存更改后再创建 PR"
  # 询问用户是否继续
fi

# 检查分支是否已推送
if ! git rev-parse --verify origin/$CURRENT_BRANCH > /dev/null 2>&1; then
  echo "提示: 当前分支尚未推送到远程，将自动推送"
fi

# 检查 GitHub CLI 是否安装（可选）
if ! command -v gh > /dev/null; then
  echo "提示: 未安装 GitHub CLI，将使用其他方式创建 PR"
fi
```

### 1. 分析当前状态

#### 1.1 检查分支信息

```bash
# 获取当前分支
CURRENT_BRANCH=$(git branch --show-current)
echo "当前分支: $CURRENT_BRANCH"

# 检测默认 base 分支（main/master/develop）
if git show-ref --verify --quiet refs/heads/main; then
  DEFAULT_BASE="main"
elif git show-ref --verify --quiet refs/heads/master; then
  DEFAULT_BASE="master"
elif git show-ref --verify --quiet refs/heads/develop; then
  DEFAULT_BASE="develop"
else
  DEFAULT_BASE="main"
fi
echo "默认目标分支: $DEFAULT_BASE"
```

#### 1.2 分析提交历史

```bash
# 查看与目标分支的差异
git log ${DEFAULT_BASE}..HEAD --oneline --no-merges

# 查看变更文件统计
git diff ${DEFAULT_BASE} --stat

# 查看变更文件列表
git diff ${DEFAULT_BASE} --name-only
```

#### 1.3 检查冲突

```bash
# 检查是否有合并冲突风险
git fetch origin ${DEFAULT_BASE}
if git merge-tree $(git merge-base HEAD origin/${DEFAULT_BASE}) HEAD origin/${DEFAULT_BASE} | grep -q "^+<<<<<<<"; then
  echo "警告: 检测到潜在的合并冲突"
fi
```

### 2. 收集信息

#### 2.1 分析提交消息

- 解析所有 commit 消息（遵循 Conventional Commits 规范）
- 识别变更类型（feat/fix/refactor/docs 等）
- 提取 scope 和描述信息
- 检测 BREAKING CHANGE

#### 2.2 识别变更类型

按照 Conventional Commits 规范分类：

| 类型 | 说明 | 显示标题 | 图标 |
|------|------|----------|------|
| feat | 新功能 | Features | ✨ |
| fix | Bug 修复 | Bug Fixes | 🐛 |
| perf | 性能优化 | Performance | ⚡ |
| refactor | 重构 | Refactoring | ♻️ |
| docs | 文档 | Documentation | 📚 |
| test | 测试 | Tests | ✅ |
| chore | 杂项 | Chores | 🔧 |
| style | 代码格式 | Style | 💎 |
| ci | CI 配置 | CI | 👷 |
| build | 构建系统 | Build | 📦 |
| breaking | 破坏性变更 | Breaking Changes | 💥 |

#### 2.3 自动关联 Issue

```bash
# 从提交消息中提取 issue 编号
git log ${DEFAULT_BASE}..HEAD --oneline | grep -oE '#[0-9]+' | sort -u

# 从分支名中提取 issue 编号
echo $CURRENT_BRANCH | grep -oE '[0-9]+'
```

#### 2.4 检测 Breaking Changes

- 检查提交消息中是否包含 `BREAKING CHANGE:` 或 `BREAKING CHANGES:`
- 检查类型后是否包含 `!`（如 `feat!:`）
- 分析代码变更是否涉及 API 变更

### 3. 生成 PR 描述

使用以下模板生成 PR 描述：

```markdown
## 概述

[一句话描述这个 PR 做了什么，说明变更的目的和影响]

## 变更类型

- [ ] ✨ 新功能 (feat)
- [ ] 🐛 Bug 修复 (fix)
- [ ] ⚡ 性能优化 (perf)
- [ ] ♻️ 重构 (refactor)
- [ ] 📚 文档 (docs)
- [ ] ✅ 测试 (test)
- [ ] 🔧 杂项 (chore)
- [ ] 💎 代码格式 (style)
- [ ] 👷 CI 配置 (ci)
- [ ] 📦 构建系统 (build)
- [ ] 💥 破坏性变更 (breaking)

## 变更内容

### 新增
- [列出新增的功能、文件、模块等]

### 修改
- [列出修改的功能、文件、模块等]

### 删除
- [列出删除的功能、文件、模块等]

## 详细说明

[详细描述变更内容，包括：
- 变更的背景和原因
- 实现方式和技术细节
- 影响范围和潜在风险
]

## 测试

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 端到端测试通过
- [ ] 手动测试通过
- [ ] 性能测试通过（如适用）

### 测试场景
[列出主要的测试场景和测试结果]

## 截图/演示（如适用）

[UI 变更请提供截图或 GIF]
[功能演示请提供录屏或链接]

## Breaking Changes

- [ ] 此 PR 包含破坏性变更

### 变更说明
[如果包含破坏性变更，详细说明：
- 哪些 API 或行为发生了变化
- 迁移步骤和注意事项
- 兼容性影响
]

### 迁移指南
```bash
# 迁移步骤示例
# 1. 更新依赖
# 2. 修改配置
# 3. 更新代码
```

## 性能影响

- [ ] 无性能影响
- [ ] 性能提升
- [ ] 性能下降（已优化）

### 性能指标
[如适用，提供性能测试数据：
- 响应时间变化
- 吞吐量变化
- 资源使用变化
]

## 回滚计划

[如果此 PR 需要回滚，说明回滚步骤和注意事项]

## 关联 Issue

Closes #
Fixes #
Resolves #
Related to #

## CI/CD 检查

- [ ] CI 构建通过
- [ ] 代码覆盖率满足要求
- [ ] 安全检查通过
- [ ] 依赖安全检查通过
- [ ] 性能测试通过（如适用）

## 检查清单

- [ ] 代码符合项目规范
- [ ] 已更新相关文档
- [ ] 已添加必要的测试
- [ ] 所有测试通过
- [ ] 已进行代码审查（self-review）
- [ ] 已更新 CHANGELOG.md（如适用）
- [ ] 已更新 API 文档（如适用）
- [ ] 已考虑向后兼容性
- [ ] 已考虑安全性影响
- [ ] 已考虑性能影响
```

### 4. 生成 PR 标题

根据提交历史自动生成 PR 标题：

```bash
# 从第一个提交提取标题
FIRST_COMMIT=$(git log ${DEFAULT_BASE}..HEAD --oneline --no-merges | tail -1)
PR_TITLE=$(echo $FIRST_COMMIT | sed 's/^[a-f0-9]* //')

# 或从多个提交生成综合标题
# 提取主要变更类型
MAIN_TYPE=$(git log ${DEFAULT_BASE}..HEAD --format="%s" | head -1 | grep -oE '^[^:]+')
PR_TITLE="${MAIN_TYPE}: [综合描述]"
```

**标题规范**：
- 遵循 Conventional Commits 格式
- 简洁明了（建议 72 字符以内）
- 使用中文，清晰描述变更
- 包含类型前缀（如 `feat:`、`fix:`）

### 5. 创建 PR

#### 5.1 推送分支

```bash
# 推送当前分支到远程
CURRENT_BRANCH=$(git branch --show-current)
git push -u origin $CURRENT_BRANCH

# 如果推送失败，提示用户
if [ $? -ne 0 ]; then
  echo "错误: 分支推送失败，请检查网络连接和权限"
  exit 1
fi
```

#### 5.2 使用 GitHub CLI 创建 PR

```bash
# 基本创建
gh pr create \
  --title "$PR_TITLE" \
  --body "$PR_DESCRIPTION" \
  --base "$DEFAULT_BASE"

# 带参数创建
gh pr create \
  --title "$PR_TITLE" \
  --body "$PR_DESCRIPTION" \
  --base "$DEFAULT_BASE" \
  --draft \
  --label "enhancement" \
  --assignee "@me" \
  --reviewer "username"
```

#### 5.3 手动创建 PR（无 GitHub CLI）

如果未安装 GitHub CLI，提供手动创建步骤：

1. 打开 GitHub 仓库页面
2. 点击 "New Pull Request"
3. 选择 base 分支和当前分支
4. 复制生成的 PR 描述
5. 填写标题和描述
6. 提交 PR

### 6. 输出结果

创建成功后输出：

- **PR 链接**：`https://github.com/owner/repo/pull/123`
- **PR 编号**：`#123`
- **建议的 reviewer**：根据变更文件自动推荐
- **需要注意的事项**：
  - 合并冲突检查
  - CI 状态监控
  - Review 反馈处理

## 参数

### 基本参数

- `--base <branch>`: 指定目标分支（默认自动检测 main/master/develop）
  - 示例: `--base develop`
- `--draft`: 创建草稿 PR
  - 示例: `--draft`
- `--no-push`: 不自动推送分支（分支必须已推送）
  - 示例: `--no-push`

### 自动模式

- `--auto`: 自动模式（自动检测和填充所有信息）
  - 自动检测 base 分支
  - 自动生成标题和描述
  - 自动关联 issue
  - 示例: `--auto`

### 模板参数

- `--template <name>`: 使用指定模板
  - 示例: `--template feature`（使用 feature 模板）
  - 可用模板: `feature`, `bugfix`, `hotfix`, `docs`, `refactor`

### 标签和分配

- `--label <label>`: 添加标签（可多次使用）
  - 示例: `--label enhancement --label frontend`
- `--assignee <user>`: 指定负责人
  - 示例: `--assignee @me` 或 `--assignee username`
- `--reviewer <user>`: 指定 reviewer（可多次使用）
  - 示例: `--reviewer username1 --reviewer username2`
- `--milestone <name>`: 关联里程碑
  - 示例: `--milestone "v2.0.0"`

### 预览模式

- `--preview`: 仅预览，不创建 PR
  - 显示生成的标题和描述
  - 不执行推送和创建操作
  - 示例: `--preview`

### 其他参数

- `--title <title>`: 手动指定 PR 标题
  - 示例: `--title "feat: 添加新功能"`
- `--body <text>`: 手动指定 PR 描述（或从文件读取）
  - 示例: `--body "PR 描述内容"` 或 `--body @pr-description.md`

## 示例

### 基本使用

```bash
# 创建 PR 到默认分支（main）
/pr

# 创建草稿 PR
/pr --draft

# 创建 PR 到 develop 分支
/pr --base develop
```

### 自动模式

```bash
# 自动检测和填充所有信息
/pr --auto

# 自动模式 + 草稿
/pr --auto --draft
```

### 标签和分配

```bash
# 添加标签和指定 reviewer
/pr --label enhancement --label frontend --reviewer alice --reviewer bob

# 指定负责人和里程碑
/pr --assignee @me --milestone "v2.0.0"
```

### 模板使用

```bash
# 使用 feature 模板
/pr --template feature

# 使用 bugfix 模板
/pr --template bugfix
```

### 组合使用

```bash
# 创建草稿 PR，添加标签，指定 reviewer
/pr --draft --label "needs-review" --reviewer alice --base develop

# 预览模式，查看生成的描述
/pr --preview --auto
```

### 手动指定

```bash
# 手动指定标题和描述
/pr --title "feat: 添加用户认证" --body "详细描述..."

# 从文件读取描述
/pr --body @pr-description.md
```

## 错误处理

### 常见错误及处理

**Git 仓库不存在**：
- 检查当前目录是否为 Git 仓库
- 提示用户初始化仓库或切换到正确目录

**分支不存在**：
- 检查分支名称是否正确
- 提示用户创建分支或切换到已存在的分支

**无变更内容**：
- 检查当前分支与 base 分支是否有差异
- 提示用户确认分支是否正确

**合并冲突**：
- 检测潜在的合并冲突
- 提示用户先解决冲突再创建 PR
- 提供解决冲突的步骤

**GitHub CLI 未安装**：
- 提供安装指南
- 提供手动创建 PR 的步骤
- 或使用其他方式（如 API）

**推送失败**：
- 检查网络连接
- 检查权限设置
- 检查远程仓库配置

**PR 创建失败**：
- 检查 GitHub 权限
- 检查仓库设置
- 查看详细错误信息

## 常见问题

### 如何更新已创建的 PR？

```bash
# 1. 在本地分支继续提交
git add .
git commit -m "fix: 修复问题"
git push

# 2. PR 会自动更新，无需重新创建
```

### 如何关闭 PR？

```bash
# 使用 GitHub CLI
gh pr close <PR_NUMBER>

# 或在 GitHub 网页上点击 "Close pull request"
```

### 如何处理 Review 反馈？

1. 在本地分支修改代码
2. 提交更改：`git add . && git commit -m "fix: 根据 review 反馈修改"`
3. 推送更新：`git push`
4. PR 会自动更新，reviewer 会收到通知

### 如何解决合并冲突？

```bash
# 1. 更新本地 base 分支
git checkout main
git pull origin main

# 2. 切换回功能分支
git checkout feature-branch

# 3. 合并 base 分支
git merge main

# 4. 解决冲突后提交
git add .
git commit -m "fix: 解决合并冲突"
git push
```

### 如何添加更多信息到 PR 描述？

```bash
# 使用 --body 参数从文件读取
/pr --body @pr-description.md

# 或创建 PR 后在 GitHub 网页上编辑
```

### 如何查看 PR 状态？

```bash
# 使用 GitHub CLI
gh pr view <PR_NUMBER>

# 或查看 PR 列表
gh pr list
```

## 最佳实践

### PR 大小建议

- **小 PR**（推荐）：< 400 行变更，1-3 个文件
- **中等 PR**：400-1000 行变更，4-10 个文件
- **大 PR**（不推荐）：> 1000 行变更，> 10 个文件

**建议**：
- 将大功能拆分为多个小 PR
- 每个 PR 只解决一个问题
- 保持 PR 的原子性和可审查性

### 提交信息规范

遵循 Conventional Commits 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**示例**：
```bash
feat(auth): 添加 JWT 认证功能

实现基于 JWT 的用户认证，包括：
- Token 生成和验证
- 刷新 Token 机制
- 过期处理

Closes #123
```

### Review 流程建议

1. **Self-Review**：创建 PR 前自己先审查一遍
2. **代码质量**：确保代码符合项目规范
3. **测试覆盖**：确保有足够的测试
4. **文档更新**：确保相关文档已更新
5. **CI 通过**：确保所有 CI 检查通过

### 合并策略说明

**Merge Commit**（默认）：
- 保留完整的提交历史
- 适合需要保留详细历史的项目

**Squash and Merge**：
- 将多个提交合并为一个
- 保持主分支历史简洁

**Rebase and Merge**：
- 将提交重新应用到主分支
- 保持线性历史

### PR 标题规范

- 遵循 Conventional Commits 格式
- 简洁明了（72 字符以内）
- 使用中文，清晰描述变更
- 包含类型前缀

**示例**：
- ✅ `feat: 添加用户登录功能`
- ✅ `fix: 修复登录页面验证码不显示的问题`
- ❌ `更新代码`
- ❌ `fix bug`

## 平台集成

### GitHub 集成

**GitHub CLI 安装**：

```bash
# macOS
brew install gh

# Linux
# 参考 https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Windows
# 参考 https://github.com/cli/cli/blob/trunk/docs/install_windows.md
```

**GitHub CLI 认证**：

```bash
# 登录 GitHub
gh auth login

# 检查认证状态
gh auth status
```

**GitHub API 使用**：

如果未安装 GitHub CLI，可以使用 GitHub API：

```bash
# 使用 curl 创建 PR
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/owner/repo/pulls \
  -d '{
    "title": "PR 标题",
    "body": "PR 描述",
    "head": "feature-branch",
    "base": "main"
  }'
```

### GitLab 集成

**GitLab CLI 安装**：

```bash
# 使用 glab
brew install glab

# 或使用 pip
pip install glab
```

**GitLab CLI 使用**：

```bash
# 创建 Merge Request
glab mr create \
  --title "PR 标题" \
  --description "PR 描述" \
  --target-branch main
```

### 其他平台

- **Bitbucket**：使用 Bitbucket API 或 Web UI
- **Azure DevOps**：使用 Azure CLI 或 Web UI
- **Gitea**：使用 Gitea API 或 Web UI

## 相关命令

### Git 命令

- `git status`: 查看 Git 状态
- `git log`: 查看提交历史
- `git diff`: 查看具体变更内容
- `git push`: 推送分支到远程
- `git fetch`: 获取远程更新

### Cursor/Claude 命令

- `/commit`: 创建 Git 提交（遵循 Conventional Commits）
- `/changelog`: 生成变更日志
- `/code-review`: 代码审查
- `/code-refactor`: 代码重构

### GitHub CLI 命令

- `gh pr create`: 创建 PR
- `gh pr view`: 查看 PR
- `gh pr list`: 列出 PR
- `gh pr close`: 关闭 PR
- `gh pr merge`: 合并 PR

## 注意事项

### 提交前检查

- ✅ 确保代码已通过必要的检查（lint、测试等）
- ✅ 提交信息应清晰描述变更内容
- ✅ 遵循项目的分支管理策略
- ✅ 对于复杂变更，建议在 body 中详细说明

### 安全提醒

- ⚠️ **不要提交包含敏感信息的文件**（`.env`、`credentials.json`、密钥文件等）
- ⚠️ 检查 `.gitignore` 确保敏感文件已被排除
- ⚠️ 提交前检查是否有硬编码的密码、API 密钥等
- ⚠️ 确保 PR 描述不包含敏感信息

### 最佳实践

- 每个 PR 只包含一个逻辑变更（原子性提交）
- PR 描述使用中文，清晰描述变更
- 复杂功能分多个 PR，便于代码审查和回滚
- 及时响应 review 反馈
- 保持 PR 大小适中，便于审查


------

**最后更新**: 2025-11-30 16:10:35
**维护者**: Documentation Team
**版本**: 1.0.0
