# Node.js/Express 开放重定向漏洞审计指南

## Details

### 漏洞成因

Express 框架 `res.redirect()` 方法在处理用户输入时，若直接使用未验证的输入作为重定向目标，攻击者可构造恶意URL使受害者被重定向到任意外部网站，实施钓鱼攻击或恶意跳转。

### 代码示例

**易受攻击的常见形式：**

```javascript
// 直接使用查询参数
app.get('/redirect', (req, res) => {
  res.redirect(req.query.url);
});

// 使用请求头中的值
app.post('/login', (req, res) => {
  res.redirect(req.headers.referer || '/');
});

// 从表单提交获取
app.post('/checkout', (req, res) => {
  res.redirect(req.body.return_url);
});

// 隐藏在嵌套数据中
app.get('/callback', (req, res) => {
  const target = JSON.parse(Buffer.from(req.query.state, 'base64')).redirect_to;
  res.redirect(target);
});
```

### 快速定位核心操作 ⏱️ 【L1: 关键词扫描】

- 查找 `res.redirect()`、`res.redirectUrl()` 等重定向方法的所有调用
- 追踪参数来源：`req.query.*`、`req.body.*`、`req.params.*`、`req.headers.*`、`req.cookies.*`
- 识别动态URL构造：字符串拼接、模板字符串、对象路径访问、base64解码后的数据
- 关注嵌套调用：先解析再重定向，增加风险（如上例中 `JSON.parse()` 后的值）

### 快速定位保护机制 🛡️ 【L2: 跳读】

- 检查重定向前是否存在验证函数调用：`isValidUrl()`、`isAllowedDomain()`、`validateRedirectUrl()`
- 寻找白名单定义：常量集合、配置文件中的 `ALLOWED_DOMAINS`、`SAFE_URLS`
- 确认URL解析库的使用：`new URL()` 构造函数异常捕获、`url.parse()` 结果的协议检查
- 查看路径限制逻辑：正则表达式 `/^\/[^/]/`、`startsWith()` 检查、`path.resolve()` 标准化

---

## Classify

### 漏洞 vs 误报 vs 代码异味的研判标准

**判定为漏洞的充要条件：**

1. 用户输入完全透传至 `res.redirect()`，无任何过滤或转义
2. 目标站点接受绝对URL（`http://`、`https://`、`//` 等协议前缀）
3. 不存在有效的域名白名单、协议校验或路径限制机制
4. 错误信任内部来源（如 `req.headers` 在代理环境下可被伪造）

**判定为误报的充要条件：**

1. 存在有效的域名白名单，使用 `Set` 或 `includes()` 精确匹配，不允许通配符
2. 强制协议限制：仅允许特定协议，使用 `url.parse(urlString).protocol` 严格校验
3. 相对路径强制：正则表达式 `^/(?!/)` 拒绝 `//` 和 `http://` 开头的输入
4. 完整性校验：使用加密签名（HMAC）或对称加密验证URL真实性

**判定为代码异味的场景：**

1. 白名单验证不完整：允许所有子域（如 `*.example.com`），未限制恶意子域
2. 过滤器可绕过：使用字符串替换 `replace('http://', '')` 导致双重编码绕过
3. 编码不一致：验证时使用URL编码，重定向时使用HTML编码，存在逻辑缝隙
4. 条件逻辑缺陷：多分支中部分缺失验证，如 `if (condition) { /* 有验证 */ } else { /* 无验证 */ }`

---

## Low risk

### 低风险评级的适用场景

**技术防护层面的低风险：**

1. **严格的相对路径限制**
   - 仅允许 `/path`、`./path`、`../path` 格式
   - 显式拒绝 `//`、`http://`、`https://` 等协议
   - 使用 `new URL(input, 'http://localhost')` 构造验证，无效URL自动异常

2. **成熟的域名白名单**
   - 白名单由配置文件或常量定义，不从用户输入生成
   - 使用 `Set` 数据结构精确匹配，时间复杂度 O(1)
   - 包含子域名限制，防止 `attacker.trusted.com` 型绕过

3. **多层防御机制**
   - 协议检查 + 域名白名单 + 路径验证三层叠加
   - 集成第三方库验证（如 `validator.js`）
   - 配置了 CSP、X-Frame-Options、Referrer-Policy 等浏览器防护

**业务上下文的低风险：**

1. **内部系统使用**
   - 端点仅在管理后台暴露，非公网访问
   - 重定向目标限制在内网IP范围

2. **后端生成的重定向**
   - 重定向URL由服务器逻辑生成，用户仅控制部分参数（如ID）
   - 实现了安全的登录后重定向模式：验证referrer来自同源

3. **风险评估降级**
   - 漏洞存在但利用链不完整（跨域限制、浏览器安全特性阻断）
   - 社工成本高，用户需多步交互才能受害
