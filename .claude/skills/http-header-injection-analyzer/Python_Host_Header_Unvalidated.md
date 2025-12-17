# Python Flask/Django Host头未验证

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `request.host`, `request.headers['Host']`, `HTTP_HOST`, `get_host()`, `request.META`, `url_for`, `redirect`, `ALLOWED_HOSTS`
- **快速检查：** Host头是否用于URL构造、重定向、邮件链接，是否有域名白名单验证

## 漏洞成因

Flask的`request.host`和Django的`request.get_host()`直接返回客户端发送的Host头，攻击者可完全控制。若未验证直接用于密码重置链接、OAuth回调、重定向URL等场景，可导致密码重置投毒、开放重定向、缓存中毒等攻击。

### 常见漏洞模式

```python
# ✗ 漏洞：Flask Host头用于密码重置链接
from flask import request, url_for

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form['email']
    token = generate_reset_token(email)
    # Host头未验证
    reset_link = f"https://{request.host}/reset?token={token}"
    send_email(email, f"Reset your password: {reset_link}")
    # 攻击: Host: evil.com -> 发送钓鱼链接
    return "Email sent"
```

```python
# ✗ 漏洞：Django Host用于重定向
from django.shortcuts import redirect

def login_view(request):
    if request.user.is_authenticated:
        # Host头用于构造重定向URL
        return redirect(f"https://{request.get_host()}/dashboard")
    return render(request, 'login.html')
```

```python
# ✗ 漏洞：X-Forwarded-Host优先使用
@app.route('/api/config')
def api_config():
    host = request.headers.get('X-Forwarded-Host', request.host)
    return jsonify({
        'api_url': f'https://{host}/api',
        'ws_url': f'wss://{host}/ws'
    })
    # 攻击者控制X-Forwarded-Host，响应可能被缓存
```

```python
# ✗ 漏洞：OAuth回调地址构造
@app.route('/oauth/start')
def oauth_start():
    callback = f"https://{request.host}/oauth/callback"
    auth_url = f"https://auth.provider.com/authorize?redirect_uri={callback}"
    return redirect(auth_url)
    # 攻击者劫持OAuth授权码
```

```python
# ✓ 修复：白名单验证
ALLOWED_HOSTS = {'example.com', 'www.example.com', 'api.example.com'}

def get_safe_host():
    host = request.host.split(':')[0].lower()  # 移除端口
    if host in ALLOWED_HOSTS:
        return host
    return 'example.com'  # 默认安全值

@app.route('/forgot-password', methods=['POST'])
def forgot_password_safe():
    email = request.form['email']
    token = generate_reset_token(email)
    safe_host = get_safe_host()
    reset_link = f"https://{safe_host}/reset?token={token}"
    send_email(email, f"Reset your password: {reset_link}")
    return "Email sent"
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 密码重置/邮件链接 | 搜索 `reset.*host\|host.*token\|host.*email`，检查链接构造 |
| **P0** | 重定向URL构造 | 搜索 `redirect.*host\|Location.*host`，检查白名单 |
| **P0** | OAuth回调地址 | 搜索 `callback.*host\|redirect_uri.*host`，检查域名验证 |
| **P1** | API响应中的URL | 搜索 `host.*json\|host.*url`，检查是否被缓存 |
| **P1** | X-Forwarded-Host | 搜索 `X-Forwarded-Host\|HTTP_X_FORWARDED_HOST`，检查代理场景 |
| **P2** | 日志或配置使用 | 搜索 `host.*log\|host.*config`，评估影响 |

### 审计专业技巧

#### 1. 数据流追踪技术
- **起点识别**：从`request.host`、`request.get_host()`、`request.META['HTTP_HOST']`、`request.headers['Host']`开始追踪
- **中间过程**：记录变量名、函数传参、字符串拼接、格式化操作
- **终点判定**：输出点是否外部可见（Response Body、Location Header、邮件内容、日志中被第三方访问）
- **关键标记**：函数内是否存在验证逻辑，验证逻辑是否完整

#### 2. 区分真实漏洞vs误报的关键

**真实漏洞特征：**
- Host头直接用于`redirect()`、邮件发送函数的参数、OAuth redirect_uri构造
- 验证缺失或验证逻辑不完整（如只检查是否包含`.com`）
- 外部可见性强：邮件、重定向、API公开响应
- 威胁模型清晰：可导致钓鱼、session固定、缓存中毒

**常见误报情形：**
```python
# ✓ 误报1：仅用于日志，无外部可见性
logger.info(f"Request from host: {request.host}")

# ✓ 误报2：用于内部验证后被覆盖
host = request.host
if not host.endswith('.internal'):
    return abort(403)
# 后续只使用已验证的host

# ✓ 误报3：用于服务内的统计分析，不影响安全决策
request_stats[request.host] = request_stats.get(request.host, 0) + 1

# ✓ 误报4：Django已在中间件验证（ALLOWED_HOSTS生效）
from django.conf import settings
if request.host not in settings.ALLOWED_HOSTS:
    # Django已拒绝请求，不会到达此处
    pass
```

**易混淆的灰色地带：**
- Host用于构造内网API请求URL（需评估网络隔离）
- Host用于日志，但日志被CDN缓存（属于缓存中毒风险）
- Host用于生成唯一键用于数据库查询（需检查是否有注入）

#### 3. 审计现场检查技能

**步骤1：快速定位**
```bash
# 一步到位找出所有Host使用点
grep -rn "request\.host\|get_host\|HTTP_HOST\|X-Forwarded" --include="*.py" src/
```

**步骤2：逐个分析**
- 打开文件，找到使用行
- 向上看5-10行：确认是否有输入验证（if语句、try-except）
- 向下看5-10行：确认Host数据流向（赋值给什么变量，在哪里使用）
- 跨文件追踪：如果传给函数，打开函数定义检查处理方式

**步骤3：构造测试用例**
```
正常请求：Host: example.com
测试用例1（重定向）：Host: evil.com -> 检查Location头
测试用例2（邮件）：手工发起请求，查看收到的邮件链接
测试用例3（缓存）：Host: attacker.com，然后用正常Host访问，检查响应是否被污染
```

**步骤4：验证修复**
- Django应用：检查`ALLOWED_HOSTS`设置是否包含通配符
- Flask应用：搜索所有Host使用前是否都有白名单检查
- 代理场景：确认`X-Forwarded-Host`是否被代理层（nginx/haproxy）覆盖设置

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 使用环境变量或配置文件域名 | **跳过**，无Host头使用 |
| **L1** | 仅日志记录使用Host头 | 关键词扫描确认无安全影响 |
| **L2** | 单函数内Host用于URL构造 | 检查白名单验证 |
| **L3** | Host跨模块传递 | 逐行追踪数据流 |
| **L4** | 中间件或代理层处理 | 跨模块检查Host验证位置 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. Host头用于构造外部可见URL（重定向、邮件、回调）
2. 无白名单验证
3. 影响安全功能

### 典型漏洞特征（满足任一项即确认）
- ✗ `f"https://{request.host}/reset?token={token}"` 用于邮件
- ✗ `redirect(f"https://{request.get_host()}/path")` 无验证
- ✗ OAuth回调URL使用未验证的Host
- ✗ API响应包含Host构造的URL且被缓存

### 安全排除（任一项充分）
- ✓ 白名单验证：`if host in ALLOWED_HOSTS`
- ✓ Django `ALLOWED_HOSTS`配置且不包含`*`
- ✓ 使用环境变量：`os.environ.get('APP_URL')`
- ✓ 配置文件固定域名
- ✓ 代理层验证Host头（如nginx proxy_set_header）

### 灰色判定（风险较低但需注意）
- 内网应用
- 有CDN/代理层验证
- 仅影响非安全功能

#### 真实案例与误报识别

**案例1：缓存中毒vs安全**
```python
# ✗ 真实漏洞：API响应被CDN缓存
@app.route('/api/user-profile')
@cache.cached(timeout=3600)  # 设置缓存
def get_user_profile():
    api_url = f"https://{request.host}/api/internal/user"
    return jsonify({'profile_url': api_url})
# 攻击流程：Host:attacker.com -> CDN缓存返回attacker.com的URL -> 其他用户访问获得污染数据

# ✓ 安全实现：带用户标识的缓存键
@app.route('/api/user-profile')
def get_user_profile():
    safe_host = config.CANONICAL_HOST
    cache_key = f"profile:{request.user.id}"
    return jsonify({'profile_url': f"https://{safe_host}/api/internal/user"})
```

**案例2：X-Forwarded-Host验证不完整**
```python
# ✗ 不完整验证：只检查存在性
@app.route('/auth/callback')
def oauth_callback():
    host = request.headers.get('X-Forwarded-Host') or request.host
    # 验证代理设置
    if not request.headers.get('X-Forwarded-For'):
        return abort(400)
    # 但没有验证X-Forwarded-Host内容，仍然易受攻击
    redirect_uri = f"https://{host}/auth/success"
    return redirect(redirect_uri)

# ✓ 正确做法：完整的信任链验证
TRUSTED_PROXIES = {'10.0.0.1', '10.0.0.2'}
@app.route('/auth/callback')
def oauth_callback():
    client_ip = request.remote_addr
    if client_ip not in TRUSTED_PROXIES:
        host = request.host  # 不信任代理头
    else:
        host = request.headers.get('X-Forwarded-Host', request.host)
        # 进一步验证主机名
        if not host in ALLOWED_HOSTS:
            return abort(400)
    return redirect(f"https://{host}/auth/success")
```

**案例3：邮件链接中的隐藏风险**
```python
# ✗ 易被遗漏的漏洞：在模板中使用Host
# email_template.html
# 密码重置链接：{{ base_url }}/reset?token={{ token }}
# 若base_url来自request.host，HTML转义不能防止此类攻击

# ✓ 审计检查：必须追踪模板数据源
# views.py
def send_reset_email(email):
    # 需要确认此处传入的base_url是否来自request.host
    reset_url = f"{request.host}/reset?token={token}"  # ✗ 漏洞
    return render_template('email.html', reset_url=reset_url)

# ✓ 正确修复
def send_reset_email(email):
    reset_url = f"{settings.BASE_URL}/reset?token={token}"  # ✓ 安全
    return render_template('email.html', reset_url=reset_url)
```

**实战审计经验总结：**
1. **邮件发送函数前后**：是最容易被遗漏的位置，需重点关注`send_mail`、`send_email`、模板渲染等
2. **重定向链调查**：跟踪`redirect()`调用处理，记录`Location`响应头的生成过程
3. **代理场景验证**：若使用代理，需确认代理层是否设置了`X-Forwarded-Host`（通过nginx/haproxy配置检查）
4. **异步任务中的Host**：Celery任务获取request.host会导致延迟使用过期数据，需特别关注

---

## 实现建议

### 核心防护方案

**方案1：白名单验证**
```python
import os

ALLOWED_HOSTS = set(os.environ.get('ALLOWED_HOSTS', 'example.com').split(','))

def validate_host(host):
    host_lower = host.split(':')[0].lower()
    if host_lower in ALLOWED_HOSTS:
        return host_lower
    return None

@app.before_request
def check_host():
    if not validate_host(request.host):
        abort(400, "Invalid Host header")
```

**方案2：使用环境变量**
```python
import os

APP_BASE_URL = os.environ.get('APP_BASE_URL', 'https://example.com')

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form['email']
    token = generate_reset_token(email)
    # 使用固定的基础URL
    reset_link = f"{APP_BASE_URL}/reset?token={token}"
    send_email(email, f"Reset your password: {reset_link}")
    return "Email sent"
```

**方案3：Django配置**
```python
# settings.py
ALLOWED_HOSTS = ['example.com', 'www.example.com']
USE_X_FORWARDED_HOST = False  # 禁用X-Forwarded-Host

# views.py
from django.conf import settings

def get_base_url(request):
    # 优先使用配置
    if hasattr(settings, 'BASE_URL'):
        return settings.BASE_URL
    # 安全地使用Host（已被ALLOWED_HOSTS验证）
    return f"https://{request.get_host()}"
```

### 检查清单
- [ ] 所有Host使用点添加白名单验证
- [ ] 密码重置链接使用配置的固定域名
- [ ] OAuth回调使用预注册的白名单URL
- [ ] Django配置`ALLOWED_HOSTS`不包含`*`
- [ ] `USE_X_FORWARDED_HOST = False`或代理层验证
- [ ] 测试Host头注入：`Host: evil.com`

---

## 修复优先级

1. **立即修复**：密码重置/OAuth回调使用未验证Host头
2. **本周修复**：所有重定向添加Host白名单验证
3. **可选加强**：使用环境变量替代动态Host获取
4. **长期优化**：添加Host验证中间件

