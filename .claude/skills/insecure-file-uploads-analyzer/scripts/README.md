# Insecure Upload Sink Detector

基于tree-sitter的文件上传危险汇(sink)自动检测工具

## 快速开始

```bash
pip install -r requirements.txt
bash scan.sh ~/WebGoat/
```

## 使用方法

```bash
bash scan.sh /path/to/code              # 扫描全部语言
bash scan.sh --lang php /path           # 仅扫描PHP
bash scan.sh --summary /path            # 显示摘要
python cli.py --output json /path       # JSON输出
```

## 支持的语言

- PHP
- Python
- Java
- JavaScript
