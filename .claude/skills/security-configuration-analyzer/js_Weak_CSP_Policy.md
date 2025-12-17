# JavaScript / TypeScript - Weak CSP Policy

## Details

### 典型代码示例

**Node.js/Express 后端设置 CSP**
```javascript
app.use((req, res, next) => {
  res.setHeader("Content-Security-Policy", "default-src * 'unsafe-inline' 'unsafe-eval'; script-src *");
});
```

**HTML meta 标签设置 CSP**
```html
<meta http-equiv="Content-Security-Policy" content="default-src *; script-src 'unsafe-inline' 'unsafe-eval' *">
```

**前端框架配置（Next.js/Nuxt.js）**
```javascript
// next.config.js
module.exports = {
  async headers() {
    return [{
      source: '/:path*',
      headers: [{ key: 'Content-Security-Policy', value: "script-src 'self' 'unsafe-inline'" }]
    }]
  }
}
```

**Webpack CSP Plugin**
```javascript
new CspHtmlWebpackPlugin({
  'script-src': ["'unsafe-inline'", "'unsafe-eval'"],
  'style-src': ["'unsafe-inline'"]
});
```

### 快速定位核心操作的技巧

**（L1：关键词扫描）** 全局搜索关键字：
- `Content-Security-Policy` / `CSP` / `csp`
- `setHeader` + `Content-Security-Policy`
- `<meta http-equiv`（HTML 文件中）

**（L2：跳读）** 快速扫描配置文件：
- `next.config.js` / `nuxt.config.js` / `vue.config.js` 的 headers 配置段
- Nginx/Apache 配置文件的 `add_header` 指令
- 中间件文件（`middleware/` 目录）中的响应头设置

**（L3：逐行读）** 检查 CSP 策略字符串构建逻辑：
- 动态拼接 CSP 字符串是否引入通配符或危险指令
- 环境变量/配置文件中的 CSP 模板是否过度宽松
- Helmet/CSP 库的配置对象是否存在 `unsafeInline: true`

**（L4：跨模块追踪）** 追踪 CSP 策略来源：
- 配置中心/环境变量的 CSP 值传递链路
- CSP 中间件的注册位置及覆盖关系（后注册可能覆盖前者）
- 反向代理层（CDN/网关）是否追加或覆盖应用层 CSP

### 快速定位保护机制的技巧

**（L0：快速跳过）** 存在以下情况可快速跳过：
- 使用严格的 CSP 库（如 `helmet` 默认严格配置且未自定义）
- 明确配置了 `script-src 'nonce-xxx'` 或 `'hash-xxx'` 且无 `unsafe-*`

**（L1：关键词扫描）** 搜索危险指令：
- `'unsafe-inline'` / `'unsafe-eval'`
- `*` 通配符（尤其在 `script-src` / `default-src`）
- `data:` / `blob:` URI scheme（需结合场景判断）

**（L2：跳读）** 检查指令完整性：
- 是否缺少 `script-src` 而仅依赖宽松的 `default-src`
- `object-src` / `base-uri` 是否设置为 `'none'`
- 是否允许 `file://` 或 `filesystem:` 协议

**（L3：逐行读）** 评估白名单有效性：
- 白名单域名是否为已知 JSONP 端点（如 `*.google.com`）
- 白名单域名是否为 CDN（攻击者可能上传文件）
- `*.example.com` 子域通配是否覆盖用户内容托管子域

**（L4：跨模块追踪）** 检查策略继承与覆盖：
- 父页面与 iframe 的 CSP 策略差异
- 不同路由/页面的 CSP 策略不一致性
- 浏览器扩展或代理是否注入额外的 CSP

## Classify

### 真实漏洞判定标准
- **同时满足**：CSP 存在 `unsafe-inline`/`unsafe-eval`/通配符 **且** 应用存在 XSS 注入点（DOM/反射/存储型）
- **同时满足**：白名单域名可被攻击者控制（JSONP 端点/开放上传 CDN）**且** 存在注入点
- **同时满足**：`base-uri` 未限制 **且** 存在相对路径资源加载 **且** 可注入 `<base>` 标签

### 误报场景
- 仅存在弱 CSP 但应用无任何用户输入/输出点（纯静态页面）
- CSP 配置在开发环境文件中（需确认生产环境配置）
- CSP 策略被更严格的上游策略覆盖（CDN/WAF 层）
- 使用 `unsafe-inline` 但所有内联脚本均通过 `nonce` 属性保护

### 代码异味
- 为兼容老旧代码临时放宽 CSP，但已有迁移计划和 TODO 注释
- 内部工具/管理后台使用宽松 CSP，但仅内网可访问且有其他认证机制
- CSP 配置项齐全但个别指令过于宽松（如 `style-src` 允许 `unsafe-inline`）

## Low risk

### 低风险评级适用场景

**环境隔离充分**
- 仅在本地开发/测试环境启用弱 CSP，生产环境有独立严格配置
- 内网隔离的管理系统，无互联网暴露面且仅受信用户可访问

**攻击面受限**
- 应用为纯静态展示页（无表单、评论、搜索等用户输入功能）
- 所有用户输入已通过严格的服务端校验+输出编码，历史无 XSS 漏洞记录

**分层防御**
- 存在 WAF/CDN 层的脚本执行监控与拦截
- 关键操作需二次认证（如 TOTP/硬件令牌），即使 XSS 也难以完成攻击链

**业务特性**
- 不处理敏感数据（无 Cookie、Token、个人信息）
- 应用生命周期短（临时活动页、即将下线的遗留系统）

**补偿控制**
- 虽允许 `unsafe-inline` 但实现了 Subresource Integrity (SRI) 校验所有外部资源
- 使用 Trusted Types API 强制 DOM XSS 保护（浏览器原生特性）

**注意**：低风险不等于无风险，需在审计报告中明确残余风险及建议改进方向。