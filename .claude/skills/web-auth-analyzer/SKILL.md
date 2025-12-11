---
name: web-auth-analyzer
description: 专业认证分析技能：分析API端点认证要求、认证机制安全性、用户角色体系，并触发下游路由扫描任务。
---

## 概述与边界

### 核心职责

- **聚焦**：识别认证机制、分析认证安全性、识别无认证访问条件、分析用户角色体系
- **输出**：认证分析报告 + 下游任务列表 + 修复建议 + PoC 说明（如发现绕过）
- **分析范围**：
  - ✅ 认证机制类型识别（JWT/Session/OAuth/API Key等）
  - ✅ 认证绕过漏洞检测（环境变量、条件判断、配置缺陷）
  - ✅ 会话管理安全（Session 固定、Cookie 属性、超时设置）
  - ✅ Token 生命周期安全（过期时间、撤销机制、存储方式）
  - ✅ 用户角色体系识别（RBAC/ABAC/ACL 模型）
  - ✅ 权限提升路径检测（角色变更接口、默认权限）
  - ✅ 无认证访问条件分析（白名单、IP 限制、环境变量）

### 明确不做

- ❌ **漏洞利用执行**：仅输出 PoC 说明，不实际执行攻击
- ❌ **授权逻辑深度分析**：具体的权限检查逻辑由 `idor-analyzer` 处理
- ❌ **业务逻辑漏洞**：业务流程中的逻辑缺陷不在范围内
- ❌ **密码学算法审计**：不深入分析加密算法的安全性
- ❌ **配置文件全面审计**：仅关注认证相关配置，其他配置由 `sensitive-info-scanner` 处理

### 与其他技能的协作

#### 前置技能
- **`vtr-scanner`**（路由扫描）：提供路由表信息，帮助识别需要保护的端点
- **`project-profiler`**（项目画像）：提供技术栈信息，指导框架特定的认证机制识别

#### 后置技能（下游任务）
- **`unauth-route-scanner`**：提取无需认证的路由，进行进一步安全分析
- **`normal-route-scanner`**：提取普通用户可访问的路由，检测 IDOR 等授权问题

#### 平行技能（配合使用）
- **`sensitive-info-scanner`**：检测配置文件中的密钥泄露（JWT secret 等）

### 执行时机

- 在项目画像（`project-profiler`）和路由扫描（`vtr-scanner`）完成后执行
- 优先级：高（认证是安全分析的基础）

## 分析维度

### 1. 认证机制分析

#### 主流语言/框架认证识别方法

**通用思路**：
- 路由入口：定位路由表/装饰器/注册函数（router、app、server）及默认路由目录，识别分组/前缀
- 鉴权挂载点：收集中间件/filters/guards/interceptors/`RequireAuthorization`/角色声明，区分全局、分组、端点级
- 认证方式与参数：辨识 `token/basic/oauth/apikey/cookie/session` 等及携带位置（header/query/body/cookie）
- 重点缺口：优先记录缺少鉴权或可绕过的公开端点，明确公开 vs 需授权

**主流框架认证模式速查**：

**Node.js/Express**
```bash
# Passport.js
rg "passport\.(use|authenticate|serializeUser)" -g'*.{js,ts}'
# express-jwt / jsonwebtoken
rg "(expressJwt|expressjwt|jwt\.verify|jwt\.sign)" -g'*.{js,ts}'
# 中间件挂载
rg "app\.use\(.*[Aa]uth|router\.use\(.*[Aa]uth" -g'*.{js,ts}'
```

**NestJS**
```bash
# Guards
rg "@UseGuards\(|class.*Guard.*implements.*CanActivate" -g'*.ts'
# 认证装饰器
rg "@(Public|Roles|RequireAuth|Authenticated)" -g'*.ts'
```

**Spring Boot (Java)**
```bash
# Spring Security 注解
rg "@(PreAuthorize|Secured|RolesAllowed|EnableWebSecurity)" -g'*.java'
# 配置类
rg "(SecurityFilterChain|WebSecurityConfigurerAdapter|authorizeRequests)" -g'*.java'
# JWT Filter
rg "OncePerRequestFilter|doFilterInternal" -g'*.java'
```

**Django (Python)**
```bash
# Django 认证装饰器
rg "@(login_required|permission_required|user_passes_test)" -g'*.py'
# DRF 权限类
rg "(IsAuthenticated|IsAdminUser|permission_classes|authentication_classes)" -g'*.py'
# 中间件配置
rg "AUTHENTICATION_BACKENDS|MIDDLEWARE.*Auth" -g'settings*.py'
```

**Flask (Python)**
```bash
# Flask-Login
rg "@login_required|LoginManager|current_user" -g'*.py'
# Flask-JWT
rg "jwt_required|create_access_token|JWTManager" -g'*.py'
```

**Go (Gin/Echo/Chi)**
```bash
# 中间件
rg "\.Use\(.*[Aa]uth|JWT\(|BasicAuth|AuthRequired" -g'*.go'
# JWT 库
rg "jwt-go|jwt\.Parse|jwt\.Sign" -g'*.go'
```

**Laravel (PHP)**
```bash
# 中间件
rg "->middleware\(.*auth|'auth'|Authenticate::class" -g'*.php'
# 路由保护
rg "Route::(middleware|group).*auth" -g'*.php'
```

**FastAPI (Python)**
```bash
# 依赖注入认证
rg "Depends\(.*auth|oauth2_scheme|HTTPBearer" -g'*.py'
# 安全依赖
rg "Security\(|get_current_user|verify_token" -g'*.py'
```

#### 认证机制安全风险

| 风险类型 | 描述 | 检测要点 |
|---------|------|---------|
| JWT 密钥泄露 | 硬编码密钥、弱密钥、密钥存储不当 | 搜索 `secret`、`key`、`jwt` 相关配置 |
| JWT 算法混淆 | 允许 `none` 算法或 RS256/HS256 混用 | 检查 JWT 验证配置 |
| 会话固定 | 登录后未重新生成 Session ID | 检查登录逻辑 |
| 认证逻辑缺陷 | 条件判断可绕过、短路逻辑 | 审查认证中间件实现 |
| 默认凭证 | 硬编码用户名密码、默认管理员账户 | 搜索 `admin`、`password`、`default` |
| Token 验证缺失 | 部分端点跳过认证检查 | 对比中间件覆盖范围 |

#### 现代认证协议识别

| 协议类型 | 识别特征 | 检测要点 |
|---------|---------|---------|
| OAuth 2.0 | `/oauth/token`、`grant_type`、`access_token` | 检查 redirect_uri 验证、state 参数、PKCE 支持 |
| OIDC | `id_token`、`.well-known/openid-configuration` | 检查 nonce、JWT 签名验证、issuer 验证 |
| SAML | `SAMLRequest`、`SAMLResponse`、XML 签名 | 检查签名验证、assertion 加密、时间戳验证 |
| API Gateway | Kong/APISIX/Envoy/Nginx 配置文件 | 检查认证插件配置、upstream 认证传递 |

#### Token 生命周期安全分析

| 检查项 | 风险点 | 检测方法 |
|-------|-------|---------|
| Token 过期时间 | 过期时间过长（>24h） | 搜索 `expiresIn`、`exp`、`TTL` 配置 |
| Refresh Token | 未设置过期、永久有效 | 搜索 `refreshToken`、`refresh_expires` |
| Token 撤销机制 | logout 未撤销 token、缺少黑名单 | 检查 logout 接口实现、Redis/DB 黑名单 |
| Token 存储 | 明文存储、localStorage（XSS 风险） | 搜索 `localStorage.setItem`、`sessionStorage` |

#### 会话管理安全检查

| 检查项 | 安全要求 | 检测要点 | 风险等级 |
|-------|---------|---------|---------|
| Session ID 生成 | 使用密码学安全随机数生成器 | 搜索 `Math.random()`（不安全）vs `crypto.randomBytes()` | 高 |
| Session 固定防护 | 登录后重新生成 Session ID | 检查登录处理函数，搜索 `regenerate()`、`session.renew()` | 高 |
| Cookie 安全属性 | 必须设置 `HttpOnly`、`Secure`、`SameSite` | 搜索 cookie 设置代码，检查属性配置 | 中-高 |
| Session 超时 | 设置空闲超时（15-30分钟）和绝对超时（24小时） | 搜索 `maxAge`、`expires`、`cookie.maxAge` | 中 |
| 并发会话控制 | 限制同一用户的并发会话数 | 搜索 session 存储逻辑、多设备登录检测 | 低-中 |
| Session 存储安全 | 使用 Redis/Memcached，避免客户端存储 | 检查 session store 配置 | 中 |

#### 会话管理检测搜索命令

```bash
# Session 配置
rg "session.*config|express-session|cookie-session" -g'*.{js,ts}'
rg "SESSION_|COOKIE_" -g'*.{env,yaml,json}'

# Cookie 属性
rg "(httpOnly|secure|sameSite).*:|setHeader.*Set-Cookie" -g'*.{js,ts,py,java,go,php}'

# Session 固定检测
rg "(regenerate|renew|rotate).*session|session\.save" -g'*.{js,ts,py,java,go,php}'

# Session ID 生成
rg "Math\.random|uuid\(\)|randomBytes|SecureRandom" -g'*.{js,ts,py,java,go,php}'
```

#### 风险等级定义与量化标准

| 风险等级 | 认证可绕过 | 影响范围 | 利用难度 | 典型示例 |
|---------|-----------|---------|---------|---------|
| 严重 (Critical) | 是 | 全部端点或管理员端点 | 低 | 环境变量全局禁用认证、JWT none 算法、硬编码万能密钥 |
| 高 (High) | 是 | 部分敏感端点 | 低-中 | IP 白名单可伪造、条件判断逻辑缺陷、会话固定、默认管理员账户 |
| 中 (Medium) | 否 | 有限范围 | 中-高 | 弱 JWT 密钥、Token 过期时间过长、Refresh Token 永久有效 |
| 低 (Low) | 否 | 信息泄露 | 高 | Session ID 可预测、认证失败信息泄露、CORS 配置不当 |
| 信息 (Info) | 否 | 仅信息泄露 | - | 公开的 Swagger 文档、健康检查端点、GraphQL Introspection |

#### 风险评分计算（可选）

综合评分 = 认证绕过权重(0.4) × 绕过难度(0-10) + 影响范围权重(0.3) × 范围评分(0-10) + 敏感度权重(0.3) × 敏感度评分(0-10)

- **绕过难度**：0(无绕过) → 10(直接绕过)
- **影响范围**：0(单一端点) → 10(全部端点)
- **敏感度**：0(公开信息) → 10(管理员操作)

评分 ≥ 8.0 = 严重，6.0-7.9 = 高，4.0-5.9 = 中，2.0-3.9 = 低，< 2.0 = 信息

### 2. 无认证/匿名访问分析

**分析目标**：判断系统是否允许无认证或匿名方式访问，以及访问的条件和范围。

#### 无认证访问识别

| 访问类型 | 识别特征 | 风险等级 |
|---------|---------|---------|
| 完全公开 | 无任何认证中间件、无 token 检查 | 视端点敏感度 |
| 白名单豁免 | `exclude`、`whitelist`、`public`、`skip` 配置 | 中 |
| 条件豁免 | 特定 IP、内网、特定 header 可跳过认证 | 高 |
| 匿名角色 | `anonymous`、`guest` 角色允许访问部分接口 | 低 |
| 开发/调试模式 | `DEBUG`、`DEV_MODE` 环境变量控制认证开关 | 高 |

#### 无认证访问条件类型

| 条件类型 | 典型实现 | 示例 |
|---------|---------|------|
| 路径白名单 | 配置文件或代码中定义的公开路径列表 | `publicPaths: ['/health', '/login']` |
| IP 白名单 | 特定 IP 或 CIDR 段无需认证 | `if (isInternalIP(req.ip)) skip auth` |
| 请求头条件 | 特定 header 存在时跳过认证 | `X-Internal-Request: true` |
| 环境变量 | 开发环境禁用认证 | `if (process.env.DISABLE_AUTH)` |
| 特定端口 | 内部端口不做认证 | 管理端口 vs 公开端口 |
| 时间窗口 | 特定时间段开放访问 | 维护窗口期 |

#### 分析步骤

1. **搜索认证豁免配置**：
```bash
# 搜索白名单/豁免配置
rg -i "(whitelist|exclude|skip|public|anonymous|noauth)" -g'*.{js,ts,py,java,go,php,yaml,json}'

# 搜索条件认证
rg -i "(disable.*auth|skip.*auth|no.*auth|bypass)" -g'*.{js,ts,py,java,go,php}'

# 搜索环境变量控制
rg "(DEBUG|DEV_MODE|DISABLE_AUTH|NO_AUTH)" -g'*.{js,ts,py,java,go,php,env}'
```

2. **分析中间件豁免逻辑**：
- 检查认证中间件的 `next()` 条件
- 识别 `return` 或 `skip` 的触发条件
- 分析路径匹配规则

3. **识别匿名访问端点**：
- 明确标记为公开的端点
- 未被认证中间件覆盖的端点
- 条件豁免的端点及其条件

#### 特殊场景豁免分析

| 场景类型 | 检测方法 | 风险评估 |
|---------|---------|---------|
| OPTIONS 请求 | 检查 CORS preflight 处理，搜索 `method === 'OPTIONS'` | 低（需关注敏感操作的 CORS 配置） |
| WebSocket 连接 | 检查握手阶段认证，搜索 `ws://`、`Socket.io`、`upgrade` | 高（易被忽略） |
| GraphQL Introspection | 检查 `introspection: true`、`__schema` 查询 | 中（API 结构泄露） |
| Swagger/OpenAPI UI | 搜索 `/api-docs`、`/swagger-ui`、`/redoc` | 中（API 文档泄露） |
| 健康检查端点 | 搜索 `/health`、`/metrics`、`/actuator`、`/status` | 中（信息泄露，可能含敏感配置） |
| 静态资源 | 检查 `/static`、`/public`、`/assets` 路由配置 | 低-中（需检查是否暴露敏感文件） |

#### 认证豁免优先级分析

当多个豁免规则同时存在时，分析其优先级逻辑：

1. **优先级顺序**（从高到低）：
   - 环境变量全局禁用 > 代码硬编码豁免 > 配置文件白名单 > IP 白名单 > 请求头条件

2. **冲突检测**：
   - 记录同一端点匹配多个豁免规则的情况
   - 识别优先级冲突（如 IP 白名单与路径黑名单）
   - 标注可能导致安全策略失效的配置组合

3. **绕过风险评估**：
   - **高风险**：环境变量控制 + 生产环境可访问配置文件
   - **中风险**：IP 白名单 + 可伪造来源 IP 的场景
   - **低风险**：明确路径白名单 + 严格的路径匹配规则

### 3. 用户角色体系分析

**分析目标**：判断系统是否包含多角色用户体系，识别不同角色的权限边界。

#### 多角色体系识别特征

| 特征类型 | 识别模式 | 示例 |
|---------|---------|------|
| 角色枚举 | `enum Role`、`ROLE_*`、`UserRole` | `enum Role { ADMIN, USER, GUEST }` |
| 角色字段 | `role`、`roles`、`user_type`、`is_admin` | `user.role`, `user.is_staff` |
| 权限装饰器 | `@Roles`、`@RequireRole`、`@hasRole` | `@Roles('admin', 'user')` |
| 权限中间件 | `RoleGuard`、`PermissionGuard` | `UseGuards(RolesGuard)` |
| 权限配置 | `authorize`、`permissions`、`access_control` | `authorize: ['admin']` |

#### 常见角色类型

| 角色类型 | 典型命名 | 权限级别 |
|---------|---------|---------|
| 超级管理员 | `superadmin`, `root`, `super` | 最高权限 |
| 管理员 | `admin`, `administrator`, `staff` | 管理权限 |
| 普通用户 | `user`, `member`, `customer` | 普通权限 |
| 访客 | `guest`, `anonymous`, `visitor` | 最低/无权限 |

#### 角色体系分析步骤

1. **搜索角色定义**：
```bash
# 搜索角色枚举/常量
rg -i "role|permission|authority" -g'*.{js,ts,py,java,go,php}'
rg "enum.*Role|ROLE_|UserType|is_admin|is_staff"
```

2. **分析权限控制实现**：
- 全局权限中间件
- 路由级权限装饰器
- 控制器级权限注解

3. **识别角色边界**：
- 管理员专属路由（`/admin/*`、`/management/*`）
- 普通用户路由（需登录但非管理员）
- 公开路由（无需登录）

### 4. 权限模型分析

**分析目标**：识别系统使用的权限控制模型类型及其实现方式。

#### 权限模型类型识别

| 模型类型 | 识别特征 | 实现模式 |
|---------|---------|---------|
| RBAC（基于角色） | `Role`、`Permission`、`roles` 字段、角色-权限映射表 | 用户 → 角色 → 权限 |
| ABAC（基于属性） | 策略引擎、属性判断、上下文条件 | `policy`、`attributes`、`context`、动态规则 |
| ACL（访问控制列表） | 访问控制列表、资源所有权 | `acl`、`access_list`、`allowed_users`、`owner_id` |
| 策略引擎 | Casbin、OPA、Cedar、Policy DSL | 配置文件、策略文件、规则引擎 |

#### 权限模型识别搜索命令

```bash
# RBAC 模式
rg "Role.*Permission|roles.*permissions|role_permissions" -g'*.{js,ts,py,java,go,php}'

# ABAC 模式
rg "policy|attributes|context.*auth|can\(|ability" -g'*.{js,ts,py,java,go,php}'

# ACL 模式
rg "acl|access.*list|owner_id|can.*access" -g'*.{js,ts,py,java,go,php}'

# 策略引擎
rg "casbin|opa|cedar|enforce|policy.*engine" -g'*.{js,ts,py,java,go,php,yaml,json}'
```

#### 权限提升路径识别

**高风险点**：检查以下可能导致权限提升的代码模式

| 检查项 | 风险描述 | 检测方法 |
|-------|---------|---------|
| 角色变更接口 | 用户可修改自己或他人角色 | 搜索 `updateRole`、`setRole`、`changeRole`、`setAdmin` |
| 权限直接赋予 | 绕过角色直接授予权限 | 搜索 `grantPermission`、`addPermission`、`permissions.push` |
| 角色继承缺陷 | 继承关系配置错误 | 检查角色继承配置，搜索 `extends`、`inherits`、`parent_role` |
| 默认权限过高 | 新用户默认管理员或高权限 | 检查用户创建逻辑，搜索 `default.*role|role.*default` |
| 权限检查遗漏 | 关键操作未检查权限 | 对比路由定义与权限中间件覆盖范围 |

#### 权限提升检测搜索命令

```bash
# 角色修改接口
rg "(update|set|change|modify).*(role|permission|admin)" -g'*.{js,ts,py,java,go,php}'

# 权限赋予
rg "(grant|add|assign|give).*(permission|role)" -g'*.{js,ts,py,java,go,php}'

# 默认角色配置
rg "default.*(role|permission)|role.*=.*(admin|root)" -g'*.{js,ts,py,java,go,php,yaml,json}'
```

## 输出要求

### 产物文件

输出路径：`.workspace/tasks/{TASK_ID}/web-auth-analyzer.md`

```markdown
# Web 认证分析报告

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

---

## 无认证/匿名访问分析

### 允许无认证访问
- **是否允许**：是/否
- **访问类型**：[完全公开 / 白名单豁免 / 条件豁免 / 匿名角色 / 开发模式]

### 无认证访问条件
| 条件类型 | 条件详情 | 影响范围 | 代码位置 |
|---------|---------|---------|---------|
| 路径白名单 | `/health`, `/login`, `/register` | 3 个端点 | src/middleware/auth.js:25 |
| IP 白名单 | `10.0.0.0/8`, `192.168.0.0/16` | 内网全部端点 | config/security.yaml:12 |
| 环境变量 | `DISABLE_AUTH=true` 时跳过认证 | 全部端点 | src/middleware/auth.js:8 |

### 无认证访问端点清单
| # | 路径 | 方法 | 访问条件 | 敏感度 |
|---|------|------|---------|--------|
| 1 | /health | GET | 无条件公开 | 低 |
| 2 | /api/login | POST | 无条件公开 | 低 |
| 3 | /internal/metrics | GET | IP 白名单 (内网) | 中 |
| 4 | /debug/pprof | GET | 环境变量 ENABLE_DEBUG | 高 |

### 风险评估
- **条件豁免风险**：[描述条件豁免可能被利用的场景]
- **开发模式风险**：[描述开发模式配置泄露到生产的风险]

---

## 用户角色体系分析

### 角色体系判定
- **多角色体系**：是/否
- **判定依据**：[具体说明]

### 识别的角色类型
| 角色名称 | 角色标识 | 权限级别 | 定义位置 |
|---------|---------|---------|---------|
| 管理员 | admin | 管理权限 | src/models/user.js:15 |
| 普通用户 | user | 普通权限 | src/models/user.js:16 |

### 角色权限边界
- **管理员专属路由前缀**：[/admin, /management, ...]
- **权限控制实现方式**：[中间件/装饰器/配置]
- **权限控制代码位置**：[file:line]

### 路由分类概览
| 分类 | 数量 | 示例路径 |
|------|------|---------|
| 无需认证 | N | /login, /register, /health |
| 普通用户 | N | /api/profile, /api/orders |
| 管理员专属 | N | /admin/users, /admin/config |

---

## 权限模型分析（如适用）

### 权限模型类型
- **识别的模型**：[RBAC / ABAC / ACL / 策略引擎 / 无明确模型]
- **实现方式**：[描述权限检查的实现位置和方式]
- **模型定义位置**：[file:line]

### 权限提升风险
| 风险项 | 风险等级 | 位置 | 描述 |
|-------|---------|------|------|
| 示例：角色变更接口未鉴权 | 严重 | src/api/user.js:45 | `/api/user/updateRole` 端点可被普通用户调用修改自己角色 |

---

## 认证绕过验证（如发现绕过）

### PoC 说明
- **绕过方法**：[详细描述绕过步骤]
- **验证命令**：
  ```bash
  # 示例：通过环境变量绕过认证访问管理员接口
  curl -X GET http://localhost:3000/admin/users \
    -H "X-Internal-Request: true"
  ```
- **预期结果**：[200 OK，返回用户列表等]
- **实际影响**：[可访问所有管理员接口、可修改用户数据等]

---

## 修复建议

### 高优先级修复

#### 1. [漏洞标题]（严重/高）
- **位置**：`src/config/jwt.js:12`
- **问题描述**：JWT 密钥硬编码为弱密钥 `secret: 'hardcoded-secret-key'`
- **安全影响**：攻击者可伪造任意用户 token，获取管理员权限
- **修复建议**：
  ```javascript
  // 使用环境变量 + 强随机密钥（至少 256 位）
  const secret = process.env.JWT_SECRET || crypto.randomBytes(32).toString('hex');
  if (!process.env.JWT_SECRET) {
    logger.warn('JWT_SECRET not set, using random key (will invalidate tokens on restart)');
  }
  ```
- **参考资料**：[OWASP JWT Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)

#### 2. [下一个高优先级问题]
...

### 中优先级修复
[按同样格式列出]

### 低优先级修复
[按同样格式列出]

---

## 认证流程图（可选）

\`\`\`mermaid
graph TB
  A[HTTP 请求] --> B{全局认证中间件}
  B -->|存在 Authorization| C[验证 JWT Token]
  B -->|无 Token| D{路径白名单?}
  C -->|Token 有效| E[提取用户信息]
  C -->|Token 无效/过期| F[401 Unauthorized]
  D -->|在白名单| G[放行]
  D -->|不在白名单| F
  E --> H{角色权限检查}
  H -->|权限足够| I[执行业务逻辑]
  H -->|权限不足| J[403 Forbidden]
\`\`\`

**流程说明**：[简要描述认证流程的关键步骤和决策点]

---

## 会话管理分析（如使用 Session）

### Session 配置
| 配置项 | 当前值 | 安全评估 |
|-------|-------|---------|
| Session Store | Redis | ✅ 安全 |
| Cookie HttpOnly | true | ✅ 安全 |
| Cookie Secure | false | ❌ 未启用 HTTPS |
| Cookie SameSite | Lax | ⚠️ 建议使用 Strict |
| Session 超时 | 24小时 | ⚠️ 建议缩短至 2-4 小时 |
| 登录后重新生成 | 否 | ❌ 存在 Session 固定风险 |

### Session 安全风险
[描述发现的 session 管理问题]
```

### 下游任务生成

根据分析结果生成下游任务：

#### 情况 1：存在多角色体系

触发两个下游任务：
- `unauth-route-scanner`：提取无需认证的路由
- `normal-route-scanner`：提取普通用户（非管理员）可访问的路由

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "unauth-route-scanner"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "normal-route-scanner"
    }
  ]
}
```

#### 情况 2：无多角色体系（单一用户类型或无用户系统）

仅触发一个下游任务：
- `unauth-route-scanner`：提取无需认证的路由

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "unauth-route-scanner"
    }
  ]
}
```

#### 情况 3：认证机制可绕过

当认证机制存在绕过漏洞时，调整下游任务策略：

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "unauth-route-scanner",
      "context": {
        "auth_bypass": true,
        "bypass_method": "[具体绕过方法，如：环境变量 DISABLE_AUTH=true]"
      }
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/web-auth-analyzer.md",
      "skill": "normal-route-scanner",
      "context": {
        "treat_as_unauthenticated": true,
        "reason": "认证可全局绕过，所有路由均可访问"
      }
    }
  ]
}
```

**说明**：
- 认证可绕过时，仍然生成两个下游任务
- 在产物中标注 `认证可绕过: 是`，下游技能会据此调整分析范围
- `normal-route-scanner` 会将所有路由（包括管理员路由）作为普通用户可访问路由分析
- 通过 context 传递绕过信息，帮助下游技能理解风险背景

### 重要约束

- **必须输出用户角色体系分析**：即使判定为无多角色体系，也需要在产物中说明判定依据
- **下游任务必须生成**：根据分析结果生成对应的 tasks 列表
- **风险评估必须明确**：认证机制的风险等级必须给出明确结论
