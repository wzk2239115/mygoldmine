# NodeJS 多行响应头未规范化

## Details

**审计等级：L2（跳读）/ L3（逐行读）**

**危险函数特征：**
- `response.setHeader()` 或 `response.header()` 传入包含 `
` 的值
- 从外部源读取头值未规范化
- 反向代理转发头时未规范化

**快速定位核心操作：**
1. 搜索关键字：`setHeader`、`header`、`
` 在值中
2. 追踪头值来源：外部 API、数据库、请求参数
3. 检查是否存在规范化
4. 追踪头值转发流程

**快速定位保护机制：**
- 规范化：`value.replace(/[
]/g, '')`
- 验证：`if (value.includes('\r') || value.includes('\n'))`
- 框架防护：Node.js 版本已修补的检测

**代码示例：**
```javascript
// 危险：外部值直接设置为响应头
app.get('/proxy', (req, res) => {
    const custom = req.headers['x-custom'];
    res.setHeader('X-Forwarded', custom);  // 危险
});

// 危险：API 响应转发
app.get('/forward', (req, res) => {
    fetch(apiUrl).then(resp => {
        Object.entries(resp.headers).forEach(([k, v]) => {
            res.setHeader(k, v);  // 危险
        });
    });
});

// 危险：数据库字段
app.get('/db-header', (req, res) => {
    const headerVal = await db.getHeader(id);
    res.setHeader('X-Custom', headerVal);  // 危险
});
```

## Classify

**漏洞（Medium）：**
- 外部值包含 `
` 未规范化
- 导致响应分割
- 框架未自动检测

**误报：**
- 头值硬编码
- 框架已规范化

**代码异味（Medium）：**
- 外部来源未验证
- 仅过滤部分字符
- 间接流程

## Low risk

**以下情况评为低风险：**
- 头值硬编码
- 明确过滤 CRLF
- 框架已验证
- 内部来源且已验证

## 审计专业技巧

### 1. 真实漏洞的核心特征识别

**必须同时满足的条件（三角洲检验）：**
1. **可控输入源**：用户能够影响值内容
   - `req.query`、`req.params`、`req.headers` 直接使用 ⚠️
   - 来自外部 API 响应 ⚠️
   - 数据库字段但数据由用户提供 ⚠️

2. **传入响应头**：通过 `setHeader()`、`header()` 设置
   - 设置发送给客户端的头
   - 转发上游 API 响应头

3. **无规范化**：值未经过清理
   - 不包含 `\r\n` 过滤
   - 不包含正则替换 `/[\r\n]/`
   - 框架版本过旧

**示例：真实漏洞（三条件都满足）**
```javascript
// 情景：Web 服务转发第三方 API 响应头
app.get('/proxy/:provider', async (req, res) => {
    const provider = req.params.provider;
    const apiResp = await fetch(`https://api.${provider}.com/data`);

    // 直接转发所有响应头 - 攻击者可控 provider 参数
    for (const [key, value] of Object.entries(apiResp.headers)) {
        res.setHeader(key, value);  // 真实漏洞
    }
});
```

### 2. 常见误报场景与识别

**误报一：硬编码值（无可控输入）**
```javascript
res.setHeader('X-Custom', 'hardcoded-value');  // 低风险
res.setHeader('Content-Type', req.accepts());  // 误报，accepts() 返回安全字符串
```

**误报二：存在防护机制**
```javascript
// ✅ 真正安全：显式过滤 CRLF
const headerValue = req.query.name;
const sanitized = headerValue.replace(/[\r\n]/g, '');
res.setHeader('X-User-Name', sanitized);  // 低风险

// ✅ 真正安全：白名单验证
const allowed = ['en', 'zh', 'es'];
if (allowed.includes(req.query.lang)) {
    res.setHeader('Content-Language', req.query.lang);  // 低风险
}
```

**误报三：框架已防护**
```javascript
// Express 4.16.0+ 已自动规范化多行头
res.setHeader('X-Test', 'value\r\ninjection');
// 框架会自动移除或拒绝 - 但需要确认版本

// 验证方式：查看 package.json 中 express 版本
// "express": "^4.18.0" - 安全
// "express": "^3.x.x" - 不安全
```

### 3. 审计实战技巧

**技巧一：追踪数据流**
- 先找 `setHeader` 调用点
- 反向追踪值来源（5步内）
- 判断是否与用户可控输入关联
- 关键：中间是否有 `.toString()`、`.split()`、`.replace()` 等转换

```javascript
// 从数据库读取，需追踪库中数据来源
const header = await db.query('SELECT header FROM config WHERE id = ?', [id]);
res.setHeader('X-Custom', header);  // 需要确认 id 是否可控

// 危险：id 来自 req.params
const header = await db.query('SELECT header FROM config WHERE id = ?',
    [req.params.id]);  // 真实漏洞
```

**技巧二：版本判断**
```bash
# 检查 Node.js 版本与补丁
node -v  # v14.x 需要检查具体小版本

# 检查依赖版本中是否有已知补丁
npm ls express http  # 查看框架版本
```

**技巧三：间接流程的风险评估**
```javascript
// 低风险：中间层有验证
app.get('/set-lang', (req, res) => {
    const lang = req.query.lang;  // 可控输入
    const langObj = SUPPORTED_LANGS[lang];  // 字典查询

    if (!langObj) {
        return res.status(400).send('Unsupported language');
    }

    res.setHeader('Content-Language', langObj.code);  // 低风险
});

// 高风险：模板注入变成头注入
app.get('/template', (req, res) => {
    const tpl = req.query.name;
    const compiled = compileTemplate(`Hello ${tpl}`);  // 可能有注入
    res.setHeader('X-Template-Name', tpl);  // 风险
});
```

**技巧四：响应头大小限制是否有效**
```javascript
// 检查是否有头大小限制
const server = http.createServer((req, res) => {
    res.setHeader('X-Data', req.query.data);
});

// Node.js 默认：8KB 头大小限制
// 但攻击者仍可注入空行或控制字符
// 不能作为安全防护
```

### 4. 真实与误报的鉴别表格

| 特征 | 真实漏洞 | 误报 | 关键判断 |
|------|--------|------|---------|
| **输入来源** | 用户直接控制 | 硬编码或白名单 | 能否改变值内容 |
| **防护机制** | 无或不完整 | `replace(/[\r\n]/)` 或白名单 | 搜索过滤代码 |
| **框架版本** | 旧版本 (<4.16) | 新版本 (>4.18) | 检查 package.json |
| **传播方式** | 直接 `setHeader()` | 框架 API 返回值 | 中间是否转换 |
| **业务逻辑** | 用户输入 → 头值 | 内部配置 → 头值 | 数据来源 |

### 5. 常见陷阱与避坑

**陷阱一：假安全的字符集限制**
```javascript
// ❌ 假安全：仅限制字母数字
const value = req.query.id.replace(/[^a-z0-9]/g, '');
res.setHeader('X-ID', value);  // 字符还是被过滤了，但可能遗漏特殊含义字符
```

**陷阱二：信任 Content-Type 中间件**
```javascript
// ❌ 不安全：中间件不能保证所有头都安全
app.use((req, res, next) => {
    res.setHeader('X-Processed', 'true');
    next();
});

app.get('/user', (req, res) => {
    const name = req.query.name;
    res.setHeader('X-User-Name', name);  // 中间件不防护这个
});
```

**陷阱三：仅验证一个方向的流向**
```javascript
// 需要检查两个方向：
// 1. 用户请求 → 响应头（HTTP 响应分割）
// 2. 外部 API → 响应头（可能注入响应头污染）
// 3. 数据库 → 响应头（如果数据库被污染）
```

### 6. 审计检查清单

在审计时按此顺序检查，提高效率：

- [ ] 搜索所有 `setHeader`、`header()` 调用
- [ ] 对每个调用，追踪值的来源（5行代码内）
- [ ] 判断来源是否在用户控制范围内
- [ ] 检查是否存在 `replace(/[\r\n]/)` 或 `filter()` 过滤
- [ ] 确认 Node.js/Express 版本是否 ≥ 已知安全版本
- [ ] 检查是否存在白名单验证
- [ ] 若有疑问，搜索：`Buffer`、`toString()`、`.split('\n')` 在附近
- [ ] 确认修复方案：规范化或白名单至少择其一
