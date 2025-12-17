# CSRF Sink Detector

A powerful tree-sitter-based static code analysis tool for detecting CSRF (Cross-Site Request Forgery) vulnerabilities by identifying state-changing endpoints (routes/actions) that may require CSRF protection.

## 核心说明：AI工具如何调用

This tool is designed to be called by AI-powered security auditing tools to automatically detect potential CSRF vulnerability entry points in web applications. It identifies POST/PUT/DELETE endpoints and other state-changing operations that are candidate sinks for CSRF protection verification.

## 项目结构

```
csrf_sink_detector/
├── README.md                    # 核心说明：AI工具如何调用
├── config/
│   └── languages.yaml          # 语言配置：文件扩展名、tree-sitter模块、优先级
├── core/
│   ├── __init__.py
│   ├── scanner.py              # 主扫描引擎（仅运行 Route/Action Sink 查询）
│   └── parser_manager.py       # 管理各语言tree-sitter实例
│
├── languages/                   # 各语言实现（可独立扩展）
│   ├── php/
│   │   └── queries/            # Tree-sitter查询文件(.scm)
│   │       └── actions.scm     # 危险汇：POST 路由定义、敏感操作函数
│   ├── python/
│   │   └── queries/
│   │       └── routes.scm      # 危险汇：Flask/Django @app.route(methods=['POST'])
│   ├── java/
│   │   └── queries/
│   │       └── controllers.scm # 危险汇：Spring @PostMapping 或 @RequestMapping(method=POST)
│   └── javascript/
│       └── queries/
│           └── routes.scm      # 危险汇：Express/Koa app.post() 定义
│
├── reports/
│   ├── __init__.py
│   ├── json_reporter.py        # 报告匹配到的 Route/Action Sink 位置
│   └── sarif_reporter.py       # SARIF标准格式 (仅 Location 报告)
│
├── tests/
│   ├── fixtures/               # 测试样例（仅用于确认 Route/Action 匹配）
│   │   ├── php/
│   │   │   └── post_routes.php
│   │   ├── python/
│   │   │   └── flask_csrf.py
│   │   ├── java/
│   │   │   └── SpringController.java
│   │   └── javascript/
│   │       └── express_routes.js
│   ├── __init__.py
│   └── test_scanner.py         # 自动化测试 (仅测试 Route/Action 匹配)
│
└── cli.py                       # 命令行入口：python cli.py --lang php --output json /path/to/code
```

## 特性

- **多语言支持**：PHP、Python、Java、JavaScript/TypeScript
- **基于 Tree-Sitter**：精确的语法树分析，避免正则表达式的局限性
- **自动识别状态修改端点**：检测 POST/PUT/DELETE 路由和操作
- **灵活的报告格式**：JSON 和 SARIF 标准格式
- **可扩展架构**：轻松添加新语言和检测规则

## 安装

```bash
pip install pyyaml
# 如果使用 tree-sitter 支持
pip install tree-sitter
```

## 使用方法

### 基本使用

扫描目录中的所有支持语言文件：

```bash
python cli.py /path/to/project
```

### 指定语言

只扫描特定语言的文件：

```bash
python cli.py --lang python java /path/to/project
```

### 输出格式

#### JSON 格式（默认）

```bash
python cli.py --format json --output report.json /path/to/project
```

#### SARIF 格式

```bash
python cli.py --format sarif --output report.sarif /path/to/project
```

### 详细输出

```bash
python cli.py --verbose /path/to/project
```

### 扫描单个文件

```bash
python cli.py /path/to/file.php
```

## 输出示例

### JSON 报告

```json
{
  "timestamp": "2025-11-30T10:30:00",
  "version": "1.0",
  "tool": "CSRF Sink Detector",
  "summary": {
    "total_sinks": 5,
    "by_type": {
      "POST_ROUTE": 3,
      "CSRF_EXEMPT": 1,
      "POST_ENDPOINT": 1
    },
    "by_file": {
      "app.py": 2,
      "views.py": 3
    }
  },
  "sinks": [
    {
      "file": "app.py",
      "line": 10,
      "column": 1,
      "type": "POST_ROUTE",
      "sink": "POST endpoint",
      "code": "@app.route('/update', methods=['POST'])"
    }
  ]
}
```

### SARIF 报告

```json
{
  "version": "2.1.0",
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "CSRF Sink Detector",
          "version": "1.0"
        }
      },
      "results": [
        {
          "message": {
            "text": "POST endpoint detected"
          },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {
                  "uri": "app.py"
                },
                "region": {
                  "startLine": 10,
                  "startColumn": 1
                }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

## 支持的 CSRF 危险汇类型

### PHP
- **POST routes**：Laravel, Slim, 通用 POST 方法调用
- **POST 处理**：直接 `$_POST` 访问，`REQUEST_METHOD` 检查

### Python
- **Flask routes**：`@app.route(..., methods=['POST'])`
- **Django views**：视图函数、CSRF 豁免装饰器
- **POST 处理**：`request.method == 'POST'`

### Java
- **Spring annotations**：`@PostMapping`, `@PutMapping`, `@DeleteMapping`
- **RequestMapping**：`method = RequestMethod.POST`
- **Security config**：`csrf().disable()` 配置

### JavaScript/TypeScript
- **Express routes**：`app.post()`, `router.post()`
- **HTTP methods**：`app.put()`, `app.delete()`
- **Koa routes**：路由处理

## 工作原理

### 扫描流程

1. **文件发现**：根据文件扩展名找到目标语言的文件
2. **内容读取**：读取文件内容
3. **语法分析**：使用 tree-sitter 解析代码生成语法树
4. **模式匹配**：应用 `.scm` 查询文件识别 POST/PUT/DELETE 端点
5. **结果提取**：提取位置和上下文信息
6. **报告生成**：生成 JSON 或 SARIF 格式报告

### 检测范围

该工具专注于识别**状态修改端点**（Route/Action Sink），这些是可能需要 CSRF 保护的地方：

- POST 请求处理
- PUT/PATCH 请求处理
- DELETE 请求处理
- 表单提交处理
- API 状态变更操作

## 局限性

- **不进行数据流分析**：仅识别端点位置，不追踪 CSRF 令牌验证逻辑
- **不验证防护**：不检查是否实际实施了 CSRF 防护
- **语言特定**：仅支持配置中列出的语言
- **tree-sitter 依赖**：高精度模式匹配需要 tree-sitter

## 扩展

### 添加新语言

1. 在 `config/languages.yaml` 中配置语言
2. 在 `languages/{language}/queries/` 中创建 `.scm` 查询文件
3. 在 `core/scanner.py` 中实现对应的 Detector 类

### 自定义查询

编辑 `languages/{language}/queries/*.scm` 文件来调整检测规则。

## 测试

运行测试套件：

```bash
python -m pytest tests/test_scanner.py -v
```

或使用 unittest：

```bash
python -m unittest tests.test_scanner -v
```

## API 使用

在 Python 代码中使用：

```python
from core.scanner import CSRFSinkScanner
from reports.json_reporter import JSONReporter

# 创建扫描器
scanner = CSRFSinkScanner()

# 扫描目录
sinks = scanner.scan_directory('/path/to/project', ['python', 'java'])

# 生成报告
reporter = JSONReporter(pretty_print=True)
reporter.save_report(sinks, 'csrf_report.json')
```

## 许可证

作为 TOP14 安全审计框架的一部分。

## 相关资源

- [CSRF 漏洞通用指南](../general.md)
- [CSRF 绕过技巧](../bypassTricks.md)
- [各语言特定漏洞指南](../)
