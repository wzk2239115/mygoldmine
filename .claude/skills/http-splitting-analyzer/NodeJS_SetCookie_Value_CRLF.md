# NodeJS Set-Cookie 值 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.cookie(name, value, options)` - Express
- `res.setHeader('Set-Cookie', value)` 直接设置
- Cookie 值包含用户输入

**快速定位核心操作：**
1. 搜索关键字：`cookie(`、`Set-Cookie`、`res.setHeader`
2. 追踪 Cookie 值来源：`req.query`、`req.body`、会话数据
3. 检查是否存在 CRLF 过滤
4. 追踪 Cookie 构造过程

**快速定位保护机制：**
- 值检查：`if (value.includes('\r') || value.includes('\n'))`
- 替换：`value.replace(/[\r\n]/g, '')`
- 白名单验证：`/^[a-zA-Z0-9\-_]*$/.test(value)`
- URL 编码：`encodeURIComponent(value)`

**代码示例：**
```javascript
// 危险：用户输入直接设置 Cookie
app.get('/setCookie', (req, res) => {
    const token = req.query.token;
    res.cookie('session', token);  // 危险
    res.send('OK');
});

// 危险：POST 数据
app.post('/auth', (req, res) => {
    const auth = req.body.auth;
    res.cookie('auth_token', auth);  // 危险
    res.send('OK');
});

// 危险：直接设置
app.get('/cookie-header', (req, res) => {
    const val = req.headers['x-token'];
    res.setHeader('Set-Cookie', 'token=' + val);  // 危险
});
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于 Cookie 值
- 无 CRLF 过滤
- 导致响应分割

**误报：**
- Cookie 值硬编码
- 系统生成的值
- 框架管理

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接拼接

## Low risk

**以下情况评为低风险：**
- Cookie 值硬编码
- 严格 CRLF 过滤
- 白名单验证
- 内部来源且已验证

## 审计专业技巧

### 1. 追踪数据流的三层分析法

**第一层：源头识别**
- 主动搜索所有 `res.cookie()` 和 `setHeader('Set-Cookie')` 调用点
- 记录每个 Cookie 值的源头：是否来自 `req.query`、`req.body`、`req.params`、`req.headers`
- 检查是否通过数据库、缓存、会话存储获取

**第二层：中间处理**
- 追踪值在赋值前是否经过函数处理
- 记录所有 `replace()`、`split()`、`substring()` 等操作
- 特别注意 `JSON.parse()` 后的数据流向

**第三层：最终验证**
- 在设置 Cookie 的那一刻，值是否完全受控
- 值的最后来源是常量还是变量
- 是否有多个代码分支可能绕过防护

### 2. 真实漏洞识别特征

**高度可疑的模式：**
```javascript
// 模式1：直接字符串拼接
res.cookie('token', user.id + '-' + req.query.extra);  // 危险
res.setHeader('Set-Cookie', `session=${req.body.sid}`); // 危险

// 模式2：JSON 序列化后的数据
const data = JSON.stringify(req.query);
res.cookie('metadata', data);  // 危险 - 包含双引号和特殊字符

// 模式3：URL 解码后的数据
const decoded = decodeURIComponent(req.query.value);
res.cookie('info', decoded);  // 危险 - 解码后可能包含 CRLF

// 模式4：正则替换不完整
const safe = value.replace(/\n/g, '');  // 仅替换 \n，漏掉 \r
res.cookie('token', safe);  // 危险

// 模式5：多层间接赋值
const processRequest = (val) => val.trim();
const token = processRequest(req.query.token);
res.cookie('auth', token);  // 危险 - trim() 不过滤 CRLF
```

### 3. 误报陷阱及区分方法

**常见误报案例1：框架自动编码**
```javascript
// Express 的 res.cookie() 会自动 URI 编码值
res.cookie('user', req.query.user);  // 表面看危险，但 Express 有保护
// 需要检查 Express 版本和配置，新版本有防护
```
**区分要点：** 阅读框架文档或查看框架源码，了解版本特性

**常见误报案例2：仅在特定条件下赋值**
```javascript
const token = 'default-value';
if (user.isAdmin) {
    token = req.query.token;  // 看似危险，但仅 admin 可控
}
res.cookie('session', token);
// 需要判断权限边界
```
**区分要点：** 追踪 `isAdmin` 的来源，判断是否可被用户伪造

**常见误报案例3：密钥管理 Cookie**
```javascript
const secret = require('./config').SESSION_SECRET;
res.cookie('csrf', secret);  // 看似使用 secret，但这样做也很危险
```
**区分要点：** 即使是密钥，也不应该在 Cookie 中暴露，这是逻辑漏洞而非注入漏洞

### 4. 实战检测清单

| 检测项 | 确认方法 | 风险判定 |
|-------|--------|--------|
| **值来源** | 是否包含 `req.` 前缀 | req.query、req.body、req.headers = 高危 |
| **链式调用** | 追踪 `.` 后的操作 | 如果只有 `.trim()`、`.toString()` = 危险 |
| **正则表达式** | 检查 `/[\r\n]/g` | 缺少任一字符 = 危险 |
| **字符串拼接** | 查看 `+` 或 `` ` `` | 有用户输入 = 危险 |
| **函数调用** | 追踪函数定义 | 是否真的过滤了 CRLF = 关键 |
| **框架版本** | package.json 版本号 | 新版本可能有自动防护 |

### 5. 易误认为安全的陷阱

**陷阱1：使用 encodeURI() 而非 encodeURIComponent()**
```javascript
const name = encodeURI(req.query.name);
res.cookie('user', name);  // 不安全！encodeURI 保留某些字符
// encodeURI 保留：; , / ? : @ & = + $ # （包括对 CRLF 的保留）
```

**陷阱2：仅检查是否包含 %0D 或 %0A**
```javascript
if (!value.includes('%0D') && !value.includes('%0A')) {
    res.cookie('token', value);  // 不安全！可用双编码 %250D 或直接用 \r
}
```

**陷阱3：使用 stripslashes 类函数**
```javascript
const clean = value.replace(/\\/g, '');
res.cookie('data', clean);  // 不安全！没处理 CRLF
```

**陷阱4：仅过滤换行，未过滤回车**
```javascript
const safe = value.replace(/\n/g, '').replace(/\r\n/g, '');  // 顺序错误
// 应该先替换 \r\n，再替换 \r 和 \n
```

### 6. 验证漏洞的手工测试方法

**步骤1：请求构造**
```
GET /setCookie?token=valid%0D%0ASet-Cookie:%20admin=1 HTTP/1.1
Host: target.com
```

**步骤2：响应检查**
- 查看是否出现两个 Set-Cookie 头
- 验证第二个 Cookie 是否被浏览器接受
- 检查是否能覆盖现有 Cookie 或设置新 Cookie

**步骤3：进阶测试**
- 尝试 `%0d%0a` 编码版本
- 尝试混合大小写 `%0D%0A`
- 尝试双编码 `%250D%250A`
- 尝试 Unicode 编码等绕过方式
