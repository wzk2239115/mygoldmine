---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Scan and organize TODO/FIXME markers in codebase
argument-hint: [directory] [--type <marker>] [--output <format>]
---


# TODO 扫描

> 扫描并整理代码中的 TODO、FIXME 等标记

## 任务

扫描代码库中的待办事项标记，生成整理报告，帮助团队跟踪和管理技术债务。

## 扫描标记

| 标记 | 优先级 | 说明 |
|------|--------|------|
| `FIXME` | 🔴 高 | 需要立即修复的问题 |
| `TODO` | 🟡 中 | 待完成的功能或改进 |
| `HACK` | 🟡 中 | 临时解决方案，需要重构 |
| `XXX` | 🟡 中 | 需要注意的问题代码 |
| `NOTE` | 🟢 低 | 说明性注释 |
| `OPTIMIZE` | 🟢 低 | 可优化的代码 |
| `DEPRECATED` | 🟡 中 | 已废弃，待移除 |

## 执行步骤

### 0. 环境检查

在执行前检查：

```bash
# 检查当前目录是否为有效项目目录
[ -d "." ] || { echo "错误: 当前目录无效"; exit 1; }

# 检查必要的工具
command -v grep > /dev/null || { echo "错误: 未安装 grep"; exit 1; }
```

### 1. 扫描代码

#### 1.1 基本扫描命令

```bash
# 扫描所有常见标记（Python、JavaScript、TypeScript）
grep -rn "TODO\|FIXME\|HACK\|XXX\|NOTE\|OPTIMIZE\|DEPRECATED" \
  --include="*.py" \
  --include="*.js" \
  --include="*.ts" \
  --include="*.jsx" \
  --include="*.tsx" \
  --include="*.java" \
  --include="*.go" \
  --include="*.rs" \
  --include="*.cpp" \
  --include="*.c" \
  --include="*.h" \
  --exclude-dir={node_modules,venv,.git,dist,build,__pycache__,.next,.cache} \
  .
```

#### 1.2 排除目录

```bash
# 排除常见的不需要扫描的目录
grep -rn "TODO\|FIXME\|HACK\|XXX" \
  --exclude-dir={node_modules,venv,.git,dist,build,__pycache__,.next,.cache,coverage,.nyc_output} \
  --exclude-dir={vendor,bin,obj,.vs,.idea,.vscode} \
  .
```

#### 1.3 使用配置文件

如果存在 `.todo-scan.yaml` 配置文件，读取配置：

```bash
# 检查配置文件是否存在
if [ -f ".todo-scan.yaml" ]; then
  echo "使用配置文件: .todo-scan.yaml"
  # 解析 YAML 配置并应用
fi
```

### 2. 解析结果

#### 2.1 提取信息

从扫描结果中提取以下信息：

- **文件路径**: 相对路径或绝对路径
- **行号**: 标记所在的行号
- **标记类型**: FIXME、TODO、HACK 等
- **内容描述**: 标记后的描述文本
- **作者**: 如果格式为 `TODO(author): ...`
- **日期**: 如果格式为 `TODO: ... - 2025-01-01`
- **优先级**: 如果格式为 `FIXME: ... - P0`

#### 2.2 解析正则表达式

```bash
# 匹配格式: TODO(author): 描述 - 日期
# 示例: TODO(zhangsan): 添加缓存支持 - 2025-02-01
PATTERN='(TODO|FIXME|HACK|XXX|NOTE|OPTIMIZE|DEPRECATED)(\([^)]+\))?:\s*(.+?)(\s*-\s*(\d{4}-\d{2}-\d{2}|P[0-9]+))?'
```

#### 2.3 数据结构

每个待办项包含：

```json
{
  "file": "src/api/handler.py",
  "line": 45,
  "type": "FIXME",
  "content": "这里有内存泄漏",
  "author": "lisi",
  "date": "2025-01-15",
  "priority": "P0"
}
```

### 3. 生成报告

#### 3.1 Markdown 格式

```markdown
## TODO 扫描报告

**扫描时间**: 2025-01-15 14:30:00
**扫描范围**: src/, tests/
**总计**: 25 项

### 📊 统计摘要

| 类型 | 数量 | 占比 |
|------|------|------|
| FIXME | 5 | 20% |
| TODO | 15 | 60% |
| HACK | 3 | 12% |
| XXX | 1 | 4% |
| 其他 | 1 | 4% |

### 🔴 FIXME (需立即处理)

#### 1. 内存泄漏问题
- **文件**: `src/api/handler.py:45`
- **内容**: FIXME(lisi): 这里有内存泄漏 - P0
- **建议**: 检查资源释放，使用上下文管理器

#### 2. 空指针异常
- **文件**: `src/utils/validator.py:78`
- **内容**: FIXME: 修复空指针异常
- **建议**: 添加空值检查

### 🟡 TODO (待完成)

#### 1. 添加缓存支持
- **文件**: `src/utils/helper.py:123`
- **内容**: TODO(zhangsan): 添加缓存支持 - 2025-02-01
- **建议**: 使用 Redis 实现缓存层

### 🟡 HACK (需重构)

#### 1. 临时绕过验证
- **文件**: `src/auth/login.py:78`
- **内容**: HACK: 临时绕过验证
- **建议**: 实现完整的验证逻辑

### 📈 趋势分析

与上次扫描对比：
- 新增: +3
- 解决: -5
- 净变化: -2 ✅
```

#### 3.2 JSON 格式

```json
{
  "scan_time": "2025-01-15T14:30:00Z",
  "scan_range": ["src/", "tests/"],
  "total": 25,
  "summary": {
    "FIXME": {"count": 5, "percentage": 20},
    "TODO": {"count": 15, "percentage": 60},
    "HACK": {"count": 3, "percentage": 12}
  },
  "items": [
    {
      "file": "src/api/handler.py",
      "line": 45,
      "type": "FIXME",
      "content": "这里有内存泄漏",
      "author": "lisi",
      "priority": "P0"
    }
  ],
  "trend": {
    "new": 3,
    "resolved": 5,
    "net_change": -2
  }
}
```

#### 3.3 CSV 格式

```csv
文件,行号,类型,内容,作者,日期,优先级
src/api/handler.py,45,FIXME,这里有内存泄漏,lisi,,P0
src/utils/helper.py,123,TODO,添加缓存支持,zhangsan,2025-02-01,
src/auth/login.py,78,HACK,临时绕过验证,,,
```

### 4. 保存报告

```bash
# 保存到默认位置
if [ "$SAVE" = "true" ]; then
  OUTPUT_FILE="${OUTPUT_FILE:-docs/TODO.md}"
  mkdir -p "$(dirname "$OUTPUT_FILE")"
  echo "$REPORT" > "$OUTPUT_FILE"
  echo "报告已保存到: $OUTPUT_FILE"
fi
```

## 参数

### 基本参数

- `--type <marker>`: 仅扫描指定类型的标记
  - 示例: `--type FIXME` 或 `--type TODO`
  - 支持多个: `--type FIXME --type TODO`
- `--dir <path>`: 扫描指定目录（默认当前目录）
  - 示例: `--dir src/` 或 `--dir tests/`
- `--output <format>`: 指定输出格式
  - 可选值: `markdown`（默认）、`json`、`csv`
  - 示例: `--output json`
- `--save`: 保存报告到文件
  - 默认保存到: `docs/TODO.md`
  - 可通过配置文件指定路径

### 过滤参数

- `--exclude <pattern>`: 排除匹配的文件或目录（正则表达式）
  - 示例: `--exclude ".*test.*"`
- `--include <pattern>`: 仅包含匹配的文件（正则表达式）
  - 示例: `--include ".*\.py$"`
- `--min-priority <level>`: 仅显示指定优先级及以上的项
  - 示例: `--min-priority P1`（仅显示 P0 和 P1）

### 输出参数

- `--output-file <path>`: 指定输出文件路径
  - 示例: `--output-file reports/todo-scan.md`
- `--no-summary`: 不显示统计摘要
- `--no-trend`: 不显示趋势分析
- `--group-by <field>`: 按字段分组显示
  - 可选值: `type`（默认）、`file`、`author`、`priority`

### 配置参数

- `--config <file>`: 指定配置文件路径
  - 示例: `--config .todo-scan.yaml`
- `--dry-run`: 仅预览，不保存文件

## 配置选项

### 配置文件格式

```yaml
# .todo-scan.yaml

# 包含的文件模式
include:
  - "src/**/*.py"
  - "src/**/*.js"
  - "src/**/*.ts"
  - "tests/**/*.py"

# 排除的目录
exclude:
  - "node_modules"
  - "venv"
  - "__pycache__"
  - ".git"
  - "dist"
  - "build"
  - ".next"
  - ".cache"

# 要扫描的标记类型
markers:
  - FIXME
  - TODO
  - HACK
  - XXX
  - NOTE
  - OPTIMIZE
  - DEPRECATED

# 输出配置
output:
  # 输出格式: markdown, json, csv
  format: markdown
  # 输出文件路径
  file: docs/TODO.md
  # 是否包含统计摘要
  include_summary: true
  # 是否包含趋势分析
  include_trend: true
  # 分组方式: type, file, author, priority, none
  group_by: type

# 过滤配置
filter:
  # 最小优先级（P0-P9，数字越小优先级越高）
  min_priority: null
  # 排除的文件模式（正则表达式）
  exclude_patterns: []
  # 包含的文件模式（正则表达式）
  include_patterns: []
```

### 配置文件使用

配置文件会自动从以下位置查找（按优先级）：

1. 命令行指定的路径（`--config`）
2. `.todo-scan.yaml`（项目根目录）
3. `.todo-scan.yml`（项目根目录）
4. `~/.todo-scan.yaml`（用户主目录）

## 示例

### 基本使用

```bash
# 扫描整个项目
/todo-scan

# 扫描指定目录
/todo-scan --dir src/

# 仅扫描 FIXME
/todo-scan --type FIXME

# 输出 JSON 格式
/todo-scan --output json

# 保存到指定文件
/todo-scan --save --output-file reports/todo-report.md
```

### 高级使用

```bash
# 扫描并保存为 JSON
/todo-scan --output json --save --output-file todo-report.json

# 仅显示高优先级项
/todo-scan --min-priority P1

# 按文件分组
/todo-scan --group-by file

# 排除测试文件
/todo-scan --exclude ".*test.*"

# 仅扫描 Python 文件
/todo-scan --include ".*\.py$"

# 使用自定义配置
/todo-scan --config .custom-todo-config.yaml

# 预览不保存
/todo-scan --dry-run
```

### 组合使用

```bash
# 扫描 src/ 目录中的 FIXME，输出 JSON 并保存
/todo-scan --dir src/ --type FIXME --output json --save

# 扫描所有标记，按作者分组，排除测试文件
/todo-scan --group-by author --exclude ".*test.*"
```

## 错误处理

### 常见错误及处理

**扫描命令执行失败**：
- 检查当前目录是否有效
- 检查 grep 命令是否安装
- 检查文件权限

**配置文件解析错误**：
- 验证 YAML 格式是否正确
- 检查配置文件路径是否正确
- 提供错误位置和修复建议
- 回退到默认配置

**无匹配结果**：
- 检查扫描范围是否正确
- 检查排除规则是否过于严格
- 提示用户调整过滤条件

**文件写入权限问题**：
- 检查输出目录是否存在
- 检查文件权限
- 检查磁盘空间

**标记格式解析失败**：
- 记录原始文本
- 尝试部分解析
- 在报告中标记为"未解析"

## 常见问题

### 如何扫描特定类型的标记？

```bash
/todo-scan --type FIXME
```

或扫描多种类型：

```bash
/todo-scan --type FIXME --type TODO
```

### 如何排除特定目录？

在配置文件中设置：

```yaml
exclude:
  - "node_modules"
  - "custom_dir"
```

或使用命令行：

```bash
# 需要在配置文件中配置排除规则
/todo-scan --config .todo-scan.yaml
```

### 如何生成不同格式的报告？

```bash
# Markdown 格式（默认）
/todo-scan --output markdown

# JSON 格式
/todo-scan --output json

# CSV 格式
/todo-scan --output csv
```

### 如何与 CI/CD 集成？

```yaml
# .github/workflows/todo-scan.yml
- name: Scan TODOs
  run: |
    /todo-scan --output json --save --output-file todo-report.json
    # 可以设置阈值，如果超过则失败
    if [ $(jq '.summary.FIXME.count' todo-report.json) -gt 10 ]; then
      echo "FIXME 数量超过阈值"
      exit 1
    fi
```

### 如何跟踪趋势？

每次扫描后保存报告，下次扫描时会自动对比：

```bash
# 首次扫描
/todo-scan --save

# 后续扫描会自动对比
/todo-scan --save
```

### 如何自定义标记格式？

在代码中使用规范格式：

```python
# TODO(author): 描述 - 预计完成日期
# TODO(zhangsan): 添加分页支持 - 2025-02-01

# FIXME(author): 描述 - 优先级
# FIXME(lisi): 修复空指针异常 - P0
```

## 最佳实践

### 规范的 TODO 格式

推荐使用以下格式，便于解析和跟踪：

```python
# TODO(author): 描述 - 预计完成日期
# TODO(zhangsan): 添加分页支持 - 2025-02-01

# FIXME(author): 描述 - 优先级
# FIXME(lisi): 修复空指针异常 - P0

# HACK(author): 描述 - 预计重构日期
# HACK(wangwu): 临时绕过验证 - 2025-03-01
```

### 定期清理

建议的清理频率：

- **每周扫描一次**: 跟踪技术债务变化
- **Sprint 结束前**: 清理高优先级的 FIXME
- **代码审查时**: 检查新增的 TODO，确保格式规范
- **发布前**: 审查所有待办项，决定是否延期

### 优先级管理

- **P0**: 必须立即修复（阻塞性问题）
- **P1**: 高优先级（影响功能或性能）
- **P2**: 中优先级（改进建议）
- **P3**: 低优先级（可选优化）

### 团队协作

- 在 PR 描述中说明新增的 TODO
- 定期在团队会议中讨论技术债务
- 将 TODO 清理纳入 Sprint 计划
- 使用 issue 跟踪重要的 TODO

------

**最后更新**: 2025-11-30 16:10:35
**维护者**: Documentation Team
**版本**: 1.0.0
