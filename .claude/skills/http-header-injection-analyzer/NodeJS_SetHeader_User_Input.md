# Node.js setHeader用户输入注入

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `setHeader`, `res.set`, `res.header`, `ctx.set`, `req.query`, `req.params`, `req.body`, `req.headers`
- **快速检查：** setHeader的头名或头值是否来自用户可控输入

## 漏洞成因

Node.js的`res.setHeader(name, value)`方法在接收用户输入作为头名或头值时，若未进行验证和过滤，攻击者可控制响应头内容。虽然Node.js 4.6.0+对值有CRLF检查，但头名可控、特殊字符绕过、或旧版本仍存在风险。

### 常见漏洞模式

```javascript
// ✗ 漏洞：用户输入作为头值
app.get('/api', (req, res) => {
    const customValue = req.query.value;
    res.setHeader('X-Custom-Header', customValue);
    res.json({ status: 'ok' });
    // 攻击: ?value=malicious%00value 或 CRLF变体
});
```

```javascript
// ✗ 漏洞：用户输入作为头名（更危险）
app.get('/dynamic-header', (req, res) => {
    const headerName = req.query.name;
    const headerValue = req.query.value;
    res.setHeader(headerName, headerValue);  // 头名和值都可控
    res.send('done');
    // 攻击: ?name=Set-Cookie&value=admin=true
});
```

```javascript
// ✗ 漏洞：请求头透传到响应头
app.use((req, res, next) => {
    const requestId = req.headers['x-request-id'];
    res.setHeader('X-Request-ID', requestId);  // 未验证来源
    next();
});
```

```javascript
// ✗ 漏洞：Express res.set批量设置头
app.get('/headers', (req, res) => {
    const headers = req.body.headers;  // 用户提交的头对象
    res.set(headers);  // 批量设置，可注入任意头
    res.send('done');
});
```

```javascript
// ✓ 修复：过滤 + 白名单
const sanitize = (val) => String(val).replace(/[\r\n\0]/g, '');

app.get('/api', (req, res) => {
    const value = sanitize(req.query.value);
    // 限制长度和字符集
    if (/^[\w-]{1,100}$/.test(value)) {
        res.setHeader('X-Custom-Header', value);
    }
    res.json({ status: 'ok' });
});
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 头名用户可控 | 搜索 `setHeader\(req\.\|setHeader\(.*\[`，检查第一参数来源 |
| **P0** | 头值直接使用请求参数 | 搜索 `setHeader.*req\.query\|req\.body\|req\.params` |
| **P1** | 请求头透传 | 搜索 `req\.headers\[` + `setHeader`，追踪数据流 |
| **P1** | res.set批量设置 | 搜索 `res\.set\(.*\)`，检查参数是否为对象且来自用户 |
| **P2** | ctx.set（Koa） | 搜索 `ctx\.set`，检查参数来源 |
| **P2** | 中间件统一处理 | 搜索自定义中间件中的setHeader调用 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 头名和值全部硬编码 | 快速跳过 |
| **L1** | 头值来自环境变量或配置 | 关键词扫描确认来源可信 |
| **L2** | 单文件内setHeader使用req参数 | 跳读检查过滤和白名单 |
| **L3** | 头值由Service层返回 | 逐行追踪返回值来源 |
| **L4** | 自定义响应中间件 | 跨模块检查封装逻辑 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. setHeader的参数（头名或头值）来自用户输入
2. 未进行CRLF过滤或白名单验证
3. 攻击者可构造恶意头影响响应

### 典型漏洞特征（满足任一项即确认）
- ✗ `res.setHeader(req.query.name, req.query.value)` 头名可控
- ✗ `res.setHeader('X-Custom', req.body.value)` 未过滤
- ✗ `res.set(req.body.headers)` 批量设置用户提交的头
- ✗ `res.setHeader('X-ID', req.headers['x-id'])` 未验证来源头

### 安全排除（任一项充分）
- ✓ Node.js >= 4.6.0 且仅值来自用户输入（头名固定）
- ✓ 存在CRLF和特殊字符过滤
- ✓ 白名单验证头名和值
- ✓ 头值来自可信来源（JWT解析、数据库等）

### 灰色判定（风险较低但需注意）
- 仅特定头使用用户输入
- 有基础正则验证但不够严格
- 内部API，攻击面有限

---

## 审计专业技巧

### 真实漏洞 vs 误报区分

**真实漏洞的关键特征：**

1. **头名完全用户可控**
   - 真漏洞：`res.setHeader(req.query.name, value)` 或 `res.setHeader(req.params.headerName, value)`
   - 误报：`res.setHeader('X-' + req.query.suffix, value)` 仍可控制头名前缀内容
   - 审计技巧：检查拼接字符串后的头名是否仍属于合法HTTP头格式

2. **头值直接透传且无长度限制**
   - 真漏洞：`res.setHeader('X-Custom', req.headers['user-agent'])` 完全透传，可注入CRLF
   - 误报：`res.setHeader('X-Custom', req.headers['user-agent'].substring(0, 50))` 长度限制
   - 审计技巧：追踪数据流中是否存在 `substring()`, `slice()`, `.length` 等长度限制

3. **版本与修复的关键判断**
   - Node.js 4.6.0+ 版本对头值进行CRLF自动检查，但头名不检查
   - 真漏洞：头名注入 `X-Custom\r\nSet-Cookie: admin=true`
   - 误报：仅值注入且Node版本 >= 4.6.0（会被自动过滤）
   - 审计技巧：查看package.json中的 `engines.node` 版本要求，版本 < 4.6.0 为高危

### 常见误报场景

**场景1：环境变量和配置的混淆**
```javascript
// 这是安全的，不是漏洞
const customHeader = process.env.CUSTOM_HEADER || 'X-Default';
res.setHeader(customHeader, value);
// 环境变量在部署时控制，不是运行时用户输入
```

**场景2：数据库查询结果的信任问题**
```javascript
// 低风险，需要考虑数据库权限
const headerFromDB = await db.query('SELECT header FROM config');
res.setHeader(headerFromDB, value);
// 数据库被攻击是另一个问题，不属于setHeader漏洞
```

**场景3：请求头复制但有白名单验证**
```javascript
// 这是安全的
const ALLOWED = ['X-Request-ID', 'X-Trace-ID'];
const name = req.headers['x-custom-name'];
if (ALLOWED.includes(name)) {
    res.setHeader(name, sanitize(req.headers[name]));
}
// 白名单限制了可设置的头名
```

### 审计数据流追踪方法

**第一步：定位所有setHeader调用**
```bash
# 搜索所有可能的设置头方式
grep -rn "setHeader\|res\.set\|ctx\.set\|ctx\.header" --include="*.js" .
```

**第二步：参数来源分析（4层判断）**
- 第1层：是否有 `req.query`, `req.params`, `req.body` 等直接用户输入
- 第2层：是否有来自请求头的透传 `req.headers[...]`
- 第3层：是否有来自URL路径的提取 `req.path`, `req.url`
- 第4层：是否经过Service/数据库查询（需要二次判断数据来源）

**第三步：验证过滤逻辑强度**
- 弱过滤：仅 `.trim()` 或简单 `replace()`
- 中过滤：`.replace(/[\r\n]/g, '')`
- 强过滤：正则白名单 `/^[A-Za-z0-9\-]{1,100}$/`

### 攻击利用点识别

| 利用点 | 识别方法 | 风险等级 |
|-------|--------|--------|
| HTTP响应分割 | CRLF `\r\n\r\n` 注入第二个响应 | 高 |
| Cookie污染 | `Set-Cookie: session=hijacked` | 高 |
| Cache投毒 | `Cache-Control`, `Vary` 头污染 | 中 |
| 信息泄露 | 注入 `X-` 开头的自定义头泄露内部信息 | 中 |
| XSS前置 | 注入 `Content-Type: text/html` 绕过 | 中 |

### 实际复现验证技巧

当发现可疑的setHeader代码时，通过以下方式进行验证：

```javascript
// 测试用例1：CRLF检测
const payload1 = "test%0d%0aSet-Cookie:%20admin=true";
// 检查响应头是否被分割为两部分

// 测试用例2：特殊字符
const payload2 = "test\x00value";
// 检查NULL字符是否导致头值截断

// 测试用例3：头名注入
const payload3 = "X-Custom\r\nSet-Cookie";
// 检查是否能注入新的响应头
```

### 代码审计核查表

- [ ] 所有setHeader/res.set/ctx.set调用已列表化
- [ ] 第一参数（头名）来源已明确分类（硬编码/白名单/用户输入）
- [ ] 第二参数（头值）的数据流已追踪（直接输入/查询/计算）
- [ ] 用户输入的参数已验证防护方式（无防护/弱防护/完整防护）
- [ ] 存在批量设置头的接口（如res.set(obj)）已检查
- [ ] 请求头透传逻辑已检查（是否有白名单）
- [ ] Node.js版本与防护措施已关联判断

---

## 实现建议

### 核心防护方案

**方案1：严格过滤函数**
```javascript
const sanitizeHeaderValue = (value) => {
    if (value == null) return '';
    return String(value)
        .replace(/[\r\n\0]/g, '')  // 移除CRLF和NULL
        .slice(0, 1000);           // 限制长度
};

const sanitizeHeaderName = (name) => {
    // 头名只允许字母数字和连字符
    if (!/^[\w-]+$/.test(name)) {
        throw new Error('Invalid header name');
    }
    return name;
};
```

**方案2：头名白名单**
```javascript
const ALLOWED_CUSTOM_HEADERS = new Set([
    'X-Request-ID',
    'X-Correlation-ID',
    'X-Custom-Data'
]);

const setCustomHeader = (res, name, value) => {
    if (!ALLOWED_CUSTOM_HEADERS.has(name)) {
        return;  // 忽略未授权的头名
    }
    res.setHeader(name, sanitizeHeaderValue(value));
};
```

**方案3：安全的头透传**
```javascript
const SAFE_FORWARD_HEADERS = ['x-request-id', 'x-correlation-id'];

app.use((req, res, next) => {
    SAFE_FORWARD_HEADERS.forEach(header => {
        const value = req.headers[header];
        if (value && /^[\w-]{1,100}$/.test(value)) {
            res.setHeader(header, value);
        }
    });
    next();
});
```

### 检查清单
- [ ] 禁止用户控制头名
- [ ] 所有用户输入头值经过CRLF过滤
- [ ] 请求头透传使用白名单
- [ ] res.set不接受用户提交的对象
- [ ] 测试特殊字符：`%00`, `%0d%0a`, `%0a`

---

## 修复优先级

1. **立即修复**：头名用户可控的场景
2. **本周修复**：所有setHeader添加值过滤
3. **可选加强**：实现头名白名单
4. **长期优化**：统一响应头设置中间件
