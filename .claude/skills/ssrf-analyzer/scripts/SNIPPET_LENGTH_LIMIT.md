# 代码片段长度统一限制配置

## 概述

SSRF Sink Detector 现在提供了**统一的全局代码片段长度限制**，可以在一个位置统一控制所有扫描输出中代码片段的长度。

## 全局配置点

在 `scan.sh` 文件的顶部有一个配置区域：

```bash
# ===== GLOBAL CONFIGURATION =====
# Set max length of code snippet (0 = unlimited, recommended: 100-200)
MAX_SNIPPET_LENGTH=200
# =================================
```

### 配置说明

- `MAX_SNIPPET_LENGTH=200` - 代码片段最多显示 200 个字符，超出部分显示为 `...`
- `MAX_SNIPPET_LENGTH=100` - 代码片段最多显示 100 个字符
- `MAX_SNIPPET_LENGTH=0` - 不限制（显示完整代码片段）

## 使用示例

### 示例 1：限制所有扫描的代码片段为 100 字符

编辑 `scan.sh` 第 8 行：

```bash
MAX_SNIPPET_LENGTH=100
```

输出变为（长于 100 字符的会被截断）：

```
file: src/main.js,line: 45,snippet: "const response = await fetch(userProvidedUrl); if (response....."
                                                                    ↑
                                                    超过 100 字符被截断
```

### 示例 2：显示完整代码片段（不限制）

编辑 `scan.sh` 第 8 行：

```bash
MAX_SNIPPET_LENGTH=0
```

所有代码片段都完整显示，无论多长。

### 示例 3：推荐的平衡设置

编辑 `scan.sh` 第 8 行：

```bash
MAX_SNIPPET_LENGTH=150
```

这样可以：
- 保留足够的代码上下文（150 字符通常包含整条语句）
- 防止输出行过长
- 保持可读性

## 实际效果对比

### 原始输出（MAX_SNIPPET_LENGTH=0）

```
file: test.py,line: 20,snippet: "response = requests.get(user_url, verify=False, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})  # VULNERABLE"
```

长度: 138 字符

### 限制为 80 字符（MAX_SNIPPET_LENGTH=80）

```
file: test.py,line: 20,snippet: "response = requests.get(user_url, verify=False, timeo..."
```

长度: 85 字符（包括 `...`）

### 限制为 150 字符（MAX_SNIPPET_LENGTH=150）

```
file: test.py,line: 20,snippet: "response = requests.get(user_url, verify=False, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})  # VULNE..."
```

长度: 153 字符（包括 `...`）

## 一个位置统一控制

所有的扫描都会自动使用这个配置，无需修改其他地方：

```
scan.sh
  ↓
第 8 行：MAX_SNIPPET_LENGTH=200
  ↓
所有扫描自动应用此限制
  ↓
输出中的所有代码片段都不超过 200 字符
```

## 推荐设置

| 使用场景 | 设置值 | 优点 |
|--------|------|------|
| CI/CD 日志输出 | 100-150 | 保持日志简洁，避免过长 |
| 开发调试 | 200-300 | 显示足够上下文 |
| 完整分析 | 0 | 显示完整代码，便于深度分析 |
| 安全审计 | 150-200 | 平衡可读性和完整性 |

## 工作流程

```
用户运行 bash scan.sh ~/code/
    ↓
读取 MAX_SNIPPET_LENGTH 配置（第 8 行）
    ↓
扫描代码找到匹配
    ↓
生成 JSON 报告（含完整代码片段）
    ↓
Python 脚本格式化输出
    ↓
检查代码片段长度
    ↓
如果超过 MAX_SNIPPET_LENGTH，则截断并添加 '...'
    ↓
输出最终结果
```

## 修改方法

只需编辑 `scan.sh` 文件的第 8 行：

**修改前：**
```bash
MAX_SNIPPET_LENGTH=200
```

**修改为：**
```bash
MAX_SNIPPET_LENGTH=150
```

**保存后，所有后续扫描都会应用新的限制。**

## 验证配置

运行扫描后，查看输出中代码片段的长度：

```bash
bash scan.sh tests/fixtures/ | grep "snippet:" | head -5
```

检查是否有 `...` 表示被截断。

## 与其他选项的关系

- `--summary` 不显示代码片段，不受此限制影响
- `--limit N` 限制结果数量，与此配置独立
- `-0` 表示不限制，设置 `MAX_SNIPPET_LENGTH=0`
