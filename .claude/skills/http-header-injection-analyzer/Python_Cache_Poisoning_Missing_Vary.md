# Python 缓存中毒Vary头缺失

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `Vary`, `Cache-Control`, `cache`, `redis`, `memcached`, `@cached`, `make_response`, `ETag`, `X-Forwarded-`
- **快速检查：** 响应是否可被缓存，Vary头是否包含所有影响响应内容的请求头

## 漏洞成因

当Web应用响应内容根据请求头（如`Accept-Language`、`User-Agent`、`X-Forwarded-Host`）变化，但`Vary`头未正确声明这些头字段时，CDN或代理缓存可能返回错误内容给不同用户。攻击者可利用此缺陷实施缓存中毒攻击。

### 常见漏洞模式

```python
# ✗ 漏洞：响应依赖Accept-Language但Vary缺失
@app.route('/api/messages')
def get_messages():
    lang = request.headers.get('Accept-Language', 'en')
    messages = load_messages(lang)  # 响应依赖语言
    resp = make_response(jsonify(messages))
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    # 缺少 Vary: Accept-Language
    return resp
    # 攻击: 缓存中文响应，其他语言用户也收到中文
```

```python
# ✗ 漏洞：X-Forwarded-Host影响响应但未加入Vary
@app.route('/api/config')
@cache.cached(timeout=300)
def api_config():
    host = request.headers.get('X-Forwarded-Host', request.host)
    return jsonify({
        'api_url': f'https://{host}/api',
        'cdn_url': f'https://cdn.{host}/static'
    })
    # 攻击: 缓存evil.com的配置给所有用户
```

```python
# ✗ 漏洞：User-Agent影响响应内容
@app.route('/download')
def download_page():
    ua = request.headers.get('User-Agent', '')
    if 'Mobile' in ua:
        content = render_template('mobile.html')
    else:
        content = render_template('desktop.html')

    resp = make_response(content)
    resp.headers['Cache-Control'] = 'public, max-age=600'
    # 缺少 Vary: User-Agent
    return resp
```

```python
# ✗ 漏洞：Cookie影响响应但Vary不完整
@app.route('/dashboard')
def dashboard():
    theme = request.cookies.get('theme', 'light')
    resp = make_response(render_template('dashboard.html', theme=theme))
    resp.headers['Cache-Control'] = 'private, max-age=60'
    resp.headers['Vary'] = 'Accept-Encoding'  # 缺少Cookie
    return resp
```

```python
# ✓ 修复：正确设置Vary头
@app.route('/api/messages')
def get_messages_safe():
    lang = request.headers.get('Accept-Language', 'en')
    messages = load_messages(lang)
    resp = make_response(jsonify(messages))
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    resp.headers['Vary'] = 'Accept-Language, Accept-Encoding'
    return resp
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | X-Forwarded-*头影响响应 | 搜索 `X-Forwarded-Host\|X-Forwarded-Proto`，检查是否加入Vary |
| **P0** | 缓存装饰器+请求头依赖 | 搜索 `@cached\|@cache`，检查处理函数是否依赖请求头 |
| **P1** | Accept-Language响应变化 | 搜索 `Accept-Language\|get_locale`，检查Vary设置 |
| **P1** | User-Agent内容适配 | 搜索 `User-Agent\|is_mobile`，检查Vary设置 |
| **P2** | Cookie影响响应 | 搜索 `request.cookies`，检查是否应禁用缓存或添加Vary |
| **P2** | Cache-Control设置 | 搜索 `Cache-Control\|max-age`，评估缓存策略 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 响应无缓存或全部private | **跳过**，无缓存中毒风险 |
| **L1** | 使用CDN但响应内容固定 | 关键词扫描确认无请求头依赖 |
| **L2** | 单函数内有请求头依赖 | 检查Vary头设置 |
| **L3** | 中间件统一设置缓存头 | 逐行追踪Vary设置逻辑 |
| **L4** | 多级缓存架构 | 跨模块审计缓存策略一致性 |

---

## 审计专业技巧

### 快速检查技巧

**1. 识别缓存关键词链**
```python
# 审计顺序：Cache-Control → 请求头依赖 → Vary验证
# 搜索序列：
# 第1步：grep -n "Cache-Control.*public\|max-age\|@cached"
# 第2步：在这些函数中搜索 request.headers/get/environ
# 第3步：检查函数返回前是否设置了Vary
```

**2. 追踪装饰器链的缓存污染**
```python
# ✗ 错误案例：多个装饰器导致缓存污染
@app.route('/content')
@cache.cached(timeout=300)  # 第一层缓存
@require_auth               # 但这可能改变响应
def content():
    user = current_user
    return jsonify({'data': get_user_data(user)})
# 问题：@cache.cached无法感知@require_auth的变化

# ✓ 修复：使用自定义装饰器控制缓存
@cache_with_user_vary()  # 明确包含user上下文
@require_auth
def content():
    ...
```

**3. 隐式请求头依赖的发现**
```python
# 难点：某些框架隐式使用请求头
# Flask-Babel示例
from flask_babel import get_locale, refresh

@app.route('/messages')
@cache.cached(timeout=300)
def messages():
    # get_locale() 隐式读取 Accept-Language
    locale = get_locale()
    return load_messages(locale)
    # 审计策略：搜索get_locale的定义，追踪其实现

# 正确做法：显式声明依赖
@app.route('/messages')
def messages():
    resp = jsonify(load_messages(get_locale()))
    resp.headers['Vary'] = 'Accept-Language'
    return resp
```

### 真实漏洞vs误报区分指南

#### ✓ 确实是漏洞的特征（高置信度）

**特征1：X-Forwarded-*影响业务逻辑**
```python
# 真实漏洞案例：域名校验失效
@app.route('/api/authenticate')
@cache.cached(timeout=600)
def authenticate():
    # X-Forwarded-Host被用于会话Domain设置
    host = request.headers.get('X-Forwarded-Host') or request.host
    session_config = {
        'domain': host,  # 攻击者可控！
        'secure': True
    }
    # 攻击：访问attacker.com/api/authenticate会缓存恶意配置

# 判定依据：
# 1. Host/X-Forwarded-Host直接进入业务逻辑
# 2. 响应可被公共缓存
# 3. 无Vary声明
# 确认等级：HIGH
```

**特征2：accept-language影响支付流程**
```python
# 真实漏洞案例：货币转换错误
@app.route('/checkout')
@cache.cached(timeout=300)
def checkout():
    lang = request.headers.get('Accept-Language', 'en')
    currency = {'en': 'USD', 'zh': 'CNY'}[lang]

    # 用户1(zh)下单，缓存价格为100CNY
    # 用户2(en)查询，收到100CNY而非USD
    return jsonify({'price': 100, 'currency': currency})

# 判定依据：
# 1. Accept-Language改变核心业务数据（货币）
# 2. 缓存时间足够长（300秒）让多用户受影响
# 3. 完全缺少Vary头
# 确认等级：CRITICAL
```

#### ✗ 常见的假漏洞（低置信度）

**误报1：内部API无缓存中毒风险**
```python
# 假漏洞案例：
@app.route('/internal/admin-stats')
@cache.cached(timeout=3600)
def admin_stats():
    region = request.headers.get('X-Admin-Region')  # 内部Only
    return jsonify(stats_by_region(region))

# 为什么不是漏洞：
# 1. 响应头无Cache-Control: public → 不会被CDN缓存
# 2. 仅内部管理员访问 → 缓存中毒范围有限
# 3. 无跨域请求可能 → 攻击路径不存在
# 判定：FALSE POSITIVE（除非环境有特殊CDN配置）
```

**误报2：极短缓存时间的风险评估**
```python
# 假漏洞案例：
@app.route('/notification')
@cache.cached(timeout=5)  # 仅5秒！
def get_notification():
    user_id = request.headers.get('X-User-ID')
    return jsonify({'msg': f'Hello {user_id}'})

# 评估：
# 虽然有请求头依赖且缺Vary，但缓存时间过短
# 5秒内两个不同用户访问的概率极低
# 风险等级：LOW → 可记录为建议但非严重漏洞
# 判定：TECHNICAL ISSUE（可改进但风险可控）
```

**误报3：Cache-Control: private下的Vary缺失**
```python
# 假漏洞案例：
@app.route('/user/profile')
def profile():
    theme = request.headers.get('X-Theme-Preference')
    resp = make_response(render_template('profile.html', theme=theme))
    # 虽然缺Vary但设置了private
    resp.headers['Cache-Control'] = 'private, max-age=300'
    return resp

# 为什么不严重：
# 1. private = 只浏览器缓存，不经过CDN
# 2. 用户浏览器只缓存自己的响应 → 无跨用户污染
# 3. 浏览器与服务器1:1对应 → 缓存中毒不可能
# 判定：IGNORED（不影响安全性）
```

#### 灰色地带的判定方法

**情况1：条件缓存**
```python
# 灰色案例：
@app.route('/api/resource')
def get_resource():
    if request.headers.get('Accept-Encoding') == 'gzip':
        resp = make_response(gzipped_data)
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        resp.headers['Vary'] = 'Accept-Encoding'  # 已正确声明
        return resp
    else:
        resp = make_response(plain_data)
        resp.headers['Cache-Control'] = 'no-cache'  # 禁用缓存
        return resp

# 判定策略：
# 检查是否所有缓存路径都正确设置了Vary
# 检查非缓存路径是否明确禁用了缓存
# 本例：SAFE → 只有gzip路径缓存且正确声明
```

**情况2：中间件统一缓存策略**
```python
# 灰色案例：中间件自动添加缓存头
@app.before_request
def set_cache_headers():
    if not current_user.is_authenticated:
        # 匿名用户响应缓存1小时
        g.cache_timeout = 3600
        g.cache_vary = 'Accept-Language'  # 中间件设置
    else:
        g.cache_timeout = 0  # 认证用户不缓存

@app.route('/content')
def content():
    data = get_content(get_locale())  # 依赖Accept-Language

    resp = make_response(jsonify(data))
    if g.cache_timeout > 0:
        resp.headers['Cache-Control'] = f'public, max-age={g.cache_timeout}'
        resp.headers['Vary'] = g.cache_vary
    return resp

# 判定策略：
# 1. 追踪所有响应的缓存头设置来源
# 2. 验证中间件逻辑是否完整覆盖所有路由
# 3. 测试边界情况（已认证用户访问公共路由等）
# 本例：SAFE → 逻辑完整，但建议单元测试验证
```

### 审计工具与脚本

**检查脚本模板**
```python
#!/usr/bin/env python3
# 自动审计缓存中毒风险的检查脚本

import ast
import re

def audit_cache_poisoning(file_path):
    with open(file_path) as f:
        content = f.read()

    findings = []

    # 搜索缓存配置
    cache_patterns = [
        (r'Cache-Control.*public', 'public_cache_found'),
        (r'@.*\.cached\(', 'decorator_cache_found'),
    ]

    # 搜索请求头依赖
    header_patterns = [
        (r'request\.headers\.get\([\'"](\w+)[\'"]', 'header_dependency'),
        (r'request\.environ\.get\([\'"]HTTP_', 'header_dependency'),
    ]

    for pattern, label in cache_patterns + header_patterns:
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            findings.append({
                'line': line_num,
                'type': label,
                'match': match.group(0)
            })

    return findings

# 使用示例
if __name__ == '__main__':
    results = audit_cache_poisoning('app.py')
    for r in results:
        print(f"Line {r['line']}: {r['type']} - {r['match']}")
```

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 响应可被缓存（Cache-Control: public 或 CDN配置）
2. 响应内容依赖某请求头
3. Vary头未包含该请求头

### 典型漏洞特征（满足任一项即确认）
- ✗ 依赖`Accept-Language`但`Vary`缺失或不包含
- ✗ 依赖`X-Forwarded-Host`生成URL但未禁用缓存
- ✗ `User-Agent`影响内容但`Vary`仅含`Accept-Encoding`
- ✗ 使用`@cache.cached()`但响应依赖请求头

### 安全排除（任一项充分）
- ✓ `Cache-Control: private` 或 `no-store`
- ✓ `Vary`包含所有影响响应的请求头
- ✓ `Vary: *` 禁用所有缓存
- ✓ 响应内容完全固定，无请求头依赖

### 灰色判定（风险较低但需注意）
- 仅内部API，无公共缓存
- 缓存时间极短（<1分钟）
- 仅影响非敏感内容

---

## 实现建议

### 核心防护方案

**方案1：正确设置Vary头**
```python
@app.after_request
def add_vary_header(response):
    # 如果响应依赖特定头，添加到Vary
    vary_headers = ['Accept-Encoding']

    # 检查是否使用了语言相关功能
    if hasattr(g, 'locale_used') and g.locale_used:
        vary_headers.append('Accept-Language')

    response.headers['Vary'] = ', '.join(vary_headers)
    return response
```

**方案2：敏感响应禁用缓存**
```python
def no_cache_response(content):
    resp = make_response(content)
    resp.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/user-config')
def user_config():
    # 用户特定配置，禁用缓存
    config = get_user_config(current_user)
    return no_cache_response(jsonify(config))
```

**方案3：缓存键包含所有变量**
```python
from functools import wraps

def cache_with_vary(*vary_headers):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 生成包含所有变量的缓存键
            cache_key_parts = [request.path]
            for header in vary_headers:
                cache_key_parts.append(request.headers.get(header, ''))
            cache_key = ':'.join(cache_key_parts)

            # 检查缓存
            cached = cache.get(cache_key)
            if cached:
                resp = make_response(cached)
            else:
                result = f(*args, **kwargs)
                cache.set(cache_key, result, timeout=300)
                resp = make_response(result)

            resp.headers['Vary'] = ', '.join(vary_headers)
            return resp
        return wrapper
    return decorator

@app.route('/api/messages')
@cache_with_vary('Accept-Language', 'Accept-Encoding')
def get_messages():
    lang = request.headers.get('Accept-Language', 'en')
    return jsonify(load_messages(lang))
```

### 检查清单
- [ ] 所有可缓存响应检查请求头依赖
- [ ] Vary头包含所有影响响应的请求头
- [ ] X-Forwarded-*头影响的响应禁用公共缓存
- [ ] 用户特定响应使用`Cache-Control: private`
- [ ] 测试缓存中毒：不同`Accept-Language`请求

---

## 修复优先级

1. **立即修复**：X-Forwarded-Host影响响应内容的缓存中毒
2. **本周修复**：添加完整的Vary头声明
3. **可选加强**：实现缓存键验证机制
4. **长期优化**：CDN配置审计，统一缓存策略

