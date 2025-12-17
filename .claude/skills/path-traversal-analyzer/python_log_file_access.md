# Python 日志文件访问路径遍历

## 漏洞成因
日志查看功能通过用户参数读取任意日志文件，缺乏路径白名单限制，允许攻击者通过路径遍历序列访问系统敏感文件。

---

## Details

### 代码示例

**危险模式：直接拼接用户输入**
```python
# Flask 路由示例
@app.route('/logs')
def view_log():
    log_name = request.args.get('file')  # 用户可控参数
    log_path = f'/var/logs/{log_name}'   # 简单拼接
    with open(log_path, 'r') as f:       # 直接读取
        return f.read()
```

**危险模式：使用 os.path.join**
```python
import os
log_file = request.GET.get('log')
full_path = os.path.join('/var/logs', log_file)  # 可被绝对路径绕过
content = open(full_path).read()
```

**危险模式：Django 文件下载**
```python
def download_log(request):
    filename = request.GET.get('name')
    file_path = LOG_DIR + filename  # 字符串拼接
    return FileResponse(open(file_path, 'rb'))
```

### 快速定位核心操作（审计等级：L1-L2）

**L1 关键词扫描：**
- 文件操作：`open()`, `read()`, `readlines()`, `Path().read_text()`
- 路径拼接：`os.path.join()`, `f'{base}/{user_input}'`, `+` 拼接
- 框架特定：`FileResponse()`, `send_file()`, `send_from_directory()`
- 参数获取：`request.args.get()`, `request.GET.get()`, `request.form[]`

**L2 跳读定位链：**
1. **入口点**：搜索路由函数中包含 "log/file/download/export" 关键词的参数名
2. **数据流**：追踪参数从获取 → 赋值 → 路径拼接 → 文件操作的完整链路
3. **核心标志**：用户输入直接或间接参与文件路径构造

### 快速定位保护机制（审计等级：L2-L3）

**L2 跳读检查：**
```python
# 正向检查
- basename() 使用：os.path.basename(user_input)
- realpath() 校验：os.path.realpath(path).startswith(base)
- 白名单匹配：if filename in ALLOWED_LOGS
- 正则限制：re.match(r'^[a-z0-9_]+\.log$', filename)

# 反向检查（无效防护）
- 黑名单过滤：'..' in filename（可编码绕过）
- 简单替换：filename.replace('..', '')（可双写绕过）
```

**L3 逐行审计要点：**
1. **路径规范化时机**：是否在所有拼接操作之后进行
2. **符号链接处理**：`os.path.realpath()` vs `os.path.abspath()`（后者不解析符号链接）
3. **编码绕过**：是否处理 URL 编码、双重编码
4. **绝对路径绕过**：`os.path.join('/base', '/etc/passwd')` 返回 `/etc/passwd`
5. **TOCTOU 竞态**：检查后使用前的时间窗口

**L4 跨模块追踪场景：**
- 路径前缀从配置文件/环境变量读取
- 中间件层面的路径预处理
- 自定义文件访问包装类

---

## Classify

### 漏洞判定标准
1. **存在用户可控输入**影响文件路径构造
2. **缺乏有效边界校验**（无白名单或 realpath 基础路径检查）
3. **可访问目标路径之外的文件**（通过 `../` 或绝对路径）

### 误报识别
- 参数值来自数据库/配置的枚举项，用户无法直接控制原始值
- 使用 `os.path.basename()` 后仅作为文件名（无目录部分）
- 硬编码路径字典映射：`FILES = {'app': 'app.log', 'db': 'db.log'}; path = FILES[user_input]`
- 已通过 `os.path.realpath()` 并校验前缀在白名单基础目录内

### 代码异味（潜在风险）
- 使用后缀白名单但允许目录遍历：`if filename.endswith('.log')`
- 路径拼接后仅检查目录部分：`if '/var/logs/' in full_path`（可包含绕过）
- 依赖前端参数限制而后端未验证
- 仅过滤 `..` 但允许绝对路径输入

---

## Low risk

### 低风险场景
1. **受限读取范围**：
   - 仅能访问日志目录内的文件，且该目录内无敏感信息
   - 日志文件通过定时清理机制自动脱敏

2. **权限隔离**：
   - 应用进程以低权限用户运行（如 `www-data`）
   - 文件系统权限限制仅能读取指定目录

3. **信息价值有限**：
   - 可访问文件仅包含公开或无敏感性的日志
   - 已通过其他接口公开相同信息

4. **防护部署**：
   - WAF/RASP 有效拦截路径遍历特征
   - 容器环境文件系统只读挂载

5. **业务逻辑限制**：
   - 需要高权限角色认证后才能访问
   - 访问频率限制 + 审计日志完善

**注意**：即使评为低风险，仍建议修复以符合安全编码规范。