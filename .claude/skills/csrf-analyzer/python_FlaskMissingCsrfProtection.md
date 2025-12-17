# Python Flask 缺少 CSRF 防护漏洞

## Details

### 漏洞成因
Flask 默认不包含 CSRF 防护，需要使用 `Flask-WTF`、`Flask-SeaSurf`、`itsdangerous` 等扩展或手动实现。如果开发者直接在视图函数中处理表单提交、Ajax 请求，未验证 CSRF Token 或未设置 SameSite Cookie，攻击者即可利用浏览器自动携带的 Session Cookie 伪造请求执行敏感操作。

### 代码示例

**易受攻击的代码：**
```python
from flask import Flask, request, jsonify, session

app = Flask(__name__)
app.secret_key = "secret"

@app.route("/settings/email", methods=["POST"])
def update_email():
    if "user_id" not in session:
        return "unauthorized", 401
    email = request.form["email"]
    update_email_for_user(session["user_id"], email)  # 未验证 CSRF Token
    return jsonify({"ok": True})
```

**另一个不安全示例（API 返回 JSON）：**
```python
@app.route("/api/transfer", methods=["POST"])
def transfer():
    data = request.json
    transfer_money(session["user_id"], data["amount"])  # 依赖 Cookie，无 Token
    return {"status": "ok"}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 表单处理：`request.form`, `request.files`, `request.json`
- 安全扩展：`FlaskForm`, `CSRFProtect`, `WTF_CSRF_ENABLED`
- 视图装饰器：`@csrf.exempt`, 自定义 `before_request`

**定位步骤：**
1. 检查应用是否导入并初始化 `CSRFProtect(app)`.
2. 搜索 POST/PUT/DELETE 端点，确认是否验证 Token。
3. 跳读（L2）模板中是否包含 `{{ form.csrf_token }}`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **Flask-WTF 表单**：继承 `FlaskForm` 并启用 CSRF。
- **全局中间件**：`CSRFProtect` 或 `Flask-SeaSurf`.
- **自定义 Token**：`itsdangerous` 签名并与 session 绑定。
- **SameSite Cookie**：`SESSION_COOKIE_SAMESITE` 设置为 `'Lax'`/`'Strict'`.

**定位技巧：**
- 确认 API Blueprint 是否绕过 CSRF 中间件。
- 检查 `WTF_CSRF_ENABLED=False` 是否在配置中出现。
- 分析基于 `fetch` 的 SPA 是否正确读取 Token。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局启用 CSRFProtect，表单包含 Token | **L0（快速跳过）** | 风险低 |
| 个别 Blueprint 未启用防护 | **L2（跳读）** | 需补齐 |
| 全局缺少 CSRF 防护 | **L3（逐行读）** | 高风险 |
| 复杂 SPA + API 混合 | **L4（跨模块追踪）** | 需检查所有入口 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Flask 应用依赖 Cookie 认证处理敏感操作。
2. 端点未启用任何 CSRF Token 或等效防护。
3. 攻击者可构造跨站请求执行操作。

#### 误报
以下情况可视为误报：
1. API 仅使用 Bearer Token/Basic Auth，无 Cookie。
2. 已配置双重提交 Cookie 并正确验证。
3. 应用只处理只读请求或内部服务调用。

#### 代码异味
需记录的风险：
1. `WTF_CSRF_CHECK_DEFAULT=False` 在配置中启用。
2. 使用 `@csrf.exempt` 装饰器范围过宽。
3. Token 通过查询字符串传递，易被日志记录。
4. 模板未统一使用 `{{ form.csrf_token }}`，开发者需手动添加。

## Low risk

### 低风险评级场景

#### 1. 内部管理系统
- **场景：** 仅内网访问，并启用 VPN 与审计。
- **风险评估：** 攻击面小，但仍建议启用 CSRF。

#### 2. REST API + JWT
- **场景：** 所有敏感请求使用 Authorization 头。
- **风险评估：** CSRF 风险低，但需确认没有 Cookie 回退。

#### 3. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict，跨站不发送。
- **风险评估：** 浏览器支持有限，不可完全依赖。

#### 4. 审计日志
- **场景：** 记录每次敏感操作来源。
- **风险评估：** 有助于追踪，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部系统 | 攻击面有限 | 中 |
| Token Auth | 不使用 Cookie | 低 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 审计与告警 | 提升检测能力 | 高（仍建议启用 CSRF）|

