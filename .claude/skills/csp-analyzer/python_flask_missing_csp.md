---
title: Flask 应用 CSP 响应头缺失审计小抄
description: Flask 应用未实现 CSP 安全策略的审计指南和关键检查点
---

# Flask 应用 CSP 响应头缺失审计小抄

Flask 作为 Python 的轻量级 Web 框架，默认不启用 CSP 防护机制，需要通过显式配置中间件或响应钩子来实现。本指南针对 Flask 应用在 HTTP 响应中缺失 `Content-Security-Policy` 响应头的审计方法。

## Details

### 核心操作技巧：快速定位漏洞点

**关键代码位置示例：**

Flask 应用的响应头设置通常在以下位置：
1. **全局中间件** - 通过 `before_request` / `after_request` 钩子
2. **蓝图级别** - 在路由处理器中设置
3. **应用工厂** - 在 `create_app()` 函数中配置

**典型缺失模式（易识别的反面示例）：**
```python
# ❌ 应用启动，但无 CSP 头注入点
from flask import Flask

app = Flask(__name__)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')
# 没有任何地方设置 Content-Security-Policy 头
```

**审计关键词扫描** - **(L1:关键词扫描)**
- 搜索 `after_request`、`before_request` 钩子函数定义
- 搜索 `@app.route()`、`@blueprint.route()` 装饰器
- 搜索响应头设置相关代码：`response.headers`、`make_response()`
- 搜索第三方 CSP 中间件：`flask-csp`、`flask-talisman` 等
- 搜索 `@app.after_request` 函数内是否有 `Content-Security-Policy` 字符串

**保护机制快速定位技巧** - **(L2:跳读)**
- 浏览 `create_app()` 或应用初始化文件，查找中间件配置段落
- 查看 `app.route()` 装饰器下的路由处理器，判断是否所有路由都在响应头注入点的覆盖范围内
- 识别是否有"特定路由例外处理"的逻辑（如某些路由故意不返回 HTML，因此不需要 CSP）
- 查看是否存在 `response.headers.update()`、`response.set_cookie()` 等响应修改点

### 二级审计：确认覆盖范围

**关键检查点** - **(L3:逐行读)**

1. **覆盖范围检查**
   - 确认 CSP 头的注入点是全局的（通过 `after_request` 钩子）还是零散的（分散在各路由）
   - 若使用零散方式，必须逐一检查所有返回 HTML 的路由是否都设置了 CSP
   - 检查是否有 API 路由（返回 JSON）被误包含在 CSP 设置中（通常不需要，需确认是否有意外的头部污染）

2. **条件判断逻辑**
   ```python
   @app.after_request
   def set_csp_header(response):
       # 检查是否有条件判断导致部分响应未设置 CSP
       if 'html' in response.content_type:  # ⚠️ 这是好的
           response.headers['Content-Security-Policy'] = "script-src 'self'"
       # ❌ 如果没有类似条件判断，API 响应也会被设置，可能造成污染
       return response
   ```
   - 验证条件判断是否正确（应检查 `response.content_type` 或路由路径）
   - 确认逻辑不会因为条件错误导致保护失效

3. **中间件执行顺序**  - **(L4:跨模块追踪)**
   - 若应用使用了多个中间件（如 CORS、HTTPS 重定向等），检查 CSP 中间件的执行顺序
   - CSP 中间件应在响应生成后立即应用，避免被其他中间件覆盖
   - 追踪 `Flask` 蓝图注册顺序，确认 `after_request` 钩子的全局覆盖

### 三级审计：深层代码跟踪

**动态响应生成**  - **(L4:跨模块追踪)**
- 追踪 `render_template()` 调用，确认所有模板渲染都通过设置 CSP 头的代码路径
- 搜索 `abort()`、`redirect()` 等特殊响应，检查这些函数返回的响应是否也被 CSP 中间件处理
- 检查是否有自定义的 `jsonify()`、`make_response()` 包装函数

**模板渲染与响应**
```python
@app.route('/page')
def page():
    return render_template('index.html')  # 需要确保 after_request 钩子会处理该响应

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404  # 错误响应也需要 CSP 保护
```

---

## Classify

### 漏洞判定的理论标准

**确定为漏洞（True Positive）：**

1. **完全缺失 CSP 头**
   - Flask 应用中找不到任何 CSP 相关的配置或代码
   - 所有返回 HTML 内容的响应都缺少 `Content-Security-Policy` 响应头
   - 应用没有使用 `flask-talisman`、`flask-csp` 等成熟中间件库

2. **部分路由缺失保护**
   - CSP 中间件只在特定路由应用，而其他返回 HTML 的路由未被覆盖
   - 通过条件判断（如路由前缀或文件扩展名）导致保护不完整
   - 例如：只有 `/api/*` 路由设置了 CSP，但 `/page/*` 路由未设置

3. **中间件配置但未生效**
   - 代码中定义了 CSP 中间件，但因为条件判断、异常处理或执行顺序问题导致未生效
   - `after_request` 钩子存在但因 `if` 条件过于严格导致绝大多数响应被跳过

**代码异味（Code Smell）：**

1. **使用了过于宽松的 CSP 值**
   - 虽然设置了 CSP 头，但使用了 `'unsafe-inline'`、`'unsafe-eval'`、`*` 等不安全指令
   - 这不属于"缺失"范畴，但也违反了安全原则（应单独审计）

2. **CSP 头仅在部分中间件生效**
   - 代码中存在多个 `after_request` 钩子，CSP 设置可能被覆盖或丢失
   - 需要确认最终响应中是否包含 CSP 头

**误报排除（False Positive）：**

1. **非 HTML 响应**
   - API 端点返回 JSON、XML 等非 HTML 格式，不需要 CSP 头
   - 文件下载端点返回二进制数据，不需要 CSP 头
   - 该判定需要逐一检查路由的 `content-type` 或返回内容类型

2. **静态文件服务**
   - Flask 应用仅用于静态文件服务（通过 `send_file()` 或 `send_from_directory()`），无动态 HTML 生成
   - 此时不需要 CSP 头设置

3. **SSO / 代理后端**
   - Flask 应用作为反向代理或 API 中间件，最终由前端/Web 服务器返回 HTML
   - CSP 头应在前端/Web 服务器层面设置，不需要在 Flask 中设置

---

## Low risk

### 低风险场景评定标准

**场景 1：特定路由合理豁免**
如果 Flask 应用的某些路由因业务需求合理地不返回 HTML（如：
- API 端点返回纯 JSON/XML 响应
- Webhook 接收端只接收请求，无响应体
- 代理转发端只负责转发，不生成 HTML

此时该路由缺失 CSP 头不构成漏洞。**但需要确认这是有意的设计，而非遗漏**。

**场景 2：前置安全防护已覆盖**
- Nginx/Apache 等 Web 服务器层已全局配置了 CSP 头，Flask 应用作为后端无需重复设置
- 需要验证生产环境配置，而非仅审计应用代码
- 此时应在审计报告中标注"Web 服务器层已配置"

**场景 3：应用本身无 XSS 风险**
- Flask 应用严格采用模板自动转义（Jinja2 默认启用），完全不存在用户输入的动态渲染
- 所有用户输入都在数据库查询前进行了参数化处理，完全不存在注入风险
- **但这种判定极其罕见且容易出错**，通常不建议作为豁免理由

**场景 4：开发/测试环境**
- 明确为开发或测试环境的 Flask 应用，可评为低风险
- **但生产环境分支必须实施完整的 CSP 配置**

### 风险等级调整

**从高风险降低到中风险的条件：**
- 应用虽然缺失全局 CSP 配置，但实施了严格的输入验证和模板转义
- 已识别并记录了特定路由的豁免理由
- 前置层（Web 服务器/WAF）已有缓解措施

**保持高风险的情形：**
- 应用本身存在动态内容渲染（如 `render_template()` 处理用户输入）
- 生产环境无任何 CSP 防护
- 无法提供前置防护的证据

---
