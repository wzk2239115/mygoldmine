# SSRF Sink Detector

A powerful static analysis tool for detecting Server-Side Request Forgery (SSRF) vulnerabilities across multiple programming languages using tree-sitter.

## 核心特性

- **多语言支持**: PHP, Python, Java, JavaScript
- **Tree-sitter 引擎**: 精确的语法树分析
- **灵活的输出格式**: 文本、JSON、SARIF 标准格式
- **易于扩展**: 模块化设计，可轻松添加新语言

## 项目结构

```
ssrf_sink_detector/
├── README.md                    # 项目文档
├── config/
│   └── languages.yaml          # 语言配置
├── core/
│   ├── __init__.py
│   ├── scanner.py              # 主扫描引擎
│   └── parser_manager.py       # Tree-sitter 管理
├── languages/                   # 各语言实现
│   ├── php/
│   │   └── queries/
│   │       └── sinks.scm       # PHP Sink 查询
│   ├── python/
│   │   └── queries/
│   │       └── sinks.scm       # Python Sink 查询
│   ├── java/
│   │   └── queries/
│   │       └── sinks.scm       # Java Sink 查询
│   └── javascript/
│       └── queries/
│           └── sinks.scm       # JavaScript Sink 查询
├── reports/
│   ├── __init__.py
│   ├── json_reporter.py        # JSON 报告生成
│   └── sarif_reporter.py       # SARIF 报告生成
├── tests/
│   ├── fixtures/               # 测试样例
│   │   ├── php/
│   │   │   └── http_calls.php
│   │   └── python/
│   │       └── http_calls.py
│   └── test_scanner.py         # 单元测试
└── cli.py                       # 命令行入口
```

## 安装

### 前置要求

- Python 3.8+
- tree-sitter
- tree-sitter 语言模块

### 安装依赖

```bash
pip install pyyaml
pip install tree-sitter
pip install tree-sitter-php tree-sitter-python tree-sitter-java tree-sitter-javascript
```

## 使用方法

### 命令行基本用法

```bash
# 扫描 PHP 文件
python cli.py --lang php /path/to/code

# 扫描 Python 项目
python cli.py --lang python /path/to/project

# 扫描所有支持的语言
python cli.py --all /path/to/code

# 输出 JSON 格式报告
python cli.py --lang php --output json /path/to/code

# 输出 SARIF 格式报告
python cli.py --lang javascript --output sarif /path/to/code

# 输出 JSON 和 SARIF 报告到文件
python cli.py --lang python --output both \
  --json-out report.json \
  --sarif-out report.sarif \
  /path/to/code
```

### 选项说明

- `path`: 要扫描的文件或目录路径（必需）
- `--lang`: 编程语言 (php, python, java, javascript)
- `--all`: 扫描所有支持的语言
- `--output`: 输出格式 (json, sarif, both, text) - 默认: text
- `--json-out FILE`: JSON 报告输出文件
- `--sarif-out FILE`: SARIF 报告输出文件
- `-v, --verbose`: 详细输出

## 检测的 Sink 函数

### PHP

| 函数 | 说明 |
|------|------|
| `file_get_contents()` | 读取远程文件 |
| `fopen()` | 打开远程文件 |
| `readfile()` | 读取并输出文件 |
| `curl_exec()` | 执行 CURL 请求 |
| `curl_multi_exec()` | 批量执行 CURL 请求 |
| `fsockopen()` | 打开 Socket 连接 |
| `pfsockopen()` | 持久 Socket 连接 |

### Python

| 模块/函数 | 说明 |
|----------|------|
| `requests.get/post/put/delete/patch()` | HTTP 请求 |
| `urllib.request.urlopen()` | URL 打开 |
| `urllib.request.urlretrieve()` | URL 下载 |
| `http.client.HTTPConnection` | HTTP 连接 |
| `socket.create_connection()` | Socket 连接 |

### Java

| 类/方法 | 说明 |
|--------|------|
| `URL.openConnection()` | 打开 URL 连接 |
| `URL.openStream()` | 打开 URL 流 |
| `URLConnection.getInputStream()` | 获取输入流 |
| `RestTemplate.exchange/getForObject()` | REST 请求 |
| `OkHttpClient.newCall/execute()` | OkHttp 请求 |
| `HttpClient.send/execute()` | HTTP 客户端请求 |

### JavaScript

| 模块/函数 | 说明 |
|----------|------|
| `http.request/get()` | Node.js HTTP 请求 |
| `https.request/get()` | Node.js HTTPS 请求 |
| `axios.get/post/request()` | Axios HTTP 请求 |
| `fetch()` | 浏览器/Node.js 原生 Fetch |
| `XMLHttpRequest.open/send()` | XHR 请求 |
| `got.get/post()` | Got HTTP 客户端 |
| `superagent.end/pipe()` | Superagent 请求 |

## 输出格式

### 文本格式（默认）

```
================================================================================
SSRF Sink Detection Results
================================================================================
Total findings: 2

1. file_get_contents
   File: /path/to/file.php
   Line: 10:5
   Language: php
   Severity: HIGH
   Code: $content = file_get_contents($url);

2. requests.get
   File: /path/to/script.py
   Line: 5:10
   Language: python
   Severity: HIGH
   Code: response = requests.get(url)

================================================================================
Summary by Severity:
  HIGH: 2

Summary by Language:
  php: 1
  python: 1
================================================================================
```

### JSON 格式

```json
{
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00.000000",
  "summary": {
    "total_findings": 2,
    "by_severity": {
      "high": 2,
      "medium": 0,
      "low": 0
    },
    "by_language": {
      "php": 1,
      "python": 1
    }
  },
  "findings": [
    {
      "file": "/path/to/file.php",
      "language": "php",
      "sink_name": "file_get_contents",
      "start_line": 10,
      "start_col": 5,
      "end_line": 10,
      "end_col": 25,
      "code_snippet": "$content = file_get_contents($url);",
      "severity": "high"
    }
  ]
}
```

### SARIF 格式

符合 SARIF 2.1.0 标准，可与各种代码分析工具集成。

## 扩展支持新语言

### 步骤 1: 更新 languages.yaml

```yaml
languages:
  newlang:
    extensions:
      - .nl
    tree_sitter_module: tree_sitter_newlang
    priority: 5
    sink_query_file: languages/newlang/queries/sinks.scm
```

### 步骤 2: 创建 Sink 查询文件

在 `languages/newlang/queries/sinks.scm` 中编写 tree-sitter 查询，例如：

```scm
;; New Language SSRF Sinks
(call_expression
  function: (identifier) @sink
  (#match? @sink "^(http_get|url_fetch)$")
)
```

### 步骤 3: 测试

创建测试样例并添加到 `tests/fixtures/newlang/`

## 运行测试

```bash
cd ssrf_sink_detector
python -m pytest tests/test_scanner.py -v
```

## 已知限制

1. **数据流分析**: 当前只检测 Sink 调用点，不追踪数据流
2. **上下文敏感**: 不分析变量赋值和传播
3. **False Positives**: 可能报告安全的 URL 使用（例如已验证的 URL）
4. **Parser 依赖**: 需要安装对应语言的 tree-sitter parser

## 改进计划

- [ ] 数据流分析（Source to Sink）
- [ ] 污点追踪
- [ ] 变量赋值追踪
- [ ] 函数参数溯源
- [ ] 支持更多编程语言
- [ ] Web UI 界面
- [ ] CI/CD 集成

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 参考资源

- [Tree-sitter 官网](https://tree-sitter.github.io/tree-sitter/)
- [OWASP SSRF](https://owasp.org/www-community/attacks/Server-Side_Request_Forgery)
- [SARIF 标准](https://sarifweb.azurewebsites.net/)
