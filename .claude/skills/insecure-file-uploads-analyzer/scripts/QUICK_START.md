# 快速开始指南

## 项目位置
```
/home/wangzekai/TOP14/insecure_file_uploads/insecure_upload_sink_detector/
```

## ⚡ 3步快速开始

### 1. 进入项目目录
```bash
cd /home/wangzekai/TOP14/insecure_file_uploads/insecure_upload_sink_detector
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 扫描你的代码
```bash
bash scan.sh ~/WebGoat/
```

## 📊 常用命令

### 扫描所有语言
```bash
bash scan.sh ~/WebGoat/
```

### 仅扫描PHP
```bash
bash scan.sh --lang php ~/WebGoat/
```

### 仅扫描Python
```bash
bash scan.sh --lang python ~/WebGoat/
```

### 显示摘要
```bash
bash scan.sh --summary ~/WebGoat/
```

### 限制结果数量
```bash
bash scan.sh --limit 20 ~/WebGoat/
```

### 生成JSON报告
```bash
python cli.py --all --output json --report findings.json ~/WebGoat/
```

### 生成SARIF报告 (IDE集成)
```bash
python cli.py --all --output sarif --report findings.sarif ~/WebGoat/
```

## 💡 实用例子

### 扫描当前目录
```bash
bash scan.sh .
```

### 扫描src目录并显示摘要
```bash
bash scan.sh --summary ./src/
```

### 扫描所有PHP文件并限制10条结果
```bash
bash scan.sh --lang php --limit 10 ~/project/
```

### 保存扫描结果到文件
```bash
bash scan.sh ~/WebGoat/ | tee scan_results.txt
```

### 查找特定函数
```bash
bash scan.sh ~/WebGoat/ | grep "move_uploaded_file"
```

## 📁 项目结构

```
insecure_upload_sink_detector/
├── core/                   # Python核心模块
│   ├── scanner.py         # 扫描引擎
│   └── parser_manager.py  # 语言管理器
├── languages/             # 语言定义
│   ├── php/queries/
│   ├── python/queries/
│   ├── java/queries/
│   └── javascript/queries/
├── reports/               # 报告生成器
│   ├── json_reporter.py
│   └── sarif_reporter.py
├── tests/                 # 测试
│   ├── test_scanner.py
│   └── fixtures/
├── cli.py                 # Python CLI
├── scan.sh                # Bash包装脚本 ⭐
├── config/
│   └── languages.yaml     # 配置文件
├── requirements.txt       # 依赖列表
├── setup.py              # 安装脚本
├── README.md             # 项目文档
└── USAGE.md              # 使用指南
```

## 🔍 支持的sink类型

### PHP
- `move_uploaded_file()` - 文件上传
- `file_put_contents()` - 文件写入
- `include/require` - 文件包含
- `unserialize()` - 反序列化

### Python
- `open()` - 文件操作
- `shutil.move/copy()` - 文件操作
- `os.path.join()` - 路径操作
- `pickle.load()` - 反序列化

### Java
- `MultipartFile.transferTo()` - 文件上传
- `Files.write/copy()` - 文件操作

### JavaScript
- `fs.writeFile()` - 文件写入
- `path.join()` - 路径操作

## 📚 更多帮助

查看详细文档：
- `README.md` - 完整项目文档
- `USAGE.md` - 详细使用指南

查看命令帮助：
```bash
bash scan.sh --help
python cli.py --help
```

## 🎯 常见任务

### 任务1: 快速检查代码中的漏洞
```bash
bash scan.sh --summary ~/my-app/
```

### 任务2: 详细审计单个语言
```bash
bash scan.sh --lang php ~/my-app/
bash scan.sh --lang python ~/my-app/
```

### 任务3: 生成安全报告
```bash
python cli.py --all --output json --report security_report.json ~/my-app/
```

### 任务4: 集成到CI/CD
```bash
bash scan.sh --summary ./src/ > results.txt
if grep -q "high" results.txt; then
    echo "Security issues found!"
    exit 1
fi
```

## ⚙️ 自定义配置

### 修改检测规则
编辑语言特定的查询文件：
```bash
nano languages/php/queries/sinks.scm
nano languages/python/queries/sinks.scm
```

### 修改输出格式
编辑 `scan.sh` 中的 `MAX_SNIPPET_LENGTH`：
```bash
MAX_SNIPPET_LENGTH=150  # 代码片段最大长度
```

## 🚀 下一步

1. ✅ 已完成快速开始
2. 📖 阅读 README.md 了解更多功能
3. 🔍 在你的项目上运行扫描
4. 📊 生成报告进行分析
5. 🔧 根据需要自定义规则

## 💬 故障排除

### 问题: Permission denied
```bash
# 解决
chmod +x scan.sh
bash scan.sh ~/code/
```

### 问题: Python module not found
```bash
# 确保在项目目录运行
cd /home/wangzekai/TOP14/insecure_file_uploads/insecure_upload_sink_detector
bash scan.sh ~/code/
```

### 问题: No sinks found
这是正常的 - 表示没有检测到漏洞。尝试在有代码的目录运行。

## 📞 获取帮助

```bash
# 查看scan.sh选项
bash scan.sh --help

# 查看Python CLI选项
python cli.py --help

# 查看项目文档
cat README.md
cat USAGE.md
```

---

**准备好了吗？** 运行以下命令开始：
```bash
bash scan.sh ~/WebGoat/
```
