# Node.js 缓存中毒 - 缓存键包含用户可控头

## 基本信息
- **难度等级：** ★★★★☆ | **审计时间：** 30-45分钟
- **关键词搜索：** `cache`, `redis`, `memcached`, `lru-cache`, `node-cache`, `req.headers`, `Vary`, `X-Forwarded`, `Accept-Language`
- **快速检查：** 缓存键是否包含用户可控的请求头，Vary头是否完整

## 漏洞成因

当Node.js应用使用缓存（Redis、内存缓存等）时，若缓存键或响应内容依赖用户可控的请求头（如Accept-Language、X-Forwarded-Host），但缓存键未正确包含这些因素或Vary头不完整，攻击者可污染缓存，影响其他用户。

### 常见漏洞模式

```javascript
// ✗ 漏洞：缓存键不包含影响响应的头
const cache = new NodeCache();

app.get('/api/data', (req, res) => {
    const cacheKey = req.url;  // 仅URL作为键
    const cached = cache.get(cacheKey);
    if (cached) {
        return res.json(cached);
    }

    const lang = req.headers['accept-language'];  // 影响响应内容
    const data = getLocalizedData(lang);
    cache.set(cacheKey, data);
    res.json(data);
    // 攻击者设置Accept-Language: evil，污染缓存
});
```

```javascript
// ✗ 漏洞：X-Forwarded-Host影响响应但未加入缓存键
app.get('/api/config', async (req, res) => {
    const host = req.headers['x-forwarded-host'] || req.hostname;
    const cacheKey = `/api/config`;  // 不包含host

    let config = await redis.get(cacheKey);
    if (!config) {
        config = { apiUrl: `https://${host}/api` };
        await redis.set(cacheKey, JSON.stringify(config));
    }

    res.json(JSON.parse(config));
    // 攻击者设置X-Forwarded-Host: evil.com污染缓存
});
```

```javascript
// ✗ 漏洞：Vary头缺失或不完整
app.get('/page', (req, res) => {
    const lang = req.headers['accept-language'];
    const ua = req.headers['user-agent'];

    res.set('Cache-Control', 'public, max-age=3600');
    res.set('Vary', 'Accept-Language');  // 缺少User-Agent
    res.send(renderPage(lang, ua));
});
```

```javascript
// ✗ 漏洞：用户可控头直接加入缓存键
app.get('/api/user', (req, res) => {
    const customHeader = req.headers['x-custom-id'];
    const cacheKey = `user:${customHeader}`;  // 可控头作为键

    // 可能导致缓存污染或缓存穿透攻击
    const data = cache.get(cacheKey) || fetchUser(customHeader);
    res.json(data);
});
```

```javascript
// ✓ 修复：完整的缓存键 + Vary头
const crypto = require('crypto');

const generateCacheKey = (req) => {
    const factors = [
        req.url,
        req.headers['accept-language'] || '',
        req.headers['accept-encoding'] || ''
    ];
    return crypto.createHash('sha256').update(factors.join('|')).digest('hex');
};

app.get('/api/data', (req, res) => {
    const cacheKey = generateCacheKey(req);
    res.set('Vary', 'Accept-Language, Accept-Encoding');
    // ...缓存逻辑
});
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | X-Forwarded-*影响响应 | 搜索 `x-forwarded-host\|x-forwarded-proto` + 缓存，检查缓存键 |
| **P0** | 缓存键仅含URL | 搜索 `cache\.get\|redis\.get` + `req\.url`，检查是否遗漏头因素 |
| **P1** | Vary头缺失 | 搜索 `Cache-Control.*public`，检查是否有对应Vary头 |
| **P1** | Accept-*影响内容 | 搜索 `accept-language\|accept-encoding` + 缓存逻辑 |
| **P2** | 用户头作为缓存键 | 搜索 `req\.headers.*cacheKey`，评估污染风险 |
| **P2** | CDN/代理缓存配置 | 检查nginx/Varnish配置与代码一致性 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 无缓存或Cache-Control: no-store | 快速跳过 |
| **L1** | 私有缓存，无公共缓存 | 关键词扫描确认无public缓存 |
| **L2** | 公共缓存，单一影响因素 | 跳读检查Vary头和缓存键 |
| **L3** | 多因素影响响应 | 逐行追踪所有req.headers使用 |
| **L4** | 多层缓存架构 | 跨层审计缓存配置一致性 |

---

## 审计专业技巧

### 真实漏洞与误报的区分经验

#### 容易误判为漏洞的场景

**场景1：内容依赖Accept-Language但时间窗口短**
```javascript
// 乍看有风险，实际风险低
app.get('/api/status', (req, res) => {
    const lang = req.headers['accept-language'];
    const status = getSystemStatus(lang);  // 仅翻译UI文本
    res.set('Cache-Control', 'public, max-age=30');
    res.set('Vary', 'Accept-Language');
    res.json(status);
});
```
**区分要点**：
- 缓存时间仅30秒，且有完整Vary头 → **非漏洞** ✓
- 虽然缺Vary头但max-age=10秒，污染时间窗口极小 → **风险可接受**
- 若max-age=86400（24小时）且缺Vary → **严重漏洞** ✗

**场景2：X-Forwarded-Host用于日志而非响应内容**
```javascript
// 虽然读取X-Forwarded-Host，但未影响响应内容
app.get('/api/data', (req, res) => {
    const clientHost = req.headers['x-forwarded-host'];
    logger.info(`Request from: ${clientHost}`);  // 仅用于日志

    res.json({ data: 'static' });  // 响应不依赖clientHost
});
```
**区分要点**：
- 用户可控头仅用于日志 → **非漏洞** ✓
- 同样的头用于设置响应location或apiUrl → **严重漏洞** ✗

**场景3：缓存键包含hostname但使用了URL参数**
```javascript
// 表面看缓存键不全，实际上URL已包含区分因素
app.get('/api/user/:id', (req, res) => {
    const lang = req.headers['accept-language'];
    const userId = req.params.id;

    // 缓存键虽然不显式含accept-language，但URL(:id)已包含用户区分因素
    const cacheKey = req.url;  // /api/user/123

    if (lang === 'zh') { /* ... */ }
    res.set('Vary', 'Accept-Language');
});
```
**区分要点**：
- 若API返回用户私有数据，仅凭userId区分足够 → **可接受**（Vary头必须）
- 若多个用户同id需不同语言内容，缺Vary → **漏洞** ✗

#### 真实漏洞的重点线索

**红线1：多因素影响但缓存键单一**
```javascript
// ✗ 确认漏洞
app.get('/api/product', (req, res) => {
    const lang = req.headers['accept-language'];
    const currency = req.headers['x-currency'];  // 两个因素影响价格

    const cacheKey = req.url;  // 仅URL，未包含两个因素
    let data = cache.get(cacheKey);
    if (!data) {
        data = {
            name: translate(lang),
            price: formatPrice(currency)
        };
        cache.set(cacheKey, data);
    }
    res.set('Cache-Control', 'public, max-age=3600');
    // 缺Vary或Vary不完整 → 用户A看到中文+USD，被污染为日文+EUR
    res.json(data);
});
```
**确认漏洞的线索**：
- ✗ 找到2+个用户可控头被读取
- ✗ 找到cache.set/redis.set但缓存键简单
- ✗ Cache-Control含public但无Vary或Vary不完整
- ✗ 实测：修改头后，其他用户受影响

**红线2：X-Forwarded-*直接用于响应**
```javascript
// ✗ 100%确认漏洞
app.get('/api/config', (req, res) => {
    const host = req.headers['x-forwarded-host'] || req.hostname;
    const cacheKey = `/config`;

    let config = cache.get(cacheKey);
    if (!config) {
        // 直接使用不可信头
        config = {
            apiEndpoint: `https://${host}/api`,
            loginUrl: `https://${host}/login`
        };
        cache.set(cacheKey, JSON.stringify(config));
    }
    res.set('Cache-Control', 'public, max-age=86400');
    res.json(JSON.parse(config));
});
```
**确认漏洞特征**：
- ✗ X-Forwarded-Host/Proto 直接用于生成URL或内容
- ✗ 缓存键未包含该头（如仅`/config`）
- ✗ Public缓存，长期有效
- ✗ 实测：设置X-Forwarded-Host: attacker.com，检查返回的apiEndpoint

**红线3：缓存穿透与污染结合**
```javascript
// ✗ 双重漏洞：穿透+污染
app.get('/user/:id', (req, res) => {
    const lang = req.headers['accept-language'];
    const cacheKey = `user:${req.params.id}:${lang}`;  // 虽包含lang，但格式不安全

    // 攻击者可用lang=../../../admin污染不同key
    let user = cache.get(cacheKey);
    if (!user) {
        user = getUser(req.params.id, lang);
        cache.set(cacheKey, user);
    }
    res.json(user);
});
```

### 审计技巧速查表

| 特征 | 是否确认漏洞 | 审计方法 |
|------|------------|---------|
| 读取Accept-Language但有完整Vary | ❌ 假阳性 | 验证Vary头覆盖所有因素 |
| X-Forwarded-Host用于日志 | ❌ 假阳性 | 追踪该变量是否影响响应体 |
| 缓存键包含URL但URL含querystring | ⚠️ 需确认 | 检查querystring是否与响应内容对应 |
| Cache-Control: public无Vary | ✅ 确认漏洞 | 直接上报，询问缓存策略意图 |
| X-Forwarded-*影响响应体或location | ✅ 确认漏洞 | 提供PoC：修改头并检查缓存内容 |
| 2+用户可控头影响响应但缓存键简单 | ✅ 确认漏洞 | 生成漏洞链接，演示缓存污染 |
| Vary头存在但格式不标准 | ⚠️ 需确认 | 检查CDN/代理是否正确解析该Vary头 |

### 漏洞证明的实验方法

**实验1：验证缓存污染**
```bash
# 第1次请求：设置Accept-Language: en
curl -H "Accept-Language: en" "http://app/api/data" -v
# 记录响应中是否含中文或英文内容

# 第2次请求：不设置Accept-Language（或设置zh）
curl -H "Accept-Language: zh" "http://app/api/data" -v
# 检查是否返回了第1次的内容（英文）
# 如果是 → 缓存污染确认 ✓

# 第3次请求：等待缓存过期或清空
curl -H "Accept-Language: fr" "http://app/api/data" -v
# 验证超过max-age后是否返回正确内容
```

**实验2：验证X-Forwarded-Host污染**
```bash
# 第1次：正常请求
curl "http://app/api/config" -v

# 第2次：注入恶意host
curl -H "X-Forwarded-Host: attacker.com" "http://app/api/config" -v
# 检查响应中的apiEndpoint是否为attacker.com

# 第3次：再次正常请求
curl "http://app/api/config" -v
# 若返回的apiEndpoint仍为attacker.com → 污染成功 ✓
```

**实验3：验证Vary头覆盖**
```bash
# 在浏览器DevTools或curl中检查响应头
curl "http://app/api/data" -i | grep -i "vary"
# 期望输出：Vary: Accept-Language, Accept-Encoding

# 若缺失Accept-Encoding但代码中使用了req.headers['accept-encoding']
# 则为不完整的Vary → 漏洞 ✗
```

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 响应被公共缓存（Cache-Control: public或CDN缓存）
2. 响应内容依赖某个用户可控请求头
3. 缓存键或Vary头未包含该头

### 典型漏洞特征（满足任一项即确认）
- ✗ 缓存键仅为URL，但响应依赖Accept-Language
- ✗ X-Forwarded-Host影响响应URL但未加入缓存键
- ✗ Vary头存在但不完整，漏掉部分影响因素
- ✗ Cache-Control: public但无Vary头

### 安全排除（任一项充分）
- ✓ Cache-Control: private或no-store
- ✓ 缓存键包含所有影响响应的因素
- ✓ Vary头完整包含所有影响因素
- ✓ 仅内部API，无公共缓存层

### 灰色判定（风险较低但需注意）
- 缓存时间短（max-age < 60）
- 内网应用，攻击者难以利用
- 响应内容无敏感性

---

## 实现建议

### 核心防护方案

**方案1：安全缓存键生成**
```javascript
const crypto = require('crypto');

const generateSecureCacheKey = (req, factors = []) => {
    const keyParts = [req.method, req.url];

    // 添加影响响应的头
    factors.forEach(factor => {
        keyParts.push(req.headers[factor.toLowerCase()] || '');
    });

    return crypto.createHash('sha256')
        .update(keyParts.join('|'))
        .digest('hex');
};

// 使用
const cacheKey = generateSecureCacheKey(req, ['accept-language', 'accept-encoding']);
```

**方案2：完整Vary头中间件**
```javascript
const varyMiddleware = (varyHeaders) => {
    return (req, res, next) => {
        res.set('Vary', varyHeaders.join(', '));
        next();
    };
};

app.use('/api', varyMiddleware(['Accept-Language', 'Accept-Encoding']));
```

**方案3：禁止不可信头影响缓存**
```javascript
const TRUSTED_VARY_HEADERS = new Set([
    'accept-language',
    'accept-encoding',
    'accept'
]);

const sanitizeCacheFactors = (req, factors) => {
    return factors.filter(f => {
        const header = f.toLowerCase();
        return TRUSTED_VARY_HEADERS.has(header);
    });
};
```

### 检查清单
- [ ] 缓存键包含所有影响响应的因素
- [ ] Vary头完整设置
- [ ] X-Forwarded-*头使用前验证
- [ ] 敏感响应设置Cache-Control: private
- [ ] 测试缓存中毒：不同头值请求后检查其他用户响应

---

## 修复优先级

1. **立即修复**：X-Forwarded-Host影响响应但未加入缓存键
2. **本周修复**：添加完整Vary头，修正缓存键
3. **可选加强**：实现安全的缓存键生成函数
4. **长期优化**：CDN配置审计，确保缓存策略一致
