# NodeJS_Session_JWT_No_Expiry

**漏洞类型**: Express/Node.js 使用 JWT 作为会话令牌时，未设置 exp (expiration) 声明，导致令牌永不过期，可被长期利用

---

## Details

### 代码示例

**易受攻击的代码模式**:
```javascript
// 示例1: 签发 JWT 未设置过期时间
const jwt = require('jsonwebtoken');
app.post('/login', (req, res) => {
    const token = jwt.sign({ userId: user.id }, 'secret');
    // 缺少 expiresIn 参数
    res.json({ token });
});

// 示例2: expiresIn 设置过长
const token = jwt.sign(
    { userId: user.id },
    'secret',
    { expiresIn: '365d' } // 过长，应为分钟或小时
);

// 示例3: 验证 JWT 时未检查过期
function verifyToken(token) {
    try {
        const decoded = jwt.verify(token, 'secret', { ignoreExpiration: true });
        // ignoreExpiration 禁用了过期检查
        return decoded;
    } catch (err) {
        return null;
    }
}

// 示例4: 手动编码不检查过期时间
function validateJWT(token) {
    const parts = token.split('.');
    const payload = JSON.parse(Buffer.from(parts[1], 'base64'));
    // 仅检查签名，未验证 exp 声明
    return verifySignature(token);
}

// 示例5: JWT 存储在 localStorage 无刷新机制
app.post('/login', (req, res) => {
    const token = jwt.sign({ userId: user.id }, 'secret');
    // 返回长期令牌，客户端存储在 localStorage
    res.json({ token, expiresIn: undefined });
});

// 示例6: 刷新令牌同样无过期时间
app.post('/refresh', (req, res) => {
    const refreshToken = jwt.sign({ userId: user.id }, 'refresh_secret');
    // 刷新令牌也未设置过期时间
    res.json({ accessToken, refreshToken });
});

// 示例7: 缓存的 JWT 未验证过期
const cache = {};
app.use((req, res, next) => {
    const token = req.headers.authorization?.split(' ')[1];
    if (cache[token]) {
        // 缓存的令牌可能已过期
        req.user = cache[token];
    }
});
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- JWT 签发: `jwt.sign()`, `jwt.verify()`, `jsonwebtoken`, `token = ` 赋值
- 过期设置: `expiresIn`, `exp`, `maxAge`, `timeout`
- 验证参数: `ignoreExpiration: true/false`, `verify()` 的第三个参数
- 令牌使用: 授权头中的 `Bearer` 令牌, localStorage 存储
- 缺失检查: 无 `expiresIn`, `ignoreExpiration: true`, `exp` 字段

**L2 跳读定位**:
- 登录路由: `/login`, `/auth`, `/authenticate`
- JWT 签发位置: 搜索所有 `jwt.sign()` 调用
- 令牌验证位置: `jwt.verify()`, 中间件中的验证
- 刷新令牌逻辑: `/refresh-token`, `refreshToken` 相关
- 令牌解码: 前端存储位置和使用方式

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- expiresIn 参数: `jwt.sign(..., { expiresIn: '...' })`
- 验证时忽略: `ignoreExpiration` 参数是否为 false
- exp 声明验证: 手动检查 `payload.exp > Date.now() / 1000`

**L3 逐行分析**:
- JWT 签发时的配置:
  - `expiresIn` 是否设置，值是否合理 (建议 15 分钟 - 1 小时)
  - 是否区分短期 access token 和长期 refresh token
  - 时间格式是否正确 ('15m', '1h', '7d' 等)
- 验证逻辑:
  - `jwt.verify()` 的第三个参数是否有 `ignoreExpiration: true`
  - 是否手动验证 `exp` 声明
  - 验证失败时错误处理是否正确
- 刷新令牌机制:
  - refresh token 是否也有过期时间
  - refresh token 的过期时间是否远长于 access token
  - 是否在刷新时重新签发新的刷新令牌
- 令牌存储和传输:
  - 是否使用 HTTP-only Cookie (更安全)
  - 如果使用 localStorage，访问时是否检查过期
  - 是否有缓存，缓存时是否考虑过期

**L4 跨模块追踪**:
- 追踪所有调用 `jwt.sign()` 的位置
- 检查所有 `jwt.verify()` 调用的参数
- 验证前端 localStorage 中的令牌使用逻辑
- 检查是否有令牌拦截器或中间件统一处理过期
- 审查配置文件中的 JWT 设置

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- `jwt.sign()` 未传递 `expiresIn` 参数，令牌永不过期
- 验证时使用 `ignoreExpiration: true`，禁用了过期检查
- 即使有 `expiresIn`，值也过长 (超过 24 小时)
- JWT 中没有 `exp` 声明
- 刷新令牌同样无过期时间
- 客户端缓存的令牌未验证过期

**误报判定**:
- `expiresIn` 设置为合理值 (15-60 分钟)
- `jwt.verify()` 正确验证了过期时间
- 实现了 access token + refresh token 的双令牌模式
- refresh token 也有明确的过期时间
- 令牌过期后自动清理本地存储
- 有刷新令牌轮换机制

**代码异味**:
- 存在多个 `jwt.sign()` 调用，有的设置过期，有的没有
- `ignoreExpiration: true` 被代码注释而非删除
- 有 `exp` 字段但验证时未使用
- 刷新令牌逻辑与访问令牌分离不清
- 令牌过期后仍能访问某些敏感资源

---

## Low risk

### 低风险场景

**令牌设计**:
- JWT 只包含非敏感信息 (如 userId)，敏感权限在服务端验证
- 每次请求时都从数据库重新查询用户权限
- 令牌签名使用强密钥且定期轮换

**补偿控制**:
- 应用有令牌黑名单机制，注销后立即失效
- 敏感操作需要实时权限检查，不依赖令牌
- 定期要求用户重新登录
- 用户登出后自动删除本地令牌

**检测与监控**:
- 实时监控令牌使用，检测异常行为
- 记录所有令牌签发和使用的历史
- 检测跨地域或异常设备的令牌使用
- 异常登录时强制登出所有会话

**存储安全**:
- 使用 HTTP-only, Secure, SameSite 的 Cookie
- 不在 localStorage 中存储敏感令牌
