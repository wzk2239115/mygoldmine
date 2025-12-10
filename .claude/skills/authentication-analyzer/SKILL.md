---
name: authentication-analyzer
description: 专业认证分析技能：分析API端点认证要求，包括认证方式、认证参数、认证流程等。
---

## 概述与边界

- 聚焦API端点认证要求分析：分析API端点认证要求，包括认证方式、认证参数、认证流程等。

## 主流语言/框架认证要求分析方法

### 通用思路
- 路由入口：定位路由表/装饰器/注册函数（router、app、server）及默认路由目录，识别分组/前缀。
- 路径拼装：自顶向下收集 `prefix/group/namespace/include`，拼接完整路径模板，标注动态参数/通配符。
- 方法默认值：提取 HTTP 方法，未声明时记录框架默认（多为 GET）。
- 鉴权挂载点：收集中间件/filters/guards/interceptors/`RequireAuthorization`/角色声明，区分全局、分组、端点级。
- 认证方式与参数：辨识 `token/basic/oauth/apikey/cookie/session` 等及携带位置（header/query/body/cookie）。
- 输出清单：形成端点列表含 `method/path/file/line/auth_hint/group_prefix`，并标记高风险端点（debug/admin/config/internal）。
- 重点缺口：优先记录缺少鉴权或可绕过的公开端点，明确公开 vs 需授权。

### .NET（ASP.NET Core）
- Minimal APIs：`app.MapGet/MapPost/...`；全局 `MapGroup("/api")`。
- MVC/Controllers：`[Route("api/[controller]")]` + `[HttpGet("x")]`；`MapControllerRoute` 模板。
- 端点元数据：`RequireAuthorization` / filters 指示鉴权。

### JavaScript 前后端一体框架（Next.js / Nuxt）
- Next.js API Routes：`pages/api/*` 或 `app/api/*/route.{js,ts}`；文件路径即路由；动态 `[id]`，catch-all `[...slug]`。
- Nuxt 3 Nitro：`server/api/**/*.ts`；文件名到路由映射。

### 识别步骤（建议执行）
1) 定位路由入口：按语言规则搜索 `route|router|RequestMapping|Controller|MapGet|Route::|resources` 等；扫描框架默认路由文件夹。
2) 拼装路径：提取 `prefix/group/namespace/include`，自顶向下拼接完整路径，记录动态参数/通配符。
3) 确认方法：提取 HTTP 方法；未指定时记录框架默认（多为 GET）。
4) 关联鉴权：收集全局/分组/端点级的 auth/role/guard/interceptor/`RequireAuthorization`；标注认证要求与认证方式/参数。
5) 输出清单：列出 `method/path/file/line/auth_hint/group_prefix`，标记高风险端点（debug/admin/config/internal），突出缺少鉴权的路径。

## 认证机制安全风险分析

### 分析目标

评估项目认证机制的安全性，判断是否存在可被绕过的漏洞。分析结论将影响下游任务的执行策略（如是否分析高权限接口）。

### 常见安全风险类型

| 风险类型 | 描述 | 检测要点 |
|---------|------|---------|
| JWT 密钥泄露 | 硬编码密钥、弱密钥、密钥存储不当 | 搜索 `secret`、`key`、`jwt` 相关配置 |
| JWT 算法混淆 | 允许 `none` 算法或 RS256/HS256 混用 | 检查 JWT 验证配置 |
| 会话固定 | 登录后未重新生成 Session ID | 检查登录逻辑 |
| 认证逻辑缺陷 | 条件判断可绕过、短路逻辑 | 审查认证中间件实现 |
| 默认凭证 | 硬编码用户名密码、默认管理员账户 | 搜索 `admin`、`password`、`default` |
| Token 验证缺失 | 部分端点跳过认证检查 | 对比中间件覆盖范围 |
| 认证信息泄露 | 错误信息暴露用户存在性 | 检查登录/注册响应 |
| 弱密码策略 | 无密码复杂度要求、无锁定机制 | 检查密码验证逻辑 |
| OAuth 配置错误 | redirect_uri 校验不严、state 缺失 | 检查 OAuth 实现 |
| API Key 管理不当 | Key 硬编码、无过期机制、权限过大 | 检查 API Key 生成和验证 |

### 风险等级定义

- **可绕过**：存在明确的绕过路径，攻击者可直接获取未授权访问
- **存在风险**：存在潜在安全隐患，需特定条件才能利用
- **安全**：认证机制实现合理，未发现明显漏洞

### 分析输出要求

在产物文件中必须包含以下内容：

```markdown
## 认证机制安全评估

### 评估结论
- **认证可绕过**：是/否
- **风险等级**：可绕过 / 存在风险 / 安全
- **结论依据**：[具体说明]

### 发现的安全风险
| 风险类型 | 风险等级 | 位置 | 描述 |
|---------|---------|------|------|
| xxx | 高/中/低 | file:line | 详细描述 |

### 认证机制概述
- **主要认证方式**：[JWT/Session/OAuth/API Key/...]
- **认证覆盖范围**：[全局/部分端点]
- **高权限接口保护**：[描述 admin 等接口的保护方式]
```

# 输出要求

## 产物输出

分析结果保存到 `.workspace/tasks/{TASK_ID}/authentication-analyzer.md` 文件中即可。

## 重要约束

- **禁止推荐下游任务**：该技能仅输出认证分析产物，不生成任何 `tasks` 列表
- 输出格式为 `{"tasks": []}`，表示无后续任务
