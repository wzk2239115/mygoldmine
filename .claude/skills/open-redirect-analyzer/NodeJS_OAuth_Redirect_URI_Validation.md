# Node.js OAuth 回调处理中 redirect_uri 未验证漏洞

OAuth 授权流程中，授权服务器必须严格验证 `redirect_uri` 参数，确保其与预先注册的重定向URI完全一致。当 Node.js 应用在处理 OAuth 回调时未进行有效验证，攻击者可利用此漏洞伪造授权码、窃取访问令牌，将用户重定向至恶意网站进行钓鱼攻击、凭证窃取或恶意内容注入。

## Details

### 代码示例

**漏洞代码：授权端点未验证 redirect_uri**

```javascript
// OAuth 授权端点 - 漏洞实现
app.get('/oauth/authorize', (req, res) => {
  const clientId = req.query.client_id;
  const redirectUri = req.query.redirect_uri;
  const scope = req.query.scope;
  const state = req.query.state;

  // 仅验证client_id存在，未验证redirect_uri
  const client = clients[clientId];
  if (!client) {
    return res.status(400).json({ error: 'invalid_client' });
  }

  // 直接生成授权码，不验证redirect_uri是否与注册时一致
  const authCode = generateAuthCode(clientId);
  authorizationCodes.set(authCode, {
    clientId,
    // ❌ 缺陷：未记录或验证redirect_uri
    expiresAt: Date.now() + 10 * 60 * 1000
  });

  // 直接使用用户提供的redirect_uri进行重定向
  const redirectUrl = `${redirectUri}?code=${authCode}&state=${state}`;
  res.redirect(redirectUrl);
});

// 令牌端点 - 不完整的验证
app.post('/oauth/token', (req, res) => {
  const clientId = req.body.client_id;
  const code = req.body.code;
  const redirectUri = req.body.redirect_uri;

  // 仅验证code是否有效，未检查redirect_uri一致性
  const codeData = authorizationCodes.get(code);
  if (!codeData || codeData.expiresAt < Date.now()) {
    return res.status(400).json({ error: 'invalid_grant' });
  }

  // ❌ 漏洞：未验证此处的redirect_uri与授权时的值是否一致
  const token = generateAccessToken(clientId);
  res.json({
    access_token: token,
    token_type: 'Bearer',
    expires_in: 3600
  });
});

// 调用示例：
// 攻击流程：
// 1. GET /oauth/authorize?client_id=myapp&redirect_uri=https://attacker.com/steal&state=xyz
// 2. 授权码直接泄露到attacker.com: https://attacker.com/steal?code=ABC123&state=xyz
// 3. 攻击者在令牌端点兑换令牌，获得访问受害用户账户的权限
```

**变种漏洞：部分验证但存在绕过**

```javascript
// 不安全的URL验证方式
app.get('/oauth/authorize', (req, res) => {
  const clientId = req.query.client_id;
  const redirectUri = req.query.redirect_uri;

  const client = clients[clientId];

  // ❌ 绕过1：仅检查前缀，允许子域绕过
  if (redirectUri.startsWith('https://myapp.com')) {
    // 这样会接受 https://myapp.com.attacker.com/callback
  }

  // ❌ 绕过2：使用includes检查，允许任意位置匹配
  if (redirectUri.includes('myapp.com')) {
    // 这样会接受 https://xmyapp.comdomain.com 或 https://attacker.com?ref=myapp.com
  }

  // ❌ 绕过3：未处理协议相对URL
  // 白名单中可能有 https://myapp.com/callback
  // 但接受 //attacker.com/callback (协议相对URL)
  if (client.redirectUris.includes(redirectUri)) {
    // 攻击者发起: /oauth/authorize?redirect_uri=//attacker.com/steal
  }

  // ❌ 绕过4：URL编码或双编码
  // 白名单验证可能在解码后，但重定向使用原始输入
  // 导致验证通过但重定向到恶意地址
});

// 回调处理端点 - 危险的应用集成
app.get('/auth/callback', (req, res) => {
  const code = req.query.code;
  const state = req.query.state;

  // 虽然验证了state，但若授权服务器未验证redirect_uri
  // 这段验证形同虚设
  if (state !== sessionState[req.sessionID]) {
    return res.status(400).json({ error: 'state mismatch' });
  }

  // ❌ 即使state正确，此时code已泄露给攻击者
  // 若后端无法验证code的真实性，攻击者可伪造
  const tokenResponse = await exchangeCodeForToken(code);

  // ...
});
```

### 快速定位到核心操作的技巧 【L1: 关键词扫描】

- 搜索关键词：`redirect_uri`、`req.query.redirect_uri`、`req.body.redirect_uri`、`res.redirect()`
- 定位授权端点：查找处理 `/authorize`、`/oauth/authorize`、`/oauth2/authorize`、`/auth/authorize` 的路由处理函数
- 定位令牌交换端点：查找处理 `/token`、`/oauth/token`、`/oauth2/token`、`/auth/token` 的路由处理函数
- 识别授权码生成：搜索 `generateAuthCode()`、`crypto.randomBytes()`、`nanoid()` 等生成函数
- 追踪重定向操作：`res.redirect()`、URL模板字符串、查询参数拼接的所有位置
- 定位回调处理：应用集成端点 `/callback`、`/auth/callback`、`/oauth/callback`、`/login/callback`

### 快速定位到保护机制的技巧 【L2: 跳读】

- **授权端点的redirect_uri验证**：
  - 搜索在使用 `redirect_uri` 前的验证调用：`validateRedirectUri()`、`isRegisteredRedirectUri()`、`checkRedirectUri()`
  - 查找白名单查表操作：`client.redirectUris`、`registeredURIs[clientId]`、`allowedRedirects.get()`
  - 寻找URL解析操作：`new URL(redirectUri)`、`url.parse()`、`.hostname`、`.pathname` 的检查
  - 确认验证结果是否被使用：验证失败时应 `res.status(400)` 而非继续执行

- **授权码与redirect_uri的绑定**：
  - 查看授权码生成时是否记录了 `redirectUri`：`authorizationCodes.set(code, { clientId, redirectUri, ... })`
  - 确认记录的是验证后的值，而非用户输入的原始值

- **令牌端点的redirect_uri一致性验证**：
  - 查找令牌兑换时是否取出了授权码中的 `redirectUri`
  - 搜索将请求中的 `redirect_uri` 与存储的 `redirectUri` 进行比对的代码
  - 确认使用的是 `===` 精确比较，而非模式匹配或包含检查
  - 验证失败时应拒绝令牌生成

- **验证函数的完整性**：
  - 检查验证函数内部逻辑：`startsWith()`、`includes()`、`===` 哪种方式
  - 确认处理了URL编码、协议相对URL等边界情况
  - 查看是否对白名单进行了标准化处理（移除末尾斜杠、规范化协议等）

## Classify

### ✅ 确认漏洞

**漏洞的判断依据：**

- 授权端点完全不验证 `redirect_uri`，直接使用查询参数进行重定向，或仅检查 `client_id` 存在性
- 授权端点生成授权码时未记录 `redirect_uri`，令牌端点因此无法进行一致性验证
- 授权端点存在验证但存在绕过：
  - 使用 `startsWith()` 或 `includes()` 进行域名检查，未防止子域绕过（`https://myapp.com.attacker.com`）
  - 接受协议相对URL（`//attacker.com`），而白名单中使用完整URL
  - 使用字符串操作而非 `new URL()` 解析，导致 `https://attacker.com?redirect_uri=https://myapp.com` 型绕过
  - 处理URL编码不当，验证 URL 编码后的值但重定向使用原始值，或反之
- 令牌端点未验证 `redirect_uri` 与授权请求时的 `redirect_uri` 一致性，仅检查授权码本身有效性
- 授权码与redirect_uri无强制绑定关系，攻击者用授权码兑换时可提供任意redirect_uri

**具体攻击场景：**

- 授权码拦截：攻击者诱导用户访问 `/oauth/authorize?client_id=app&redirect_uri=https://attacker.com/callback`，授权码直接泄露到attacker.com
- 令牌兑换：攻击者获得授权码后，若令牌端点未验证redirect_uri一致性，可用自己的redirect_uri兑换（虽然OAuth规范要求必须提供redirect_uri）
- 账户接管：攻击者获得访问令牌后可访问用户资源，进行账户接管、数据窃取或恶意操作

### ⚠️ 代码异味

- OAuth流程中存在redirect_uri验证逻辑，但仅对授权端点验证，令牌端点缺失一致性检查
- 验证函数存在但使用了不安全的字符串方法（`startsWith`、`includes`）而非URL解析库
- 授权码与redirect_uri无绑定关系，令牌端点虽然要求redirect_uri参数但未进行比对
- 存在多个授权流程分支（如不同的OAuth库、自定义实现混用），部分验证完整，部分验证不完整
- 使用过时的URL验证方式，虽未成为漏洞但不符合RFC 6749规范要求
- redirect_uri白名单允许通配符或过于宽泛的域名模式

### ❌ 误报

- `redirect_uri` 完全硬编码于服务端配置中，不从用户输入接收
- 授权端点在生成授权码前对 `redirect_uri` 进行了完整的白名单验证：
  - 使用 `new URL()` 解析后进行 `hostname` 和 `pathname` 的完整比对
  - 使用 `===` 精确比较，白名单由常量或配置定义，不可被用户输入控制
  - 验证失败时明确返回 `invalid_redirect_uri` 错误，拒绝授权码生成
- 授权码生成时记录了验证后的 `redirect_uri`（而非用户输入的原始值）
- 令牌端点在兑换令牌前严格验证了 `redirect_uri` 与授权请求时的值完全一致
- 使用成熟的 Node.js OAuth 库（如 `oauth2-server`、`simple-oauth2`、`passport`），库已内置redirect_uri验证并正确配置

## Low risk

低风险情况的评级标准：

**完整的redirect_uri白名单验证**

- 代码在授权端点明确检查 `redirect_uri` 是否在预注册的白名单中：
  ```javascript
  const client = clients[clientId];
  if (!client.redirectUris.includes(redirectUri)) {
    return res.status(400).json({ error: 'invalid_redirect_uri' });
  }
  ```
- 使用 `new URL()` 进行标准化和精确比较，而非字符串操作：
  ```javascript
  try {
    const providedUrl = new URL(redirectUri);
    const registeredUrl = new URL(client.redirectUris[0]);
    if (providedUrl.href !== registeredUrl.href) {
      return res.status(400).json({ error: 'invalid_redirect_uri' });
    }
  } catch (e) {
    return res.status(400).json({ error: 'invalid_redirect_uri' });
  }
  ```
- 白名单中明确列举所有允许的重定向URI（至多使用一层子域通配符，如 `*.myapp.com`，并在应用层确保子域受控）
- 验证过程在生成授权码前进行，失败时拒绝请求

**授权码与redirect_uri的强制绑定**

- 授权码生成时必须记录经过验证的 `redirect_uri`：
  ```javascript
  const authCode = generateAuthCode(clientId);
  authorizationCodes.set(authCode, {
    clientId,
    redirectUri: redirectUri,  // 存储验证后的值
    expiresAt: Date.now() + 10 * 60 * 1000,
    used: false
  });
  ```
- 令牌端点兑换时强制验证 `redirect_uri` 与授权时一致：
  ```javascript
  const codeData = authorizationCodes.get(code);
  if (codeData.redirectUri !== redirectUri) {
    return res.status(400).json({ error: 'invalid_grant' });
  }
  ```
- 授权码一次性使用，兑换后标记为已用，防止重放攻击

**规范的OAuth2流程实现**

- 授权端点在重定向时使用验证过的 `redirect_uri`（从存储中取出），而非用户输入
- 令牌端点强制要求 `redirect_uri` 参数，并与授权请求时的值进行逐字符比较
- 授权码具有短期有效期（通常5-10分钟）且仅可使用一次
- 遵循RFC 6749 Section 4.1.3的规范：token endpoint必须要求redirection URI且与授权请求中的值完全一致

**框架级或库级安全特性**

- 使用成熟的Node.js OAuth2库（如 `oauth2-server`、`ory/hydra`客户端、`@panva/node-openid-client`）
- 库的redirect_uri验证已通过安全审计，实现符合RFC规范
- 在中间件或统一的验证层实现redirect_uri检查，所有OAuth端点均通过此层处理
- 库或中间件代码包含详细注释，明确说明验证逻辑和RFC规范要求
