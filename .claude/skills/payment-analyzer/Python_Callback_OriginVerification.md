# Python_Callback_OriginVerification

## Details

**核心漏洞特征**：Python应用中回调源验证缺失，无IP白名单、签名验证或源身份检查，攻击者可伪造支付通知。

**代码示例定位**：查找回调处理函数，关键词包括 `request.remote_addr`, `verify`, `callback`, `webhook`, `signature` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `request.remote_addr` - 检查是否获取源IP
- 搜索 `verify_signature()` 或签名验证 - 检查是否验证签名
- 搜索 `request.headers` - 检查是否验证HTTP头
- 搜索 `@app.route('/callback')` - 找到回调端点

**快速定位保护机制**（L2: 跳读）：
- 检查是否有IP白名单
- 检查是否验证HMAC签名
- 检查是否验证时间戳
- 检查是否使用HTTPS

## Classify

**漏洞判定标准**：
- 无源IP验证 → **漏洞**
- 无签名验证 → **漏洞**
- 允许HTTP明文回调 → **漏洞**
- 无身份验证 → **漏洞**

**误报情况**：
- IP白名单+签名验证 → 低风险
- HTTPS+证书验证 → 低风险
- 多层验证 → 低风险

**代码异味**：
- IP检查在签名之后 → 审计
- 白名单过宽泛 → 审计

## Low risk

**低风险评级条件**：
1. **IP白名单**：严格限制回调源IP
2. **签名验证**：HMAC-SHA256验证
3. **时间戳检查**：防止重放
4. **HTTPS强制**：仅接受加密连接
5. **详细日志**：所有验证步骤都记录