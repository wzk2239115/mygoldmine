# JavaScript / TypeScript - Insecure OAuth Redirect

## Details

### 代码示例

```typescript
// 示例1: 未验证 redirect_uri（开放重定向）
app.get('/oauth/authorize', (req, res) => {
  const redirectUri = req.query.redirect_uri;
  const authCode = generateAuthCode();
  res.redirect(`${redirectUri}?code=${authCode}`); // 危险：未校验直接跳转
});

// 示例2: 宽松的域名白名单（正则绕过）
const allowedDomains = /.*\.example\.com$/;
if (allowedDomains.test(redirectUri)) {
  res.redirect(redirectUri); // 危险：可被 evil.example.com.attacker.com 绕过
}

// 示例3: 通配符匹配（协议绕过）
const config = {
  redirectUris: ['http://*.example.com/*'] // 危险：允许任意子域和路径
};

// 示例4: 仅验证前缀（路径遍历）
if (redirectUri.startsWith('https://example.com')) {
  res.redirect(redirectUri); // 危险：可被 https://example.com.evil.com 绕过
}

// 示例5: 前端 OAuth 回调（未验证 state）
useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const state = params.get('state');
  // 危险：未验证 state 导致 CSRF
  exchangeCodeForToken(code);
}, []);

// 示例6: 动态构造重定向（URL 拼接）
const baseUrl = 'https://oauth.provider.com/authorize';
const redirectUrl = `${baseUrl}?redirect_uri=${userInput}`; // 危险：未编码导致注入
window.location.href = redirectUrl;
```

### 快速定位核心操作（审计技巧）

**L1 - 关键词扫描：**
- 参数名：`redirect_uri`、`redirect_url`、`callback`、`return_to`、`continue`、`next`
- 函数调用：`res.redirect()`、`window.location`、`Router.push()`、`navigate()`
- OAuth关键词：`/oauth/`、`/authorize`、`access_token`、`auth_code`、`state`

**L2 - 跳读：**
- 路由处理器：重点看 `/oauth/*`、`/callback`、`/auth/*` 路由的 handler
- 查询参数提取：检查 `req.query`、`req.params`、`URLSearchParams` 的使用
- 重定向调用点：快速定位所有 `redirect()`、`location.href=` 语句

**L3 - 逐行读：**
- URL 解析逻辑：检查是否使用 `new URL()` 解析并验证 origin/hostname
- 白名单比对：分析正则表达式或字符串比对的严格性（`===` vs `includes()`）
- state 参数生成与验证：追踪 state 的生成、存储、校验三个环节
- 协议检查：确认是否强制 `https://` 协议

**L4 - 跨模块追踪：**
- 配置文件读取：追踪 `allowedRedirects` 配置来源（`.env`、数据库、硬编码）
- 中间件链：检查是否有全局 redirect 验证中间件
- 第三方库集成：关注 `passport.js`、`next-auth` 等库的配置项
- 客户端注册流程：追踪 OAuth client 的 `redirect_uris` 注册与存储逻辑

### 快速定位保护机制（审计技巧）

**L1 - 关键词扫描：**
- 验证函数：`validateRedirectUri()`、`isAllowedOrigin()`、`checkCallback()`
- 白名单变量：`ALLOWED_ORIGINS`、`TRUSTED_DOMAINS`、`redirectWhitelist`
- 安全库：`validator.isURL()`、`url-parse`、`cors` 配置

**L2 - 跳读：**
- 验证时机：检查 redirect 前是否有 `if (validate())` 守卫逻辑
- 精确匹配：查找 `===`、`Set.has()`、数组 `includes()` 的完整 URL 比对
- state 机制：确认是否生成随机 state 并与 session/cookie 绑定

**L3 - 逐行读：**
- URL 规范化：检查是否统一处理尾部斜杠、端口号、大小写
- 协议降级防护：确认是否拒绝 `javascript:`、`data:`、`file:` 等危险协议
- 子域隔离：验证逻辑是否区分 `example.com` 与 `sub.example.com`
- 编码处理：检查 URL 参数是否经过 `encodeURIComponent()` 编码

**L0 - 快速跳过：**
- 测试文件：`*.test.ts`、`*.spec.ts`、`__tests__/` 目录
- Mock服务：本地开发的 OAuth mock server
- 文档示例：注释中的伪代码、README 的演示代码

## Classify

### 确认为漏洞的判定标准：
- 直接使用用户可控的 `redirect_uri` 参数进行跳转且无任何验证
- 白名单验证存在绕过可能（正则缺陷、前缀匹配、协议缺失）
- state 参数未生成或未验证，可导致 CSRF 攻击
- 授权码/访问令牌泄露到不可信的第三方域
- 验证逻辑在客户端实现，服务端无二次校验

### 误报的常见场景：
- 内部系统间跳转，所有域名均在可控范围内且有网络隔离
- redirect_uri 来自数据库的已注册客户端白名单且注册需管理员审核
- 使用成熟库（如 `passport.js`）且配置正确（精确匹配模式）
- 仅跳转到固定的 `/dashboard`、`/home` 等内部路径（无参数拼接）

### 代码异味的判定：
- 使用宽松的正则表达式（`.*`、`.+`）进行域名匹配
- 白名单中包含通配符且未明确限制子域数量
- 验证逻辑与跳转逻辑相隔多个函数调用，存在逻辑分支绕过风险
- 客户端有验证但服务端未同步实现，可通过直接 API 调用绕过
- 开发环境的宽松配置未通过环境变量区分生产环境

### 研判流程：
1. 识别数据流：追踪 `redirect_uri` 从用户输入到 `redirect()` 的完整链路
2. 评估验证强度：测试白名单逻辑能否被常见绕过技术突破
3. 检查 state 绑定：确认 state 是否与用户会话强绑定且有时效性
4. 模拟攻击场景：构造 PoC URL 验证是否可泄露授权码到攻击者域
5. 确认影响范围：评估泄露的 token 权限范围和有效期

## Low Risk

### 低风险场景评级标准：

**场景1：完全内部系统**
- 所有 `redirect_uri` 均指向同一内网域名下的路径
- 网络层面已通过防火墙/VPN 隔离，外部域名无法访问
- OAuth 仅用于内部服务间的单点登录（SSO）

**场景2：严格的静态白名单**
- redirect_uri 通过 `Set` 或数组精确匹配（含协议、域名、路径、端口）
- 白名单配置在编译时确定，运行时不可修改
- 所有白名单域名均为自有且受控的资产

**场景3：成熟框架的正确配置**
- 使用 `next-auth`、`Auth0 SDK` 等经过安全审计的库
- 配置文件中明确指定 `redirect_uri_strict_mode: true`
- 框架内置 state 验证且未被开发者禁用

**场景4：仅授权无敏感数据**
- OAuth 流程仅用于身份验证，不返回访问令牌
- 授权码有效期极短（<30秒）且仅可使用一次
- 即使泄露也无法通过 PKCE 验证（适用于公开客户端）

**评级降级条件（即使符合低风险也需提升等级）：**
- 系统处理高敏感数据（金融、医疗、政务）即使验证较严格也应严格审查
- 白名单中包含第三方托管服务（如 CDN、analytics.js）可能被链式利用
- 历史漏洞记录显示该系统曾因 OAuth 配置问题被攻破
- 多租户环境下不同租户共享 OAuth 配置，存在横向越权风险