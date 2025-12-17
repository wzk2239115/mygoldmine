# C/C++ JWT 未验证签名漏洞

## Details

**代码示例：**

```cpp
// 典型漏洞场景1：仅解码未验证
json payload = jwt::decode(token);  // 直接使用 payload，未验证签名
string user_id = payload["sub"];

// 典型漏洞场景2：使用 base64 解码绕过验证
auto parts = split(token, '.');
string payload_b64 = parts[1];
json data = base64_decode(payload_b64);  // 手动解析，跳过验证

// 典型漏洞场景3：条件分支缺失验证
if (verify_signature) {
    jwt::verify().verify_signature(token, key);
} else {
    // 直接使用 token，未验证路径
    auto decoded = jwt::decode(token);
}

// 典型漏洞场景4：异常处理不当
try {
    auto verifier = jwt::verify().allow_algorithm(jwt::algorithm::hs256{secret});
    verifier.verify(decoded_token);
} catch(...) {
    // 捕获异常后继续使用 token
    process_user(decoded_token);
}
```

**快速定位核心操作（L1-L2 审计等级）：**
- L1：关键词扫描 - `jwt::decode`、`base64_decode`、`split`、`payload`、`.verify`、`verify_signature`
- L2：跳读定位 - 在 JWT 解码后，追踪 payload 使用点（如 `["sub"]`、`["role"]`、`["exp"]`），查看使用前是否经过验证函数

**快速定位保护机制（L2-L4 审计等级）：**
- L2：跳读检查 - 寻找 `verify()`、`verify_signature()`、`allow_algorithm()` 等验证函数调用
- L3：逐行读取 - 确认验证函数在 decode 和 payload 使用之间的调用链路完整性
- L4：跨模块追踪 - 检查验证逻辑是否通过配置开关、环境变量或条件编译被禁用；追踪异常处理分支是否存在绕过验证的路径

## Classify

**漏洞判定：**
- JWT token 被解码后直接使用 payload 数据（用户权限、身份信息等），且整个请求链路中未调用签名验证函数
- 使用 base64 等通用解码方式手动解析 JWT payload，完全绕过库的验证机制
- 验证函数存在但位于可跳过的条件分支、异常捕获后继续使用未验证 token

**误报识别：**
- 验证逻辑通过中间件或拦截器在上游已完成，当前代码段仅处理已验证的 token（需追踪确认）
- 仅用于日志记录、调试输出等非安全决策场景的 payload 解析
- 测试代码、示例代码中的未验证解码

**代码异味：**
- 验证逻辑与业务逻辑耦合在同一函数中，验证调用存在但不明显
- 验证函数返回值未检查，静默失败后继续执行
- 使用已废弃或不安全的验证方式（如仅验证格式不验证签名）

## Low Risk

**低风险场景：**
- JWT 仅用于非关键功能的用户偏好存储，不涉及权限控制或身份认证
- 内网环境且 token 生命周期极短（秒级），配合其他强认证机制使用
- token 数据仅作为缓存键或查询参数，后续通过数据库二次验证用户权限
- 公开信息传输场景，payload 不包含敏感数据且不用于安全决策
- 代码处于已标记为 deprecated 的遗留模块，且有明确的迁移计划和时间表

## Audit Tips（审计专业技巧）

### 真实漏洞特征识别

**1. 强烈风险信号（必定是漏洞）：**
- 解码后直接通过 `payload["sub"]`、`payload["role"]` 等调用权限敏感字段，且整个代码路径未见验证函数
- JWT 验证函数调用存在但被 `try-catch` 捕获异常后继续使用：
  ```cpp
  try { jwt::verify(token, secret); } catch(...) { process_user(token); }
  ```
- 使用 `split(token, '.')` 和 `base64_decode(parts[1])` 手工解析，说明完全绕过 JWT 库的验证机制
- 验证逻辑位于 `if (condition)` 分支中，同时存在未验证的 else 分支用于生产代码路径

**2. 二级特征（需交叉验证）：**
- 项目包含多个 JWT 处理函数，部分做验证，部分不做 → 检查当前函数是否属于可信层（中间件、拦截器）
- `jwt::decode` 调用后紧跟 `jwt::verify`，但 verify 返回值被忽略，或异常处理后继续使用
- 环境变量控制验证：`if (getenv("SKIP_JWT_VERIFY"))` → 确认生产环境中是否被禁用

### 误报消除技巧

**1. 识别上游已验证的场景：**
- 在中间件或拦截器中搜索：`router.use(jwt_middleware)` 或 `filter.doFilter(jwt_verification)`
- 追踪函数调用链：若当前函数被装饰器或属性标注 `@Authenticated` 或 `@RequireJWT`，需查看框架定义
- 在 HTTP 框架级别验证：Spring Security、ASP.NET Identity 等框架层验证不在单函数内体现，需查看配置

**2. 非安全关键的 decode 操作：**
```cpp
// 低风险：仅用于日志/调试
void log_token_info(const string& token) {
    auto decoded = jwt::decode(token);  // 未验证但仅输出日志
    cout << "Token user: " << decoded.get_payload()["sub"] << endl;
}

// 高风险：decode 后的数据用于访问控制
bool check_user_role(const string& token) {
    auto decoded = jwt::decode(token);  // 未验证
    return decoded.get_payload()["role"] == "admin";  // ← 直接用于权限判定
}
```

**3. 防护机制已存在但位置隐蔽的情况：**
- 检查请求拦截、身份验证过滤器、中间件堆栈
- 查看 JWT 是否通过安全通道传递（HTTPS、内部消息队列）
- 确认当前函数是否处于 "已验证用户" 的后续处理链路

### 审计检查清单

| 检查项 | 漏洞特征 | 误报排除法 |
|--------|---------|----------|
| **Decode 调用** | `jwt::decode` 后无 `verify` 调用 | 确认验证是否在上游中间件完成 |
| **Payload 使用** | `["role"]`、`["sub"]` 等权限字段直接使用 | 检查使用上下文是否为日志/调试 |
| **异常处理** | catch 块内继续使用未验证 token | 检查异常处理是否合理（应拒绝 token） |
| **条件分支** | 存在跳过验证的分支（如 `if (!verify_enabled)`) | 确认分支是否仅在测试/调试中启用 |
| **密钥管理** | 硬编码密钥或空密钥验证 | 风险等同于无验证 |

### 特殊场景处理

**API Gateway/边界层的设计：**
- 若该函数位于 API Gateway 内部调用链：可能网关已完成验证，当前函数处于可信域
- 需追踪请求流向：外部请求 → Gateway 验证 → 内部服务（decode only）

**多层架构中的 token 传递：**
```cpp
// 服务A：验证并提取
jwt::verify(token, secret);
string user_id = jwt::decode(token)["sub"];
pass_to_service_b(user_id);  // 传递用户ID而非token

// 服务B：接收用户ID，不需要重新验证 token
process_user(user_id);  // 低风险
```

**配置驱动的验证：**
```cpp
// 风险：配置中禁用了验证
if (config.verify_jwt) {
    jwt::verify(token, secret);
}
// 需确认：config 是否可被外部攻击者修改或绕过
```

### 实际审计流程示例

1. **第一步**：全局搜索 `jwt::decode`、`base64_decode` 等调用点（约 5 分钟）
2. **第二步**：逐行追踪每个 decode 调用点后是否有 verify（约 10 分钟）
3. **第三步**：若无 verify，检查上游中间件、框架配置（约 15 分钟）
4. **第四步**：确认 payload 数据是否用于权限决策（约 10 分钟）
5. **最终判定**：若 decode + 权限使用 + 无验证 + 无上游保护 = 真实漏洞