#!/usr/bin/env python3
"""Quick reference guide for SSRF Sink Detector."""

QUICK_REFERENCE = """
╔════════════════════════════════════════════════════════════════════════════╗
║                     SSRF Sink Detector Quick Reference                     ║
╚════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 安装依赖
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ pip install -r requirements.txt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. 基本使用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 扫描 PHP 项目
$ python cli.py --lang php /path/to/project

# 扫描 Python 项目
$ python cli.py --lang python /path/to/project

# 扫描单个文件
$ python cli.py --lang javascript /path/to/file.js

# 自动检测语言并扫描
$ python cli.py /path/to/code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. 输出格式选项
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 文本输出（默认）
$ python cli.py --lang php /path/to/code

# JSON 输出
$ python cli.py --lang php --output json /path/to/code

# SARIF 输出（安全分析标准）
$ python cli.py --lang php --output sarif /path/to/code

# 同时输出 JSON 和 SARIF
$ python cli.py --lang php --output both \\
    --json-out report.json \\
    --sarif-out report.sarif \\
    /path/to/code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. 常见使用场景
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

场景 1: 审计完整项目
  $ python cli.py --all --output json --json-out audit.json /path/to/project

场景 2: CI/CD 集成
  $ python cli.py --lang php --output sarif --sarif-out results.sarif /src

场景 3: 快速文件检查
  $ python cli.py --lang python -v /path/to/script.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. 支持的编程语言
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ PHP          - file_get_contents(), curl_exec(), etc.
✓ Python       - requests.get(), urllib.urlopen(), etc.
✓ Java         - URL.openConnection(), RestTemplate, etc.
✓ JavaScript   - fetch(), http.request(), axios, etc.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. 命令行帮助
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ python cli.py --help

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. 运行测试
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ python -m pytest tests/test_scanner.py -v

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. 项目文件说明
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 ssrf_sink_detector/
├── 📄 cli.py                  - 命令行入口
├── 📁 config/
│   └── languages.yaml         - 语言配置
├── 📁 core/
│   ├── scanner.py             - 扫描引擎
│   └── parser_manager.py      - Parser 管理
├── 📁 languages/              - 各语言 Sink 查询
├── 📁 reports/                - 报告生成器
├── 📁 tests/                  - 测试代码
└── 📄 requirements.txt         - 依赖列表

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

if __name__ == '__main__':
    print(QUICK_REFERENCE)
