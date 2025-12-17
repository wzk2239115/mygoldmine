# 使用指南

## 快速开始

### 使用scan.sh (推荐)
```bash
bash scan.sh ~/WebGoat/                      # 扫描全部
bash scan.sh --lang php ~/WebGoat/           # PHP仅
bash scan.sh --summary ~/WebGoat/            # 摘要
bash scan.sh --limit 20 ~/WebGoat/           # 限制结果
```

### 使用Python CLI
```bash
python cli.py --all ~/WebGoat/               # 全部
python cli.py --lang php ~/WebGoat/          # PHP
python cli.py --output json ~/WebGoat/       # JSON
python cli.py --report report.json ~/WebGoat/ # 保存文件
```

## 示例

```bash
bash scan.sh ~/WebGoat/
bash scan.sh --lang php --summary ~/my-project/
python cli.py --all --output json --report findings.json ~/code/
```
