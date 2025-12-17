# NodeJS_FetchUserProvidedURL

**漏洞类型**: 使用 axios/node-fetch 等 HTTP 客户端发起用户控制的请求，缺乏对目标地址的过滤

**漏洞成因**

Node.js 应用中需要从用户提供的 URL 获取资源时（图片预览、文档转换、资源加载等），若直接将用户输入用于 HTTP 请求且缺乏验证，攻击者可指向内网地址、云元数据服务或本地文件，导致：

- 内网端口扫描和服务探测
- 云环境元数据服务泄露（AWS、GCP、Azure）
- 本地敏感文件读取
- 拒绝服务（加载超大文件、握手协议攻击）
- 内网反向代理穿透

---

## Details

### 代码示例

**危险模式1：完整URL由用户指定，无任何验证**
```javascript
// axios 示例
const axios = require('axios');
app.get('/fetch', async (req, res) => {
  const url = req.query.url; // 用户可控输入
  const response = await axios.get(url); // 直接使用未过滤的URL
  res.json(response.data);
});

// node-fetch 示例
const fetch = require('node-fetch');
app.post('/proxy', async (req, res) => {
  const targetUrl = req.body.target; // 用户输入
  const result = await fetch(targetUrl); // 无验证直接请求
  res.send(await result.text());
});

// got 示例
const got = require('got');
app.get('/download', async (req, res) => {
  const fileUrl = req.query.file;
  const data = await got(fileUrl).text(); // 用户完全控制目标
  res.send(data);
});
```

**危险模式2：仅检查协议或黑名单，可被绕过**
```javascript
// 危险的黑名单检查
app.get('/preview', async (req, res) => {
  const url = req.query.url;

  // 黑名单检查：仅禁止127.0.0.1，但允许其他内网地址
  if (url.includes('127.0.0.1') || url.includes('localhost')) {
    return res.status(403).send('Internal access denied');
  }

  // 攻击者可使用：
  // - http://127.1 (八进制简写)
  // - http://0 (等同于127.0.0.1)
  // - http://169.254.169.254 (AWS元数据)
  // - http://[::1] (IPv6本地回环)
  // - http://10.0.0.1 (RFC1918私网)

  const response = await axios.get(url);
  res.json(response.data);
});

// 不完整的协议检查
app.post('/load', async (req, res) => {
  const url = req.body.url;

  // 错误的协议验证：大小写混淆可绕过
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return res.status(403).send('Invalid protocol');
  }

  // 攻击者可使用 HTTP:// 或 HtTp:// 绕过（取决于库的实现）
  // 或使用 javaScript://、data:// 等

  const response = await axios.get(url);
  res.json(response.data);
});
```

**危险模式3：DNS重绑定攻击**
```javascript
app.post('/resource', async (req, res) => {
  const domain = req.body.domain;

  // 问题：先验证IP，再请求时可能重新解析
  const dns = require('dns').promises;
  const ip = await dns.resolve4(domain);

  // 验证 IP 不是私网
  const isPrivate = ip[0].startsWith('10.') ||
                    ip[0].startsWith('172.16.') ||
                    ip[0].startsWith('192.168.');

  if (isPrivate) {
    return res.status(403).send('Private IP rejected');
  }

  // 在此期间，DNS 可被重绑定至内网 IP
  // 参考：https://en.wikipedia.org/wiki/DNS_rebinding
  const result = await axios.get(`http://${domain}/data`);
  res.json(result.data);
});
```

**危险模式4：重定向跟随导致SSRF链**
```javascript
const axios = require('axios');

// axios 默认跟随重定向
app.get('/fetch-page', async (req, res) => {
  const url = req.query.url;

  // 白名单检查
  const WHITELIST = ['example.com', 'github.com', 'google.com'];
  const hostname = new URL(url).hostname;

  if (!WHITELIST.includes(hostname)) {
    return res.status(403).send('Host not in whitelist');
  }

  // 问题：即使初始URL在白名单内，若跟随302重定向
  // 重定向目标（如 http://127.0.0.1:9200）不再验证
  const response = await axios.get(url);
  // axios默认maxRedirects: 5，会跟随重定向

  res.json(response.data);
});
```

**危险模式5：内容类型未验证导致文件读取**
```javascript
app.post('/preview', async (req, res) => {
  const url = req.body.url;

  // 即使URL来自可信域名，也可能被恶意利用
  const response = await axios.get(url);

  // 问题：未检查Content-Type，可能接收恶意内容
  // 若用第三方库处理（如PDF转图片），可能触发漏洞

  // 返回原始响应给用户或缓存
  res.type(response.headers['content-type']);
  res.send(response.data);
});
```

**危险模式6：超时时间过长导致DOS**
```javascript
const axios = require('axios');

app.get('/fetch', async (req, res) => {
  const url = req.query.url;

  // 超时时间过长，攻击者可发送超大文件或握手延迟
  const response = await axios.get(url, {
    timeout: 30000  // 30秒超时太长
  });

  // 或使用fetch（默认无超时）
  const result = await fetch(url);
  const text = await result.text();  // 可能堵塞

  res.json({ data: text });
});
```

**危险模式7：响应直接返回导致信息泄露**
```javascript
app.post('/load', async (req, res) => {
  const resourceUrl = req.body.url;

  try {
    const response = await axios.get(resourceUrl);
    // 响应头和响应体直接返回
    res.set(response.headers);
    res.send(response.data);
  } catch (error) {
    // 错误信息泄露内网信息
    res.json({
      error: error.message,  // "connect ECONNREFUSED 127.0.0.1:9200"
      code: error.code,
      errno: error.errno
    });
  }
});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描:**
- HTTP 客户端库导入: `require('axios')`、`import axios`、`require('node-fetch')`、`require('got')`、`require('request')`
- 请求方法: `.get()`、`.post()`、`.put()`、`.delete()`、`fetch()`、`axios()`、`got()`、`.request()`
- 参数来源: `req.query`、`req.body`、`req.params`、`req.headers`
- URL 处理: `` `http://${...}` ``、`new URL()`、`url.parse()`、`url.resolve()`

**L2 跳读定位:**
- 从路由处理函数入口扫描用户输入获取点
- 追踪用户输入变量到 HTTP 请求调用点之间是否有 URL 构造逻辑
- 重点关注: 完整 URL 字符串作为参数、模板字符串拼接、URL 构造函数参数
- 检查是否有异常处理可能泄露内网信息

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测:**
- URL 白名单检查: `allowedDomains.includes()`、`whitelistHosts.indexOf()`、正则匹配 `url.match(/^https:\/\/trusted\.com/)`
- URL 解析验证: `new URL()`、`url.parse()` 然后检查 `hostname`、`protocol`
- IP 过滤: 检查是否有 `isPrivateIP()`、`isInternalIP()` 等函数调用
- 重定向配置: `maxRedirects`、`followRedirect`、`redirect` 参数设置

**L3 逐行分析:**
- 检查白名单实现是否可绕过（如 `url.startsWith()` 可用 `@` 或大小写绕过）
- 验证重定向跟随是否禁用（`maxRedirects: 0`、`followRedirect: false`）
- 确认协议限制是否完整（仅允许 `http/https`）
- 检查超时是否过长（应 < 5s）

**L4 跨模块追踪:**
- 追踪自定义验证函数的实现完整性
- 检查中间件或全局拦截器中的保护措施
- 验证配置文件中的全局 HTTP 客户端设置（如 axios 默认配置）
- 检查异常处理是否泄露内网信息

---

## Classify

### 漏洞判定标准

**确认为真漏洞的特征:**
1. 用户可完全控制请求目标 URL，且无任何验证
2. 可访问内网资源（`127.0.0.1`、`169.254.x.x`、RFC1918 地址、其他内网服务）
3. 可访问云元数据服务（`169.254.169.254`）
4. 保护机制存在可绕过缺陷（如协议检查大小写混淆、黑名单不完整、解析差异）
5. 可跟随重定向链从白名单域名重定向至内网地址
6. DNS 重绑定未防护（验证 IP 后仍可在请求前重新解析）
7. 响应内容直接返回给用户或缓存，可泄露内网服务信息
8. 超时时间过长导致 DoS 风险

**误报判定:**
- URL 来自可信配置文件或环境变量，非运行时用户输入
- URL 仅包含用户可控的 query 参数，域名部分硬编码（须确认无 Host 头覆盖）
- 存在完整且正确的白名单验证（精确匹配 + 协议限制 + IP 过滤 + 重定向禁止）
- 在隔离沙箱/容器中运行，无敏感内网资源可访问
- 功能仅限高权限用户访问且有审计日志

**代码异味:**
- 有基础验证但不够完善（如仅检查协议，未限制域名）
- 使用黑名单而非白名单（容易被绕过）
- 依赖客户端传递的 `Host`、`Referer` 头进行验证
- URL 处理逻辑分散多处，难以统一防护
- 错误处理不当，泄露内网信息（IP、服务名、异常堆栈）
- 白名单检查使用字符串包含而非精确匹配

---

## Low risk

**以下场景可评为低风险:**

1. **严格的白名单防护**
   - 精确匹配白名单域名或 IP 地址（`===` 而非 `includes()`）
   - 协议明确限制为 `http` 和 `https` 只
   - 重定向完全禁用（`maxRedirects: 0`）
   - 若不禁用重定向，则重定向后再次验证目标

2. **应用场景受限**
   - 功能仅限管理员或高权限用户可访问
   - 需要有效的身份验证令牌且有严格速率限制（<10/min）
   - 所有请求完整记录且有实时异常检测

3. **网络隔离保护**
   - 应用部署在严格的网络隔离环境，出口流量受防火墙限制
   - 防火墙规则显式禁止访问内网敏感段和元数据服务
   - 即使 SSRF 成功，内网服务也因网络隔离而无法访问

4. **响应内容控制**
   - 响应内容经过严格过滤，仅返回必要的元数据（Content-Type、大小等）
   - 完整响应体被过滤或丢弃
   - 错误消息不泄露内部信息（无 IP、服务名、异常堆栈）

5. **操作限制**
   - 超时时间极短（<3s），难以进行端口扫描或握手攻击
   - 响应大小限制（<1MB），防止加载超大文件
   - 仅支持 GET 请求，不支持其他可能导致服务端修改的方法

6. **资源类型验证**
   - 仅允许特定资源类型（如图片、PDF），通过 Content-Type 校验
   - Content-Type 校验在读取整个响应体前进行（流式检查）

7. **DNS 重绑定防护**
   - 使用 IP 锁定：第一次解析后缓存 IP，后续请求使用缓存值
   - 或在 DNS 查询和请求间时间间隔极短（<100ms）

8. **认证和签名**
   - 目标服务要求身份验证（Basic Auth、证书等）
   - 或请求需要特定签名，即使攻击者指向内网也无法伪造

**注意:**
即使标记为低风险，仍建议通过代码层防护和网络层隔离实现纵深防御。低风险基于多个防护措施叠加，移除其中任一措施都可能升级为中高风险。