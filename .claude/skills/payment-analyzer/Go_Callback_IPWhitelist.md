# Go_Callback_IPWhitelist

## Details

**核心漏洞特征**：Go应用中回调IP白名单检查缺失或不完整，可能检查错误（如仅检查第一个IP）或被绕过。

**代码示例定位**：查找IP验证代码，关键词包括 `net.RemoteAddr`, `X-Forwarded-For`, `ClientIP()`, `whitelist` 等。

**快速定位核心操作**（L1: 关键词扫描）：
- 搜索 `conn.RemoteAddr()` 或 `r.RemoteAddr` - 检查IP获取
- 搜索 `X-Forwarded-For` - 检查是否处理代理
- 搜索 `strings.Contains(ip, ...)` - 检查IP匹配逻辑
- 搜索白名单列表定义 - 检查配置

**快速定位保护机制**（L2: 跳读）：
- 检查是否正确处理X-Forwarded-For头
- 检查是否验证所有可能的IP头
- 检查IP匹配逻辑是否正确（不能子串匹配）
- 检查白名单是否完整

## Classify

**漏洞判定标准**：
- 无IP白名单检查 → **漏洞**
- IP匹配逻辑错误（子串匹配） → **漏洞**
- 错误处理X-Forwarded-For → **漏洞**
- 白名单不完整或硬编码 → **漏洞**

**误报情况**：
- 正确的IP匹配逻辑 → 低风险
- 完整的白名单列表 → 低风险
- 正确处理代理IP → 低风险

**代码异味**：
- 虽有白名单但未用于验证 → 审计
- 多处IP检查代码 → 审计

## Low risk

**低风险评级条件**：
1. **IP获取**：正确获取实际客户端IP
2. **代理处理**：正确处理X-Forwarded-For和X-Real-IP
3. **精确匹配**：使用==或net.ParseIP而非子串匹配
4. **完整白名单**：包含所有支付服务器IP
5. **外部化配置**：白名单从配置文件而非硬编码