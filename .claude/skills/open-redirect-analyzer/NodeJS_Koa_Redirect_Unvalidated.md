# Node.js Koa ctx.redirect() 未验证重定向

## Details

### 核心代码示例

**漏洞代码：**
```javascript
// 直接使用用户输入参数进行重定向
router.get('/callback', async (ctx) => {
  const redirectUrl = ctx.query.redirect_uri;
  ctx.redirect(redirectUrl);
});

// POST 请求中的重定向
router.post('/login', async (ctx) => {
  const { username, password, return_url } = ctx.request.body;
  // 认证逻辑...
  ctx.redirect(return_url);
});

// 使用 referer 头作为重定向目标
router.get('/api/logout', async (ctx) => {
  const returnUrl = ctx.request.header.referer;
  ctx.redirect(returnUrl);
});
```

---

### 核心操作快速定位技巧 **[L1: 关键词扫描]**

**1. 直接搜索 `ctx.redirect()` 调用**
```bash
grep -r "ctx\.redirect\(" --include="*.js" --include="*.ts"
grep -r "\.redirect\(" --include="*.js" --include="*.ts" | grep -v "http" | grep -v "https"
```

**2. 识别重定向源头来自用户输入**
- `ctx.query.*` - URL 查询参数
- `ctx.params.*` - 路由参数
- `ctx.request.body.*` - POST 请求体
- `ctx.request.header.*` - HTTP 请求头（referer、origin 等）
- `ctx.cookies.get()` - Cookie 值

**3. 关键代码行特征**
```
ctx.redirect(ctx.query.*)     ← 参数直接传入
ctx.redirect(return_url)      ← 需检查 return_url 源头
ctx.redirect(redirectUrl)     ← 需检查 redirectUrl 源头
ctx.redirect(req.body.*)      ← POST 参数直接传入
```

---

### 保护机制识别技巧 **[L2: 跳读]**

**1. 白名单验证模式**
```javascript
// 完整的域名白名单
const ALLOWED_REDIRECT_HOSTS = new Set([
  'example.com',
  'trusted-partner.com'
]);

router.get('/callback', async (ctx) => {
  const redirectUrl = ctx.query.redirect_uri;
  const url = new URL(redirectUrl);

  if (!ALLOWED_REDIRECT_HOSTS.has(url.hostname)) {
    ctx.status = 400;
    return;
  }
  ctx.redirect(redirectUrl);
});
```

**2. 相对路径验证**
```javascript
router.get('/api/logout', async (ctx) => {
  const returnPath = ctx.query.return_url;

  // 仅允许相对路径（不含 :// 或 // 开头）
  if (returnPath.includes('://') || returnPath.startsWith('//')) {
    ctx.status = 400;
    return;
  }

  // 防止目录遍历
  if (returnPath.includes('..')) {
    ctx.status = 400;
    return;
  }

  ctx.redirect(returnPath);
});
```

**3. URL 解析与主机验证**
```javascript
const isAllowedRedirect = (urlString) => {
  try {
    const url = new URL(urlString);
    return url.hostname === 'example.com' || url.hostname.endsWith('.example.com');
  } catch {
    // 无效 URL 格式
    return false;
  }
};
```

**4. 配置驱动的重定向映射**
```javascript
const REDIRECT_MAPPING = {
  'dashboard': '/user/dashboard',
  'profile': '/user/profile'
};

router.get('/callback', async (ctx) => {
  const target = ctx.query.redirect_key;
  const path = REDIRECT_MAPPING[target];

  if (!path) {
    ctx.redirect('/');
    return;
  }
  ctx.redirect(path);
});
```

**关键观察点：**
- 是否存在 `new URL()` 或 `url.parse()` 的主机验证
- 是否有显式的白名单或黑名单检查
- 是否限制仅允许相对路径
- 是否使用映射表而非直接参数

---

## Classify

### 漏洞判定标准

**确认为漏洞的条件：**
1. **直接传入重定向** - 用户可控参数直接作为 `ctx.redirect()` 的参数，无任何验证
2. **跨域重定向可达** - 攻击者可构造指向任意外部域名的重定向链接
3. **可信信息源欺骗** - 未验证 referer/origin 等请求头的真实性

**误报常见场景：**
1. **仅允许相对路径** - `ctx.redirect(path)` 中 path 确实无法包含协议（如 `http://`）
   - 但仍需检查是否能通过 `//` 构造协议相对 URL
2. **动态跳转参数来自授权用户** - 管理员后台中的内部链接跳转通常风险较低
3. **登录前的临时存储** - 在会话中存储合法的 return_url，之后验证使用

**代码异味：**
- 存在注释说明 "TODO: 添加重定向验证" 或 "需要白名单"
- 重定向逻辑分散在多个路由中，缺乏统一的验证函数

---

## Low risk

### 低风险场景评级标准

**1. 仅允许相对路径且格式严格**
```javascript
// 相对路径模式验证
if (returnPath.startsWith('/') && !returnPath.includes('//')) {
  ctx.redirect(returnPath);
}
```
- ✅ 无法通过 `//` 或 `http://` 构造外部链接
- ✅ 攻击面受限于应用内部路径

**2. 使用配置驱动的映射表**
```javascript
const ROUTES = { login: '/dashboard', logout: '/' };
ctx.redirect(ROUTES[ctx.query.target] || '/');
```
- ✅ 用户仅能选择预定义的目标
- ✅ 无法注入任意 URL

**3. 在严格的身份认证/授权上下文中**
- 高级管理员在内部系统中的重定向
- 已认证用户的个人资料页面跳转到自身资源

**4. 明确的白名单验证**
```javascript
const TRUSTED_DOMAINS = ['example.com', 'api.example.com'];
const isAllowedHost = TRUSTED_DOMAINS.some(domain =>
  new URL(url).hostname === domain
);
```
- ✅ 白名单完整且可维护
- ✅ 包含所有业务需要的合法域名

**5. 使用成熟的中间件库处理重定向**
- 采用专门的 OIDC/OAuth2 库处理授权重定向
- 库内部已实现标准的重定向验证机制

---

## 审计建议

### 高优先级检查项
- [ ] `ctx.redirect()` 是否直接使用 `ctx.query.*` 或 `ctx.request.body.*`
- [ ] 是否验证了请求头（referer、origin）的真实性
- [ ] 白名单是否完整覆盖所有业务场景

### 中优先级检查项
- [ ] 重定向逻辑是否集中管理还是分散在多个路由
- [ ] 是否存在日志记录追踪所有重定向操作
- [ ] 是否有自动化测试覆盖 Open Redirect 场景

