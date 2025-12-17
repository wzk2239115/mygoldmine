# C/C++ 状态修改端点缺少 CSRF Token 漏洞

## Details

### 漏洞成因
使用 Wt、CppCMS、自研 HTTP 服务器或 CGI 程序时，开发者通常手动处理表单数据。如果在处理敏感操作（如账户修改、支付、权限管理）的端点未生成和验证 CSRF Token，浏览器会自动发送 Session Cookie，攻击者可以利用跨站请求诱导已登录用户执行恶意操作。

### 代码示例

**易受攻击的代码：**
```cpp
void AccountController::postUpdateEmail(const Wt::Http::Request& req, Wt::Http::Response& resp) {
    auto session = getSession(req);
    if (!session.isAuthenticated()) {
        resp.setStatus(401);
        return;
    }
    auto email = req.getParameter("email"); // 未验证 CSRF Token
    userRepository.updateEmail(session.userId(), *email);
    resp.out() << "OK";
}
```

```cpp
void handle_request(struct evhttp_request* req, void* arg) {
    if (evhttp_request_get_command(req) == EVHTTP_REQ_POST &&
        strcmp(evhttp_uri_get_path(evhttp_request_get_evhttp_uri(req)), "/admin/delete") == 0) {
        // 未检查 Token
        perform_delete(req);
        evhttp_send_reply(req, 200, "OK", nullptr);
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 表单处理：`req.getParameter`, `request.parameter`, `cgi["field"]`
- Session 验证：`session.isAuthenticated`, `SessionManager::get`
- Token 字段：`_csrf`, `token`, `nonce`

**定位步骤：**
1. 搜索所有 POST/PUT/DELETE 处理函数，确认是否读取 Token 参数。
2. 检查模板渲染是否输出隐藏 Token 字段。
3. 跳读（L2）分析 Token 是否与会话绑定并严格验证。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **Token 生成**：每次渲染表单生成随机 Token 并存入会话。
- **验证逻辑**：`if (token != sessionToken) { reject }`.
- **一次性 Token**：使用后删除或更新。
- **辅助保护**：Referer/Origin 校验、SameSite Cookie。

**定位技巧：**
- 确认使用多线程时 Token 存储线程安全。
- 检查 CGI 脚本是否使用全局变量共享 Token。
- 关注 Token 是否通过 URL 传递导致泄露。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Token 验证严格、会话绑定 | **L0（快速跳过）** | 风险低 |
| 部分端点缺 Token | **L2（跳读）** | 需补齐 |
| 核心端点无 Token | **L3（逐行读）** | 高风险 |
| 模板与处理逻辑分离，易遗漏 | **L4（跨模块追踪）** | 需全面梳理 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 状态修改端点未验证 CSRF Token。
2. 端点依赖 Cookie/Session。
3. 无其它防护措施。

#### 误报
以下情况非漏洞：
1. 接口通过自定义 HMAC 签名验证，不依赖 Cookie。
2. 仅用于只读查询或内部服务调用。
3. Token 验证在下游服务完成。

#### 代码异味
需记录：
1. Token 生成使用不安全随机数。
2. 验证失败仅打印日志并继续执行。
3. Token 与会话未绑定或可多次使用。
4. 同一个页面存在多个表单共享旧 Token。

## Low risk

### 低风险评级场景

#### 1. 内部系统
- **场景：** 仅内网访问且配合审计。
- **风险评估：** 攻击面有限，但仍建议实现 Token。

#### 2. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict，减少跨站请求。
- **风险评估：** 浏览器兼容性有限。

#### 3. 二次确认
- **场景：** 操作需 PIN/MFA 确认。
- **风险评估：** 提高攻击难度，仍建议 Token。

#### 4. 签名参数
- **场景：** 请求包含 HMAC 签名并在服务端验证。
- **风险评估：** 可视作替代防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 + 审计 | 攻击面有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 二次确认 | 提高攻击成本 | 中 |
| HMAC 签名 | 等效防护 | 低 |

