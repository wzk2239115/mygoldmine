# Node.js Host头未验证

## 基本信息
- **难度等级：** ★★★☆☆ | **审计时间：** 20-30分钟
- **关键词搜索：** `req.hostname`, `req.host`, `req.headers.host`, `req.get('host')`, `req.headers['host']`, `x-forwarded-host`
- **快速检查：** Host头是否用于URL构造、重定向、邮件链接，是否有域名白名单

## 漏洞成因

Node.js/Express中`req.hostname`、`req.headers.host`直接来自客户端HTTP请求的Host头，攻击者可完全控制。若未验证直接用于重定向URL、密码重置链接、OAuth回调等场景，可导致开放重定向、密码重置投毒、缓存中毒等攻击。

### 常见漏洞模式

```javascript
// ✗ 漏洞：Host头直接用于重定向
app.get('/login', (req, res) => {
    const host = req.hostname;
    res.redirect(`https://${host}/dashboard`);
    // 攻击: Host: evil.com -> 重定向到 https://evil.com/dashboard
});
```

```javascript
// ✗ 漏洞：密码重置链接使用Host头
app.post('/forgot-password', async (req, res) => {
    const host = req.headers.host;
    const token = generateToken(req.body.email);
    const resetLink = `https://${host}/reset?token=${token}`;
    await sendEmail(req.body.email, resetLink);
    // 攻击者发送 Host: evil.com，受害者收到钓鱼链接
    res.json({ message: 'Email sent' });
});
```

```javascript
// ✗ 漏洞：OAuth回调地址构造
app.get('/auth/google', (req, res) => {
    const host = req.get('host');
    const callback = `https://${host}/auth/google/callback`;
    const authUrl = googleOAuth.getAuthUrl({ redirect_uri: callback });
    res.redirect(authUrl);
    // 攻击者劫持OAuth回调
});
```

```javascript
// ✗ 漏洞：API响应中使用Host头
app.get('/api/config', (req, res) => {
    const host = req.headers.host;
    res.json({
        apiUrl: `https://${host}/api`,
        wsUrl: `wss://${host}/ws`
    });
    // 缓存后可能影响其他用户
});
```

```javascript
// ✓ 修复：白名单验证
const ALLOWED_HOSTS = new Set(['example.com', 'www.example.com', 'api.example.com']);

const getValidHost = (req) => {
    const host = req.hostname || 'example.com';
    return ALLOWED_HOSTS.has(host) ? host : 'example.com';
};

app.get('/login', (req, res) => {
    const host = getValidHost(req);
    res.redirect(`https://${host}/dashboard`);
});
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | 密码重置/邮件链接 | 搜索 `req\.hostname\|req\.host.*mail\|token\|reset`，检查链接构造 |
| **P0** | 重定向URL构造 | 搜索 `redirect.*req\.host\|req\.hostname`，检查白名单 |
| **P0** | OAuth回调地址 | 搜索 `callback\|redirect_uri.*host`，检查域名验证 |
| **P1** | API响应中的URL | 搜索 `req\.host.*json\|send`，检查是否被缓存 |
| **P1** | X-Forwarded-Host | 搜索 `x-forwarded-host`，检查代理场景 |
| **P2** | 配置或日志使用 | 搜索 `host.*log\|config`，评估影响范围 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 使用环境变量或配置文件的域名 | 快速跳过，无Host头使用 |
| **L1** | 仅日志记录使用Host头 | 关键词扫描确认无安全影响 |
| **L2** | 单文件内Host用于URL构造 | 跳读检查白名单验证存在 |
| **L3** | 工具函数封装Host获取 | 逐行追踪函数内部验证逻辑 |
| **L4** | 中间件或代理层处理 | 跨模块检查Host验证位置 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. req.hostname/req.headers.host用于构造外部可见URL
2. 无白名单验证（无`ALLOWED_HOSTS.has()`或类似检查）
3. 影响安全功能（重定向、邮件、OAuth）

### 典型漏洞特征（满足任一项即确认）
- ✗ `res.redirect('https://' + req.hostname + '/path')`
- ✗ `sendEmail(email, 'https://' + req.headers.host + '/reset?token=' + token)`
- ✗ `const callback = 'https://' + req.get('host') + '/oauth/callback'`
- ✗ API响应包含`req.host`构造的URL且被缓存

### 安全排除（任一项充分）
- ✓ 白名单验证：`ALLOWED_HOSTS.has(req.hostname)`
- ✓ 使用环境变量：`process.env.APP_URL`
- ✓ 配置文件固定域名：`config.get('app.baseUrl')`
- ✓ Express trust proxy正确配置且有代理验证

### 灰色判定（风险较低但需注意）
- 内网应用，外部攻击者无法访问
- 有CDN/代理层验证Host头
- 仅影响非安全功能

---

## 审计专业技巧

### 真实漏洞vs误报区分

#### 常见误报场景（不是漏洞）

**误报1：仅用于日志记录**
```javascript
// 无害：仅用于日志，不影响安全功能
app.use((req, res, next) => {
    console.log(`Request from ${req.hostname}`);  // ✓ 不是漏洞
    next();
});
```
**判定方法**：追踪变量流向，确认Host头最终未用于重定向、链接生成或缓存响应

**误报2：存在多层验证**
```javascript
// ✓ 真正安全：虽然看起来使用Host，但有验证
app.get('/callback', (req, res) => {
    const host = req.hostname;
    // 关键：验证逻辑在上游中间件
    if (!res.locals.hostValidated) {
        return res.status(400).send('Invalid');
    }
    const url = `https://${host}/api`;  // 已在中间件验证过
    res.json({ url });
});
```
**判定方法**：搜索req.hostname前面的全部代码，查找验证中间件或守卫函数

**误报3：内网应用受网络隔离**
```javascript
// 在完全隔离的内网环境中可能不是漏洞
const isIntranet = req.ip.startsWith('10.') || req.ip.startsWith('172.');
if (!isIntranet) {
    return res.status(403).send('Only intranet');
}
const host = req.hostname;
res.redirect(`https://${host}/admin`);
```
**判定方法**：确认访问来源真正受限（防火墙规则、VPN验证等）

#### 真实漏洞信号（高可信度）

**漏洞信号1：密码重置链接直接使用Host**
```javascript
// 必然漏洞：邮件链接使用Host头
app.post('/forgot-password', (req, res) => {
    const resetUrl = `https://${req.hostname}/reset?token=${token}`;
    // 攻击者注入 Host: attacker.com，受害者收到钓鱼邮件链接
    sendEmail(resetUrl);
});
```
**证实方法**：
1. 确认邮件确实被发送（搜索sendEmail、mail、email函数）
2. 链接直接来自req.hostname或req.headers.host
3. 无域名白名单验证

**漏洞信号2：OAuth回调地址包含Host**
```javascript
// 必然漏洞：OAuth框架会验证回调地址
app.get('/auth/oauth', (req, res) => {
    const callback = `https://${req.hostname}/auth/callback`;
    const authUrl = getOAuthUrl({ redirect_uri: callback });
    // 攻击者通过Host注入劫持OAuth授权流程
});
```
**证实方法**：
1. 找到OAuth配置，确认redirect_uri来自req.hostname
2. 检查OAuth提供商是否有预注册的回调地址列表
3. 如果没有白名单，可以动态修改回调地址→必然漏洞

**漏洞信号3：缓存的API响应包含Host**
```javascript
// 高危漏洞：API缓存投毒
app.get('/api/config', (req, res) => {
    const cacheKey = '/api/config';  // 未区分Host
    if (cache.has(cacheKey)) {
        return res.json(cache.get(cacheKey));  // 返回别人注入的Host
    }
    const config = {
        apiUrl: `https://${req.hostname}/api`,  // Host头注入
        version: '1.0'
    };
    cache.set(cacheKey, config);  // ✗ 缓存被污染
    res.json(config);
});
```
**证实方法**：
1. 搜索cache、redis、缓存相关代码
2. 检查缓存键是否包含Host信息
3. 如果缓存键不含Host但响应体含Host→缓存投毒漏洞

### 审计流程（从疑似到确认）

#### 第一步：关键词搜索确定可疑点
```bash
# 搜索所有Host头使用
grep -n "req\.hostname\|req\.host\|req\.get.*host\|headers\.host" app.js

# 结果示例
12: const host = req.hostname;
13: res.redirect(`https://${host}/dashboard`);
```

#### 第二步：追踪变量流向，判定使用场景
```javascript
// 观察第12-13行的具体使用
const host = req.hostname;           // 第12行
res.redirect(`https://${host}/...`); // 第13行
// 结论：用于重定向URL - 需要深入审计
```

#### 第三步：查找验证逻辑
```javascript
// 向上搜索同一个路由器的验证中间件
app.use('/login', (req, res, next) => {
    if (!ALLOWED_HOSTS.has(req.hostname)) {
        return res.status(400).send('Invalid');
    }
    next();
});

app.get('/login', (req, res) => {
    const host = req.hostname;  // 已在中间件验证
    res.redirect(`https://${host}/dashboard`);  // ✓ 可能安全
});
```

#### 第四步：确认白名单和配置
```javascript
// 查找白名单定义位置和内容
const ALLOWED_HOSTS = ['example.com', 'www.example.com'];
// 检查：是否完整？是否在启用？
```

#### 第五步：结合上下文做出判定
```javascript
// 必须同时考虑：
// 1. 应用部署方式（单域名 vs 多域名？）
// 2. Host验证位置（全局中间件 vs 路由级别？）
// 3. 影响范围（仅日志 vs 邮件/重定向？）
// 4. 防御层数（一层 vs 多层防护？）
```

### 高级判定技巧

**技巧1：压力测试法**
在审计时假设自己是攻击者，尝试：
- 注入 `Host: attacker.com`
- 检查返回的URL、邮件、重定向目标
- 如果能改变这些内容→确认漏洞

**技巧2：配置对比法**
比较不同环境的处理方式：
```javascript
// 生产环境
const ALLOWED_HOSTS = ['example.com'];

// 开发环境
const ALLOWED_HOSTS = ['localhost', '*.local'];

// 如果生产环境允许过多Host→潜在风险
```

**技巧3：OAuth特殊判定法**
- 搜索OAuth SDK的redirect_uri参数
- 如果是动态构造（含req.hostname）→漏洞
- 如果是配置预设→可能安全
- 需要检查OAuth应用后台是否有域名白名单

**技巧4：缓存投毒判定法**
```javascript
// 搜索缓存键的构造方式
const cacheKey = `/api/endpoint`;  // ✗ 不含Host
const cacheKey = `${req.hostname}:/api/endpoint`;  // ✓ 含Host，可能安全
const cacheKey = `${req.hostname}:${req.path}`;  // ✓ 更安全
```

---

## 实现建议

### 核心防护方案

**方案1：白名单验证**
```javascript
const ALLOWED_HOSTS = new Set([
    'example.com',
    'www.example.com',
    'api.example.com'
]);

const getValidHost = (req) => {
    let host = req.hostname || req.headers.host || '';
    // 移除端口号
    host = host.split(':')[0].toLowerCase();

    if (ALLOWED_HOSTS.has(host)) {
        return host;
    }
    return 'example.com';  // 默认安全域名
};
```

**方案2：使用环境变量**
```javascript
// 配置
const APP_BASE_URL = process.env.APP_URL || 'https://example.com';

// 使用
app.post('/forgot-password', async (req, res) => {
    const token = generateToken(req.body.email);
    const resetLink = `${APP_BASE_URL}/reset?token=${token}`;
    await sendEmail(req.body.email, resetLink);
    res.json({ message: 'Email sent' });
});
```

**方案3：Express配置安全设置**
```javascript
// 信任代理（仅当有可信代理时）
app.set('trust proxy', 'loopback');

// 中间件验证Host
app.use((req, res, next) => {
    if (!ALLOWED_HOSTS.has(req.hostname)) {
        return res.status(400).send('Invalid Host');
    }
    next();
});
```

### 检查清单
- [ ] 所有使用req.hostname/host的地方添加白名单验证
- [ ] 密码重置链接使用配置的固定域名
- [ ] OAuth回调使用预注册的白名单URL
- [ ] API响应中的URL使用环境变量
- [ ] 测试Host头注入：`Host: evil.com`

---

## 修复优先级

1. **立即修复**：密码重置/OAuth回调使用未验证Host头
2. **本周修复**：所有重定向添加Host白名单验证
3. **可选加强**：使用环境变量替代动态Host获取
4. **长期优化**：添加Host验证中间件
