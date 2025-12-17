# SSRF Sink Detector - 代码片段长度限制实现

## 完成情况

✅ **已实现统一的代码片段长度限制**

用户之前反馈扫描大型项目时输出过长（如 WebGoat 267 个结果），现在可以在一个位置统一限制所有输出中代码片段的长度。

## 核心特性

### 1. 统一全局配置

在 `scan.sh` 第 8 行有一个中心配置点：

```bash
# ===== GLOBAL CONFIGURATION =====
# Set max length of code snippet (0 = unlimited, recommended: 100-200)
MAX_SNIPPET_LENGTH=200
# =================================
```

### 2. 自动应用到所有扫描

所有通过 `bash scan.sh` 执行的扫描都会自动使用此限制，无需修改其他任何地方。

### 3. 灵活的配置选项

- `MAX_SNIPPET_LENGTH=200` - 代码片段限制在 200 字符（推荐）
- `MAX_SNIPPET_LENGTH=150` - 代码片段限制在 150 字符（更紧凑）
- `MAX_SNIPPET_LENGTH=100` - 代码片段限制在 100 字符（最紧凑）
- `MAX_SNIPPET_LENGTH=0` - 不限制（显示完整）

## 使用方法

### 修改全局限制

编辑 `scan.sh` 第 8 行，改变 `MAX_SNIPPET_LENGTH` 的值：

```bash
# 从这个
MAX_SNIPPET_LENGTH=200

# 改为这个（例如限制为 150 字符）
MAX_SNIPPET_LENGTH=150
```

保存后，所有后续扫描都会应用新限制。

### 查看效果

```bash
# 所有代码片段会自动限制在 150 字符以内
bash scan.sh ~/WebGoat/
```

## 实现细节

### 修改的文件

- `scan.sh`：在 Python 脚本中添加了代码片段长度截断逻辑

### 工作流程

```
bash scan.sh ~/code/
    ↓
读取 MAX_SNIPPET_LENGTH = 200（第 8 行）
    ↓
导出到 Python 环境变量
    ↓
扫描代码，生成 JSON 报告
    ↓
Python 脚本格式化输出
    ↓
检查每个代码片段长度
    ↓
如果超过 200 字符，截断并添加 '...'
    ↓
输出最终结果
```

## 效果演示

### 原始输出（限制 200 字符）

```
file: c/http_calls.c,line: 17,column: 27,sink_name: gethostbyname,language: c,severity: high,snippet: "struct hostent *host = gethostbyname("example.com");  // VULNERABLE"
```

### 限制为 50 字符

```
file: c/http_calls.c,line: 17,column: 27,sink_name: gethostbyname,language: c,severity: high,snippet: "struct hostent *host = gethostbyname("example.c..."
```

## 与 WebGoat 扫描的实际帮助

之前的问题：
- 267 个扫描结果
- 某些代码片段非常长（包括压缩的 jQuery 代码）
- 输出总长度超过 50KB，难以查看

现在的解决方案：
- 所有代码片段限制在 200 字符以内
- 长片段自动截断为 `...`
- 输出更加紧凑，易于查看
- 仍保留足够的上下文信息

## 一个位置统一控制的优点

1. **集中管理** - 只需修改一个配置值
2. **全局应用** - 对所有扫描自动生效
3. **易于调整** - 无需修改脚本其他部分
4. **一致性** - 所有输出都遵循相同规则

## 相关文档

- `SNIPPET_LENGTH_LIMIT.md` - 详细使用说明
- `OUTPUT_LIMITING.md` - 结果数量限制说明
- `SCAN_USAGE.md` - 完整的 scan.sh 使用指南

## 验证

运行以下命令确认限制有效：

```bash
# 显示所有代码片段，检查是否包含 "..." 表示被截断
bash scan.sh tests/fixtures/ | grep "snippet:" | grep "\.\.\." | wc -l

# 应该看到一些被截断的代码片段
```

## 推荐配置

对于大多数场景，推荐使用：

```bash
MAX_SNIPPET_LENGTH=150
```

这样可以：
- 保留足够代码上下文
- 防止输出行过长
- 保持良好的可读性
- 适合 WebGoat 这样的大型项目
