# Next.js CSP 配置审计指南

## Details

### 代码示例

Next.js 项目中常见的 CSP 配置位置：

**next.config.js / next.config.ts:**
```typescript
// 不安全示例
const nextConfig = {
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'"
          }
        ]
      }
    ]
  }
}
```

**middleware.ts (App Router):**
```typescript
// 弱策略配置
export function middleware(request: NextRequest) {
  const response = NextResponse.next()
  response.headers.set('Content-Security-Policy', "default-src *; script-src 'unsafe-inline'")
  return response
}
```

**API Route (pages/api/):**
```typescript
// 未配置 CSP 的路由
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  res.json({ data: 'unprotected' })
}
```

### 核心操作快速定位技巧

**审计等级：L1（关键词扫描）**

在代码中搜索以下关键词标识配置位置：
- `Content-Security-Policy` 响应头名称
- `next.config.js/ts` 中的 `headers()` 函数
- `middleware.ts` 中的响应对象
- `unsafe-inline` 和 `unsafe-eval` 危险指令
- `*` 或 `data:` 等通配符指令
- `_app.tsx/_document.tsx` 中的 `<meta>` 标签（非标准但常见的配置方式）

关键搜索模式：
```
- grep -r "unsafe-inline\|unsafe-eval\|\*.*script" next.config.*
- grep -r "'unsafe-" pages/api/ app/api/
- grep -rn "Content-Security-Policy" middleware.ts
```

### 保护机制快速定位技巧

**审计等级：L2（跳读）**

识别正确的防护配置特征：

1. **指令完整性检查**（L2）：
   - 确认是否定义了 `default-src` 基础策略
   - 检查 `script-src`/`style-src` 是否使用 `'nonce-'` 或 `'hash-'`
   - 验证是否使用了 `strict-dynamic` 加强 nonce 效力

2. **配置位置检查**（L2）：
   ```typescript
   // next.config.ts 中完整的头配置
   {
     key: 'Content-Security-Policy',
     value: "default-src 'self'; script-src 'self' 'nonce-${nonce}'; style-src 'self' 'nonce-${nonce}'"
   }
   ```
   - 验证 nonce 值是否在运行时动态生成
   - 确认 nonce 是否正确传递给页面组件

3. **跨模块依赖检查**（L3）：
   - 在 `next.config.ts` 中查找 nonce 生成逻辑
   - 检查 `lib/csp.ts` 或类似工具函数中的实现
   - 验证 nonce 在所有动态脚本标签中的应用

4. **特殊框架特性检查**（L2）：
   - 检查是否使用 Next.js 内置脚本（`next/script`）
   - 验证 `_document.tsx` 是否正确处理了 nonce 传递
   - 确认是否存在内联脚本或样式

---

## Classify

### 漏洞特征

将 CSP 配置问题分类为**真实漏洞**的判断标准：

1. **不安全指令的存在**
   - 响应头中包含 `unsafe-inline` 或 `unsafe-eval`
   - 使用 `*` 作为源的通配符策略
   - 缺失 `default-src` 导致的隐式宽松策略

   **理论依据**：这些指令直接削弱 XSS 防护效能，使攻击者能够注入执行任意脚本。

2. **缺失关键指令**
   - 仅配置了 `default-src` 而未明确定义 `script-src`/`style-src`/`img-src`
   - 未设置 `frame-ancestors` 导致 clickjacking 风险
   - 缺少 `report-uri` 或 `report-to` 的监控机制

   **理论依据**：隐式继承可能导致与实际需求的偏离，留下防护盲点。

3. **动态 nonce 配置失效**
   - nonce 值硬编码或在页面加载后仍不变
   - nonce 未在所有内联脚本上应用
   - nonce 生成逻辑存在可预测性

   **理论依据**：nonce 的本质价值在于一次性随机性，如果可预测或未全覆盖，则失去防护意义。

### 误报场景

将配置问题分类为**误报**的条件：

1. **API 路由无 CSP 头** - 若路由仅返回 JSON 数据，无 HTML 内容，CSP 无必要
2. **测试/开发环境特意宽松** - 明确注释说明仅用于开发环境，生产环境独立配置
3. **第三方脚本授权** - 由于业务需求被迫信任的第三方（如 GA、Stripe），应在白名单中明确记录原因

### 代码异味信号

识别为**代码异味**（需关注但非直接漏洞）：

1. **过度严格的策略** - 策略过于严格导致正常功能受阻，易被绕过或禁用
2. **未启用报告模式** - 未使用 `Content-Security-Policy-Report-Only` 进行灰度验证
3. **缺少版本控制** - nonce 生成库未明确版本依赖，更新时可能引入不兼容

---

## Low risk

以下情况应评级为**低风险**：

1. **使用 nonce 的内联脚本**
   ```typescript
   // 内联脚本每次加载时使用不同的 nonce，指令为：script-src 'nonce-xxx'
   <script nonce={generatedNonce}>console.log('safe')</script>
   ```
   理由：nonce 机制充分对抗 XSS，符合现代 CSP 最佳实践。

2. **严格的域名白名单 + 无 unsafe 指令**
   ```typescript
   "script-src 'self' https://trusted-cdn.example.com; default-src 'self';"
   ```
   理由：明确的源白名单限制了攻击面，虽需验证白名单合理性，但整体风险受控。

3. **使用 hash 的内联样式/脚本**
   ```typescript
   "style-src 'sha256-<base64-hash>'; script-src 'sha256-<base64-hash>';"
   ```
   理由：内容哈希检验能防止未授权的脚本修改，与 nonce 同等安全。

4. **中间件层统一配置 + 特定路由豁免**
   ```typescript
   // middleware.ts 全局配置
   // 在 next.config.ts 为静态资源路由返回更宽松的头
   ```
   理由：分层策略是合理的，关键是每层的指令需明确审查。

5. **仅在 `report-uri` 中出现的可疑指令**
   - 例如：`default-src 'self'; report-uri https://report.example.com`
   - 不应因为报告端点而降低主策略的等级

---

## 审计检查清单

### 必检项

- [ ] 所有 HTML 返回路由是否配置了 CSP 头
- [ ] 是否存在 `unsafe-inline` 或 `unsafe-eval` 指令
- [ ] 是否使用了 `*` 通配符指令
- [ ] 如果使用内联脚本，是否通过 nonce 或 hash 授权
- [ ] `default-src` 策略是否被明确定义
- [ ] nonce 的生成和传递机制是否正确

### 风险指标

- 🔴 **高危**：`script-src 'unsafe-inline'` 或缺失 CSP
- 🟡 **中危**：`script-src 'self' 'unsafe-inline' https://*`（混合不安全指令）
- 🟢 **低危**：`script-src 'self' 'nonce-xxx'`（无 unsafe 指令）

