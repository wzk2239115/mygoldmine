# NodeJS API Gateway SSRF

**漏洞类型：** API 网关转发场景中直接使用用户输入构造上游请求，或协议、主机、端口可被用户控制

**漏洞成因**

Node.js 应用中作为 API 网关或反向代理时，常需转发客户端请求至上游服务。当上游服务地址（URL、Host、Port）或请求参数由用户输入控制且缺乏有效验证时，攻击者可指向内网资源或云元数据服务，导致：

- 内网服务访问与探测（扫描端口、服务识别）
- 云元数据服务泄露（AWS IMDSv1、GCP 元数据）
- 本地敏感文件读取（file:// 协议）
- 供应链攻击（DNS 重绑定、二次解析）

---

## Details

### 代码示例

**危险模式1：完整URL由用户指定**
```javascript
// 典型漏洞：直接使用用户输入的完整URL
app.post('/proxy', async (req, res) => {
  const targetUrl = req.body.url;  // 用户完全控制
  const response = await axios.get(targetUrl);  // 无验证直接请求
  res.send(response.data);
});

// 使用fetch（Node 18+原生API）
app.post('/forward', async (req, res) => {
  const url = req.query.target;  // query参数可控
  const result = await fetch(url);
  res.json(await result.json());
});
```

**危险模式2：路径由用户控制，Host硬编码但URL完整可控**
```javascript
app.get('/api/*', async (req, res) => {
  const path = req.params[0];
  const upstreamUrl = `http://backend:8080/${path}`;  // 路径可控，但Host固定
  const result = await axios.get(upstreamUrl);
  res.json(result.data);
});

// 问题：虽然Host固定，但若支持多服务，易演变为完整URL可控
app.get('/service/:name/*', async (req, res) => {
  const serviceName = req.params.name;  // 服务名由用户指定
  const path = req.params[0];
  // 若serviceName映射到URL而非仅作路径，则存在SSRF
  const serviceUrl = `http://${serviceName}.internal:8080/${path}`;
  const result = await axios.get(serviceUrl);
  res.json(result.data);
});
```

**危险模式3：Host头注入**
```javascript
// X-Target-Host 头可被用户控制
app.all('/forward', async (req, res) => {
  const host = req.headers['x-target-host'] || 'default.com';
  const url = `http://${host}/api/data`;  // Host由Header控制
  const resp = await axios.get(url);
  res.send(resp);
});

// Host头与拼接：Referer头用于重定向
app.get('/redirect', async (req, res) => {
  const targetHost = req.get('referer')?.match(/https?:\/\/([^/]+)/)?.[1];
  if (targetHost) {
    const url = `http://${targetHost}/callback`;
    const data = await axios.get(url);
    res.json(data);
  }
});
```

**危险模式4：Port可控导致端口扫描**
```javascript
app.post('/access', async (req, res) => {
  const host = req.body.host;      // 可控，可为内网IP
  const port = req.body.port;      // 可控，用户可扫描任意端口
  const url = `http://${host}:${port}`;
  try {
    const result = await axios.get(url, { timeout: 1000 });
    res.json({ success: true });
  } catch (e) {
    // 通过异常时间差判断端口开放状态
    res.json({ success: false, error: e.message });
  }
});
```

**危险模式5：Cookie/Authorization泄露**
```javascript
const axios = require('axios');

// 创建带有默认认证的axios实例
const client = axios.create({
  timeout: 5000,
  // 问题：若代理转发，默认会携带这些凭证
  headers: {
    'Authorization': `Bearer ${process.env.INTERNAL_TOKEN}`
  }
});

app.get('/proxy', async (req, res) => {
  const url = req.query.url;
  // 此axios实例会自动添加Authorization头
  const result = await client.get(url);
  res.json(result.data);  // 内网服务响应直接返回
});

// 或通过用户指定协议走私凭证
app.post('/callback', async (req, res) => {
  const callback = req.body.callback_url;
  // 若callback内含@ userinfo可走私凭证：http://user:pass@evil.com
  const result = await axios.get(callback);
});
```

**危险模式6：重定向跟随导致SSRF链**
```javascript
const axios = require('axios');

// axios默认跟随重定向(maxRedirects: 5)
app.get('/load', async (req, res) => {
  const externalUrl = req.query.url;

  // 即使externalUrl是公网URL，经过重定向链可跳转至内网
  const response = await axios.get(externalUrl, {
    // 若未显式禁用，则会跟随重定向
    maxRedirects: 5
  });

  res.json(response.data);
});

// 防护不足的白名单
const WHITELIST = ['example.com', 'trusted.com'];
app.get('/proxy-safe', async (req, res) => {
  const url = req.query.url;
  const hostname = new URL(url).hostname;

  if (!WHITELIST.includes(hostname)) {
    return res.status(403).send('Not in whitelist');
  }

  // 问题：白名单验证后，若跟随重定向，重定向目标不再验证
  const response = await axios.get(url);
  res.json(response.data);
});
```

**危险模式7：协议未限制导致文件读取**
```javascript
app.get('/fetch', async (req, res) => {
  const url = req.query.url;

  // axios 与 fetch 不支持file://，但若使用其他库或自定义实现
  // 需要检查协议限制

  // 问题场景：使用了支持多协议的库
  const protocol = new URL(url).protocol;
  // 若无检查，用户可使用 file:///etc/passwd

  const result = await axios.get(url);
  res.json(result.data);
});
```

**危险模式8：DNS重绑定攻击**
```javascript
app.post('/request', async (req, res) => {
  const domain = req.body.domain;

  // 问题：验证时解析IP为公网，但axios请求时再次解析可得内网IP
  // 这是TOCTOU（检查时间/使用时间竞态）漏洞

  const ip = require('dns').resolveSync(domain)[0];

  // 验证 IP 不在黑名单
  const privateRanges = ['127.0.0.1', '10.', '172.16.', '192.168.', '169.254.'];
  const isPrivate = privateRanges.some(r => ip.startsWith(r));

  if (isPrivate) {
    return res.status(403).send('Private IP rejected');
  }

  // 在此期间（检查与请求间），DNS 可被重绑定
  const result = await axios.get(`http://${domain}`);
  res.json(result.data);
});
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- HTTP 客户端库：`axios`、`fetch`、`node-fetch`、`got`、`request`、`http.request`、`https.request`
- 请求方法：`.get()`、`.post()`、`.put()`、`.delete()`、`.request()`、`axios()`、`fetch()`
- 参数来源：`req.body`、`req.query`、`req.params`、`req.headers`、`req.get()`
- 路由定义：`app.get/post/all/use`、`router.`、`handler:`
- URL拼接：`` `http://${...}` ``、字符串 `+` 拼接、`url.resolve()`

**快速定位保护机制 [L2-L3]**

- **白名单检查**：
  - `allowedHosts`、`WHITELIST`、`trustedDomains`、`validServices`
  - 检查是否使用 `includes()`、`indexOf()`、正则 `test()`、精确匹配 `===`
  - 注意：`url.includes('trusted.com')` 可被 `evil.com?x=trusted.com` 绕过

- **协议限制**：
  - 搜索 `protocol`、`scheme` 相关检查
  - 检查是否仅允许 `http:`、`https:`
  - 使用 `new URL().protocol` 或正则 `/^https?:/` 验证

- **IP/内网过滤**：
  - `isPrivateIP()`、`isInternalIP()`、`isLoopback()`
  - `dns.resolve()` 后验证 IP 或者 `net.isPrivateIP()`
  - 注意：需在请求前验证且不易被DNS重绑定

- **重定向防护**：
  - `maxRedirects: 0`、`followRedirect: false`、`redirects: 0`
  - 或在重定向时再次验证目标地址

- **审计等级**：
  - **L1**: 存在白名单/过滤关键字 → 跳读实现细节
  - **L2**: 有基础验证但可能不完整 → 逐行审查绕过方式
  - **L3**: 白名单逻辑正确但跨模块 → 追踪所有调用点
  - **L4**: DNS重绑定防护（锁定IP）或使用框架自动防护

---

## Classify

### 漏洞判定

**确认为真漏洞的特征:**
1. 完整 URL 或 Host 由用户输入控制，无白名单验证
2. 协议未限制，可指定 `file://`、`gopher://` 等危险协议
3. 可访问内网资源（`127.0.0.1`、`10.0.0.0/8`、`169.254.169.254`）
4. 可跟随重定向至内网（白名单验证仅在初始URL）
5. 存在 DNS 重绑定风险（验证后在请求前可重新解析）
6. Port 由用户指定，可进行端口扫描
7. 可观测异常的错误消息、响应时间、状态码判断内网服务开放状态

### 误报判定

**以下情况可排除为误报:**
- URL 来自环境变量或配置文件，非运行时用户输入
- 仅路径参数可控，`scheme` 和 `host` 完全硬编码
- 存在严格的白名单：精确匹配（`===` 或 `.includes()`）+ 协议限制 + IP验证 + 重定向禁止
- 代理目标从可信来源（数据库、服务注册中心）根据索引查询，索引验证完备
- 中间件或全局过滤器统一防护所有请求

### 代码异味

**需要进一步审查的特征:**
- 白名单使用字符串包含而非精确匹配，如 `url.includes('trusted.com')`
- 正则表达式未锚定，如 `matches(".*\\.trusted\\.com")` 可匹配 `trusted.com.evil.com`
- 重定向处理不当，白名单验证仅在初始请求
- 依赖请求库的默认行为（应显式配置安全参数）
- 使用自定义 URL 解析逻辑而非标准 `new URL()` API
- DNS 查询与请求间存在时间窗口，易被DNS重绑定

---

## Low risk

**以下场景可评为低风险:**

1. **严格的白名单防护**
   - 精确匹配：`if (url === WHITELIST[hostname]) { ... }`
   - 支持 CIDR 或子域名白名单但逻辑正确
   - 协议明确限制为 `http` 和 `https`
   - 重定向禁用或重定向后再次验证

2. **内网资源访问受网络层限制**
   - 应用运行在严格的网络隔离环境
   - 防火墙规则显式禁止访问内网敏感段（`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`）
   - 元数据服务地址 `169.254.169.254` 被路由黑洞或防火墙阻止

3. **仅后端服务间通信**
   - 转发目标为明确的内部服务地址，所有服务间通信均在可信网络
   - 请求需要身份验证（mTLS、签名），即使指向内网也无法被恶意利用
   - 响应内容不直接返回给用户，仅用于内部日志或异步处理

4. **功能设计合理且访问受限**
   - 此功能仅限管理员或高权限用户访问
   - 有严格的速率限制和请求日志记录
   - 用户指定的 URL 仅用于特定资源类型（图片、文档），返回前检查 Content-Type

5. **DNS 重绑定防护**
   - DNS 查询与请求间使用 IP 锁定（第一次解析 IP 后缓存，后续请求使用缓存IP）
   - 使用 `CURLOPT_RESOLVE`（cURL）或等效机制固定 IP 映射
   - 或使用支持防护的库/框架（如 Go 的 `net.Dialer.Control`）

6. **响应内容控制**
   - 即使成功访问，响应内容过滤严格（仅返回元数据、头信息，不返回响应体）
   - 或响应经过完整性校验（签名、HMAC），异常响应会被识别

7. **攻击成本高或难以利用**
   - 虽有潜在风险但利用难度高（需特定网络条件、多步骤准备）
   - 环境中所有可达的内网服务已加固（强身份验证、无敏感数据暴露）

