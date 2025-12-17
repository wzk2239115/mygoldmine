# NodeJS_Session_Client_Storage

**漏洞类型**: Express Session 中会话数据存储在客户端 (如 Cookie) 且未签名或签名不安全，导致会话数据可被篡改

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 示例1: Session 数据存储在 Cookie，未签名
const session = require('express-session');
app.use(session({
    secret: 'keyboard cat',
    resave: false,
    saveUninitialized: true,
    cookie: { 
        httpOnly: true,
        secure: false // 未加密传输
    }
}));

// 示例2: 使用 CookieStore，会话数据直接存储在客户端
const CookieStore = require('cookie-signature');
app.use(session({
    store: new CookieStore(), // 客户端存储
    secret: 'weak_secret' // 密钥过弱
}));

// 示例3: 手动设置 Cookie 作为会话，无签名
app.post('/login', (req, res) => {
    res.cookie('session', JSON.stringify({
        userId: user.id,
        role: 'admin'
    }));
    // 客户端可直接修改 session Cookie
});

// 示例4: 使用弱签名算法
app.use(session({
    secret: 'password123',
    cookie: { signed: true }
    // 默认使用 MD5，不安全
}));

// 示例5: 签名密钥泄露
const SECRET = 'hardcoded_secret_in_code';
app.use(session({
    secret: SECRET,
    cookie: { signed: true }
}));

// 示例6: 会话数据序列化不安全
app.post('/update-profile', (req, res) => {
    const data = JSON.parse(req.body.session);
    // 反序列化未验证数据
    req.session.data = data;
});

// 示例7: 会话签名可被绕过
const sessionCookie = req.cookies.session;
if (sessionCookie && sessionCookie.includes('userId')) {
    // 仅检查是否包含字段，未验证签名
    req.user = JSON.parse(sessionCookie);
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- Cookie Store: `CookieStore`, `cookie-signature`, `client-sessions`
- 会话配置: `express-session`, `session.Options`, `secret`, `cookie`
- 签名相关: `signed: true/false`, `signature`, `mac`
- 数据序列化: `JSON.parse()`, `JSON.stringify()` 用于会话
- 会话访问: `req.session`, `res.cookie('session')`

**L2 跳读定位**:
- Session 中间件配置: 搜索 `app.use(session())`
- Store 类型: 是 Cookie、内存还是数据库
- 密钥设置: `secret` 的值和强度
- Cookie 属性: `signed`, `httpOnly`, `secure`
- 会话使用: 所有 `req.session` 的访问

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 签名启用: `cookie: { signed: true }`
- 强密钥: `secret` 长度和随机性
- 签名算法: HMAC-SHA256 而非 MD5

**L3 逐行分析**:
- Session Store 配置:
  - 是否使用了服务端 Store (database, Redis) 而非客户端
  - 如果使用客户端，是否启用了签名
  - Cookie 大小是否合理 (客户端存储时受限)
- 签名配置:
  - `signed: true` 是否设置
  - `secret` 长度是否足够 (建议 >= 32 字符)
  - 密钥是否硬编码或从环境变量读取
  - 密钥轮换是否实现
- 数据验证:
  - 反序列化时是否验证签名
  - 是否有 JSON 验证 (如 schema validation)
  - 敏感字段是否加密存储
- 传输安全:
  - Cookie 是否设置 `Secure` 标志 (HTTPS only)
  - 是否设置 `HttpOnly` 防止 JavaScript 访问
  - 是否使用 `SameSite` 防止 CSRF

**L4 跨模块追踪**:
- 检查所有会话 Store 的配置和实现
- 验证密钥管理策略
- 检查是否有会话验证中间件
- 审查配置文件中的会话设置
- 检查是否有第三方身份验证集成

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 会话数据存储在客户端 Cookie 中，未签名
- 签名算法不安全 (MD5, SHA1)
- 签名密钥过弱或硬编码在代码中
- Cookie 可被 JavaScript 修改 (缺少 HttpOnly)
- Cookie 在不安全通道传输 (缺少 Secure)
- 会话字段 (如 role, userId) 直接存储在客户端可被篡改

**误报判定**:
- 使用服务端 Session Store (database, Redis)
- 如果使用 Cookie Store，启用了强签名 (HMAC-SHA256)
- `secret` 足够强且从安全配置源读取
- Cookie 设置了 HttpOnly, Secure, SameSite
- 有签名验证和数据验证逻辑
- 应用还有额外的权限检查

**代码异味**:
- 配置中有 `signed: false` 或未明确设置
- 硬编码的密钥或默认密钥未修改
- 存在多个 session 相关的 Cookie，安全属性不一致
- 有注释提到"需要验证签名"但代码未实现
- 用户输入被直接存储到会话中而未过滤

---

## Low risk

### 低风险场景

**数据隔离**:
- 会话中仅存储非敏感数据 (如匿名 ID)
- 所有权限和敏感信息在服务端保存

**验证强化**:
- 虽然会话可被篡改，但每次请求都验证权限
- 关键操作需要实时权限检查而非依赖会话

**监控**:
- 实时检测会话数据异常变化
- 检测到篡改时自动登出并告警
