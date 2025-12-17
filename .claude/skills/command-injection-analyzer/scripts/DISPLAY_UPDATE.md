# ✅ Command Injection Sink Detector - 直接显示结果

## 问题已解决

你想要的用法现在完全实现了：

```bash
bash scan.sh ~/WebGoat/
```

输出将**直接显示**所有检测到的sink，而不是写入文件。

## 使用方法

### 最简单的用法 - 直接显示
```bash
# 扫描目录并直接显示结果
bash scan.sh ~/WebGoat/

# 扫描指定语言
bash scan.sh ~/WebGoat/ --languages php,python

# 冗长模式
bash scan.sh ~/WebGoat/ --verbose
```

### 保存到文件
```bash
# 保存为JSON
bash scan.sh ~/WebGoat/ --output findings.json

# 保存为HTML
bash scan.sh ~/WebGoat/ --output audit.html

# 保存为CSV
bash scan.sh ~/WebGoat/ --output findings.csv
```

### 其他选项
```bash
# 扫描单个语言
bash scan.sh . --languages php

# 多个语言
bash scan.sh . --languages php,python,java,javascript,go,rust

# 显示所有帮助
bash scan.sh --help
```

## 输出示例

```
Report written to: /tmp/tmp.xxxx.json
Total sinks detected: 6


================================================================================
Command Injection Sinks Found: 6
================================================================================

[1] path/to/file.php:6:1
    Function: system
    Category: direct_execution
    Parameters: "cat /tmp/" . $filename

[2] path/to/file.php:10:1
    Function: exec
    Category: direct_execution
    Parameters: $command, $output

...

================================================================================
Summary:
  Total Sinks: 6
  By Category:
    - direct_execution: 5
    - process_control: 1
  By File (Top 10):
    - path/to/file.php: 6
================================================================================
```

## 技术细节

### 为什么之前不工作

1. `mktemp` 创建的文件没有扩展名（如 `/tmp/tmp.xxx`）
2. cli.py 根据文件扩展名判断输出格式
3. 没有扩展名的文件无法匹配 `.json` 检查
4. 导致文件没被写入

### 解决方案

- 使用 `mktemp --suffix=.json` 创建带有 `.json` 扩展名的临时文件
- cli.py 现在能正确识别并写入文件
- `display_results.py` 读取并格式化输出

## 文件说明

### 已更新
- `scan.sh` - 修复了临时文件处理
- `cli.py` - 添加了错误处理

### 新增
- `display_results.py` - 将JSON结果格式化为人类可读的输出

## 现在可以使用！

直接扫描你的代码：
```bash
bash ~/TOP14/command_injection/scripts/scan.sh ~/WebGoat/
```
