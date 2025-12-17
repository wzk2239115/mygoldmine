# NodeJS SSR 资源预取 SSRF

**漏洞成因**：SSR 框架（Next.js、Nuxt、Remix 等）预取资源时直接使用用户 URL，未校验协议/域名/IP 范围，攻击者可探测内网、访问 EC2 元数据、读取内部服务响应。

**真实场景**：头像 URL 预取、缩略图生成、文档预览、RSS 订阅、Open Graph 元数据获取等功能。

## 快速审计清单

### 1. 危险调用点识别
```
搜索关键词：
  - fetch()、axios()、got()、request()、$fetch()、curl_exec()
  - getImageData()、sharp.fetch()、jimp.read()
  - loadTemplate()、getPreview()

关键函数：
  - getServerSideProps、getStaticProps、asyncData、getInitialProps
  - API 路由处理器、中间件、建构时函数

位置：pages/api/*、pages/ssr/*、middleware、utils/server.js
```

### 2. 源检查（用户输入来源）
| 来源类型 | 示例 | 风险 | 审计建议 |
|---------|------|------|---------|
| 查询参数 | `req.query.url`、`req.query.imageUrl` | ⚠️ 高 | 必审，直接可控 |
| 路由参数 | `[...slug].js` 中 `req.params.slug` | ⚠️ 高 | 必审，完整 URL 匹配 |
| POST body | `req.body.resourceUrl`、JSON 负载 | ⚠️ 高 | 必审，流式验证 |
| 请求头 | `Referer`、`x-forward-url`、`Origin` | ⚠️ 中 | 可控但需特殊条件 |
| Cookie | `req.cookies.targetUrl` | ⚠️ 中 | 自身可控，验证必须 |
| DB/文件 | 从数据库读取 URL | ✓ 低 | 确认原始来源是否受信 |

### 3. 核心检查清单
- [ ] 用户输入是否直接传入 fetch/请求库？或者仅控制部分 URL？
- [ ] 协议白名单是否存在？仅允许 `http://` 和 `https://`？
- [ ] 域名校验是否使用了 `URL.hostname` 而非字符串匹配？
- [ ] IP 黑名单是否完整（所有 RFC1918 私网段 + `127.0.0.0/8` + `169.254.0.0/16`）？
- [ ] IPv6 映射地址是否处理（`::ffff:127.0.0.1` → `127.0.0.1`）？
- [ ] DNS rebinding 防护？仅黑名单 IP 无法防护，需双重解析或检查 DNS TTL
- [ ] 重定向跟随是否关闭（`redirect: 'manual'`）？或重定向目标也进行验证？
- [ ] 非标准端口是否受限（仅允许 80/443）？

## 真实漏洞模式

### 模式1：无验证的 URL 预取（最常见）
```javascript
// ❌ 危险 - Next.js 头像预加载
export async function getServerSideProps(ctx) {
  const userAvatar = ctx.query.avatar; // 用户控制完整 URL
  const res = await fetch(userAvatar); // 直接请求
  return { props: { avatarData: await res.json() } };
}

// ❌ 内部 API 调用
export default async function handler(req, res) {
  const targetService = req.body.service; // "http://localhost:9000"
  const data = await axios.get(targetService);
  res.json(data);
}
```

### 模式2：不完整的协议/域名校验（高频绕过）
```javascript
// ❌ 仅检查协议 → 仍可访问内网
if (url.startsWith('http://') || url.startsWith('https://')) {
  await fetch(url); // http://127.0.0.1 / http://localhost / http://10.0.0.1
}

// ❌ 正则未锚定 → 绕过
if (/example\.com/.test(url)) { // evilexample.com / evil.com/example.com
  await fetch(url);
}

// ❌ 字符串包含 → 完全可绕过
if (url.includes('example.com')) { // evil.com?example.com / example.com.evil.com
  await fetch(url);
}

// ✓ 安全做法
const parsed = new URL(userInput);
const allowedHosts = ['cdn.example.com', 'api.example.com'];
if (!allowedHosts.includes(parsed.hostname)) {
  throw new Error('Hostname not allowed');
}
if (!['http:', 'https:'].includes(parsed.protocol)) {
  throw new Error('Protocol not allowed');
}
if (![80, 443, ''].includes(parsed.port)) { // 空字符串 = 默认端口
  throw new Error('Port not allowed');
}
```

### 模式3：缺失或不完整的 IP 黑名单
```javascript
// ❌ 仅封禁几个 IP（AWS 元数据绕过、Kubernetes 服务发现）
const blacklist = ['127.0.0.1', '169.254.169.254'];

// ✓ 完整黑名单（生产级别）
const isPrivateIP = (ip) => {
  const ipRanges = [
    /^127\./,                    // 127.0.0.0/8
    /^10\./,                     // 10.0.0.0/8
    /^172\.(1[6-9]|2[0-9]|3[0-1])\./, // 172.16.0.0/12
    /^192\.168\./,               // 192.168.0.0/16
    /^169\.254\./,               // 169.254.0.0/16 (AWS)
    /^0\./,                      // 0.0.0.0/8
    /^::1$/,                     // IPv6 loopback
    /^::ffff:(127\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])|192\.168\.)/, // IPv6 mapped
    /^fc00:/,                    // IPv6 ULA
    /^fe80:/                     // IPv6 link-local
  ];
  return ipRanges.some(regex => regex.test(ip));
};
```

### 模式4：DNS Rebinding 防护缺失
```javascript
// ❌ 仅检查域名 → Rebinding 攻击可成功
const parsed = new URL(url);
if (!['example.com'].includes(parsed.hostname)) {
  await fetch(url); // 第一次 DNS 解析 → evil.com → 攻击者 IP
             // 攻击者改 DNS 指向 127.0.0.1
             // 第二次自动 fetch 时 → localhost
}

// ✓ 防护：同时检查 IP + 双重解析
const dns = require('dns').promises;
const hostIP = await dns.resolve4(parsed.hostname);
if (isPrivateIP(hostIP[0])) throw new Error('Private IP');

// 执行请求前再解析一次
const finalIP = await dns.resolve4(parsed.hostname);
if (hostIP[0] !== finalIP[0]) throw new Error('DNS changed');
```

## 审计经验与技巧

### 常见绕过技巧
| 绕过方式 | 示例 | 防护方案 |
|---------|------|--------|
| 进制转换 | `2130706433` = `127.0.0.1` | 需要规范化为标准点分十进制 |
| 八进制 | `0177.0.0.1` | 同上 |
| 短格式 IP | `10.1` = `10.0.0.1` | 用成熟库验证（如 ipaddr.js） |
| URL 编码 | `http://%31%32%37.0.0.1` | 先 decode 再验证 |
| IPv6 简写 | `::1` / `::ffff:127.0.0.1` | 规范化后再比对 |
| 带用户名 URL | `http://evil@example.com/` | 检查 hostname 而非手动解析 |

### 审计坑点
1. **框架自动解析**：axios/got 会自动跟随重定向 → 重定向到内网
2. **DNS 缓存**：即使多次解析，DNS 缓存可能导致 rebinding 失败检测
3. **超时设置**：极短超时可能导致 Blind SSRF 误判（无法回包）
4. **协议混淆**：`javascript://`、`data://` 虽然会 fetch 失败但仍值得检查
5. **端口绕过**：如允许自定义端口，`http://example.com:6379` 可能访问内部 Redis

### 响应分析技巧
- **Blind SSRF 判断**：无响应返回 ≠ 安全，需配合日志/指标分析
- **反向代理干扰**：Nginx 可能因上游超时自动返回 504，难以判断请求是否发出
- **二阶 SSRF**：预取的 URL 被存储后，在模板渲染时再使用 → 延迟触发

## 误报排查要点

✓ **确认为误报的情况**：
- URL 完全来自数据库/配置文件且配置受信任（非用户直接控制）
- 硬编码白名单 + 严格相等校验 + 协议/端口明确限制
- 用户仅控制 Path/Query 部分，协议+Hostname 由框架写死
- WAF/反向代理在应用层之前拦截外部 URL

✗ **需要二次审查的情况**：
- 宣称"有防火墙保护"→ 应假设攻击者可在内网/VPN
- 说"仅限内部使用" → 考虑内部威胁
- 存在任何参数化构造 URL 的逻辑（即使看似安全）

## 低风险确认

只有满足以下所有条件才能定为低风险：
- ✓ 协议白名单严格（仅 http/https）
- ✓ 域名白名单硬编码或从受信配置读取
- ✓ IP 黑名单完整（包括所有 RFC1918 段 + IPv6）
- ✓ 端口限制为 80/443 或白名单端口
- ✓ 重定向禁用或重定向目标也验证
- ✓ 响应被充分过滤（不返回 HTTP 头、body 字段限制等）
