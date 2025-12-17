# Python Flask Redirect User Input

## Details

### 漏洞成因
Flask 框架的 `redirect()` 函数接受用户控制的 URL 参数直接进行重定向，当应用未对重定向目标进行严格的域名验证时，攻击者可以构造恶意 URL 将用户引导至任意外部站点。此漏洞的核心在于：

1. **输入接收**：应用直接从 HTTP 请求参数（query string、form data、JSON payload）中获取 URL
2. **信任假设**：开发者假设用户会访问预期的重定向目标，未进行白名单或格式验证
3. **执行无防护**：调用 `redirect(user_input)` 不经过任何安全检查即执行重定向

### 代码示例与定位技巧

**典型漏洞模式：**
```python
from flask import Flask, redirect, request

app = Flask(__name__)

@app.route('/login')
def login():
    next_url = request.args.get('next', '/')
    # 直接使用用户输入的 next 参数进行重定向
    return redirect(next_url)

@app.route('/verify')
def verify():
    redirect_to = request.form.get('redirect_url')
    return redirect(redirect_to)
```

**快速定位到核心操作的技巧** `[L1: 关键词扫描]`
- 搜索 `redirect(` 调用点，特别是参数来自 `request.args`、`request.form`、`request.json` 的情况
- 关键词模式：`redirect(request.args.get())`, `redirect(request.form.get())`, `redirect(request.json.get())`, `redirect(request.values.get())`
- 留意拼写变体：`redirect_to`, `next_url`, `return_url`, `back_url`, `goto`, `url`, `target` 等重定向相关参数名

**快速定位到保护机制的技巧** `[L2: 跳读]`
- 检查 `redirect()` 调用前是否存在：
  - URL 解析库验证：`urlparse()`、`urllib.parse.urlparse()` 获取 scheme 和 netloc
  - 域名白名单对比：`if parsed_url.netloc in ALLOWED_DOMAINS`
  - 相对 URL 强制：`if url.startswith('/') and not url.startswith('//')`
  - URL 验证库：`validators`、`django-security` 等第三方库的 URL 检查方法
- 观察是否存在不安全的保护尝试：
  - 仅检查 scheme：`if url.startswith('http')` 可被绕过（`javascript:`、`data:`）
  - 黑名单检查：`if 'http' not in url` 极易绕过（`//domain.com`, `///path`）
  - 正则表达式验证：需逐行审视正则是否存在缺陷

---

## Classify

### 漏洞 vs 误报 vs 代码异味的研判逻辑

**确定为漏洞的条件：**
1. `redirect()` 或等效重定向函数的参数完全或主要由用户输入组成
2. 参数未经过有效的白名单验证（相对路径强制、域名白名单、URL 格式验证）
3. 重定向目标可以指向任意外部站点（即能够突破域名限制）

**可能为误报的情况：**
1. 参数来自可信来源（数据库中的静态配置、环境变量、硬编码值）
2. 使用了有效的白名单验证：例如 `parsed_url.netloc in ALLOWED_DOMAINS`
3. 强制使用相对路径：`if url.startswith('/') and not url.startswith('//')` 能够阻止外部重定向
4. 使用了经过充分测试的安全库进行 URL 验证

**代码异味的识别：**
1. 存在不安全的验证尝试（黑名单、不完整的正则表达式）
2. 有条件判断但逻辑不严密（例如只检查 scheme 而不检查 netloc）
3. URL 验证在多个分支中不一致（某些路径绕过了验证）

---

## Low risk

### 低风险评级的场景

**仅在以下情况应评为低风险：**

1. **强制相对路径**：应用确保所有重定向目标都以单个前导斜杠开头，且排除了协议类重定向（`//domain.com` 形式），这样可以限制重定向仅限于同源路径

2. **严格的域名白名单**：开发者维护了一个明确的允许域名列表，使用 `urlparse()` 解析用户输入后，通过 `parsed_url.netloc in WHITELIST_DOMAINS` 进行校验，白名单包含所有可能的合法重定向目标域名

3. **URL 验证库的正确使用**：例如 `validators.url()` 库虽然主要用于格式验证，但结合白名单检查可以确保安全性

4. **不可控的参数源**：虽然调用了 `redirect()`，但其参数完全来自应用内部逻辑或配置文件，用户无法控制其值

5. **限制性的参数值**：例如 `next_url` 只能取特定的枚举值（`'/dashboard'`, `'/home'` 等），且在代码中进行了显式的值验证

**注意：** 低风险评级不等于零风险，仍需确认上述条件在所有调用路径中都被满足。
