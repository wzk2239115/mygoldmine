# NodeJS 相对路径重定向漏洞审计指南

## Details

### 核心操作定位
相对路径重定向漏洞通常出现在以下场景：

1. **URL 跳转操作** - `res.redirect()` 或 `res.location()` 处理来自用户输入的重定向目标
2. **路径拼接** - 使用字符串拼接或 `path.join()` 处理用户控制的路径段
3. **查询参数提取** - `req.query.redirect`、`req.body.returnUrl` 等未验证的重定向参数

代码示例：
```javascript
// 易受攻击的模式
app.get('/login', (req, res) => {
  const redirectUrl = req.query.redirect || '/dashboard';
  res.redirect(redirectUrl);
});

// 路径拼接场景
app.get('/resource/:id', (req, res) => {
  const resourcePath = path.join(__dirname, 'public', req.params.id);
  res.sendFile(resourcePath);
});

// 组合利用场景
app.post('/share', (req, res) => {
  const baseUrl = req.body.baseUrl || 'https://example.com';
  const nextPath = req.query.next;
  res.redirect(baseUrl + nextPath);
});
```

**快速定位核心操作技巧** `【L1:关键词扫描】`
- 检索关键词：`res.redirect()`、`res.location()`、`res.statusCode = 3xx`
- 追踪数据流来源：关键词周围 10 行内查看参数来自 `req.query`、`req.params`、`req.body`
- 重点检查条件分支：是否存在硬编码白名单或正则校验

**快速定位保护机制技巧** `【L2:跳读】`
- 查找 URL 解析相关代码：`new URL()`、`url.parse()`、`urlparse` 的使用
- 追踪主机验证逻辑：检查 `.hostname`、`.origin`、`.protocol` 相关校验
- 搜索重定向白名单实现：`allowlist`、`whitelist`、`ALLOWED_DOMAINS`、`isSafeUrl()` 函数
- 审查路径标准化：`path.normalize()`、`path.resolve()` 使用场景
- 关键流程追踪 `【L3:逐行读】`：从 redirect 参数接收到实际跳转的完整链路，确保没有绕过保护机制的中间环节

## Classify

### 漏洞 vs 误报 vs 代码异味研判标准

**确认为漏洞的关键特征：**
1. **无验证的用户输入直接参与重定向决策** - 用户提供的值未经任何白名单或格式校验直接用于 `redirect()`
2. **保护机制可被绕过** - 存在黑名单但使用了不完整的模式（如仅检查 `//`，未防御 `///`；仅检查协议未防御 `//example.com`）
3. **相对路径攻击** - 输入值包含 `../` 且未被过滤，导致目录遍历
4. **多参数组合利用** - 不同参数虽单独看似安全（如一个参数固定为 `http://example.com`），但组合使用时被绕过

**误报判断标准：**
- 重定向目标来自可信数据源（如数据库存储的业务数据、内部配置文件）
- 存在有效的白名单验证：使用 `url.parse()` 严格验证 `hostname` 或相对路径限制在特定目录
- 使用了 Express 或框架提供的安全重定向函数（如经过安全审计的第三方库）
- 重定向仅限制于内部路径：验证路径不包含协议且经过 `path.resolve()` 标准化后位于预期目录

**代码异味指征：**
- 存在 TODO、FIXME 注释涉及重定向安全
- 重定向逻辑中出现多次 `.replace()`、`.split()` 等临时性防护
- 保护机制中使用了已知被绕过的技术（如正则 `/^https?:\/\/` 对抗 `javascript:` 协议）
- 路径操作混合使用字符串拼接和 `path.join()`，导致标准化不一致

## Low risk

### 低风险评级的情况

**可评定为低风险的场景包括：**

1. **严格的相对路径重定向** - 验证目标路径不包含协议、域名，仅允许 `/` 开头的内部路径，且经过白名单检查（如重定向池限制在特定路由列表）

2. **完整的域名白名单验证** - 使用 `new URL()` 解析用户输入，严格验证 `hostname` 属性与白名单对比（字符串相等而非正则），协议固定为 HTTPS

3. **不可信数据仅用于路径片段** - 用户输入只控制路径的一部分（如 `/api/v1/{userId}/profile`），且该部分经过校验不包含目录遍历序列（`../`、`..\\` 等）

4. **路径标准化后的目录边界检查** - 使用 `path.resolve()` 标准化用户提供的路径，通过比较 `realpath` 或 `startsWith()` 确保其位于预期目录树内

5. **同站点重定向的安全实现** - 验证重定向目标的 `origin` 与当前请求 `origin` 一致，防止跨域重定向（仅允许协议+主机+端口完全相同）

6. **隔离的低权限上下文** - 重定向仅用于展示层或静态资源跳转，不涉及敏感业务流程、会话切换或权限相关操作

