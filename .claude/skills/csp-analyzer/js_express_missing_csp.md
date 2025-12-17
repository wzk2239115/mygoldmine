---
title: Express 应用缺失 CSP 响应头审计指南
description: 识别 Express 中间件中缺失 Content-Security-Policy 响应头的漏洞
---

# Express 应用缺失 CSP 响应头审计指南

## Details

### 漏洞成因分析

Express 作为 Node.js 最流行的 Web 框架，应用通过中间件设置 HTTP 响应头。当开发者未配置专门的中间件来设置 `Content-Security-Policy` 响应头时，所有返回 HTML 的响应将缺失该安全头，导致应用完全暴露于 XSS 攻击。

Express 应用中缺失 CSP 头的典型场景：
- 完全未使用任何 CSP 中间件（如 helmet.js）
- 使用 helmet.js 但未启用 CSP 功能或配置为空
- 选择性应用 CSP 中间件导致部分路由无保护

### 代码示例

**危险模式 1：完全缺失 CSP 中间件**

```javascript
const express = require('express');
const app = express();

// 未配置任何 CSP 相关中间件
app.get('/', (req, res) => {
  res.send('<html><body>Welcome</body></html>');
});

app.listen(3000);
```

**危险模式 2：使用 helmet 但 CSP 未启用**

```javascript
const express = require('express');
const helmet = require('helmet');
const app = express();

// helmet 默认启用 CSP，但如果显式禁用
app.use(helmet({
  contentSecurityPolicy: false  // ❌ CSP 被禁用
}));

app.get('/', (req, res) => {
  res.send('<html><body>Content</body></html>');
});
```

**危险模式 3：helmet CSP 配置过于宽松**

```javascript
const express = require('express');
const helmet = require('helmet');
const app = express();

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'unsafe-inline'"],  // ❌ 允许所有内联脚本
      styleSrc: ["'self'", "'unsafe-inline'"]
    }
  }
}));
```

**危险模式 4：仅部分路由配置 CSP**

```javascript
const express = require('express');
const helmet = require('helmet');
const app = express();

// 中间件仅应用于部分路由
app.get('/admin', helmet({ contentSecurityPolicy: {...} }), (req, res) => {
  res.send('<html>Admin</html>');
});

// 其他路由完全无保护
app.get('/', (req, res) => {
  res.send('<html>Home</html>');  // ❌ 无 CSP 保护
});
```

**安全模式**

```javascript
const express = require('express');
const helmet = require('helmet');
const app = express();

// 全局应用 helmet 的 CSP 中间件
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "https://cdn.example.com"],
      styleSrc: ["'self'"],
      imgSrc: ["'self'", "https:"],
      connectSrc: ["'self'"],
      frameSrc: ["'self'"],
      fontSrc: ["'self'"],
      objectSrc: ["'none'"],
      upgradeInsecureRequests: []
    }
  }
}));

app.get('/', (req, res) => {
  res.send('<html><body>Protected</body></html>');
});

app.listen(3000);
```

### 快速定位技巧

**【L1:关键词扫描】- 定位核心操作**

使用关键词搜索快速定位 CSP 中间件配置位置：
- `helmet` - 检查是否使用了 helmet 库
- `contentSecurityPolicy` - 查找 CSP 配置
- `Content-Security-Policy` - 查找手动设置响应头的地方
- `app.use()` 和 `app.get()/post()` - 识别中间件应用的作用域

**【L2:跳读】- 定位保护机制**

快速跳读以下位置来判断 CSP 配置状态：
- 应用主文件（通常为 `index.js`、`app.js`、`server.js`）顶部中间件注册区域
- `package.json` 的 dependencies 中是否包含 `helmet`
- 搜索 `helmet()` 调用的配置对象，确认 `contentSecurityPolicy` 的状态
- 检查是否存在全局应用 middleware 的代码（`app.use()`），vs 仅在特定路由应用

**【L3:逐行读】- 验证配置有效性**

逐行审视以下细节：
- 确认 CSP 中间件是否全局注册（在所有路由定义之前）
- 检查 `contentSecurityPolicy: false` 或缺失配置
- 验证 CSP 指令中是否包含 `'unsafe-inline'`、`'unsafe-eval'`、`*` 等危险配置
- 确认 `defaultSrc`、`scriptSrc`、`styleSrc` 是否显式定义

**【L4:跨模块追踪】- 追踪完整流程**

对于复杂架构追踪：
- 跨多个中间件文件查看 helmet 的完整配置
- 检查是否在其他地方覆盖了全局 CSP 设置
- 追踪自定义中间件中是否手动设置了 `Content-Security-Policy` 响应头
- 检查是否存在条件性的中间件应用（如仅在特定环境启用 CSP）

---

## Classify

### 漏洞确认标准

确认为真实漏洞的条件（满足任一条即为漏洞）：

1. **完全缺失 CSP 配置**：应用未使用任何 CSP 中间件，所有 HTML 响应都缺失 `Content-Security-Policy` 头

2. **显式禁用 CSP**：使用 helmet 但明确设置 `contentSecurityPolicy: false`

3. **helmet 版本过低或配置不当**：虽然使用了 helmet，但由于版本问题或配置缺陷导致 CSP 实际未生效

4. **仅部分路由有保护**：不同路由的 CSP 保护不一致，某些路由完全无保护

5. **CSP 指令过于宽松**：配置了 CSP 但包含 `'unsafe-inline'`、`'unsafe-eval'` 或 `*` 等绕过防护的指令

### 误报判定

以下情况应判定为误报：

1. **纯 API 应用**：应用仅返回 JSON，不生成 HTML（`Content-Type: application/json`），无需 CSP

2. **部分非 HTML 路由**：如果应用同时提供 API 和 HTML，需确认：
   - HTML 路由都有 CSP（即使 API 路由没有）
   - 不能因某个 API 路由缺失 CSP 就判定为漏洞

3. **Content-Security-Policy-Report-Only 在测试环境**：在开发或测试环境使用 Report-Only 模式是可接受的，但生产环境必须使用强制执行

4. **框架内置防护**：某些高级框架或网关可能在 Express 层之外处理 CSP（如反向代理、WAF），需仔细确认

### 代码异味识别

识别为代码异味（需要优化但不算漏洞）的情况：

1. **CSP 配置不够严格**：虽然设置了 CSP，但指令的白名单过于宽松（如 `scriptSrc: ["'self'", "https:"]`）

2. **缺少 nonce/hash 机制**：应用包含内联脚本但未使用 nonce 或 hash 进行保护

3. **缺少报告机制**：未配置 `report-uri` 或 `report-to` 导致 CSP 违规无法监控

4. **硬编码 CSP 策略**：CSP 配置硬编码在代码中，难以根据环境动态调整

---

## Low risk

### 可降低风险等级的场景

以下情况可将风险评级从高降低为中或低：

1. **内网应用或局域网限制**：应用运行在完全隔离的内网环境中，无外部网络访问，CSP 的必要性下降

2. **已部署其他 XSS 防护层**：
   - 已在网关/反向代理层配置全局 CSP
   - 应用使用了 WAF（Web Application Firewall）进行流量过滤
   - 使用了自动化的输入输出编码库确保 XSS 防护

3. **应用经过客户端沙箱保护**：
   - 客户端使用了浏览器扩展进行额外保护
   - 应用运行在受限权限的容器中

4. **低敏感度的应用**：
   - 内容完全来自受信内部来源，无用户生成内容
   - 应用不处理任何敏感业务数据（如支付、认证、个人隐私信息）

5. **已知的技术限制**：
   - 应用因需要兼容过时浏览器而无法使用 CSP
   - 第三方依赖严重限制了 CSP 的实用性

6. **临时测试或演示应用**：虽然生产应该有 CSP，但对明确的临时应用可给予宽限

### 风险缓解建议

即使存在上述低风险情况，仍应考虑以下缓解措施来提高安全姿态：

- 逐步迁移到使用 CSP（如在 Report-Only 模式下测试）
- 结合其他防护手段（如 X-Frame-Options、X-Content-Type-Options）
- 实施严格的内容策略审核流程
- 定期进行安全审计和 XSS 检测
