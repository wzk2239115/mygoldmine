# Python 手动 Token 校验绕过漏洞

## Details

### 漏洞成因
在未使用框架默认 CSRF 防护的 Python 项目中，开发者可能自行实现 Token 校验，但常出现逻辑缺陷：例如仅检查 Token 是否存在、不区分大小写、忽略过期、允许空字符串、未绑定用户、仅在 GET 请求时生成 Token 等。这些缺陷使得攻击者可以伪造或重复使用 Token，在用户已登录的情况下执行敏感操作。

### 代码示例

**易受攻击的代码：**
```python
def validate_csrf(request):
    token = request.form.get("_csrf")
    if not token:
        return False
    return True  # 仅检查存在性

@app.route("/billing/update", methods=["POST"])
def update_billing():
    if not validate_csrf(request):
        abort(403)
    # 未与 session 中的 token 对比
    save_billing_info(request.form)
    return "ok"
```

**另一个不安全示例（大小写/空白绕过）：**
```python
def validate_csrf(token_from_request, token_from_session):
    if token_from_request.strip().lower() == token_from_session.lower():
        return True
    return False
# 攻击者可提交空 token，strip 后为空字符串，与空 session token 匹配
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `request.form.get("_csrf")`, `request.headers.get("X-CSRF-Token")`
- 自定义函数：`validate_csrf`, `check_token`, `verify_csrf`
- Session 存储：`session["csrf_token"]`, `redis.set("csrf:", token)`

**定位步骤：**
1. 搜索 Token 验证函数，查看是否与存储的 Token 比较。
2. 检查是否验证 Token 过期、单次使用、与用户绑定。
3. 跳读（L2）Confirm 验证失败是否中止请求。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **会话绑定**：`session["csrf_token"]` 与请求值严格比较。
- **随机性**：使用 `os.urandom` 或安全库生成。
- **一次性**：验证后删除或刷新。
- **时间限制**：Token 存储有效期。

**定位技巧：**
- 确认 Token 是否通过 URL、日志或 HTML 注释泄露。
- 检查多表单场景，Token 是否针对每个表单更新。
- 关注 API 和网页共用 Token 时的跨域问题。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 严格比较 + 会话绑定 + 过期控制 | **L0（快速跳过）** | 风险低 |
| 缺少某项校验（大小写/过期） | **L2（跳读）** | 需补齐逻辑 |
| 仅检查存在或可空值绕过 | **L3（逐行读）** | 高风险 |
| 验证失败仍继续执行业务 | **L4（跨模块追踪）** | 防护完全失效 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Token 校验逻辑存在明显缺陷（不比对、易绕过）。
2. 端点使用 Cookie 认证并执行敏感操作。
3. 攻击者可利用缺陷伪造请求。

#### 误报
以下情形非漏洞：
1. 该校验函数仅用于日志/监控，实际防护由其它机制完成。
2. 端点仅用于只读请求或已采用 Token Auth。
3. 校验失败由其他中间件阻断。

#### 代码异味
需记录的风险：
1. Token 存在多个存储位置，逻辑复杂易混淆。
2. 对 Token 进行 Base64/JSON 解码但未验证签名。
3. 多线程环境中 Token 存储使用全局变量。
4. Token 长期不刷新，可能被长期复用。

## Low risk

### 低风险评级场景

#### 1. 内部系统 + 审计
- **场景：** 系统仅内部使用，失败会被日志捕捉。
- **风险评估：** 攻击面小，但仍应完善逻辑。

#### 2. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict，降低跨站风险。
- **风险评估：** 缓解有限，仍需修复。

#### 3. 二次确认
- **场景：** 敏感操作需短信/验证码确认。
- **风险评估：** 降低风险，但不替代修复。

#### 4. Token 频繁刷新
- **场景：** Token 每次请求后必定刷新，窗口期短。
- **风险评估：** 有助于缓解，但仍需会话绑定。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 + 审计 | 攻击面有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 二次确认 | 提高攻击成本 | 中 |
| Token 快速刷新 | 缩短窗口期 | 中 |

