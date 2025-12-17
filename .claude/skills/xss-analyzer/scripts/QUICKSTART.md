# 快速开始指南

## 安装

### 1. 安装基础依赖
```bash
cd xss_sink_detector
pip install -r requirements.txt
```

### 2. 安装语言库
```bash
# 根据你需要的语言安装对应库

# PHP支持
pip install tree-sitter-php

# Python支持
pip install tree-sitter-python

# JavaScript/TypeScript支持
pip install tree-sitter-javascript

# Java支持
pip install tree-sitter-java
```

## 5分钟快速开始

### 1. 扫描一个文件
```bash
python cli.py tests/fixtures/php/output_calls.php
```

输出示例：
```
发现 5 个XSS Sink

📄 tests/fixtures/php/output_calls.php
  [       php       ] Line    2: xss_sink_output      - echo $_GET['user_input'];
  [       php       ] Line    3: xss_sink_output      - echo "Hello " . $_POST['name'];
  ...
```

### 2. 生成JSON报告
```bash
python cli.py --output json --output-file report.json tests/fixtures/
```

查看报告：
```bash
cat report.json
```

### 3. 扫描整个项目
```bash
python cli.py /path/to/your/project
```

### 4. 生成SARIF报告（用于IDE集成）
```bash
python cli.py --output sarif --output-file report.sarif /path/to/your/project
```

## 常用命令

### 扫描PHP文件
```bash
python cli.py --lang php --output text /path/to/code.php
```

### 扫描Python代码
```bash
python cli.py --lang python --output json /path/to/django_app.py
```

### 扫描JavaScript
```bash
python cli.py --lang javascript /path/to/app.js
```

### 详细扫描
```bash
python cli.py --verbose --output json --output-file report.json /path/to/code
```

### 紧凑JSON输出
```bash
python cli.py --output json --compact /path/to/code
```

## 项目结构速览

```
xss_sink_detector/
├── cli.py              # 命令行工具（直接运行）
├── core/               # 核心模块
├── languages/          # 各语言的Sink规则
├── reports/            # 报告生成器
├── tests/              # 测试和示例代码
└── config/             # 配置文件
```

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/test_scanner.py -v

# 运行特定测试
python -m pytest tests/test_scanner.py::TestScanner::test_scan_php_fixtures -v
```

## 检测规则

工具会自动检测以下XSS Sink：

### PHP
- `echo`, `print`, `var_dump`
- `header()`, `render()`, `view()`
- `eval()`, `assert()`

### Python
- `render_template()`, `render_template_string()`
- `response.write()`, `print()`
- `eval()`, `exec()`

### JavaScript
- `innerHTML`, `outerHTML`
- `document.write()`
- `eval()`, `Function()`
- `insertAdjacentHTML()`

### Java
- `response.getWriter().write()`
- `response.setHeader()`, `addHeader()`
- `model.addAttribute()`
- `System.out.println()`

## 理解输出

### JSON格式
```json
{
  "total_sinks_found": 5,
  "results": [
    {
      "file": "path/to/file.php",
      "language": "php",
      "sink_type": "xss_sink_output",
      "line": 10,
      "code": "echo $_GET['input'];"
    }
  ]
}
```

### 文本格式
- 按文件分组
- 每行显示: 语言 + 行号 + Sink类型 + 代码片段
- 底部显示统计信息

## 集成到CI/CD

### GitHub Actions
```yaml
- name: XSS Sink Detection
  run: |
    pip install -r requirements.txt
    pip install tree-sitter-php tree-sitter-python tree-sitter-javascript
    python cli.py --output sarif --output-file xss-report.sarif .
```

### GitLab CI
```yaml
security_scan:
  script:
    - pip install -r requirements.txt
    - pip install tree-sitter-php tree-sitter-python tree-sitter-javascript
    - python cli.py --output json --output-file report.json .
  artifacts:
    paths:
      - report.json
```

## 常见问题

**Q: 为什么检测不到我的代码?**
A: 确保：
1. 已安装对应语言的tree-sitter库
2. 文件扩展名正确
3. 代码语法有效

**Q: 如何处理误报?**
A: 手动审查结果，理解代码上下文。Sink检测本身是安全的（只是标记可能的危险点），实际风险取决于输入是否被正确清理。

**Q: 可以自定义检测规则吗?**
A: 可以！编辑 `languages/*/queries/sinks.scm` 文件，使用Tree-sitter Query语法。

**Q: 性能如何?**
A: 通常可在几秒内扫描数百个文件，取决于文件大小和复杂度。

## 下一步

1. 阅读 `README.md` 了解详细文档
2. 查看 `tests/fixtures/` 中的示例代码
3. 尝试在自己的项目上运行
4. 根据需要自定义检测规则

## 获取帮助

- 查看 `README.md` 中的详细文档
- 运行 `python cli.py --help` 获取命令帮助
- 查看测试文件理解用法

---

现在开始使用XSS Sink Detector吧！
