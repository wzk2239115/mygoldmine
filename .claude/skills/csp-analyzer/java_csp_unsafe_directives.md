# Java CSP Unsafe Directives

## Details

CSP (Content Security Policy) 中包含 `unsafe-inline` 或 `unsafe-eval` 指令会使得内容安全策略失效，导致XSS攻击防护完全绕过。

**代码示例：**

```java
// unsafe-inline 示例 - 允许内联脚本执行
response.setHeader("Content-Security-Policy",
    "default-src 'self'; script-src 'self' 'unsafe-inline'");

// unsafe-eval 示例 - 允许动态代码执行
response.setHeader("Content-Security-Policy",
    "default-src 'self'; script-src 'self' 'unsafe-eval'");

// 高危组合 - 同时包含两个不安全指令
response.setHeader("Content-Security-Policy",
    "script-src 'unsafe-inline' 'unsafe-eval'");

// Spring Security 配置示例
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http.headers()
            .contentSecurityPolicy("script-src 'unsafe-inline' 'unsafe-eval'");
    }
}

// 通过代码动态生成的不安全CSP
public String generateCSP(boolean allowInline) {
    String policy = "default-src 'self'; ";
    if (allowInline) {
        policy += "script-src 'unsafe-inline'";  // 危险：根据参数决定是否允许不安全指令
    }
    return policy;
}
```

**快速定位核心操作的技巧（L1：关键词扫描）**

扫描以下关键字组合：
- `unsafe-inline`、`unsafe-eval` 与 CSP 相关方法共现
- 常见的CSP设置方法：`setHeader("Content-Security-Policy"`、`contentSecurityPolicy(`、`CSP配置`
- 在 Filter、Interceptor、SecurityConfig 中搜索这些模式
- 正则模式：`(unsafe-inline|unsafe-eval)` 结合 CSP 相关代码段

**快速定位保护机制的技巧（L2：跳读）**

检查以下保护机制的存在：
- 是否存在 Nonce 机制（动态生成的 `nonce-<value>`）
- 是否使用 Hash 机制（`'sha256-<hash>'` 或 `'sha384-<hash>'`）
- 是否配置了严格的 `default-src` 限制
- 是否实现了 Content Security Policy 的版本控制或动态策略验证
- 是否在开发/测试环境与生产环境使用不同的CSP策略

观察点：
- 正常情况下应使用 `script-src 'self'` 加上具体的白名单域名
- 如果有外部脚本需求，应使用 `'strict-dynamic'` 结合 Nonce
- 避免在 `script-src` 中允许 `data:` 协议
- 检查是否对报告进行了配置：`report-uri` 或 `report-to` 用于监测策略违规

**审计等级标注：**

| 审计等级 | 说明 |
|---------|------|
| L1 | 关键词扫描：在 Java 代码中搜索 `unsafe-inline`、`unsafe-eval`、`CSP`、`Content-Security-Policy` 等关键词 |
| L2 | 跳读：定位到 CSP 设置代码段（Filter、SecurityConfig、Controller），阅读策略内容判断是否包含不安全指令 |
| L3 | 逐行读：检查 CSP 策略的构建逻辑，是否存在条件判断或动态生成不安全指令的场景 |
| L4 | 跨模块追踪：追踪 CSP 策略在安全配置、请求响应、缓存中的完整流转，验证所有出口是否都遵循安全策略 |

---

## Classify

研判漏洞/误报/代码异味的分类理论：

**确定为漏洞的关键指标：**
- 在生产环境或默认配置中明确出现 `unsafe-inline` 或 `unsafe-eval`
- 未配置任何替代的安全机制（Nonce、Hash 等）
- CSP 策略允许执行用户可控的脚本内容（如通过用户输入动态生成策略）
- 在高度敏感的区域（管理后台、支付页面）存在不安全指令
- 没有任何注释说明为什么必须使用这些不安全指令

**可能为误报的情况：**
- 在明确的开发/测试代码中出现，且在生产编译时被移除或覆盖
- 虽然包含 `unsafe-inline`，但同时配置了 Nonce 或强 CSP 上下文
- 代码为传统遗留系统，已有其他层面的安全防御措施（Web应用防火墙等）且无法重构
- 在仅处理静态内容的特定区域使用（需人工判断是否真的只有静态内容）

**代码异味信号：**
- 代码注释明确说明因为兼容性问题而使用不安全指令，但未有计划升级
- CSP 策略在多个地方定义，定义不一致
- 存在条件逻辑决定是否使用不安全指令，说明这个决定存在业务逻辑问题
- CSP 策略过于宽松：如 `script-src *` 或 `default-src *` 等

---

## Low risk

低风险场景的评级指导：

**场景1：仅在特定非关键页面使用不安全指令**
- 该页面不涉及用户敏感数据、认证、授权或交易功能
- 该页面明确不受 XSS 风险影响（例如：完全静态页面被错误标记）
- 示例：文档查看页面、帮助中心、公开的错误提示页面

**场景2：使用了替代的安全机制进行补偿**
- 虽然包含 `unsafe-inline`，但在 `<script>` 标签上配置了动态 Nonce
- 内联样式虽允许，但样式内容完全受控，不来自用户输入
- 示例：框架在运行时为脚本注入 Nonce 值

**场景3：充分的上层防护措施**
- 部署了企业级 WAF（Web 应用防火墙），能有效过滤 XSS 攻击载荷
- 严格的输入验证与输出编码机制已在全栈实施
- 浏览器端和服务端都实现了多层验证
- 注意：WAF 可能被绕过，此评级需谨慎

**场景4：性能优化的有意选择**
- 在充分权衡安全与性能后的明确选择（需有书面决策文档）
- 实施了额外的运行时监测与入侵检测
- CSP 违规通过 `report-uri` 实时监测，可以快速响应异常

**风险降低的客观证据要求：**
- 存在配置管理文档说明为什么必须使用不安全指令
- 实施了定期的安全审计计划
- 如果涉及用户输入，必须有 SAST 工具或人工审计确认不存在 XSS 注入点
- 如果涉及 `unsafe-eval`，需要确认没有 eval()、Function()、setTimeout(string) 等危险模式
