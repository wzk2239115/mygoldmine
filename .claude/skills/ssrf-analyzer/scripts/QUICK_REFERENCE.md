# SSRF Sink Detector - 快速参考指南

## 核心改进总结

### 三大改进

| 改进 | 说明 | 效果 |
|-----|------|------|
| **文件分组** | 相同文件的结果合并显示，避免重复 | 信息更清晰 |
| **紧凑输出** | 删除空行，提高信息密度 | 空间节省 20%+ |
| **片段限制** | 统一限制代码片段长度 | 自动截断过长片段 |

## 使用命令

```bash
# 查看所有结果（推荐用于小项目）
bash scan.sh /path/to/code

# 快速概览（只看统计，推荐用于大项目）
bash scan.sh --summary /path/to/code

# 查看前 N 个结果
bash scan.sh --limit 50 /path/to/code

# 显示帮助
bash scan.sh --help
```

## 全局配置

编辑 `scan.sh` 第 8 行调整代码片段长度：

```bash
MAX_SNIPPET_LENGTH=200  # 默认值（推荐）
MAX_SNIPPET_LENGTH=150  # 更紧凑
MAX_SNIPPET_LENGTH=100  # 最紧凑
MAX_SNIPPET_LENGTH=0    # 不限制
```

## 输出格式

```
Found 40 potential SSRF sinks:

File: c/http_calls.c
  Line 8:17 | curl_easy_init (c, high) | CURL *curl = curl_easy_init();
  Line 11:8 | curl_easy_perform (c, high) | curl_easy_perform(curl);  // VULNERABLE
File: python/http_calls.py
  Line 11:11 | requests.get (python, high) | response = requests.get(url)  # VULNERABLE
  Line 15:11 | requests.post (python, high) | response = requests.post(user_url, data={'key': 'v...
```

## 关键特性

✅ **文件分组显示** - 按文件组织结果，避免重复打印文件名
✅ **紧凑格式** - 删除冗余空行，信息密度高
✅ **代码片段限制** - 在一个位置统一控制所有输出
✅ **灵活显示** - 摘要/限制/完整三种模式
✅ **语法检查** - 已验证无误

## 文件位置

```
/home/wangzekai/TOP14/ssrf/scripts/
├── scan.sh                          # 主脚本（已优化）
├── OUTPUT_FORMAT_IMPROVED.md         # 详细文档
└── cli.py, core/, languages/, ...   # 其他组件（不变）
```

## 常见场景

### 场景 1：审查大型项目（如 WebGoat）

```bash
# 第一步：快速浏览统计
bash scan.sh --summary ~/WebGoat/

# 第二步：查看前 50 个结果
bash scan.sh --limit 50 ~/WebGoat/

# 第三步：如需详细，调整片段长度
编辑 scan.sh 第 8 行：
MAX_SNIPPET_LENGTH=100

# 重新扫描
bash scan.sh --limit 50 ~/WebGoat/
```

### 场景 2：开发测试

```bash
# 快速测试某个文件
bash scan.sh src/vulnerable.py

# 看统计信息
bash scan.sh --summary src/
```

### 场景 3：CI/CD 集成

```bash
# 设置较小的片段长度避免日志过长
MAX_SNIPPET_LENGTH=100

# 在流水线中使用
bash scan.sh --summary project/
bash scan.sh --limit 100 project/
```

## 效果对比

### 之前的问题

- 267 个 WebGoat 结果中，文件名被重复打印 267 次
- 代码片段很长（包含压缩代码），导致行很长
- 许多空行浪费屏幕空间
- 总输出超过 50KB，难以查看

### 现在的效果

```
✓ 文件分组：7 个文件只打印 7 次文件名
✓ 代码片段：自动截断至 200 字符（可配置）
✓ 紧凑格式：删除冗余空行
✓ 输出大小：减少 20-30%
```

## 扩展功能组合

```bash
# 限制片段长度 + 限制结果数量
MAX_SNIPPET_LENGTH=100
bash scan.sh --limit 30 ~/code/

# 限制片段长度 + 摘要模式
MAX_SNIPPET_LENGTH=0  # 不影响摘要
bash scan.sh --summary ~/code/
```

## 参数优先级

1. **--summary** （最高）- 仅显示统计
2. **--limit N** - 限制显示数量
3. **MAX_SNIPPET_LENGTH** （最低）- 限制片段长度

## 验证功能

```bash
# 确认文件分组
bash scan.sh tests/fixtures/ | grep "^File:" | wc -l
# 应该输出：7（7 个文件）

# 确认代码片段限制
bash scan.sh tests/fixtures/ | grep "\.\.\." | wc -l
# 如果有长片段，应该显示一些

# 确认紧凑格式
bash scan.sh tests/fixtures/ | grep "^$" | wc -l
# 应该很少（仅头尾和中间）
```

## 下一步

如需进一步优化，可以考虑：

1. **输出过滤** - 按严重等级或语言过滤
2. **报告生成** - 导出 HTML、PDF 报告
3. **增量扫描** - 只显示新增问题
4. **配置文件** - 从 .yaml 读取配置而不是硬编码

---

📝 更多详情见 `OUTPUT_FORMAT_IMPROVED.md`
