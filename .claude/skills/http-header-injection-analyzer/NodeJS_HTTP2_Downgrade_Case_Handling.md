# Node.js HTTP/2降级 - 头字段大小写处理

## 基本信息
- **难度等级：** ★★★★★ | **审计时间：** 40-60分钟
- **关键词搜索：** `http2`, `spdy`, `:authority`, `:method`, `toLowerCase`, `req.headers`, `proxy`, `http2-wrapper`
- **快速检查：** 是否处理HTTP/2请求，头字段大小写比较是否敏感

## 漏洞成因

HTTP/2协议强制所有头字段小写（如`content-type`），而HTTP/1.1传统使用Title-Case（如`Content-Type`）。当Node.js应用处理HTTP/2请求或作为代理转发时，若代码假设特定大小写或进行大小写敏感比较，可能导致安全检查绕过、请求走私等攻击。

### 常见漏洞模式

```javascript
// ✗ 漏洞：硬编码大小写检查
app.use((req, res, next) => {
    // HTTP/2请求的头是小写：content-type
    // Title-Case检查可能被绕过
    if (req.headers['Content-Type'] === 'application/json') {
        // 安全检查
    }
    next();
    // HTTP/2请求发送 content-type: application/json 绕过检查
});
```

```javascript
// ✗ 漏洞：大小写敏感的黑名单
const blockedHeaders = ['X-Forwarded-For', 'X-Real-IP'];

app.use((req, res, next) => {
    blockedHeaders.forEach(header => {
        if (req.headers[header]) {  // 大小写敏感
            delete req.headers[header];
        }
    });
    next();
    // HTTP/2的 x-forwarded-for（小写）未被过滤
});
```

```javascript
// ✗ 漏洞：代理转发时头规范化不一致
const http2 = require('http2');
const http = require('http');

const proxy = http2.createServer((req, res) => {
    const headers = {};
    for (const [key, value] of Object.entries(req.headers)) {
        // 简单复制，未规范化
        headers[key] = value;
    }
    // 转发到HTTP/1.1后端
    http.request({ headers }, (response) => { ... });
});
```

```javascript
// ✗ 漏洞：Express req.get()大小写问题
app.post('/api', (req, res) => {
    // req.get()虽然大小写不敏感，但直接访问headers不是
    const auth = req.headers['Authorization'];  // HTTP/2下可能为空
    if (!auth) {
        return res.status(401).send('Unauthorized');
    }
    // ...
});
```

```javascript
// ✓ 修复：大小写不敏感处理
const getHeaderInsensitive = (headers, name) => {
    const lowerName = name.toLowerCase();
    for (const key in headers) {
        if (key.toLowerCase() === lowerName) {
            return headers[key];
        }
    }
    return null;
};

app.use((req, res, next) => {
    const contentType = getHeaderInsensitive(req.headers, 'Content-Type');
    if (contentType === 'application/json') {
        // 安全检查
    }
    next();
});
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 硬编码Title-Case头检查 | 搜索 `req\.headers\['[A-Z]`，检查是否有小写变体处理 |
| **P0** | 安全检查大小写敏感 | 搜索认证/授权逻辑，验证头比较方式 |
| **P1** | 黑名单过滤大小写 | 搜索 `delete req\.headers\|blockedHeaders`，检查大小写处理 |
| **P1** | HTTP/2代理转发 | 搜索 `http2\.create\|spdy`，检查头规范化 |
| **P2** | 自定义头处理中间件 | 搜索遍历req.headers的代码，评估大小写处理 |
| **P2** | 混合协议场景 | 搜索同时支持h2和http/1.1的代码 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 仅HTTP/1.1，无HTTP/2支持 | 快速跳过 |
| **L1** | 使用Express/Koa，框架处理 | 关键词扫描，确认使用req.get() |
| **L2** | 直接访问req.headers | 跳读检查是否大小写敏感 |
| **L3** | 自定义头处理逻辑 | 逐行审计比较和过滤代码 |
| **L4** | HTTP/2代理/网关场景 | 跨模块追踪协议转换 |

---

## 审计专业技巧

### 1. 区分真实漏洞与误报的关键指标

#### ✓ 确实存在漏洞的证据链
```javascript
// 线索1：直接访问 + 安全功能 + 可控输入
app.post('/secure-endpoint', (req, res) => {
    // 线索2：使用了硬编码的大小写形式
    const token = req.headers['X-Auth-Token'];  // Title-Case
    if (!token) return res.status(401).send('Unauthorized');

    // 线索3：token用于安全决策，而不仅是日志
    const isValid = validateToken(token);
    if (isValid) {
        // 执行敏感操作
        deleteUserData(req.userId);
    }
});
// 攻击者以HTTP/2发送 x-auth-token（小写）绕过认证
```

#### ✗ 常见误报场景
```javascript
// 误报1：日志/调试用头，不影响安全
app.use((req, res, next) => {
    const userAgent = req.headers['User-Agent'];  // 硬编码大小写
    console.log(`UA: ${userAgent}`);  // 仅用于logging
    next();
});

// 误报2：框架已处理过头的规范化
const express = require('express');
const app = express();
// Express内部已将所有头转为小写
app.get('/', (req, res) => {
    console.log(Object.keys(req.headers));  // ['content-type', 'accept', ...]
    // 所以 req.headers['Content-Type'] 实际总是undefined
});

// 误报3：条件判断有其他安全检查
const api = (req, res) => {
    // 即使头被绕过，也有其他验证机制
    const token = req.headers['Authorization'] || extractFromCookie(req);
    if (!token) return res.status(401).send('No Auth');
    // ...
};
```

### 2. 审计流程 - 真实漏洞检测

**第一步：确认HTTP/2支持**
```bash
# 检查package.json或import语句
grep -r "http2\|spdy\|h2\|h2c" package.json
grep -r "const.*require.*http2"

# 检查Express/Koa版本（新版本更新了头处理）
# Express 4.17+、Koa 2.13+ 的req.headers已确保小写
```

**第二步：追踪头的使用路径**
```javascript
// 关键问题：这个头的值在哪里被使用？
// 使用三层追踪法：

// 层1：发现大小写敏感的访问
const auth = req.headers['Authorization'];  // 📍 发现点

// 层2：追踪该变量如何被使用
if (auth) {  // 用于条件判断？
    const user = authenticateUser(auth);  // 传递给认证函数？
    if (user) {
        // 层3：该认证结果用于什么决策？
        deleteUser(user.id);  // 修改数据的决策！
    }
}
```

**第三步：构造PoC验证**
```javascript
// 测试用例：HTTP/2小写头是否被读取
const http2 = require('http2');

// 发送小写头
const client = http2.connect('http://localhost:3000');
const req = client.request({
    ':path': '/api/sensitive',
    ':method': 'POST',
    'x-auth-token': 'malicious-token',  // 小写而非 X-Auth-Token
});

// 监控应用日志/数据库
// 如果应用处理了小写头，说明漏洞存在
```

### 3. 区分漏洞真假的判定表

| 场景 | 现象 | 判定 | 理由 |
|------|------|------|------|
| `req.headers['Authorization']` + 认证 | 代码存在 | **真漏洞** | 直接访问且用于安全决策 |
| `req.headers['User-Agent']` + 日志 | 代码存在 | **误报** | 仅用于日志，不影响安全 |
| Express + `req.get('auth')` | 代码存在 | **误报** | 框架已规范化 |
| `req.headers['X-Forwarded-For']` + 反向代理 | 代码存在 | **真漏洞** | 用于识别真实客户端IP |
| 自定义中间件 + `.toLowerCase()` | 代码存在 | **误报** | 有防护措施 |
| 代码注释：`// h2 headers normalized by nginx` | 代码存在 | **排除** | 上游已处理 |

### 4. 常见的"隐藏"误报陷阱

**陷阱1：Express框架的自动规范化**
```javascript
// ❌ 审计员误认为有漏洞
const middleware = (req, res, next) => {
    const ct = req.headers['Content-Type'];  // 大小写检查
};

// ✓ 实际上Express已处理
console.log(req.headers);
// { 'content-type': 'application/json', ... }  // 已是小写
```

**陷阱2：头虽然大小写敏感，但有备用方案**
```javascript
// 看起来是漏洞，实际不是
const getAuth = () => {
    // 方案1：尝试硬编码大小写（可能失败）
    return req.headers['Authorization'] ||
           // 方案2：从Cookie读取（总是可用）
           req.cookies.auth_token;
};
```

**陷阱3：代理层已规范化**
```javascript
// Nginx/HAProxy等反向代理通常会规范化头
// 即使Node.js代码有问题，也形不成安全漏洞
// 审计建议：与基础设施团队确认
```

### 5. 审计时的实际问题清单

```
□ 是否测试过HTTP/2 + 小写头的实际请求？
□ 这个头的缺失会导致什么后果？（权限绕过？数据泄露？）
□ 代码中是否有其他验证机制补救？
□ 框架版本是否足够新，已修复头规范化？
□ 反向代理是否在上游处理了头规范化？
□ 头的值是否可由攻击者控制？
□ 真实部署中是否使用HTTP/2？（很多部署仍是HTTP/1.1）
```

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 应用处理HTTP/2请求（直接或通过代理）
2. 代码中存在大小写敏感的头字段检查
3. 安全功能依赖该头字段检查

### 典型漏洞特征（满足任一项即确认）
- ✗ `req.headers['Content-Type']` 硬编码Title-Case检查
- ✗ `blockedHeaders.includes(header)` 大小写敏感黑名单
- ✗ HTTP/2代理未规范化头字段
- ✗ 认证逻辑使用 `req.headers['Authorization']` 而非 `req.get('authorization')`

### 安全排除（任一项充分）
- ✓ 使用Express `req.get()`（大小写不敏感）
- ✓ 所有头比较使用`.toLowerCase()`
- ✓ 仅HTTP/1.1环境，无HTTP/2支持
- ✓ 反向代理层统一规范化头字段

### 灰色判定（风险较低但需注意）
- 仅内部服务通信
- 大小写差异仅影响非安全功能
- 有代理层规范化但未确认

---

## 实现建议

### 核心防护方案

**方案1：大小写不敏感的头访问**
```javascript
// 使用Express/Koa内置方法
const contentType = req.get('content-type');  // 大小写不敏感
const auth = req.get('authorization');

// 或自定义函数
const getHeader = (headers, name) => {
    const lower = name.toLowerCase();
    return Object.keys(headers).reduce((found, key) => {
        return key.toLowerCase() === lower ? headers[key] : found;
    }, null);
};
```

**方案2：安全的头黑名单**
```javascript
const BLOCKED_HEADERS = new Set([
    'x-forwarded-for',
    'x-real-ip',
    'x-forwarded-host'
]);

const filterBlockedHeaders = (headers) => {
    const filtered = {};
    for (const [key, value] of Object.entries(headers)) {
        if (!BLOCKED_HEADERS.has(key.toLowerCase())) {
            filtered[key] = value;
        }
    }
    return filtered;
};
```

**方案3：HTTP/2代理头规范化**
```javascript
const normalizeHeaders = (headers) => {
    const normalized = {};
    for (const [key, value] of Object.entries(headers)) {
        // 跳过HTTP/2伪头
        if (key.startsWith(':')) continue;
        // 统一转为小写
        normalized[key.toLowerCase()] = value;
    }
    return normalized;
};
```

### 检查清单
- [ ] 使用`req.get()`替代直接访问`req.headers['X-']`
- [ ] 黑名单/白名单使用小写形式
- [ ] 安全检查使用大小写不敏感比较
- [ ] HTTP/2代理场景添加头规范化
- [ ] 测试HTTP/2请求的小写头绕过

---

## 修复优先级

1. **立即修复**：认证/授权逻辑中的大小写敏感检查
2. **本周修复**：统一使用大小写不敏感的头访问方法
3. **可选加强**：实现统一的头访问中间件
4. **长期优化**：使用框架标准API，避免直接访问headers对象
