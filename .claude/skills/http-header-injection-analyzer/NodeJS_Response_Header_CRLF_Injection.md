# Node.js Express/Koa响应头CRLF注入

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `res.setHeader`, `res.set`, `res.header`, `response.set`, `ctx.set`, `writeHead`, `req.query`, `req.params`
- **快速检查：** 响应头值是否来自用户输入（req.query/params/body），是否有CRLF过滤

## 漏洞成因

Node.js在较新版本（v4.6.0+）对`res.setHeader`有CRLF检查，但Express/Koa等框架可能通过不同API绕过检查，或旧版本Node存在漏洞。若用户输入直接设置响应头值，攻击者可注入CRLF实现HTTP响应拆分、XSS、会话劫持等攻击。

### 常见漏洞模式

```javascript
// ✗ 漏洞：Express直接使用用户输入设置响应头
app.get('/api', (req, res) => {
    const lang = req.query.lang;
    res.setHeader('Content-Language', lang);  // 未过滤CRLF
    res.send('data');
    // 攻击: ?lang=en%0d%0aSet-Cookie:admin=true
});
```

```javascript
// ✗ 漏洞：Koa ctx.set直接使用用户输入
app.use(async (ctx) => {
    const customHeader = ctx.query.header;
    ctx.set('X-Custom', customHeader);  // 未验证
    ctx.body = 'response';
});
```

```javascript
// ✗ 漏洞：Location重定向头注入
app.get('/redirect', (req, res) => {
    const url = req.query.url;
    res.setHeader('Location', url);
    res.status(302).end();
    // 攻击: ?url=http://evil.com%0d%0aSet-Cookie:session=hijacked
});
```

```javascript
// ✗ 漏洞：Content-Disposition文件名注入
app.get('/download', (req, res) => {
    const filename = req.query.filename;
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.sendFile('/path/to/file');
    // 攻击: ?filename=file.txt%0d%0aX-Injected:header
});
```

```javascript
// ✓ 修复：CRLF过滤 + 白名单验证
const sanitizeHeader = (value) => {
    return String(value).replace(/[\r\n]/g, '');
};

app.get('/api', (req, res) => {
    const lang = sanitizeHeader(req.query.lang);
    const validLangs = ['en', 'zh', 'ja'];
    if (validLangs.includes(lang)) {
        res.setHeader('Content-Language', lang);
    }
    res.send('data');
});
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | res.setHeader/set用户输入 | 搜索 `setHeader\|res\.set\|res\.header` + `req\.query\|req\.params\|req\.body` |
| **P0** | Location重定向 | 搜索 `Location\|redirect` + 用户输入，检查URL验证 |
| **P1** | Content-Disposition | 搜索 `Content-Disposition\|filename=`，检查文件名过滤 |
| **P1** | Koa ctx.set | 搜索 `ctx\.set\|ctx\.response\.set`，检查参数来源 |
| **P2** | writeHead直接调用 | 搜索 `writeHead`，检查头对象中的用户输入 |
| **P2** | Node.js版本检查 | 确认Node版本 >= 4.6.0（有基础CRLF检查） |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 头值全部硬编码 | 快速跳过，无用户输入 |
| **L1** | 头值来自配置或环境变量 | 关键词扫描，确认来源可信 |
| **L2** | 单文件内setHeader使用req参数 | 跳读检查过滤函数存在 |
| **L3** | 头值由中间件或Service返回 | 逐行追踪数据流 |
| **L4** | 自定义响应包装器 | 跨模块检查setHeader封装 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. res.setHeader/set的值来自用户输入（req.query/params/body/headers）
2. 未进行CRLF过滤（无`.replace(/[\r\n]/g, '')`）
3. Node.js版本 < 4.6.0 或使用可绕过的API

### 典型漏洞特征（满足任一项即确认）
- ✗ `res.setHeader('X-Custom', req.query.value)`
- ✗ `res.set('Location', req.body.redirectUrl)`
- ✗ `ctx.set('Content-Disposition', 'attachment; filename=' + userInput)`
- ✗ `res.writeHead(200, { 'X-Custom': req.params.header })`

### 安全排除（任一项充分）
- ✓ Node.js >= 4.6.0 且使用标准`setHeader`API
- ✓ 存在CRLF过滤：`.replace(/[\r\n\0]/g, '')`
- ✓ 白名单验证：`['en', 'zh'].includes(value)`
- ✓ 使用helmet等安全中间件

### 灰色判定（风险较低但需注意）
- Node版本不确定
- 部分头有过滤，部分无
- 依赖框架版本的安全检查

---

## 审计专业技巧

### 真实漏洞与误报的区分经验

#### 1. 版本上下文的关键判断
**误报场景：** Node.js >= 4.6.0 环境下使用 `setHeader`
```javascript
// ⚠️ 看起来危险，实际安全（Node >= 4.6.0）
res.setHeader('X-Custom', req.query.value);  // Node内置CRLF检查会拒绝\r\n
```
**实际漏洞：** 早期Node版本或通过其他API绕过
```javascript
// ✗ 真实漏洞（Node < 4.6.0 或使用原生 writeHead）
const headers = { 'X-Custom': req.query.value };
res.writeHead(200, headers);  // 绕过setHeader的检查
```
**审计技巧：**
- 优先检查 `package.json` 或 `.nvmrc` 确认 Node 版本
- 对于 Node >= 4.6.0，`setHeader` 本身安全，关键看是否有框架层绕过

#### 2. 框架特定的绕过方式
**Express误报：**
```javascript
// 误报：Express.js的res.set()在新版本已防护
app.get('/test', (req, res) => {
    res.set('X-Custom', req.query.value);  // Express 4.x+ 也通过Node native检查
});
```
**Koa真实漏洞：**
```javascript
// 真实漏洞：某些Koa中间件可能直接操作原生response
app.use(ctx => {
    const value = ctx.query.value;
    ctx.response.headers['X-Custom'] = value;  // 绕过ctx.set()的验证
    // 或者通过原生Node对象
    ctx.res.setHeader('X-Custom', value + '\r\nInjected: header');
});
```
**审计技巧：**
- 区分 `ctx.set()` 和 `ctx.res.setHeader()`，后者风险更高
- 查看框架版本和相关安全补丁记录

#### 3. Location头的隐蔽误报
**常见误报：** URL被认为完全可控，实际不存在
```javascript
// 误报：Location值实际由多部分组成，中间部分被过滤
app.get('/redirect', (req, res) => {
    const path = sanitizeUrl(req.query.path);  // 已过滤
    res.redirect(`https://example.com${path}`);  // 虽然query被过滤，但path是安全的
});
```
**真实漏洞：** 整个Location值来自用户，或过滤不完整
```javascript
// ✗ 真实漏洞
res.redirect(req.query.url);  // 直接使用未验证的URL

// ✗ 真实漏洞（过滤不完整）
const url = req.query.url.replace(/\r/g, '');  // 只过滤\r，遗漏\n
res.redirect(url);  // 用%0a可绕过
```
**审计技巧：**
- 对Location头进行严格的URL白名单检查
- 检查是否同时过滤 `\r` 和 `\n`（两个都要有）
- 注意 `%0d%0a` 和 `\r\n` 两种形式

#### 4. Content-Disposition文件名的典型误报
**误报案例：** 文件名的CRLF虽然存在，但框架或浏览器已防护
```javascript
// 可能被视为漏洞，但实际风险极低
app.get('/download/:id', (req, res) => {
    const filename = req.params.id;  // 虽然未过滤，但：
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    // 现代浏览器对Content-Disposition中的特殊字符已做隔离处理
});
```
**真实漏洞：** 能够真正执行HTTP响应拆分
```javascript
// ✗ 真实漏洞（旧版本Node + 特定payload）
const filename = 'file.txt\r\nX-Injected: malicious';
res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
// 在Node < 4.6.0时能注入新头
```
**审计技巧：**
- 先测试环境的Node版本，不同版本漏洞等级完全不同
- Content-Disposition注入即使存在也需配合其他漏洞才能形成威胁
- 优先标记为 Medium（需要特定Node版本或配合其他条件）

#### 5. 数据流追踪中的隐蔽真漏洞
**容易遗漏的真漏洞：** 数据经过中间件变化
```javascript
// ✗ 真实漏洞（因为middleware修改了value）
app.use((req, res, next) => {
    res.locals.customHeader = req.query.header;  // 将用户输入存储到res.locals
    next();
});

app.get('/endpoint', (req, res) => {
    res.setHeader('X-Custom', res.locals.customHeader);  // 间接使用用户输入
});
```
**审计技巧：**
- 追踪跨中间件的数据流，特别是 `req.query` → 全局/本地变量 → `res.setHeader`
- 即使直接代码看不出问题，也要检查该头值是否在其他地方被设置过
- 查看是否存在通用的头设置中间件

#### 6. 框架级防护的可靠性评估
**可信的防护方式：**
```javascript
// ✓ Express 4.x内置安全检查（可信）
res.setHeader('X-Custom', userValue);  // 依赖Node.js native检查

// ✓ 使用成熟的验证库
const validator = require('validator');
const safe = validator.escape(userValue);
res.setHeader('X-Custom', safe);

// ✓ helmet中间件（可信）
const helmet = require('helmet');
app.use(helmet());
```
**不可信的防护方式：**
```javascript
// ✗ 自行检查特定字符但遗漏edge case
if (!userValue.includes('%0d') && !userValue.includes('%0a')) {
    res.setHeader('X-Custom', userValue);  // 可能被双编码绕过
}

// ✗ 仅在应用层检查，原生API可能有差异
if (userValue.length < 100) {
    res.setHeader('X-Custom', userValue);  // 长度检查不能防CRLF
}
```
**审计技巧：**
- 优先信任Node >= 4.6.0的`setHeader`防护（官方安全公告已确认）
- 对自定义防护函数要求看完整实现
- helmet中间件在适当配置下安全性较高

### 审计决策树
```
发现 res.setHeader(header, userValue) ?
├─ Node版本 >= 4.6.0？ YES → 判定：L1（低风险，但记录）
├─ 值来自 req.query/params/body？ YES
│  ├─ 存在.replace(/[\r\n]/g, '')? → 判定：L0（安全）
│  └─ 无过滤 → 判定：L3+（真实漏洞）
└─ 使用 writeHead/原生API？ YES → 判定：L4（高风险）
```

---

## 实现建议

### 核心防护方案

**方案1：CRLF过滤函数**
```javascript
const sanitizeHeaderValue = (value) => {
    if (value === null || value === undefined) return '';
    return String(value).replace(/[\r\n\0]/g, '');
};

// 使用
res.setHeader('X-Custom', sanitizeHeaderValue(req.query.value));
```

**方案2：白名单验证**
```javascript
const ALLOWED_LANGUAGES = new Set(['en', 'zh', 'ja', 'ko']);

app.get('/api', (req, res) => {
    const lang = req.query.lang;
    if (ALLOWED_LANGUAGES.has(lang)) {
        res.setHeader('Content-Language', lang);
    }
    res.send('data');
});
```

**方案3：使用helmet安全中间件**
```javascript
const helmet = require('helmet');
app.use(helmet());

// 或针对特定头
app.use(helmet.contentSecurityPolicy());
app.use(helmet.xssFilter());
```

### 检查清单
- [ ] 所有用户输入的头值经过CRLF过滤
- [ ] Location重定向使用URL白名单
- [ ] Content-Disposition文件名使用安全编码
- [ ] 确认Node.js版本 >= 4.6.0
- [ ] 测试CRLF注入：`?value=test%0d%0aSet-Cookie:admin=1`

---

## 修复优先级

1. **立即修复**：Location重定向使用未验证的用户输入
2. **本周修复**：所有setHeader调用添加CRLF过滤
3. **可选加强**：实现白名单验证头值
4. **长期优化**：升级Node.js版本，使用helmet中间件
