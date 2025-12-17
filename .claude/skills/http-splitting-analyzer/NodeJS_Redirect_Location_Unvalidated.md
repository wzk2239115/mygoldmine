# NodeJS 重定向 Location 头未验证

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `response.redirect(url)` - Express 重定向
- `response.redirect(statusCode, url)` - 带状态码
- `res.location(url)` - 设置 Location 头
- `res.setHeader('Location', url)`

**快速定位核心操作：**
1. 搜索关键字：`redirect`、`Location`、`res.location`
2. 追踪 URL 来源：`req.query`、`req.body`、参数
3. 检查是否存在 URL 验证
4. 查看是否检查域名和协议

**快速定位保护机制：**
- URL 白名单：`if (allowedUrls.includes(url))`
- 域名验证：`new URL(url).hostname` 检查
- 协议限制：仅允许 `http://` 和 `https://`
- 相对 URL：检查 `!url.startsWith('http')`

**代码示例：**
```javascript
// 危险：用户输入直接重定向
app.get('/redirect', (req, res) => {
    const url = req.query.url;
    res.redirect(url);  // 危险
});

// 危险：POST 数据
app.post('/login', (req, res) => {
    const next = req.body.next || '/';
    res.redirect(next);  // 危险
});

// 危险：Location 头
app.get('/jump', (req, res) => {
    res.location(req.query.dest);  // 危险
});
```

## Classify

**漏洞（High）：**
- 用户输入直接重定向
- 无域名验证
- 允许开放重定向

**误报：**
- 重定向目标硬编码
- 框架验证已启用

**代码异味（Medium）：**
- 仅检查前缀
- 黑名单不完整
- 检查不完整

## Audit Skills

### 1. HTTP Splitting vs 开放重定向的区分

**开放重定向（Open Redirect）：**
- 验证漏洞：直接重定向到用户控制的任意域名
- 演进程度：简单但常见，常被低估
- 典型危害：钓鱼攻击、信任链破坏

```javascript
// 真实案例：LinkedIn-like 开放重定向
app.get('/auth/callback', (req, res) => {
    const returnUrl = req.query.return_to;
    // 只检查了是否为空，未验证域名
    if (returnUrl) {
        res.redirect(returnUrl);  // 可重定向到 evil.com
    }
});
```

**HTTP Splitting 攻击：**
- 验证漏洞：在 Location 头中注入 CRLF (`\r\n`)
- 进阶程度：更复杂，需要特定条件
- 典型危害：缓存中毒、响应拆分、会话固定

```javascript
// 真实案例：可能的 HTTP Splitting
app.get('/redirect', (req, res) => {
    const referer = req.get('referer');
    // 仅检查协议，未过滤换行符
    if (referer.startsWith('https://')) {
        res.setHeader('Location', referer);  // 危险
    }
});

// 攻击载荷示例：
// GET /redirect?ref=https://evil.com%0d%0aSet-Cookie:admin=true
```

### 2. 审计核心技巧

**技巧 1：追踪数据流的多个入口**
- 直接检查：`req.query.url`、`req.body.url`、`req.params.id`
- 间接入口：`req.get('referer')`、`req.get('origin')`、`req.headers.*`
- 隐藏入口：Cookie 重定向、JSON 中的嵌套 URL 字段

```javascript
// 常被遗漏的入口
app.post('/login', (req, res) => {
    const referer = req.get('referer');  // 审计时常忽视
    if (isValidUser(req.body)) {
        res.redirect(referer || '/dashboard');
    }
});
```

**技巧 2：识别虚假的防护机制**
- ❌ 仅检查前缀：`url.startsWith('http')`（可被 `http://evil.com` 绕过）
- ❌ 基于路径检查：`url.includes('//')`（可被编码绕过）
- ❌ 简单字符串匹配：`url.indexOf('evil.com') === -1`（可被子域绕过）
- ✅ 真正的防护：URL 对象解析 + 严格域名白名单

```javascript
// 虚假防护 1：前缀检查不完整
if (url.startsWith('http://trusted.com') || url.startsWith('https://trusted.com')) {
    // 错误：'http://trusted.com.evil.com' 也会通过
}

// 虚假防护 2：包含检查太宽松
if (!url.includes('evil.com') && !url.includes('malicious.com')) {
    // 错误：黑名单永远不完整
}

// 真正的防护
try {
    const urlObj = new URL(url);
    const allowedDomains = ['trusted.com', 'api.trusted.com'];
    if (!allowedDomains.includes(urlObj.hostname)) {
        res.redirect('/');  // 默认重定向
    } else {
        res.redirect(url);
    }
} catch (e) {
    res.redirect('/');  // 非法 URL 拒绝
}
```

**技巧 3：识别相对 URL 的陷阱**
- 相对 URL：`/dashboard`、`./profile`、`../admin` 通常是安全的
- 特殊情况：`//evil.com` 和 `///evil.com` 看起来像相对但实际是绝对 URL

```javascript
// 危险：允许 // 开头的"相对"URL
if (!url.startsWith('http')) {
    res.redirect(url);  // 错误：'//evil.com' 会被视为相对 URL
}

// 正确做法
const isSafe = url.startsWith('/') && !url.startsWith('//');
if (isSafe) {
    res.redirect(url);
}
```

### 3. 真实漏洞 vs 误报的区分经验

**必定是漏洞的特征：**
| 特征 | 示例 | 信心等级 |
|------|------|--------|
| 直接使用用户输入 | `res.redirect(req.query.url)` | 100% |
| 仅检查前缀 | `url.startsWith('http')` | 95% |
| POST body 重定向 | `res.redirect(req.body.next)` | 100% |
| 反射到响应头 | `res.set('Location', userInput)` | 100% |
| 白名单为空或未使用 | `const whitelist = []` 但无检查 | 90% |

**可能是误报的特征：**
| 特征 | 原因 | 验证方法 |
|------|------|--------|
| 看似重定向的字符串变量 | 可能是日志记录 | 查看是否实际进入响应头 |
| 框架自动处理 | Express/Next.js 可能有内置防护 | 检查框架版本文档 |
| 硬编码 URL 列表中的选择 | 虚假阳性 | 追踪该变量是否接收用户输入 |
| 前端重定向 | 客户端代码，不同威胁模型 | 检查是否涉及服务器端验证 |

**诊断案例：区分真假漏洞**

```javascript
// 案例 1：典型漏洞
app.get('/go', (req, res) => {
    res.redirect(req.query.target);  // 100% 漏洞
});

// 案例 2：可能是误报 - 需要进一步检查
const redirectTarget = getUserProfile(req.query.userId).redirectUrl;
res.redirect(redirectTarget);

// 判断方式：检查 getUserProfile 中的 redirectUrl 是否来自数据库
// - 如果来自数据库且有人工审核：可能是误报
// - 如果来自用户上传的配置：仍然是漏洞
// - 如果没有任何验证，只是从 DB 读取：需要检查 DB 初始化

// 案例 3：HTTP Splitting 特定检查
const referer = req.get('referer');
if (referer && /^https?:\/\/trusted\.com/.test(referer)) {
    res.redirect(referer);  // 风险：未过滤 \r\n
}

// 测试方法：尝试注入 \r\n
// %0d%0aSet-Cookie:x=y 或 %0d%0a%0d%0a<script>alert(1)</script>
```

### 4. 自动化检查清单

审计时按以下顺序验证：

1. **搜索阶段**：`grep -r "redirect\|location\|Location" --include="*.js"`
2. **数据流追踪**：标记所有 `req.query`、`req.body`、`req.params` 的使用
3. **验证检查**：是否存在 URL 验证逻辑
   - URL 解析（`new URL()`）
   - 域名白名单
   - 协议限制
   - CRLF 过滤
4. **风险判定**：
   - 无验证 + 用户输入 = 高危
   - 虚假验证（前缀/黑名单）= 中危
   - 硬编码 + 白名单 = 低风险

## Low risk

**以下情况评为低风险：**
- 重定向目标硬编码
- 严格白名单验证（URL 对象 + 域名检查）
- 仅允许相对 URL（以 `/` 开头，不含 `//`）
- 管理员配置的 URL（有审核流程）
