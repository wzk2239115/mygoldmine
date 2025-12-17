# XSS Sink Detector

基于Tree-sitter的XSS漏洞Sink检测工具。通过静态代码分析识别代码中可能导致XSS漏洞的危险函数调用和DOM操作。

## 核心特性

- **多语言支持**: PHP、Python、JavaScript、Java
- **精准的Sink检测**: 使用Tree-sitter进行AST分析，避免正则表达式的误报
- **灵活的报告格式**: 支持JSON、SARIF、纯文本输出
- **可扩展架构**: 轻松添加新语言或自定义Sink规则

## 项目结构

```
xss_sink_detector/
├── README.md                    # 本文件
├── config/
│   └── languages.yaml          # 语言配置：文件扩展名、tree-sitter模块、优先级
├── core/
│   ├── __init__.py
│   ├── scanner.py              # 主扫描引擎（仅运行 Sink 查询）
│   └── parser_manager.py       # 管理各语言tree-sitter实例
│
├── languages/                   # 各语言实现（可独立扩展）
│   ├── php/
│   │   └── queries/
│   │       └── sinks.scm       # XSS 危险汇：echo, print, header()等
│   ├── python/
│   │   └── queries/
│   │       └── sinks.scm       # XSS 危险汇：response.write(), 模板渲染中的危险点
│   ├── java/
│   │   └── queries/
│   │       └── sinks.scm       # XSS 危险汇：response.getWriter().write(), 模板输出点
│   └── javascript/
│       └── queries/
│           └── sinks.scm       # XSS 危险汇：innerHTML, outerHTML, document.write()等
│
├── reports/
│   ├── __init__.py
│   ├── json_reporter.py        # 报告匹配到的 XSS Sink 位置
│   └── sarif_reporter.py       # SARIF标准格式 (仅 Location 报告)
│
├── tests/
│   ├── fixtures/               # 测试样例（仅用于确认 XSS Sink 匹配）
│   │   ├── php/
│   │   │   └── output_calls.php
│   │   ├── python/
│   │   │   └── test_sinks.py
│   │   ├── javascript/
│   │   │   └── test_sinks.js
│   │   └── java/
│   │       └── TestXSSSinks.java
│   └── test_scanner.py         # 自动化测试 (仅测试 Sink 匹配)
│
├── cli.py                       # 命令行入口
└── requirements.txt            # 依赖列表
```

## 安装

### 前置要求

- Python 3.7+
- pip

### 安装步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装tree-sitter语言库（以PHP为例）
pip install tree-sitter-php
pip install tree-sitter-python
pip install tree-sitter-javascript
pip install tree-sitter-java
```

## 使用方法

### 基本用法

```bash
# 扫描单个文件
python -m xss_sink_detector.cli /path/to/file.php

# 扫描整个目录
python -m xss_sink_detector.cli /path/to/project

# 指定编程语言
python -m xss_sink_detector.cli --lang php /path/to/code.php
```

### 输出格式

```bash
# JSON格式（默认为漂亮打印）
python -m xss_sink_detector.cli --output json /path/to/code

# 紧凑JSON格式
python -m xss_sink_detector.cli --output json --compact /path/to/code

# SARIF格式（用于集成到IDE和CI/CD）
python -m xss_sink_detector.cli --output sarif --output-file report.sarif /path/to/code

# 纯文本格式
python -m xss_sink_detector.cli --output text /path/to/code
```

### 保存报告

```bash
# 保存JSON报告
python -m xss_sink_detector.cli --output json --output-file report.json /path/to/code

# 保存SARIF报告
python -m xss_sink_detector.cli --output sarif --output-file report.sarif /path/to/code
```

### 详细模式

```bash
# 启用详细输出
python -m xss_sink_detector.cli --verbose /path/to/code
```

## 检测的XSS Sink

### PHP
- 直接输出: `echo`, `print`, `var_dump`, `print_r`, `var_export`
- 头部设置: `header()`
- 模板渲染: `render()`, `view()`, `display()`, `output()`
- 动态执行: `eval()`, `assert()`, `create_function()`
- 缓冲输出: `ob_get_contents()`, `ob_get_clean()`, `ob_get_flush()`

### Python
- Flask/Django响应: `response.write()`, `render_template()`, `render_template_string()`
- 输出: `print()`
- 模板: `render()`, `format()`
- 动态执行: `eval()`, `exec()`, `compile()`
- 响应对象: `set_data()`, `set_cookie()`
- 字符串操作: `str()`, `repr()`, `format()`

### JavaScript
- DOM属性赋值: `innerHTML`, `outerHTML`
- 文档写入: `document.write()`, `document.writeln()`
- 动态执行: `eval()`, `Function()构造函数`
- 计时器: `setTimeout()`, `setInterval()`（使用字符串参数时）
- 邻近插入: `insertAdjacentHTML()`
- 文本内容: `textContent`（赋值时）

### Java
- 响应输出: `response.getWriter().write()`, `.println()`, `.append()`
- 输出流: `response.getOutputStream().write()`
- 头部设置: `response.setHeader()`, `.addHeader()`, `.sendRedirect()`
- 模型属性: `model.addAttribute()`
- 标准输出: `System.out.println()`, `.print()`
- 缓冲区: `StringBuffer.append()`

## 报告格式

### JSON格式

```json
{
  "status": "success",
  "total_sinks_found": 5,
  "results": [
    {
      "file": "/path/to/file.php",
      "language": "php",
      "sink_type": "xss_sink_output",
      "line": 10,
      "column": 0,
      "end_line": 10,
      "end_column": 20,
      "code": "echo $_GET['input'];",
      "node_text": "echo"
    }
  ],
  "summary_by_language": {
    "php": 3,
    "javascript": 2
  },
  "summary_by_sink_type": {
    "xss_sink_output": 3,
    "xss_sink_html_property": 2
  }
}
```

### SARIF格式

符合SARIF 2.1.0标准，可直接集成到支持SARIF的工具（如Visual Studio Code、GitHub CodeQL等）。

### 文本格式

人类可读的格式，包含：
- 按文件分组的Sink列表
- 每个Sink的位置和代码上下文
- 按语言和类型的统计信息

## 扩展功能

### 添加新语言

1. 在 `config/languages.yaml` 中添加语言配置：
   ```yaml
   go:
     extensions:
       - .go
     tree_sitter_module: tree_sitter_go
     priority: 5
     query_file: languages/go/queries/sinks.scm
   ```

2. 创建查询文件 `languages/go/queries/sinks.scm`

3. 安装对应的tree-sitter库：
   ```bash
   pip install tree-sitter-go
   ```

### 自定义Sink规则

编辑对应语言的 `.scm` 查询文件，使用Tree-sitter Query语法定义新的Sink模式。

## 测试

```bash
# 运行自动化测试
python -m pytest xss_sink_detector/tests/test_scanner.py -v

# 运行特定测试
python -m pytest xss_sink_detector/tests/test_scanner.py::TestScanner::test_scan_php_fixtures -v
```

## 局限性

1. **仅检测Sink**: 这是一个Sink检测工具，不进行污点跟踪或数据流分析
2. **语言局限**: 只支持配置中定义的编程语言
3. **模式局限**: 检测规则基于代码模式匹配，不能识别所有可能的XSS Sink
4. **误报**: 某些输出函数的使用可能是安全的（如已经转义的数据）

## 最佳实践

1. **使用本工具作为辅助**: 结合手工审查和其他安全测试工具
2. **定期更新规则**: 根据新发现的XSS模式更新查询规则
3. **集成到CI/CD**: 在代码审查流程中自动运行扫描
4. **上下文审查**: 检查每个Sink的实际用途，排除误报

## 常见问题

**Q: 为什么没有检测到某个Sink?**
A: 可能原因：
- 代码语言不在支持列表中
- Sink模式不在查询规则中
- 代码语法有误，无法正确解析

**Q: 如何减少误报?**
A:
- 手动审查结果，识别误报
- 更新查询规则以排除特定模式
- 使用SARIF报告集成到IDE进行上下文过滤

**Q: 性能如何?**
A: 取决于代码量和复杂度，通常可以在几秒内扫描数百个文件。

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，请在GitHub上提交Issue。
