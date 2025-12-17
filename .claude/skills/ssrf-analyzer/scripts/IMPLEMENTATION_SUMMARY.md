# SSRF Sink Detector - 实现总结

## 项目概述

成功实现了一个基于 tree-sitter 的 SSRF（Server-Side Request Forgery）漏洞检测工具，支持 PHP、Python、Java 和 JavaScript 四种编程语言。

## 核心功能

### 1. 扫描引擎 (core/scanner.py)
- **功能**: 主要扫描引擎，使用 tree-sitter 进行语法树分析
- **特性**:
  - 支持单文件和目录递归扫描
  - 自动语言检测
  - 精确的节点位置提取
  - 代码片段捕获

### 2. Parser 管理器 (core/parser_manager.py)
- **功能**: 管理多语言 tree-sitter parser 实例
- **特性**:
  - 动态 parser 加载
  - 查询文本加载和缓存
  - 语言和文件扩展名映射
  - 支持易扩展的架构

### 3. Sink 查询文件
- **PHP** (languages/php/queries/sinks.scm):
  - file_get_contents, fopen, readfile, curl_exec, fsockopen 等

- **Python** (languages/python/queries/sinks.scm):
  - requests 库: get, post, put, delete, patch, request
  - urllib 库: urlopen, urlretrieve
  - http.client 和 socket 操作

- **Java** (languages/java/queries/sinks.scm):
  - URL.openConnection, URL.openStream
  - RestTemplate 方法
  - OkHttp 和 HttpClient 操作

- **JavaScript** (languages/javascript/queries/sinks.scm):
  - http/https 模块
  - axios, fetch, XMLHttpRequest
  - got, superagent 库

### 4. 报告生成器

#### JSON 报告 (reports/json_reporter.py)
- 结构化的 JSON 输出
- 包含统计摘要
- 按严重程度和语言分类

#### SARIF 报告 (reports/sarif_reporter.py)
- 符合 SARIF 2.1.0 标准
- 与代码分析工具兼容
- 详细的位置和规则信息

### 5. 命令行界面 (cli.py)
- **支持的选项**:
  - `--lang`: 指定编程语言
  - `--all`: 扫描所有语言
  - `--output`: 输出格式 (text, json, sarif, both)
  - `--json-out/--sarif-out`: 报告输出文件路径
  - `-v/--verbose`: 详细输出

### 6. 测试框架 (tests/)
- 单元测试覆盖
  - Scanner 初始化和操作
  - 文件扩展名检测
  - 报告生成

- 测试样例
  - PHP: http_calls.php（包含 5 个漏洞示例）
  - Python: http_calls.py（包含 7 个漏洞示例）

## 项目结构

```
ssrf_sink_detector/
├── __init__.py                  # 包初始化
├── cli.py                       # CLI 入口
├── QUICKREF.py                  # 快速参考指南
├── requirements.txt             # 依赖列表
├── README.md                    # 完整文档
│
├── config/
│   └── languages.yaml           # 语言配置
│
├── core/
│   ├── __init__.py
│   ├── scanner.py               # 主扫描引擎
│   └── parser_manager.py        # Parser 管理
│
├── languages/                   # 各语言 Sink 查询
│   ├── php/queries/sinks.scm
│   ├── python/queries/sinks.scm
│   ├── java/queries/sinks.scm
│   └── javascript/queries/sinks.scm
│
├── reports/
│   ├── __init__.py
│   ├── json_reporter.py         # JSON 报告生成
│   └── sarif_reporter.py        # SARIF 报告生成
│
└── tests/
    ├── __init__.py
    ├── fixtures/                # 测试样例
    │   ├── php/http_calls.php
    │   └── python/http_calls.py
    └── test_scanner.py          # 单元测试
```

## 使用示例

### 基本扫描
```bash
# 扫描 PHP 项目
python cli.py --lang php /path/to/project

# 扫描 Python 文件
python cli.py --lang python /path/to/script.py
```

### 输出格式
```bash
# 默认文本输出
python cli.py --lang php /path/to/code

# JSON 输出
python cli.py --lang php --output json /path/to/code

# SARIF 输出（标准格式）
python cli.py --lang php --output sarif /path/to/code

# 同时输出多种格式
python cli.py --lang php --output both \
  --json-out report.json \
  --sarif-out report.sarif \
  /path/to/code
```

### 测试运行
```bash
# 运行所有测试
python -m pytest tests/test_scanner.py -v

# 测试 cli.py 帮助
python cli.py --help
```

## 技术亮点

1. **Tree-sitter 驱动**: 使用精确的语法树分析，而不是正则表达式
2. **多语言支持**: 统一的框架支持多种编程语言
3. **标准格式输出**: 支持 SARIF 2.1.0 标准，方便与其他工具集成
4. **易于扩展**: 模块化设计，轻松添加新语言和 Sink
5. **清晰文档**: 完整的 README、快速参考和代码注释

## 依赖说明

| 包 | 版本 | 用途 |
|----|------|------|
| pyyaml | >=6.0 | YAML 配置解析 |
| tree-sitter | >=0.21.0 | 语法树解析核心 |
| tree-sitter-php | >=0.21.0 | PHP 语言支持 |
| tree-sitter-python | >=0.21.0 | Python 语言支持 |
| tree-sitter-java | >=0.21.0 | Java 语言支持 |
| tree-sitter-javascript | >=0.21.0 | JavaScript 语言支持 |

## 已实现的检测功能

### PHP (7 个 Sink)
- file_get_contents
- fopen, readfile
- curl_exec, curl_multi_exec
- fsockopen, pfsockopen

### Python (7+ 个 Sink)
- requests: get, post, put, delete, patch, request
- urllib: urlopen, urlretrieve
- http.client: HTTPConnection, HTTPSConnection
- socket: create_connection

### Java (6+ 个 Sink)
- URL: openConnection, openStream
- URLConnection: getInputStream, connect
- RestTemplate: exchange, getForObject, getForEntity, postForObject
- OkHttpClient: newCall, execute
- HttpClient: send, execute

### JavaScript (8+ 个 Sink)
- http/https: request, get, createConnection
- axios: get, post, put, delete, patch, request
- fetch
- XMLHttpRequest: open, send
- got: get, post, put, delete, patch, stream
- superagent: end, pipe

## 未来改进方向

1. **数据流分析**: 追踪用户输入到 Sink 的数据流
2. **污点分析**: 实现污点传播算法
3. **配置文件支持**: 支持自定义 Sink 规则
4. **Web 界面**: 开发 Web UI 用于可视化扫描结果
5. **CI/CD 集成**: 预构建集成脚本
6. **性能优化**: 缓存和并行处理

## 完成情况

✅ 项目结构创建
✅ 配置系统实现
✅ 核心扫描引擎
✅ Parser 管理器
✅ 四语言 Sink 查询
✅ JSON 报告生成
✅ SARIF 报告生成
✅ CLI 命令行工具
✅ 单元测试框架
✅ 测试样例数据
✅ 完整文档

## 总结

该 SSRF Sink Detector 项目提供了一个健壮、可扩展的框架，用于在代码库中自动检测潜在的 SSRF 漏洞。通过使用 tree-sitter 进行精确的语法分析，避免了基于模式匹配的误报，同时支持多种编程语言和输出格式，使其适合集成到 DevSecOps 工作流中。
