# Python 登录重定向 URL 未校验

登录成功后将用户重定向到 `return_url` 参数，但未对目标域名进行验证，允许攻击者将用户重定向到任意外部网站。

## Details

### 代码示例

典型的易发漏洞代码：

```python
from flask import Flask, request, redirect

@app.route('/login', methods=['POST'])
def login():
    if authenticate(request.form['username'], request.form['password']):
        return_url = request.args.get('return_url', '/')
        return redirect(return_url)  # 直接重定向，无任何验证
```

### 核心操作快速定位技巧（审计等级：L1 - 关键词扫描）

重定向操作通常出现在以下位置，扫描这些关键词可快速定位：
- **关键函数**：`redirect()`、`HttpResponseRedirect()`、`Response.set_cookie(location=...)`、`return` 语句中的 URL 拼接
- **HTTP 响应头**：`Location`、`Refresh`、`X-Redirect`
- **JavaScript 重定向**：`window.location = `、`window.location.href = `、`document.location = `

搜索模式：
```
redirect\s*\(\s*(request\.|flask\.|django\.)
location\s*=\s*request\.
window\.location\s*=\s*.*request\.
```

### 保护机制快速定位技巧（审计等级：L2 - 跳读）

需要检查以下保护措施是否存在：

1. **白名单验证**（最优）
```python
ALLOWED_DOMAINS = {'example.com', 'api.example.com'}

def is_safe_redirect(url):
    parsed = urlparse(url)
    return parsed.netloc in ALLOWED_DOMAINS
```

2. **URL 格式校验**
```python
from urllib.parse import urlparse

def is_safe_redirect(url):
    parsed = urlparse(url)
    # 检查是否为相对 URL（本地重定向）
    return parsed.netloc == '' and not url.startswith('//')
```

3. **协议检查**
```python
if url.startswith(('http://', 'https://')):
    # 额外验证逻辑
```

审计要点：
- 检查白名单是否完整（不应包含用户可控制的值）
- 检查是否仅允许相对路径（`/path`）或特定域名
- 检查协议限制是否正确（禁止 `javascript:`、`data:` 等）
- 检查验证逻辑是否在所有重定向入口都被应用（跨模块追踪 - L4）

---

## Classify

### 漏洞特征判定

**确认为漏洞**的条件：
1. 重定向 URL 直接来自 HTTP 请求参数（`request.args`、`request.form`、`request.GET` 等）
2. 未经任何域名/URL 格式验证直接用于 HTTP 重定向
3. 多个重定向入口存在相同问题（如登录、退出、授权完成等均未校验）

**判定为误报**的条件：
1. URL 只能来自应用内部生成（如数据库查询结果，且数据源可信）
2. 参数经过白名单验证，且白名单完全由代码定义（无外部输入）
3. 使用了安全的框架级 API（如某些框架的 `is_safe_url()` 等内置函数且配置正确）

**识别代码异味**（可能存在隐患）：
1. 重定向前有字符串替换、URL 编码操作，但缺少域名验证
2. 注释中提及"临时禁用 URL 校验"、"待修复"等
3. 多个重定向端点实现不一致，部分有验证、部分无
4. 使用了过于宽松的正则表达式（如 `.*example\.com.*` 能匹配 `fake-example.com.attacker.com`）

---

## Low risk

### 低风险场景评级

以下情况可评定为低风险：

1. **完全相对路径重定向**
   - 条件：只允许 `/path` 开头的重定向，完全禁止协议前缀（无 `://`）和双斜杠 `//`
   - 示例：`/account/settings`、`/` 有效，`//attacker.com`、`https://attacker.com` 被拒绝
   - 审计风险：需检查是否真的拒绝了所有绝对 URL 形式

2. **严格白名单验证**
   - 条件：域名白名单完全硬编码、不可动态修改、白名单覆盖所有重定向出口
   - 示例：允许 `example.com`、`api.example.com`，其他所有域名拒绝
   - 审计风险：确认白名单来源可信且无遗漏的重定向入口

3. **内部重定向机制**
   - 条件：用户无法控制 URL 参数，参数由应用内部生成或从可信源（数据库、配置文件）读取
   - 示例：根据用户角色自动生成的重定向路径
   - 审计风险：追踪参数来源，验证用户确实无法篡改

4. **非浏览器重定向**
   - 条件：返回重定向给移动端应用或第三方系统，这些客户端不会解释恶意重定向
   - 审计风险：低但需注意日志记录、API 返回值是否泄露 URL 信息

### 升级风险场景

即使上述条件部分满足，以下情况应升级风险：
- 白名单中包含用户可注册的子域名（`*.example.com`）
- 使用了黑名单而非白名单（`if url != 'attacker.com'`）
- 校验仅在某个特定用户流程中进行，其他流程缺失（跨模块不一致）
- 重定向用于敏感操作前（如修改密码验证、支付确认等）
