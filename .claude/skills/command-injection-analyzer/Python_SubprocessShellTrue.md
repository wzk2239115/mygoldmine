# Python Subprocess Shell=True 命令注入

## Details

**审计等级：L3（逐行读）/ L4（跨模块追踪）**

**危险函数特征：**
- `subprocess.run(cmd, shell=True)`
- `subprocess.call(cmd, shell=True)`
- `subprocess.Popen(cmd, shell=True)`
- `subprocess.check_output(cmd, shell=True)`
- `subprocess.check_call(cmd, shell=True)`

**快速定位核心操作：**
1. 全局搜索 `shell=True` 关键字
2. 追溯命令字符串来源：是否包含变量拼接（`+`、`f""`、`.format()`、`%s`）
3. 变量回溯：追踪到数据源头（request参数、用户输入、数据库、配置文件）
4. 特别关注：动态构造的文件名/路径/参数传入命令

**快速定位保护机制：**
- 白名单校验：`if input in ['allowed1', 'allowed2']`
- 正则过滤：`re.match(r'^[a-zA-Z0-9]+$', input)`
- shlex转义：`shlex.quote(user_input)`
- 参数化传递：改用 `shell=False` + list 形式

**代码示例：**
```python
# 危险：用户输入直接拼接
filename = request.GET.get('file')
subprocess.run(f"cat /data/{filename}", shell=True)

# 危险：格式化字符串
cmd = "ping -c 4 %s" % user_ip
subprocess.call(cmd, shell=True)
```

## Classify

**漏洞（High）：**
- 外部输入（HTTP参数、表单、Cookie、Header）直接或间接拼接进命令字符串
- 无任何过滤或仅有黑名单过滤（易绕过）
- 命令执行结果返回给用户或影响业务逻辑

**误报：**
- 命令字符串完全硬编码，无任何动态部分
- `shell=True` 存在但命令不包含任何变量：`subprocess.run("ls -la", shell=True)`

**代码异味（Medium）：**
- 输入来自配置文件、环境变量但缺少校验
- 有白名单校验但范围过宽（如允许所有字母数字+特殊符号）
- 输入经过部分清洗但不完整（只过滤`;`和`|`，遗漏`$()` `` `command` ``等）
- 间接拼接：`user_input` → `function_A` → `function_B` → `subprocess`（需L4追踪）

## Low risk

**以下情况评为低风险：**
- 输入来源为管理员专属功能，且有严格权限控制（RBAC）
- 使用了 `shlex.quote()` 对所有外部输入进行转义
- 白名单极为严格且业务合理（如：仅允许3个固定值）
- 已改用 `shell=False` 并以列表形式传参（最佳实践）
- 输入仅用于命令执行的非关键部分且有长度限制（如环境变量名称）
- 代码运行在隔离沙箱环境（Docker with --read-only, 无敏感权限）
