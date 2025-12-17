# TypeScript 框架 CSRF 防护被禁用漏洞

## Details

### 漏洞成因
在使用 NestJS、Next.js、Express（TypeScript）等框架时，官方通常提供 CSRF 防护中间件（如 `csurf`、`@nestjs/csrf`, Next.js API Route 的 `csrf` 插件）。若为了调试或跨域需求而禁用这些中间件，或在某些路由上错误地跳过防护，敏感接口将暴露于 CSRF 攻击。此外，SSR/BFF 场景可能在某些部署环境遗漏配置，导致部分端点未启用 CSRF 守卫。

### 代码示例

**易受攻击的代码：**
```typescript
// main.ts (NestJS)
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.use(cookieParser());
  // 开发时为方便测试直接关闭 CSRF
  // app.use(csurf());
  await app.listen(3000);
}
bootstrap();
```

```typescript
// Next.js API Route
import nc from "next-connect";
const handler = nc()
  // .use(csrf())  // 被注释
  .post((req, res) => {
    // 修改密码的敏感操作，没有 Token 验证
  });
export default handler;
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- NestJS：`app.use(csurf())`, `CsrfFilter`, `@UseGuards(CsrfGuard)`
- Express：`csurf`, `cookieParser`, `app.use('/api', ...)`
- Next.js：`csrf`, `next-connect`, `csrfProtection`
- 路由豁免：`ignoreMethods`, `ignoreRoutes`, `if (bypassCsrf)`

**定位步骤：**
1. 检查入口文件是否注册 CSRF 中间件，以及是否在生产环境被禁用。
2. 搜索路由守卫、拦截器的 `exclude` 列表。
3. 跳读（L2）关注自定义中间件是否在某些路径返回 `next()` 而未校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **环境变量控制**：仅在 `NODE_ENV=production` 启用，需要确认部署环境。
- **路径白名单**：确认是否错误地将敏感接口加入跳过列表。
- **Token 注入**：SSR 页面是否将 Token 传递到客户端。
- **错误处理**：Token 验证失败时是否正确返回 403。

**定位技巧：**
- 检查多实例/微前端部署是否共享相同配置。
- 分析 serverless 函数中的 CSRF 防护是否未被打包。
- 关注 WebSockets/SSE 等特殊协议是否需要额外防护。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局启用中间件且无豁免 | **L0（快速跳过）** | 风险低 |
| 部分模块禁用防护 | **L2（跳读）** | 需确认是否必要 |
| 全局禁用或忘记启用 | **L3（逐行读）** | 高风险 |
| 多环境配置不一致 | **L4（跨模块追踪）** | 易在特定环境失效 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 框架提供的 CSRF 中间件被禁用或未启用。
2. 敏感接口依赖 Cookie 认证且缺乏其它防护。
3. 攻击者可构造跨站请求执行敏感操作。

#### 误报
以下情况可视为误报：
1. 接口采用纯 REST/Bearer Token，不依赖浏览器 Cookie。
2. 在 API Gateway 层已实现等效 CSRF 防护。
3. 路由仅供可信内部服务调用并有网络层隔离。

#### 代码异味
仍需记录的风险：
1. 只在生产环境启用，测试环境缺失导致上线时被注释遗忘。
2. 某些中间件使用 `ignoreMethods` 忽略 `POST`，设置错误。
3. 自定义守卫中将 Token 验证错误处理为日志警告。
4. 使用 `Helmet` 等安全中间件时未配合 CSRF 守卫。

## Low risk

### 低风险评级场景

#### 1. 内部网络 + 限制访问
- **场景：** API 仅在内网/VPN 使用。
- **风险评估：** 攻击面小，但仍不建议关闭。

#### 2. 只读 API
- **场景：** 所有端点均为 GET/只读，无状态修改。
- **风险评估：** CSRF 影响有限。

#### 3. Bearer Token 鉴权
- **场景：** 请求不依赖 Cookie，使用 OAuth2 / JWT header。
- **风险评估：** CSRF 风险较低，但需确保无 Cookie 回退。

#### 4. 审计与告警
- **场景：** 未启用 CSRF 前提下，监控敏感操作的来源和频率。
- **风险评估：** 有助于发现异常，但非根治。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内网/受控环境 | 攻击面有限 | 中 |
| 只读接口 | 不涉及状态变更 | 低 |
| Bearer Token 良好实现 | 不依赖 Cookie | 低 |
| 审计监控 | 提升检测能力 | 高（仍建议开启 CSRF 防护）|

