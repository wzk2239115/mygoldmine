---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Generate CHANGELOG from git history using Conventional Commits
argument-hint: [version] | --unreleased | --full
---


# 生成变更日志

> 基于 Git 提交历史生成 CHANGELOG

## 任务

分析 Git 提交历史，生成或更新 CHANGELOG.md 文件，支持 Conventional Commits 规范、自动分类、链接生成等功能。

## 分析范围

### 1. 提交历史分析

- 获取指定范围内的 Git 提交
- 解析提交消息（Conventional Commits 格式）
- 提取提交类型、scope、描述等信息
- 识别破坏性变更（BREAKING CHANGE）

### 2. 版本管理

- 自动检测最新版本号（从 tag 或 CHANGELOG）
- 语义化版本号递增（major/minor/patch）
- 版本号格式验证
- 支持自定义版本号

### 3. 内容生成

- 按类型分类提交（feat/fix/perf/refactor 等）
- 按 scope 或模块分组
- 生成提交链接（GitHub/GitLab）
- 格式化输出（Markdown）

## 执行步骤

### 0. 环境检查

在执行前检查：

```bash
# 检查是否为 Git 仓库
git rev-parse --git-dir > /dev/null 2>&1 || { echo "错误: 当前目录不是 Git 仓库"; exit 1; }

# 检查 CHANGELOG.md 文件状态
if [ -f "CHANGELOG.md" ]; then
  echo "发现现有 CHANGELOG.md"
  # 检查文件是否可写
  [ -w "CHANGELOG.md" ] || { echo "错误: CHANGELOG.md 不可写"; exit 1; }
fi

# 检查 Git 命令可用性
command -v git > /dev/null || { echo "错误: 未安装 Git"; exit 1; }
```

### 1. 分析提交历史

#### 1.1 获取版本范围

```bash
# 获取最近的 tag
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)

# 如果没有 tag，从初始提交开始
if [ -z "$LATEST_TAG" ]; then
  FROM_REF=""
  echo "首次发布：从初始提交开始"
else
  FROM_REF="$LATEST_TAG"
  echo "从 tag $LATEST_TAG 开始"
fi

# 获取提交范围
git log ${FROM_REF}..HEAD --oneline --no-merges
```

#### 1.2 边界情况处理

**首次发布（无 tag）**：
- 从初始提交（`$(git rev-list --max-parents=0 HEAD)`）开始
- 或从指定日期开始
- 版本号默认为 `1.0.0`

**空提交列表**：
- 检查是否有有效提交
- 如果没有，提示用户并退出

**无符合规范的提交**：
- 统计不符合 Conventional Commits 的提交
- 可选择是否包含这些提交（使用 `--include-invalid`）

**多个 tag 处理**：
- 使用 `--tags` 获取所有 tag
- 按时间排序，选择最新的
- 支持指定起始 tag（`--from <tag>`）

### 2. 过滤和分类提交

#### 2.1 提交过滤

```bash
# 默认过滤规则
git log ${FROM_REF}..HEAD \
  --no-merges \                    # 排除 merge 提交
  --grep="^revert" --invert-grep \ # 排除 revert 提交
  --grep="^WIP:" --invert-grep \   # 排除 WIP 提交
  --grep="^\[skip ci\]" --invert-grep \ # 排除 CI 跳过提交
  --format="%H|%s|%b"              # 输出格式：hash|subject|body
```

**过滤规则**：
- **默认排除**：merge 提交、revert 提交
- **可选排除**：WIP 提交、`[skip ci]` 提交、特定前缀
- **自定义过滤**：使用 `--ignore <pattern>` 指定正则表达式

#### 2.2 解析提交消息

按照 Conventional Commits 规范解析：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型映射**：

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

**BREAKING CHANGE 检测**：
- 在 footer 中包含 `BREAKING CHANGE:` 或 `BREAKING CHANGES:`
- 或在类型后包含 `!`（如 `feat!:`）

#### 2.3 分组功能

**按 scope 分组**：
```markdown
### ✨ Features

#### Auth
- feat(auth): 添加 JWT 认证 ([abc123](链接))

#### API
- feat(api): 新增用户接口 ([def456](链接))
```

**按模块分组**：
- 根据文件路径推断模块
- 或根据 scope 映射到模块

**分组选项**：
- `--group-by scope`: 按 scope 分组
- `--group-by module`: 按模块分组
- `--group-by none`: 不分组（默认）

### 3. 生成链接

#### 3.1 自动检测仓库 URL

```bash
# 从 Git remote 获取仓库 URL
REPO_URL=$(git remote get-url origin 2>/dev/null)

# 转换为 HTTPS URL（如果是 SSH）
if [[ $REPO_URL == git@* ]]; then
  REPO_URL=$(echo $REPO_URL | sed 's/git@\(.*\):\(.*\)\.git/https:\/\/\1\/\2/')
fi

# 提取仓库信息（GitHub/GitLab）
# GitHub: https://github.com/owner/repo
# GitLab: https://gitlab.com/owner/repo
```

#### 3.2 链接格式

**Commit 链接**：
- GitHub: `https://github.com/owner/repo/commit/{hash}`
- GitLab: `https://gitlab.com/owner/repo/-/commit/{hash}`

**比较链接**：
- GitHub: `https://github.com/owner/repo/compare/{from}...{to}`
- GitLab: `https://gitlab.com/owner/repo/-/compare/{from}...{to}`

**自定义链接模板**：
- 使用 `--repo-url <url>` 指定仓库 URL
- 支持自定义链接模板（配置文件）

### 4. 生成 CHANGELOG 条目

#### 4.1 版本号处理

**自动递增逻辑**：
1. 从最新 tag 读取版本号（如 `v1.2.3`）
2. 根据提交类型决定递增：
   - 包含 `BREAKING CHANGE` → major (1.2.3 → 2.0.0)
   - 包含 `feat` → minor (1.2.3 → 1.3.0)
   - 其他 → patch (1.2.3 → 1.2.4)
3. 如果无 tag，从 CHANGELOG.md 读取最新版本
4. 如果都没有，默认为 `1.0.0`

**版本号验证**：
- 必须符合语义化版本规范（major.minor.patch）
- 支持预发布版本（1.0.0-alpha.1）
- 支持构建元数据（1.0.0+20230101）

#### 4.2 生成格式

```markdown
## [版本号] - YYYY-MM-DD

### ✨ Features
- feat(scope): 描述 ([commit](链接))

### 🐛 Bug Fixes
- fix(scope): 描述 ([commit](链接))

### ♻️ Refactoring
- refactor(scope): 描述 ([commit](链接))

### 💥 Breaking Changes
- feat!: 描述 ([commit](链接))
  - 详细说明变更内容
```

### 5. 更新 CHANGELOG.md

#### 5.1 文件操作

- **文件不存在**：创建新文件，使用模板
- **文件存在**：在 `[Unreleased]` 部分后插入新版本
- **保留历史**：保留所有历史版本记录

#### 5.2 插入位置

```markdown
# Changelog

## [Unreleased]

## [新版本] - YYYY-MM-DD  ← 插入这里
...

## [旧版本] - YYYY-MM-DD
...
```

### 6. 生成统计信息

输出统计摘要：

```markdown
## 统计摘要

- **版本号**: 1.2.3
- **提交总数**: 25
- **时间范围**: 2025-01-01 至 2025-01-15
- **变更类型分布**:
  - Features: 8 (32%)
  - Bug Fixes: 12 (48%)
  - Refactoring: 3 (12%)
  - Documentation: 2 (8%)
```

### 7. 验证和输出

- 验证生成的 CHANGELOG 格式
- 显示生成的变更日志内容
- 提示下一步操作（如：更新版本号、打 tag、提交更改）

## 参数

### 基本参数

- `--version <ver>`: 指定版本号（默认自动递增）
  - 示例: `--version 2.0.0`
- `--from <tag>`: 从指定 tag 开始（默认最新 tag）
  - 示例: `--from v1.0.0`
- `--to <ref>`: 到指定 ref 结束（默认 HEAD）
  - 示例: `--to main`
- `--dry-run`: 仅预览，不写入文件
- `--output <file>`: 输出文件路径（默认 CHANGELOG.md）
  - 示例: `--output docs/CHANGELOG.md`

### 过滤参数

- `--ignore <pattern>`: 忽略匹配的提交（正则表达式）
  - 示例: `--ignore "^(WIP|skip)"`
- `--include-merge`: 包含 merge 提交（默认排除）
- `--include-invalid`: 包含不符合规范的提交

### 分组参数

- `--group-by <field>`: 分组方式
  - `scope`: 按 scope 分组
  - `module`: 按模块分组
  - `none`: 不分组（默认）

### 链接参数

- `--repo-url <url>`: 仓库 URL（用于生成链接）
  - 示例: `--repo-url https://github.com/owner/repo`
- `--no-links`: 不生成提交链接

### 配置参数

- `--config <file>`: 配置文件路径
  - 示例: `--config .changelogrc.yaml`

## 配置选项

### 配置文件格式

```yaml
# .changelogrc.yaml
version:
  # 版本号递增策略
  strategy: auto  # auto, manual
  # 默认版本号（无 tag 时）
  default: "1.0.0"

filter:
  # 排除的提交类型
  exclude_types: []
  # 排除的正则表达式
  exclude_patterns:
    - "^WIP:"
    - "^\\[skip ci\\]"
  # 包含 merge 提交
  include_merge: false

group:
  # 分组方式
  by: none  # scope, module, none
  # scope 到模块的映射
  scope_mapping:
    auth: Authentication
    api: API

links:
  # 仓库 URL（自动检测或手动指定）
  repo_url: ""
  # 链接模板
  commit_template: "https://github.com/{owner}/{repo}/commit/{hash}"
  compare_template: "https://github.com/{owner}/{repo}/compare/{from}...{to}"

output:
  # 输出文件
  file: "CHANGELOG.md"
  # 日期格式
  date_format: "YYYY-MM-DD"
  # 是否包含统计信息
  include_stats: true
```

## 示例

### 基本使用

```bash
# 生成下一版本的 changelog
/changelog

# 指定版本号
/changelog --version 2.0.0

# 预览不写入
/changelog --dry-run

# 从指定 tag 开始
/changelog --from v1.0.0
```

### 首次发布

```bash
# 首次发布，从初始提交开始
/changelog --version 1.0.0 --from ""

# 或从指定日期开始
/changelog --version 1.0.0 --from $(git log --reverse --format="%H" | head -1)
```

### 过滤和分组

```bash
# 忽略 WIP 提交
/changelog --ignore "^WIP:"

# 按 scope 分组
/changelog --group-by scope

# 包含 merge 提交
/changelog --include-merge
```

### 自定义输出

```bash
# 输出到指定文件
/changelog --output docs/CHANGELOG.md

# 指定仓库 URL
/changelog --repo-url https://github.com/owner/repo

# 不生成链接
/changelog --no-links
```

### CI/CD 集成

```yaml
# .github/workflows/release.yml
- name: Generate Changelog
  run: |
    /changelog --version ${{ github.ref_name }} --repo-url ${{ github.repositoryUrl }}
    git add CHANGELOG.md
    git commit -m "chore: update changelog for ${{ github.ref_name }}"
```

## CHANGELOG.md 模板

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2025-01-01

### ✨ Features
- Initial release
```

## 错误处理

### 常见错误及处理

**Git 命令执行失败**：
- 检查是否为 Git 仓库
- 检查 Git 是否安装
- 检查网络连接（如果涉及远程仓库）

**文件写入权限问题**：
- 检查文件权限
- 检查目录是否存在
- 检查磁盘空间

**版本号格式错误**：
- 验证版本号格式（语义化版本）
- 提供格式建议
- 允许用户修正

**无有效提交**：
- 提示用户检查提交范围
- 建议使用 `--include-invalid` 包含所有提交
- 或手动指定版本号

**配置文件解析错误**：
- 验证 YAML 格式
- 提供错误位置和修复建议
- 回退到默认配置

## 常见问题

### 如何生成首次发布的 CHANGELOG？

```bash
/changelog --version 1.0.0 --from ""
```

### 如何包含不符合规范的提交？

使用 `--include-invalid` 参数，这些提交会被归类到 "Other" 类别。

### 如何自定义提交类型映射？

在配置文件中添加 `type_mapping` 配置：

```yaml
type_mapping:
  enhancement: feat
  bug: fix
```

### 如何生成特定时间范围的 CHANGELOG？

```bash
# 从指定日期开始
/changelog --from $(git log --until="2025-01-01" --format="%H" | tail -1)
```

### 如何与语义化版本工具集成？

```bash
# 使用 standard-version
npx standard-version

# 或使用 semantic-release
npx semantic-release
```

这些工具会自动调用 changelog 生成功能。

## 最佳实践

### 提交消息规范

遵循 Conventional Commits 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 版本发布流程

1. 开发完成后，运行 `/changelog --dry-run` 预览
2. 确认无误后，运行 `/changelog` 生成
3. 检查生成的 CHANGELOG.md
4. 提交更改：`git add CHANGELOG.md && git commit -m "chore: update changelog"`
5. 打 tag：`git tag -a v1.2.3 -m "Release v1.2.3"`
6. 推送：`git push && git push --tags`

### 定期更新

建议在以下时机更新 CHANGELOG：
- 每次发布新版本前
- 重大功能完成后
- 修复重要 bug 后

------

**最后更新**: 2025-11-30 16:10:35
**维护者**: Documentation Team
**版本**: 1.0.0
