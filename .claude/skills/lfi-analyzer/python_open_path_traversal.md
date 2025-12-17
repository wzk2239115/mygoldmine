# Python open()/pathlib 路径遍历与文件包含

## Details

### 漏洞成因

Python 应用使用 `open()`、`pathlib.Path()`、`os.path.join()`、`os.path.expanduser()` 等函数读取文件时，若直接将用户输入拼接到文件路径而未做路径规范化和白名单验证，攻击者可利用 `../` 相对路径实现目录遍历，访问应用目录外的敏感文件（如 `/etc/passwd`、配置文件、密钥）。此漏洞常见于文件下载接口、日志查看、配置读取、图片上传预览等功能。

### 代码示例

**易受攻击的代码（文件下载）：**
```python
from flask import Flask, request, send_file

app = Flask(__name__)
BASE_DIR = '/var/www/uploads/'

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(BASE_DIR, filename)  # filename=../../etc/passwd
    with open(file_path, 'rb') as f:
        return send_file(f)
```

**pathlib 版本：**
```python
from pathlib import Path
from flask import Flask, request

app = Flask(__name__)
BASE_DIR = Path('/var/www/uploads/')

@app.route('/read/<filename>')
def read_file(filename):
    file_path = BASE_DIR / filename  # filename=../../etc/passwd
    return file_path.read_text()
```

**日志查看接口：**
```python
import os
from django.http import HttpResponse

def view_log(request):
    log_file = request.GET.get('log')  # log=../../var/log/app.log
    log_path = f"/var/log/app/{log_file}"
    with open(log_path, 'r') as f:
        return HttpResponse(f.read())
```

**配置文件加载：**
```python
def load_config(config_name):
    config_path = f"config/{config_name}.json"  # config_name=../../sensitive
    with open(config_path, 'r') as f:
        return json.load(f)
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）

**关键词扫描：**
- 文件读取：`open()`, `read()`, `read_text()`, `read_bytes()`
- 路径操作：`os.path.join()`, `Path()`, `pathlib`, `os.path.expanduser()`, `os.path.abspath()`
- 文件访问：`exists()`, `is_file()`, `stat()`, `open()`
- 发送文件：`send_file()`, `FileResponse()`, `StreamingHttpResponse()`
- 输入源：`request.args`, `request.GET`, `request.POST`, `request.form`, `sys.argv`

**定位步骤：**
1. 搜索 `open(` 并检查参数是否包含变量（特别是来自 HTTP 请求或命令行的变量）。
2. 查找路径拼接操作：`f-string` 、`str.format()`、`.join()` 等与文件路径相关的字符串操作。
3. 跳读确认是否存在 `realpath()`、`abspath()` 或白名单验证。

#### 保护机制定位（审计等级：L2-L3）

**检查是否存在：**
- **路径规范化：** `os.path.realpath()`, `os.path.abspath()`, `Path.resolve()`
- **前缀校验：** 规范化后检查 `startswith()` 基础目录
- **白名单验证：** 将用户输入与已知安全文件列表对比
- **路径分隔符检查：** 禁止 `/`, `\`, `..` 等危险字符
- **符号链接检查：** `os.path.islink()` 或 `Path.is_symlink()`

**定位技巧：**
- 确认 `realpath()` 返回值是否真实用于后续操作，若返回 `None` 或异常是否被捕获。
- 检查白名单逻辑：使用 `in` 列表或字典查询是否比 `startswith()` 比较安全。
- 验证符号链接处理：若未检查符号链接，攻击者可创建符号链接指向敏感文件。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单映射 + 文件名索引 | **L0（快速跳过）** | 用户输入仅为键值 |
| `realpath()` + `startswith()` 前缀校验 | **L2（跳读）** | 确认校验逻辑完备 |
| 直接拼接用户输入 | **L3（逐行读）** | 极高风险 |
| 符号链接 + 目录遍历 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **用户可控路径** 用于文件读取或访问。
2. **缺乏有效防护**（无路径规范化、白名单、符号链接检查）。
3. **能够访问敏感资源**（读取配置、密钥、系统文件）。

#### 误报

可视为误报的情况：
1. **输入仅用于索引白名单字典**，返回固定文件。
2. **路径经 `realpath()` 规范化并检查前缀**。
3. **使用固定常量或框架内部构造的路径**。

#### 代码异味

需记录的潜在问题：
1. **仅使用 `basename()` 去除目录**，仍可利用双写或编码绕过。
2. **字符串替换而非规范化**（如 `.replace('..', '')` 可被双层绕过 `....//`）。
3. **符号链接未检查**，攻击者可创建符号链接绕过目录限制。
4. **异常处理不当**，错误消息泄露文件系统结构。

## Low risk

### 低风险评级场景

#### 1. 受控后台操作

- **场景：** 功能仅对管理员开放，认证与授权完善。
- **风险评估：** 外部攻击面小，但需防止账号滥用。

#### 2. 白名单保护 + 路径规范化

- **场景：** 使用 `realpath()` 规范化路径，检查 `startswith()` 前缀，且白名单完整。
- **风险评估：** 防护有效，但需确认白名单覆盖所有包含点。

#### 3. 容器/沙箱隔离

- **场景：** 应用运行在限制权限的容器或 chroot 中，访问目录层级有限。
- **风险评估：** 限制破坏面，但建议修复代码根本问题。

#### 4. 只读公开目录

- **场景：** 仅访问公开静态资源，无敏感信息（如公开图片库）。
- **风险评估：** 危害有限，但仍可能泄露目录结构。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员限定 | 攻击面小 | 中 |
| `realpath()` + 前缀校验 | 有效防护 | 低 |
| 符号链接检查 + 白名单 | 深度防御 | 低 |
| 容器/沙箱运行 | 限制影响面 | 高（持续跟进修复）|
