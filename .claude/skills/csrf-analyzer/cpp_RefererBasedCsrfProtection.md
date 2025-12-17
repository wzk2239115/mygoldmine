# C/C++ 仅依赖 Referer/Origin 的 CSRF 防护漏洞

## Details

### 漏洞成因
在 C/C++ 实现的 Web 服务中，开发者可能通过读取 `HTTP_REFERER`/`Origin` 头判断请求来源，若来源不匹配则拒绝。由于部分浏览器、浏览器扩展或跨协议转换会省略或篡改 Referer，并且攻击者可利用中间人或开放式重定向构造合法 Referer，这种防护方式无法替代随机 Token，导致敏感操作仍然暴露于 CSRF。

### 代码示例

**易受攻击的代码：**
```cpp
void handleTransfer(const Request& req, Response& resp) {
    auto referer = req.header("Referer");
    if (!referer.starts_with("https://bank.example.com")) {
        resp.setStatus(403);
        return;
    }
    // 未验证 CSRF Token
    processTransfer(req.getParam("amount"));
    resp.out() << "OK";
}
```

```cpp
if (req.header("Origin") == "https://admin.example.com") {
    deleteUser(userId); // 攻击者可通过隐藏 iframe 构造合法 Origin
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `req.header("Referer")`, `request.getHeader("Origin")`
- 字符串比较：`starts_with`, `find`, `strcmp`
- 配置项：`checkReferer`, `requireSameOrigin`

**定位步骤：**
1. 搜索敏感请求处理逻辑中 Referer/Origin 判断。
2. 检查是否同时存在 Token 验证。
3. 跳读（L2）确认是否存在特殊情况下 Referer 为空时放行。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **Token/MAC**：是否结合随机 Token。
- **白名单**：是否严格限定可信域。
- **SameSite Cookie**：辅助缓解。
- **日志监控**：Referer 缺失时告警。

**定位技巧：**
- 验证 HTTP → HTTPS、非浏览器客户端场景 Referer 是否为空。
- 检查是否对 `Origin` 为 `null` 场景放行（如从 file://）。
- 分析外部重定向/代理是否可构造合法 Referer。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Token + Referer 双重防护 | **L0（快速跳过）** | 风险低 |
| 仅依赖 Referer/Origin | **L3（逐行读）** | 高风险 |
| Referer 为空默认放行 | **L4（跨模块追踪）** | 极易绕过 |
| Referer 校验补充 Token | **L2（跳读）** | 需确认 Token 实现 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 防护手段仅依赖 Referer/Origin。
2. 无 Token 或其它不可伪造凭证。
3. 端点依赖 Cookie 认证。

#### 误报
以下情况非漏洞：
1. Referer 校验作为辅助，主要防护是 Token。
2. 接口仅限内部网络或受控客户端。
3. 请求使用 Bearer Token/签名，无 Cookie。

#### 代码异味
需记录：
1. Referer 比较允许 `http` 而非 `https`。
2. 对 `Origin` 为 `null` 或空字符串放行。
3. 校验逻辑在某些子域/路径下被绕过。
4. Referer 白名单过宽，包含通配符。

## Low risk

### 低风险评级场景

#### 1. 内部系统
- **场景：** 仅内网访问并结合监控。
- **风险评估：** 攻击面有限，但仍建议 Token。

#### 2. SameSite=Strict Cookie
- **场景：** Cookie 配置 Strict。
- **风险评估：** 提供一定防护，仍需 Token。

#### 3. 二次确认
- **场景：** 敏感操作需二次认证。
- **风险评估：** 提升攻击成本，仍建议 Token。

#### 4. 日志审计
- **场景：** 记录 Referer 缺失/异常并告警。
- **风险评估：** 提升检测能力，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 | 攻击面有限 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| 二次确认 | 提高攻击成本 | 中 |
| 审计告警 | 及时发现异常 | 高（仍需 Token）|

