# NodeJS 登录重定向未校验漏洞审计

## Details

### 漏洞成因
登录认证成功后，应用直接使用用户提供的 `returnUrl`/`redirect_uri`/`callback` 等参数进行重定向，而未对目标 URL 的域名、协议或来源进行任何白名单验证。攻击者可构造恶意登录链接诱导受害用户，在通过身份认证后被重定向至第三方恶意网站，从而窃取会话 Token、进行钓鱼攻击或传播恶意代码。

### 代码示例与快速定位
**核心操作位置** （L1: 关键词扫描）
- 扫描关键参数：`returnUrl`, `redirect`, `redirect_uri`, `callback`, `return_to`, `next`, `back_url`, `landing_url`, `goto`
- 扫描重定向调用：`res.redirect()`, `res.location()`, `window.location`, `window.location.href`, `window.location.replace()`, `location.assign()`

典型易漏代码模式：
```javascript
// 登录验证后的重定向逻辑
app.post('/login', async (req, res) => {
  const { username, password, returnUrl } = req.body;

  // 身份认证...
  if (isValidCredentials(username, password)) {
    // ❌ 危险：直接使用用户提供的 returnUrl
    res.redirect(returnUrl);
  }
});

// 或在前端
if (loginResponse.success) {
  // ❌ 危险：直接跳转到 returnUrl 参数
  window.location.href = urlParams.get('returnUrl');
}
```

**保护机制检查位置** （L2: 跳读）
- 检查是否存在 URL 白名单验证（Allow-list Pattern）
- 检查是否对 URL 进行了协议校验（必须是 `http://` 或 `https://`，禁止 `javascript:`, `data:`, `file:` 等危险协议）
- 检查是否对域名进行了 origin/host 白名单校验
- 检查是否使用了 URL 解析器进行完整性验证（防止绕过技巧）
- 搜索关键安全函数：`URL`, `new URL()`, `urlParse()`, `isAllowedUrl()`, `isValidRedirect()`, `validateReturnUrl()`, `whitelist`, `allowedDomains`, `trustedHosts`

应该存在的防护代码模式：
```javascript
// 正确做法
const ALLOWED_DOMAINS = ['example.com', 'trusted-app.com'];

function isValidRedirectUrl(url) {
  try {
    const parsed = new URL(url);
    // 1. 协议校验
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return false;
    }
    // 2. 域名白名单校验
    return ALLOWED_DOMAINS.includes(parsed.hostname);
  } catch {
    return false;
  }
}

app.post('/login', async (req, res) => {
  const { returnUrl } = req.body;
  if (isValidRedirectUrl(returnUrl)) {
    res.redirect(returnUrl);
  } else {
    res.redirect('/dashboard'); // 默认安全路径
  }
});
```

## Classify

### 漏洞判定标准
确认为 **漏洞** 需同时满足：
1. **参数可控性**：用户可通过 URL 参数、POST 数据、Cookie 等方式控制重定向目标
2. **缺乏有效白名单**：不存在对目标 URL 的域名/来源验证，或白名单验证存在绕过（如协议校验缺失、正则表达式不严谨）
3. **完整链路**：从参数输入 → 认证成功 → 重定向输出，完整链路未中断

### 判定为 **误报** 的情况
- 重定向目标已硬编码在代码中，用户参数仅用于内部路由选择（如 `if (returnUrl === 'dashboard')` 后再构造完整 URL）
- 虽然接收用户参数，但已通过严格的白名单验证（使用 `URL` 类解析 + 域名列表校验）
- 重定向发生在同域名内（相对路径重定向，如 `/dashboard` 而非完整 URL）
- 使用了成熟的安全库（如 `passport.js` 的官方回调处理，且正确配置了 `callbackURL` 白名单）

### 判定为 **代码异味** 的情况
- 存在不完整的验证逻辑，如仅检查 URL 是否以 `https://` 开头，但未验证域名
- 存在防护机制但存在明显绕过手段（如使用 URL 编码、双重编码、大小写混淆等绕过黑名单）
- 使用了易被绕过的验证方式（如 `includes()` 或前缀匹配检查，而非 URL 解析 + 完整域名比对）
- 存在多个重定向调用，部分有保护而部分没有保护（不一致性）

## Low risk

### 低风险评级场景
1. **受限的重定向范围**
   - 仅支持内部相对路径重定向（如 `/profile`, `/settings`），不支持外部 URL
   - 仅重定向到同一子域名内（如 `app.example.com` 内部的相对跳转）

2. **存在不完整但有一定防护的机制**
   - 虽未实现完整的白名单，但使用了协议校验（禁止 `javascript:`, `data:` 等）
   - 使用了正则表达式进行域名检查，虽有绕过风险但难度较高（如 `/^https:\/\/[a-z0-9]+\.example\.com$/`）
   - 使用了 URL 编码防护，防止了最直观的注入，但理论上存在高级绕过

3. **业务上下文的风险降低**
   - 重定向仅在内部系统中使用，外部用户难以访问到登录页面
   - 登录参数需要多步验证（如电话 OTP 确认），单纯 returnUrl 参数注入风险被大幅降低
   - 应用对身份认证的 Token 有严格的生命周期限制（如仅 1 分钟内有效），减少了攻击窗口

4. **框架级默认防护**
   - 使用了现代 Web 框架的内置防护（如 Next.js 的 API 路由默认同源策略）
   - CSP（Content Security Policy）策略严格禁止了 `<meta>` 刷新和 JavaScript 跳转到外部站点
