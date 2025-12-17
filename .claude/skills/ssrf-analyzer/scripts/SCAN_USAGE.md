# SSRF Sink Detector - Scan Script Usage

## 概述

`scan.sh` 是一个 bash 包装脚本，用于调用 SSRF Sink Detector CLI 工具进行代码扫描。

## 文件位置

```
/home/wangzekai/TOP14/ssrf/scripts/scan.sh
```

## 使用方法

### 基本用法

```bash
bash scripts/scan.sh <target_directory>
```

或者从任何位置：

```bash
/home/wangzekai/TOP14/ssrf/scripts/scan.sh <target_directory>
```

### 参数

- `<target_directory>` - 要扫描的目录或文件路径（可选，默认为当前目录）

## 使用示例

### 示例 1：扫描 WebGoat 项目

```bash
bash scripts/scan.sh ~/WebGoat/
```

输出：
```
======================================
SSRF Sink Detector
======================================
Scanning directory: /home/user/WebGoat
======================================
Found X potential SSRF sinks:

file: src/main/java/...,line: 42,column: 10,sink_name: URL.openConnection,language: java,severity: high,snippet: "conn = url.openConnection();"
...

Scan completed!
```

### 示例 2：扫描单个文件

```bash
bash scripts/scan.sh ~/WebGoat/src/main/java/TestFile.java
```

### 示例 3：扫描 PHP 项目

```bash
bash scripts/scan.sh /var/www/html/myapp/
```

### 示例 4：扫描 Python 项目

```bash
bash scripts/scan.sh ~/python_project/
```

### 示例 5：扫描 JavaScript 项目

```bash
bash scripts/scan.sh ~/node_app/
```

## 脚本工作流程

1. **解析参数**: 获取目标目录路径
2. **验证依赖**: 检查 cli.py 是否存在
3. **创建临时文件**: 用于存储 JSON 输出
4. **运行 CLI 工具**: 执行 `python3 cli.py --output json <target>`
5. **解析 JSON**: 提取发现的 sinks
6. **格式化输出**: 转换为易读的格式
7. **清理临时文件**: 删除中间文件

## 输出格式

每一行输出代表一个发现的 SSRF sink：

```
file: <相对路径>,line: <行号>,column: <列号>,sink_name: <Sink名称>,language: <编程语言>,severity: <严重等级>,snippet: "<代码片段>"
```

## 环境要求

1. Python 3.6+
2. tree-sitter 库及其语言模块（可选，但建议安装以获得完整功能）

### 安装依赖

```bash
cd /home/wangzekai/TOP14/ssrf/scripts
pip install -r requirements.txt
```

## 输出示例

### 有发现的情况

```bash
$ bash scripts/scan.sh tests/fixtures/
======================================
SSRF Sink Detector
======================================
Scanning directory: /absolute/path/to/tests/fixtures
======================================
Found 5 potential SSRF sinks:

file: php/http_calls.php,line: 10,column: 18,sink_name: file_get_contents,language: php,severity: high,snippet: "$content = file_get_contents($url);"
file: php/http_calls.php,line: 15,column: 13,sink_name: fopen,language: php,severity: high,snippet: "$handle = fopen($file, 'r');"
file: python/http_calls.py,line: 11,column: 18,sink_name: requests.get,language: python,severity: high,snippet: "response = requests.get(url)"
file: python/http_calls.py,line: 19,column: 22,sink_name: urllib.request.urlopen,language: python,severity: high,snippet: "response = urllib.request.urlopen(target_url)"

Scan completed!
```

### 无发现的情况

```bash
$ bash scripts/scan.sh empty_directory/
======================================
SSRF Sink Detector
======================================
Scanning directory: /absolute/path/to/empty_directory
======================================
No SSRF sinks found.

Scan completed!
```

## 支持的语言

- ✅ PHP
- ✅ Python
- ✅ Java
- ✅ JavaScript

## 故障排除

### 问题：找不到 cli.py

**错误消息**:
```
Error: cli.py not found in script directory
```

**解决方案**:
- 确保在 `/home/wangzekai/TOP14/ssrf/scripts/` 目录中有 `cli.py` 文件
- 检查文件权限

### 问题：没有找到 Python 3

**错误消息**:
```
python3: command not found
```

**解决方案**:
- 安装 Python 3: `sudo apt-get install python3`
- 或使用 `python` 代替 `python3`（取决于系统配置）

### 问题：tree-sitter 模块未找到

**错误消息**:
```
Warning: Could not load parser for php: No module named 'tree_sitter_php'
```

**解决方案**:
- 安装缺失的 tree-sitter 语言模块
- `pip install tree-sitter-php tree-sitter-python tree-sitter-java tree-sitter-javascript`

### 问题：JSON 解析错误

**错误消息**:
```
Error: Failed to parse scan results
```

**解决方案**:
- 检查 cli.py 是否正确安装
- 验证 Python 环境中的依赖是否完整
- 查看临时输出文件内容（调试用）

## 高级用法

### 脚本内部集成

```bash
#!/bin/bash
# 在其他脚本中调用 scan.sh

SCAN_SCRIPT="/home/wangzekai/TOP14/ssrf/scripts/scan.sh"
TARGET="$1"

# 运行扫描
bash "$SCAN_SCRIPT" "$TARGET"

# 捕获返回值
if [ $? -eq 0 ]; then
    echo "Scan completed successfully"
else
    echo "Scan failed"
    exit 1
fi
```

### 自动化定时扫描

```bash
# 在 crontab 中定期运行
# 每天凌晨 2 点扫描 /var/www/html
0 2 * * * bash /home/wangzekai/TOP14/ssrf/scripts/scan.sh /var/www/html > /var/log/ssrf_scan.log 2>&1
```

### 与 CI/CD 集成

```yaml
# GitHub Actions 示例
- name: SSRF Sink Detection
  run: bash scripts/scan.sh ./src
```

## 注意事项

1. **性能**: 大型代码库可能需要较长的扫描时间
2. **准确性**: 检测依赖于 tree-sitter 语言模块的正确安装
3. **False Positives**: 工具可能报告一些误报（已验证的 URL 等）
4. **权限**: 确保有权读取目标目录中的所有文件

## 相关文件

- `cli.py` - 主 CLI 工具
- `config/languages.yaml` - 语言配置
- `core/scanner.py` - 扫描引擎
- `reports/json_reporter.py` - JSON 报告生成
- `tests/fixtures/` - 测试样例
