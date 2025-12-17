# Python OAuth 回调重定向漏洞审计指南

## Details

OAuth 流程中，授权服务器在用户授权后将验证码或令牌通过 `redirect_uri` 参数返回给应用客户端。若应用对 `redirect_uri` 参数缺乏严格验证，攻击者可以控制重定向目标，将授权码或 token 窃取到恶意服务器。

### 核心操作代码定位

对应代码示例（快速定位漏洞点）：
```python
# Flask/Django 中的 OAuth 回调处理
@app.route('/oauth/callback', methods=['GET'])
def oauth_callback():
    code = request.args.get('code')
    redirect_uri = request.args.get('redirect_uri')  # 危险：未验证

    # 直接使用用户提供的 redirect_uri
    response = requests.post(
        'https://auth-server.com/token',
        data={
            'code': code,
            'redirect_uri': redirect_uri,  # 可被控制
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
    )
    token = response.json()['access_token']

    # 危险操作：重定向到用户控制的地址
    return redirect(redirect_uri)  # open redirect 漏洞
```

**快速定位核心操作的技巧** [L1:关键词扫描]
- 搜索 `redirect(`, `redirect_uri`, `return_to`, `next_url` 等参数获取相关代码
- 查找 HTTP 重定向相关方法：Flask 的 `redirect()`, Django 的 `HttpResponseRedirect()`, Werkzeug 的 `redirect()`
- 检查 GET/POST 参数中是否直接接收重定向目标

**快速定位保护机制的技巧** [L2:跳读]
- 在回调处理函数中查找 `redirect_uri` 的预先定义列表或白名单验证
- 查找 URL 校验函数：`urlparse()`, `urllib.parse.urlparse()`, 自定义的 URL 验证函数
- 检查是否调用了 `is_safe_url()` 或类似的安全检查函数
- 查找配置文件中的 `ALLOWED_REDIRECT_URIS`, `OAUTH_REDIRECT_WHITELIST` 等白名单配置

---

## Classify

### 漏洞判定标准

**确认为漏洞的条件：**
1. OAuth 回调端点接收 `redirect_uri` 或类似参数，且该参数可由攻击者控制
2. 应用未对参数值进行白名单校验（仅依赖黑名单或格式检查是不充分的）
3. 存在跨域重定向场景：
   - 绝对 URL 重定向到任意外部域名（如 `https://attacker.com/steal?token=xxx`）
   - 协议切换（如 `http://` 变 `https://`，或 `//` 协议相对 URL）
   - 双重编码或特殊字符绕过（如 `%252e%252e/`, 127.0.0.1 与 localhost 混淆）
4. 验证流程存在漏洞：
   - 仅检查 URL 前缀（如 `startswith('https')`），可被 `https://attacker.com@trusted.com` 绕过）
   - 仅检查域名部分，未检查路径（如允许任意路径重定向到目标域）
   - 白名单校验在重定向前被移除或被条件语句绕过

### 误报识别

**以下情况可能为误报或误检：**
1. 参数名为 `state` 而非 `redirect_uri`，且其值仅用于返回时附加在 URL 中（`state` 本身无需加密，但不应用于重定向目标）
2. 重定向目标为相对路径且已正确验证（如 `/dashboard`, `/profile`）
3. 重定向发生于同源内，且经过 URL 规范化和路径遍历防护
4. 存在 CSRF token 或其他会话绑定机制，降低实际风险

### 代码异味识别

**值得深入审计的代码异味：**
1. 使用了可能被绕过的验证方式：
   - `in`, `contains`, `startswith` 等字符串方法而非完整 URL 解析
   - 正则表达式验证不够严格（如 `^https?://.*` 未固定域名）
   - 多次解析或转换导致验证绕过（URL 编码/解码不一致）
2. 参数来源不清晰：
   - 从 session、cookie、header 等多个来源获取，未统一验证
   - OAuth 配置来自数据库或外部配置中心，未在应用启动时验证
3. 条件逻辑复杂：
   - 多个 if-elif 分支，某些分支可能遗漏白名单检查
   - 开发/测试环境使用宽松的验证规则，生产环境规则变严格但测试不充分

---

## Low risk

### 低风险评级场景

**以下情况可被评定为低风险：**

1. **完整白名单验证且配置可控**
   - 应用维护预定义的 OAuth 回调 URL 白名单（如 `OAUTH_REDIRECT_URIS = {'https://myapp.com/callback', 'https://mobile.myapp.com/callback'}`)
   - 重定向前对 `redirect_uri` 进行精确匹配验证
   - 白名单配置在应用启动时验证，不可在运行时动态修改

2. **不存在外部重定向**
   - 应用仅重定向到内部相对路径（如 `/dashboard?token=xxx`）
   - 使用框架的相对路径重定向机制，确保不会跳出应用域名

3. **充分的会话绑定保护**
   - OAuth `state` 参数与服务端 session 绑定，且验证严格
   - 即使攻击者构造了重定向链接，也无法通过 CSRF 或 state 验证
   - 令牌仅可在特定用户会话内使用，不可跨会话转移

4. **架构设计隔离**
   - OAuth token 不在 URL 中传递（通过 POST body 或隐藏的 HTTPS 通道返回）
   - 回调端点不直接暴露 token 给前端，而是在服务端完成 token 交换
   - 重定向目标与 token 处理逻辑分离，减少 token 泄露的直接风险
