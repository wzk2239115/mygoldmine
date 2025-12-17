# JavaScript/Node.js Express速率限制绕过漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-20分钟
- **风险：** 可直接用于暴力破解、账户枚举、API滥用

## 🚀 快速审计清单（按优先级）
- [ ] **环境架构**：是否多实例部署(PM2/cluster)？→使用MemoryStore则高危
- [ ] **Store配置**：是否使用Redis/其他分布式Store？→无则必然漏洞
- [ ] **IP获取**：信任X-Forwarded-For？→无代理IP验证则可伪造
- [ ] **Key维度**：keyGenerator是否仅按IP？→应为IP+username组合
- [ ] **Skip配置**：skipSuccessfulRequests值为true？→登录端点致命缺陷
- [ ] **一致性**：所有认证端点(/login, /oauth/token, /password-reset)限制相同？
- [ ] **阈值**：限制值>10次/15分钟？→过于宽松
- [ ] **并发**：能发送50个并发请求通过验证？→竞态条件漏洞

## 核心漏洞类型及绕过方法

### 🔴 L1：内存存储多实例失效（高危）
**症状**：使用`rateLimit({max: 5})`无store参数，PM2/cluster多实例运行
**绕过**：每个实例独立计数，实际limit = 5 × 实例数。发送请求轮询不同实例
```bash
# 快速测试：4个实例+5次限制=20次实际尝试
for i in {1..20}; do curl http://target/login -d "user=admin&pass=x"; done
```
**确认**：查看`app.js`是否存在`require('cluster')`或PM2配置，且store未使用Redis

### 🔴 L2：单维度限流被横向扫描（高危）
**症状**：`keyGenerator: (req) => req.ip`，仅按IP限制
**绕过**：同一IP对100个账户各尝试9次，每个账户都未触发限制
```javascript
// 审计代码示例：寻找这种缺陷
const limiter = rateLimit({
    max: 10,
    keyGenerator: (req) => req.ip  // ❌ 缺少用户维度
});
```
**确认**：keyGenerator仅包含IP或仅包含username，无组合逻辑

### 🔴 L3：X-Forwarded-For Header伪造（中危）
**症状**：`app.set('trust proxy', true)` + 无IP白名单验证
**绕过**：每请求伪造不同IP：`curl -H "X-Forwarded-For: 1.2.3.X"`
```javascript
// 危险配置
app.set('trust proxy', true); // 信任所有代理
// 正确配置
app.set('trust proxy', ['loopback', '10.0.0.0/8']); // 仅信任特定IP
```
**确认**：搜索`trust proxy: true`，验证是否有代理IP白名单

### 🟡 L4：skip配置误用（中危）
**症状**：`skipSuccessfulRequests: true`用于登录端点
**绕过**：攻击者可混合错误密码(计数)和正确密码(不计数)的请求
**确认**：找到登录handler，检查skip相关参数

### 🟡 L5：多端点防护不一致（中危）
**症状**：/api/login限制5次，/oauth/token限制100次，/api/v1/auth无限制
**攻击**：利用防护较弱的端点进行相同功能的暴力破解
**确认**：检查所有认证相关路由，跨文件对比limiter配置

### 🟢 L6：keyGenerator键冲突（低-中危）
**症状**：`keyGenerator: (req) => req.user.id`，未处理undefined
**绕过**：未登录用户共享同一key"undefined"，第一个攻击者的限制影响所有用户
**确认**：keyGenerator实现中是否有`req.user?.id`或安全检查

## 代码审计技巧与定位方法

### 快速定位关键代码
1. **搜索关键字**：`express-rate-limit`, `rateLimit(`, `RedisStore`, `MemoryStore`, `rate-limit-redis`
2. **检查初始化**：寻找limiter定义和中间件应用位置
3. **跟踪应用**：`app.use(limiter)`, `app.post(..., limiter, handler)`, `router.use(limiter)`
4. **对比配置**：同一功能的多个端点是否使用相同的limiter实例
5. **验证参数**：逐一检查`windowMs`, `max`, `keyGenerator`, `skipSuccessfulRequests`, `store`

### 实战审计技巧
| 场景 | 审计方法 | 漏洞信号 |
|-----|--------|--------|
| **多实例环境** | 检查PM2/cluster配置 + 搜索MemoryStore | 无Redis/分布式store |
| **IP溯源** | 找到getClientIp函数，检查是否验证代理 | 信任所有X-Forwarded-For |
| **限制强度** | 测试实际能发多少请求 | >10次/15分钟或能发50+并发 |
| **绕过验证** | 尝试不同IP/username组合 | keyGenerator过于简单 |
| **异常行为** | 观察不同实例响应 | 某些实例限制比其他快 |
| **并发绕过** | `ab -n 50 -c 50`并发攻击 | 多数请求通过验证 |

## 漏洞确认条件

| 级别 | 漏洞特征 | 确认方法 |
|-----|--------|--------|
| **高危** | 多实例+MemoryStore | grep "PM2\|cluster" + 无RedisStore |
| **高危** | 单维度限流(仅IP) | keyGenerator仅含IP，无username |
| **中危** | 信任所有代理 | `trust proxy: true` 无IP白名单 |
| **中危** | skipSuccessfulRequests: true | 登录端点配置此参数 |
| **中危** | 多端点防护不一致 | /login vs /oauth/token limiter不同 |
| **中危** | 能发送50+并发请求 | 使用ab -n 100 -c 50测试 |
| **低中危** | keyGenerator未处理undefined | req.user?.id无?.操作符 |
| **低危** | 单实例+MemoryStore | 无cluster但仅用内存存储 |

## 安全配置检查清单

```javascript
// ✅ 安全的关键配置点
const limiter = rateLimit({
    store: new RedisStore(/* ... */),           // ✓ 必须使用分布式store
    keyGenerator: (req) => {
        return `${getClientIp(req)}|${req.body?.username || 'anon'}`; // ✓ IP+username
    },
    windowMs: 15 * 60 * 1000,                   // ✓ 15分钟窗口
    max: 5,                                      // ✓ 5次/窗口（合理阈值）
    skipSuccessfulRequests: false,               // ✓ 所有请求计数
    standardHeaders: true,                       // ✓ 返回429+headers
    handler: (req, res) => {
        res.status(429).json({ error: 'Too many requests' }); // ✓ 正确状态码
    }
});

// 信任代理的正确方式
app.set('trust proxy', ['loopback', '10.0.0.0/8', '172.16.0.0/12']); // ✓ 白名单

// 获取IP的安全实现
function getClientIp(req) {
    if (req.headers['x-forwarded-for']) {
        // 验证请求来自可信代理后才取第一个IP
        return req.headers['x-forwarded-for'].split(',')[0].trim();
    }
    return req.ip || req.connection.remoteAddress;
}

// 所有认证端点使用相同limiter
app.post('/api/login', ipLimiter, accountLimiter, loginHandler);
app.post('/oauth/token', ipLimiter, accountLimiter, tokenHandler);
app.post('/password-reset', ipLimiter, accountLimiter, resetHandler);
```

## 审计报告模板

**漏洞概述**：[描述发现的具体漏洞类型]

**复现步骤**：
1. [具体操作步骤，如使用ab/curl]
2. [观察到的异常行为]
3. [实际能发送的请求数 vs 预期限制]

**影响面**：
- 可被用于[暴力破解/账户枚举/API滥用]
- 涉及端点：[/api/login, /password-reset等]
- 环境类型：[单实例/多实例/集群]

**修复建议**：
1. 使用Redis Store替代MemoryStore
2. 将keyGenerator改为IP+username组合
3. 验证所有端点使用统一limiter配置
4. 配置trust proxy白名单而非true

**修复优先级**：立即（P1）/ 紧急（P2）/ 短期（P3）

