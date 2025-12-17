# Python_Session_Cookie_Insecure

**漏洞类型**: Django/Flask 会话 Cookie 未设置 HttpOnly 和 Secure 标志，导致会话令牌可被 JavaScript 访问和在不安全通道传输，易被窃取

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# 示例1: Django Session Cookie 配置不安全
SESSION_COOKIE_HTTPONLY = False  # 允许 JavaScript 访问
SESSION_COOKIE_SECURE = False    # 允许 HTTP 传输
SESSION_COOKIE_SAMESITE = None   # 无 CSRF 保护

# 示例2: Flask 会话未配置安全属性
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # 过弱

# 示例3: 手动设置 Cookie，忽略安全标志
def login(request):
    response = HttpResponse('Login successful')
    response.set_cookie('session_id', session_token)
    # 缺少 httponly=True, secure=True, samesite='Strict'
    return response

# 示例4: Flask 手动设置不安全 Cookie
@app.route('/login', methods=['POST'])
def flask_login():
    response = make_response('Login successful')
    response.set_cookie('session_id', token, httponly=False, secure=False)
    return response

# 示例5: 环境依赖配置，生产环境未设置
if DEBUG:
    SESSION_COOKIE_SECURE = False  # 开发环境可接受
# 缺少非 DEBUG 时的正确设置

# 示例6: 多个会话 Cookie，部分不安全
response.set_cookie('session_id', token1, httponly=True, secure=True)
response.set_cookie('csrf_token', token2)  # 忘记设置安全属性
response.set_cookie('tracking_id', token3, httponly=False)  # 不必要

# 示例7: Cookie 覆盖不安全设置
def set_insecure_cookie(response, name, value):
    response.set_cookie(name, value, httponly=False, secure=False)
    # 通用函数被错误使用
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Session Cookie 配置: `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`
- Cookie 设置: `response.set_cookie()`, `set_cookie()`, 参数中的 `httponly`, `secure`, `samesite`
- 配置值: `False`, `None`, `'Lax'`, 缺少的安全参数
- 调试模式: `DEBUG = True`, `if DEBUG:` 下的不安全配置

**L2 跳读定位**:
- Django settings.py: 搜索 `SESSION_COOKIE_*` 配置
- Flask config: `app.config['SESSION_COOKIE_*']`
- 登录/注册处理函数: 所有 `set_cookie()` 调用
- 中间件或装饰器: 其中设置 Cookie 的代码
- 检查是否有环境特定配置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- HttpOnly 设置: 配置中 `SESSION_COOKIE_HTTPONLY = True`
- Secure 设置: `SESSION_COOKIE_SECURE = True`
- SameSite 设置: `SESSION_COOKIE_SAMESITE = 'Strict'` 或 `'Lax'`

**L3 逐行分析**:
- Django 配置:
  - 检查 `SESSION_COOKIE_HTTPONLY` 是否为 `True`
  - 检查 `SESSION_COOKIE_SECURE` 是否为 `True` (生产环境)
  - 检查 `SESSION_COOKIE_SAMESITE` 是否为 `'Strict'` 或 `'Lax'`
  - 检查 `SESSION_COOKIE_AGE` 是否设置合理 (建议 1800 - 3600 秒)
  - 检查是否有 `CSRF_COOKIE_HTTPONLY`, `CSRF_COOKIE_SECURE` 等 CSRF token 的配置
- Flask 配置:
  - `app.config['SESSION_COOKIE_HTTPONLY']`, `SECURE`, `SAMESITE`
  - 是否依赖环境变量或 `os.environ`
  - 是否在所有环境中一致设置
- set_cookie() 调用:
  - 每个 `set_cookie()` 是否都有 `httponly=True, secure=True, samesite='Strict'`
  - 是否有默认参数函数，这些默认参数是否安全
  - Cookie 名称是否暴露了敏感信息
- 中间件:
  - 是否有统一的 Cookie 设置函数
  - 是否在中间件中修改了 Session Cookie 属性

**L4 跨模块追踪**:
- 追踪所有 set_cookie() 调用的位置和参数
- 检查是否有多个地方设置 Cookie，配置是否一致
- 验证 CSRF token 的 Cookie 是否也有安全保护
- 检查第三方库是否设置了额外的 Cookie
- 审查 WSGI/ASGI 中间件的 Cookie 处理

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- `SESSION_COOKIE_HTTPONLY = False` 或未设置，JavaScript 可访问会话 Cookie
- `SESSION_COOKIE_SECURE = False` 或未设置，会话 Cookie 在 HTTP 传输
- `SESSION_COOKIE_SAMESITE = None` 或未设置，无 CSRF 保护
- 生产环境中有 Cookie 未设置 HttpOnly 或 Secure 标志
- 存在多个 set_cookie() 调用，某些缺少安全属性

**误报判定**:
- `SESSION_COOKIE_HTTPONLY = True`, `SECURE = True`, `SAMESITE = 'Strict'` 全部设置
- 所有需要保护的 Cookie 都有完整的安全属性
- 应用全站使用 HTTPS，Secure 标志必须设置
- 不同环境有不同配置，生产环境完全安全

**代码异味**:
- 配置中存在 `if DEBUG:` 但非 DEBUG 时配置缺失
- CSRF token 的 Cookie 安全属性与 Session Cookie 不一致
- 某些旧的 set_cookie() 调用缺少安全参数
- 有注释说明某个标志为什么禁用，但理由不充分
- Cookie 属性在多处修改，最终值不确定

---

## Low risk

### 低风险场景

**架构保护**:
- 会话数据不包含敏感信息，仅包含匿名 ID
- 应用 URL 和资源无法通过 JavaScript 直接访问
- 敏感操作需要额外的 CSRF token 或验证

**技术防御**:
- 部署了 WAF 或网关级的 XSS 防护
- 使用了 Content Security Policy (CSP) 限制脚本执行
- 应用有完整的 XSS 防护，Cookie 即使被 JavaScript 访问也无法利用

**监控与检测**:
- 实时检测 Cookie 被异常访问或修改的行为
- 记录所有登录会话的 IP 和 User-Agent
- 检测到异常时自动登出并通知用户
