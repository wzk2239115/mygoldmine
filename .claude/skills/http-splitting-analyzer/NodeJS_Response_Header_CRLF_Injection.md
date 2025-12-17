# NodeJS 响应头 CRLF 注入

## Details

**审计等级：L1（关键词扫描）/ L3（逐行读）**

**危险函数特征：**
- `response.setHeader(name, value)` - Express/Node.js
- `response.header(name, value)` - Express
- `response.set()` 设置响应头
- 自定义头拼接

**快速定位核心操作：**
1. 搜索关键字：`setHeader`、`response.header`、`response.set`
2. 追踪头值来源：`req.query`、`req.body`、`req.headers`
3. 检查是否存在 CRLF 过滤
4. 追踪从请求到响应头的链路

**快速定位保护机制：**
- 值检查：`if (value.includes('\r') || value.includes('\n'))`
- 替换：`value.replace(/[\r\n]/g, '')`
- 白名单验证：`/^[a-zA-Z0-9\-_.]+$/.test(value)`
- 框架防护：某些版本的 Node.js/Express 自动检测

**代码示例：**
```javascript
// 危险：用户输入直接设置为响应头
app.get('/send-header', (req, res) => {
    const custom = req.query.name;
    res.setHeader('X-Custom', custom);  // 危险
    res.send('OK');
});

// 危险：Express header 方法
app.post('/header', (req, res) => {
    const value = req.body.value;
    res.header('X-Data', value);  // 危险
    res.send('OK');
});

// 危险：set 方法
app.get('/set', (req, res) => {
    const param = req.headers['x-param'];
    res.set('X-Forwarded', param);  // 危险
    res.send('OK');
});
```

## Classify

**漏洞（Critical）：**
- 用户输入直接用于响应头
- 无 CRLF 过滤
- 允许响应分割

**误报：**
- 响应头值硬编码
- Node.js 版本已修补
- 框架已验证

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接拼接

## Low risk

**以下情况评为低风险：**
- 响应头值硬编码
- 严格 CRLF 过滤
- 白名单验证
- 内部来源且已验证

## 审计专业技巧

### 1. 真实漏洞特征识别

**关键特征：**
- **直接流链路**：`req.query/body/headers` → `res.setHeader()` 无中间过滤
- **版本检查**：Node.js < 9.x，Express < 4.16.x 版本缺乏内置防护
- **响应体分割**：能否通过 `\r\n\r\n` 分割响应头和体，注入恶意内容
- **Cookie 注入**：特别关注 `Set-Cookie` 头，可导致会话劫持

**实战示例：**
```javascript
// 真实漏洞模式：无任何过滤的直接使用
const router = require('express').Router();
router.get('/api/callback', (req, res) => {
  const redirectUrl = req.query.url;  // 直接使用
  res.setHeader('X-Redirect', redirectUrl);
  res.send('Redirecting...');
});
// 攻击：/api/callback?url=attacker.com\r\nSet-Cookie:admin=true
```

### 2. 误报识别规则

**误报一：版本防护**
```javascript
// Node.js 12+ 自动检测，不能注入 \r\n
// 但要检查：是否使用了 rawHeaders 或绕过机制
const nodeVersion = process.version; // v12.0.0+
```

**误报二：框架层防护**
```javascript
// Express 4.16+ 自动进行验证
const express = require('express'); // 版本确认很重要
const app = express();
// 但需要确认没有禁用中间件或使用 res.writeHead 绕过
```

**误报三：不可达代码路径**
```javascript
// 如果设置头的代码在条件判断下，且条件永不满足
if (adminOnly && isAdminUser) {  // 如果 isAdminUser 始终为 false
  res.setHeader('X-Admin', userInput);  // 实际不可达
}
```

### 3. 区分真实漏洞 vs 误报的审计步骤

**Step 1: 版本确认（快速排除大量误报）**
```bash
# 查看 package.json 依赖版本
- Node.js >= 12.0：框架层有防护，需验证绕过方式
- Express >= 4.16：自动CRLF检测，继续查看是否有 res.writeHead 直接调用
- 自定义框架：高风险
```

**Step 2: 追踪数据流（确认可控性）**
```javascript
// 可信来源检查
req.query.x       // 完全可控 ✓ 优先审查
req.body.x        // 完全可控 ✓ 优先审查
req.headers.x     // 完全可控 ✓ 优先审查
req.params.x      // 同上
req.cookies.x     // 同上
req.url           // 同上

// 低信任来源
config.getHeader()    // 配置文件来源，需看配置管理
process.env.x         // 环境变量，通常误报
constants.HEADER      // 硬编码常量，误报
```

**Step 3: 寻找防护逻辑（黑名单vs白名单）**
```javascript
// 白名单防护（安全）
const allowed = /^[a-zA-Z0-9\-_]+$/.test(value);

// 黑名单防护（可能绕过）
if (!value.includes('\r') && !value.includes('\n')) {
  // 缺点1：Unicode 转义 \u000d \u000a
  // 缺点2：Netscape Cookie 语法允许 ;
  // 缺点3：可能有其他分隔符如 \x0d
}

// 不完整防护（误报概率高）
value = value.replace('\r\n', '');  // 只替换一次，可被绕过
```

**Step 4: 测试可利用性（核心步骤）**
```
通过编码测试：
1. 直接 CRLF：/test?x=a%0d%0ab
2. Unicode：/test?x=a\u000d\u000ab
3. 其他编码：/test?x=a%0D%0Ab（大写）
4. 条件路由：在关键分支点下断点或日志

如果任何一种能注入额外响应头 → 真实漏洞
否则 → 可能是误报或防护生效
```

### 4. 常见误报场景及判断

**误报场景1：硬编码头值**
```javascript
const headers = {
  'X-Frame-Options': 'DENY',  // 硬编码，即使有 req.x 也是别的
  'X-Content-Type': 'nosniff'
};
// ✓ 这是误报
```

**误报场景2：参数通过白名单映射**
```javascript
const headerMap = {
  'lang': 'X-Language',
  'cache': 'Cache-Control'
};
const allowed = ['en', 'zh', 'max-age=3600'];
if (allowed.includes(req.query.value)) {
  res.setHeader(headerMap[req.query.type], req.query.value);
}
// ✓ 白名单保护，误报
```

**误报场景3：服务器端生成的头值**
```javascript
const uuid = generateUUID();  // 服务端生成
res.setHeader('X-Request-ID', uuid);
// ✓ 来源可信，误报
```

**真实漏洞场景：组合攻击**
```javascript
const sanitize = (x) => x.replace('\r\n', ' ');  // 不完整
const value = req.query.x;
const header = `Dangerous: ${sanitize(value)}`;
res.setHeader('X-Custom', header);
// 攻击：?x=%0aSet-Cookie:%20admin=1
// ✗ 真实漏洞，黑名单绕过
```

### 5. 审计检查清单

- [ ] Node.js/Express 版本 >= 防护版本？
- [ ] 用户输入来源是否 100% 被白名单过滤？
- [ ] 是否存在 `res.writeHead()` 直接调用绕过？
- [ ] 是否有间接拼接（字符串模板、concat）？
- [ ] 响应体是否可通过 CRLF 分割注入？
- [ ] 是否测试过编码绕过（Unicode、%0D、\r）？
- [ ] Set-Cookie 头是否特别保护？
