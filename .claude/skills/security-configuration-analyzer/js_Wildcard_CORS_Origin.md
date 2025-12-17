# JS/TS - Wildcard CORS Origin

## Details

### 代码示例

**后端 - Express/Koa 通配符配置**
```javascript
// 危险：直接返回 *
app.use(cors({ origin: '*', credentials: true }));

// 危险：动态反射 Origin 头
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin);
  res.setHeader('Access-Control-Allow-Credentials', 'true');
});

// 危险：正则宽松匹配
const corsOptions = { 
  origin: /.*\.example\.com$/,  // 可被 evil.example.com 绕过
  credentials: true 
};
```

**原生 Node.js HTTP**
```javascript
http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
});
```

**Next.js API 路由**
```javascript
export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  // 或动态反射
  res.setHeader('Access-Control-Allow-Origin', req.headers.origin);
}
```

**配置文件场景**
```javascript
// .env 或 config.js
CORS_ORIGIN=*
ALLOWED_ORIGINS=*,http://localhost:3000
```

### 快速定位核心操作（L1-L3）

**L1 - 关键词全局扫描**
```
Access-Control-Allow-Origin
cors({ origin
setHeader.*Allow-Origin
CORS_ORIGIN
allowedOrigins
```

**L2 - 中间件注册点跳读**
- `app.use(cors` → Express/Koa CORS 中间件
- `app.use((req, res` → 自定义 CORS 逻辑
- `res.setHeader` → 手动设置响应头
- `next.config.js` 的 `headers()` 函数
- Vercel/Netlify 配置文件 `vercel.json`、`netlify.toml`

**L3 - 动态值逐行追踪**
- 检查 `origin:` 后是否为变量 → 追踪变量来源（环境变量、配置文件、数据库）
- 检查是否为函数 `origin: function(origin, callback)` → 审查函数逻辑
- 检查正则表达式 `/pattern/` → 是否可通过子域名绕过

### 快速定位保护机制（L2-L4）

**L2 - 白名单验证跳读**
```javascript
// 安全模式：硬编码白名单
const whitelist = ['https://app.example.com', 'https://admin.example.com'];
origin: function(origin, callback) {
  if (whitelist.indexOf(origin) !== -1) callback(null, true);
}
```
审计要点：
- 是否存在 `whitelist` / `allowedOrigins` 数组？
- 是否使用严格相等 `===` 或 `indexOf`？
- 白名单是否从可信源加载？

**L3 - 条件分支逐行读**
```javascript
// 需逐行确认条件完整性
if (origin && isAllowed(origin)) {
  res.setHeader('Access-Control-Allow-Origin', origin);
}
```
检查项：
- `isAllowed` 函数实现是否严格？
- 是否有 `else` 分支拒绝非法 origin？
- 是否同时检查了 `credentials` 标志？

**L4 - 跨模块追踪配置源**
- 环境变量 → 检查 `.env`、Kubernetes ConfigMap
- 数据库配置 → 追踪配置表的写入点
- 远程配置中心 → 确认是否有访问控制
- 第三方 CORS 库 → 检查库的默认行为

## Classify

### 确认为漏洞
- **动态反射 Origin 且带 credentials**：`setHeader(origin, req.headers.origin)` + `credentials: true`，允许任意站点携带 Cookie 请求
- **通配符 + 凭证组合**：`origin: '*'` 与 `credentials: true` 同时出现（虽然浏览器会阻止，但表明配置意图危险）
- **正则宽松匹配**：`/.*example\.com/` 可被 `evilexample.com` 绕过
- **未验证即反射**：无任何白名单检查直接返回请求的 Origin

### 判定为误报
- **开发环境隔离**：`if (process.env.NODE_ENV === 'development') origin: '*'` 且确认不会部署到生产
- **公开只读 API**：明确标注为公开数据接口（如天气 API、静态资源 CDN）且无敏感操作
- **已被覆盖的配置**：后续中间件或配置显式覆盖了通配符设置
- **注释掉的代码**：`// res.setHeader('Access-Control-Allow-Origin', '*');`

### 代码异味
- **白名单包含不可控域名**：白名单中含 `localhost`、`*.ngrok.io` 等临时域名未清理
- **正则过于宽松但未启用**：定义了危险正则但实际未使用
- **配置项命名混乱**：多个 CORS 配置变量，不清楚哪个生效

## Low Risk

### 降低风险的场景
- **内网专用服务**：仅在内网部署，无公网暴露，且内网环境可信
- **无认证的公开数据**：接口返回完全公开的只读数据（如公开博客列表），无用户身份或敏感信息
- **已有上层网关控制**：API Gateway 或 WAF 已统一处理 CORS，应用层配置不生效
- **无状态 JWT 无敏感 Cookie**：使用纯 Authorization Header 的 JWT 认证，不依赖 Cookie，`credentials: false`
- **静态资源服务**：CDN 或静态文件服务器，仅托管 JS/CSS/图片等公开资源
- **短期临时接口**：PoC、演示系统，生命周期短且不处理真实用户数据

### 风险提升因素
即使看似低风险，以下情况应重新评估：
- 接口处理敏感操作（支付、权限变更）
- 使用 Session 或 Cookie 作为认证凭证
- 前端通过 CORS 请求传递 CSRF Token
- 存在同站脚本注入点可配合利用