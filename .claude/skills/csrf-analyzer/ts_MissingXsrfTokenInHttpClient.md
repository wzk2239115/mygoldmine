# TypeScript Angular HttpClient 缺少 XSRF Token 漏洞

## Details

### 漏洞成因
Angular 默认提供 XSRF 防护：当后端在 Cookie 中设置 `XSRF-TOKEN` 时，`HttpClient` 会自动将其添加到 `X-XSRF-TOKEN` 头。但如果禁用了默认防护、未调用 `HttpClientXsrfModule.withOptions` 正确配置，或通过 `HttpClient` 直接 `fetch`/自定义 `HttpBackend` 绕过拦截器，敏感请求将缺少 Token，从而暴露于 CSRF 攻击。

### 代码示例

**易受攻击的代码：**
```typescript
// app.module.ts
@NgModule({
  imports: [
    HttpClientModule,
    // 未导入 HttpClientXsrfModule，默认 Token 不会注入
  ],
})
export class AppModule {}
```

```typescript
// account.service.ts
updatePassword(data: PasswordPayload): Observable<void> {
  return this.http.post<void>("/api/account/password", data); // 未携带 XSRF 头
}
```

**另一个不安全示例（自定义 HttpBackend 绕过拦截器）：**
```typescript
constructor(private handler: HttpBackend) {
  this.rawHttp = new HttpClient(handler); // 绕过拦截器，不注入 Token
}

createTransfer(order: Transfer) {
  return this.rawHttp.post("/api/transfer", order);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 模块导入：`HttpClientModule`, `HttpClientXsrfModule`
- 自定义 HttpClient：`new HttpClient(httpBackend)`
- 原始请求：`fetch`, `HttpBackend`, `HttpRequest`
- Token 字段：`X-XSRF-TOKEN`, `xsrfCookieName`, `xsrfHeaderName`

**定位步骤：**
1. 检查根模块是否导入 `HttpClientXsrfModule`.
2. 搜索所有使用 `HttpClient` 的服务，看是否使用自定义 `HttpBackend`.
3. 跳读（L2）确认是否在拦截器中主动移除了 XSRF 头。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **正确配置**：`HttpClientXsrfModule.withOptions({ cookieName, headerName })`.
- **拦截器**：在 `HttpInterceptor` 中统一附加 Token。
- **后端设置 Cookie**：响应中返回 `Set-Cookie: XSRF-TOKEN`.
- **禁用场景白名单**：是否有 `withCredentials=false` 或显式删除头部。

**定位技巧：**
- 确认 SSR/预渲染场景下 Token 注入是否正常。
- 检查多域/子域部署时 Cookie 域名是否匹配。
- 分析 `HttpClientModule` 是否在懒加载模块重复导入导致覆盖。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全局启用 HttpClientXsrfModule + 后端校验 | **L0（快速跳过）** | 风险低 |
| 部分服务绕过拦截器 | **L2（跳读）** | 需补齐 Token 注入 |
| 未启用 XSRF 模块且无手动 Token | **L3（逐行读）** | 高风险 |
| 多域部署导致 Cookie 不生效 | **L4（跨模块追踪）** | 需排查环境配置 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 使用 Angular `HttpClient` 调用敏感接口。
2. 未启用/正确配置 XSRF Token 注入，也无其它防护。
3. 服务端依赖 Cookie 认证且未进行 Token 验证。

#### 误报
以下情况可视为误报：
1. 接口仅在安全上下文调用（如带有 Bearer Token，无 Cookie）。
2. 服务端实施了双重提交 Cookie、Origin 校验等等效防护。
3. 请求通过 `withCredentials: false` 且后端不依赖 Cookie。

#### 代码异味
需记录的风险：
1. 某些请求手动删除了 `X-XSRF-TOKEN` 头。
2. 多语言版本或插件模块未复用统一 `HttpClient`.
3. Token 读取逻辑依赖 `document.cookie`，存在 XSS 风险。
4. 使用 `XsrfStrategy` 自定义实现但未覆盖所有请求。

## Low risk

### 低风险评级场景

#### 1. 后台管理配合 MFA
- **场景：** 管理接口需二次验证。
- **风险评估：** 攻击成本高，但仍应启用 Token。

#### 2. API 使用 SameSite=Strict Cookie
- **场景：** 后端 Cookie 配置 Strict。
- **风险评估：** 部分浏览器有效，但不全面。

#### 3. 接口仅供内部应用
- **场景：** 通过 mTLS/VPN 调用的内部 API。
- **风险评估：** 攻击面小，但仍建议 Token。

#### 4. 完整审计日志
- **场景：** 记录所有敏感 API 的来源与参数。
- **风险评估：** 有助于追踪滥用，仍需技术防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 二次验证 | 增强防护 | 中 |
| SameSite=Strict Cookie | 浏览器级缓解 | 低 |
| 内部调用/受控网络 | 攻击面有限 | 中 |
| 审计与告警 | 提升检测能力 | 高（仍需恢复 Token）|

