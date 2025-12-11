---
name: route-deep-analyzer
description: |
    专业路由深度分析技能：分析API端点功能，包括请求参数、响应数据、权限要求等。
    依赖上游任务 project-profiler（项目画像）和 web-auth-analyzer（认证分析）的分析结果，需要给定这些任务产物路径作为输入。
---

# 概述与边界

## 核心职责

- **聚焦**：深度分析API端点功能，包括请求参数、响应数据、权限要求、业务逻辑、外部依赖等
- **输出**：端点分析文件 + 下游任务列表（code-security-analyzer）

## 输入约束

### 路由来源限制

**严格约束**：本技能仅分析输入文件中明确列出的路由，禁止自行发现或扩展路由范围。

#### 允许的输入来源

1. **上游扫描器产物**：
   - `unauth-route-scanner` 生成的无认证路由清单
   - `normal-route-scanner` 生成的普通用户路由清单
   - `vtr-scanner` 生成的完整路由表

2. **拆分任务产物**：
   - 由本技能拆分生成的 `routes-group-{N}.md` 文件

3. **手动指定清单**：
   - 用户或编排系统提供的路由清单文件

#### 输入文件格式要求

输入文件必须包含以下路由信息：
- 路由路径（必需）
- HTTP 方法（必需）
- 源文件路径（可选，但强烈建议）
- 行号（可选）

#### 禁止行为

❌ **禁止自行扫描项目发现新路由**
❌ **禁止扩展到输入文件未列出的路由**
❌ **禁止分析输入范围外的端点**
❌ **禁止推测或补全缺失的路由**

#### 执行流程

1. **读取输入文件**：解析输入文件中的路由清单
2. **验证路由范围**：确认所有待分析路由都在输入文件中
3. **应用过滤规则**：根据认证机制分析结果过滤高权限路由（如适用）
4. **执行深度分析**：仅分析通过验证和过滤的路由
5. **输出结果**：生成端点分析文件和下游任务

# 代码位置定位方法

**重要说明**：本章节描述的是如何定位输入文件中已知路由的代码实现位置，而非发现新路由的方法。

**适用场景**：当输入文件仅提供路由路径和 HTTP 方法，但缺少源文件路径或行号时，需要通过以下方法定位该路由的代码实现位置。

**核心原则**：仅定位输入文件中列出的路由，禁止在定位过程中发现并分析其他路由。

### 通用思路（从已知路由定位代码）
- 锁定入口：根据输入文件中的路由路径和方法，在项目中查找对应的路由声明/控制器/文件，确认其所在分组、前缀与注册方式（router/app/server/subrouter）。
- 路径拼装：向上溯源 `group/prefix/subrouter/namespace/Area/MapControllerRoute`，拼出完整路径模板，记录动态参数/通配符。
- 方法与参数：明确 HTTP 方法；枚举路径参数、查询参数、Body/表单/文件上传、Header 依赖（如版本、租户）。
- 中间件上下文：列出命中链路的 auth/role/guard/interceptor/validator/rate-limit/logging 等，记录触发顺序与作用点。
- 处理逻辑：阅读 handler（或控制器方法），归纳功能类别（查询/创建/更新/删除/导出/登录/文件/调度/后台任务/管理操作等）。
- 外部交互：标注 DB/缓存/消息队列/第三方服务/内部 RPC 调用及关键参数；注意软删除/幂等/事务。


### 定位步骤

**前提条件**：待定位的路由必须在输入文件中明确列出，禁止定位和分析输入范围外的路由。

1) **验证路由范围**：确认待定位路由在输入文件的路由清单中，如不在清单中则跳过。
2) **入口定位**：根据输入文件中的路由路径和方法，在项目中查找对应的路由声明（或控制器方法），确认其所在文件、分组、注册点。
3) **路径复原**：自入口向上收集 `prefix/group/namespace/include/Area`，拼接完整路径，标注动态参数/正则/通配符。
4) **方法与输入**：确认 HTTP 方法；列出路径/查询/Body/表单/文件/Headers 需求及默认值。
5) **中间件链路**：梳理全局/分组/端点级中间件与 filters/guards/interceptors/validators/rate-limit/logging，记录顺序与影响（含认证授权提示）。
6) **功能归类**：阅读 handler 逻辑，识别 CRUD/导入导出/登录注册/文件处理/任务调度/管理操作等，注明关键分支与副作用。
7) **外部依赖**：列出 DB/缓存/消息队列/第三方 API/内部 RPC 调用，记录核心参数与错误处理/事务/幂等策略。
8) **记录代码位置**：形成条目 `method/path/file/line/group_prefix/middlewares/inputs/function_summary/risks`，标注高风险（debug/admin/config/internal/批量写入/文件上传/脚本执行）。

**重要提醒**：
- ✅ 仅定位和分析输入文件中列出的路由
- ❌ 定位过程中发现其他路由时，不得将其纳入分析范围
- ❌ 禁止扩展到相关但未列出的路由
- ❌ 禁止推测或补全路由清单

# 路由过滤规则

## 过滤逻辑

结合认证机制的分析结果，决定是否过滤需要高权限（如 admin/superuser）才能访问的接口：

### 情况 1：认证机制可绕过

如果认证机制分析结果表明存在绕过漏洞（如 JWT 密钥泄露、会话固定、认证逻辑缺陷等）：
- **不过滤** admin 权限接口
- 继续分析所有接口，包括需要高权限才能访问的管理接口
- 在端点分析文件中标注：`认证绕过风险: 是`

### 情况 2：认证机制不可绕过

如果认证机制分析结果表明认证机制安全、无法绕过：
- **过滤掉**需要 admin/superuser/管理员等高权限才能访问的接口
- 仅分析普通用户可访问的接口或无需认证的公开接口
- **不生成**被过滤接口的端点分析文件和下游任务
- 在总结中记录被过滤的接口数量和原因

### 判断标准

识别需要高权限的接口特征：
- 路由路径包含：`/admin/`、`/management/`、`/internal/`、`/superuser/`等管理员路径
- 中间件/装饰器包含：`@admin_required`、`@superuser_only`、`AdminGuard`、`RoleGuard('admin')`等管理员中间件/装饰器
- 权限注解包含：`roles=['admin']`、`permission='admin'`、`is_staff=True`、`is_superuser=True`等管理员权限注解

### 过滤记录

当触发过滤时，在总结文档（summary.md）中说明被过滤的接口信息，包括：
- 过滤原因
- 被过滤的接口数量
- 被过滤的接口列表（方法、路径、所需权限）

**重要**：被过滤的路由不生成端点分析文件，也不推荐下游任务。只有未被过滤的路由才会出现在 `tasks` 列表中。

# 路由数量限制与拆分机制

## 触发条件

当待分析的路由数量超过 10 个（即 ≥ 11 个）时，触发拆分机制。

**约束**：拆分时仅对输入文件中列出的路由进行分组，不得添加新路由。

## 处理流程

1. **读取输入文件**：解析输入文件中的完整路由清单
2. **应用过滤规则**：根据认证机制分析结果过滤高权限路由（如适用）
3. **统计路由数量**：统计过滤后的路由总数
4. **判断是否拆分**：
   - 如果路由数量 ≤ 10，直接进行深度分析
   - 如果路由数量 ≥ 11，触发拆分机制
5. **拆分处理**（如触发）：
   - 立即停止分析，不执行任何路由的详细分析
   - 将过滤后的路由按每 10 个一组进行拆分
   - 为每一组创建一个新的 `route-deep-analyzer` 任务

## 拆分输出格式

1. **生成分组路由文件**：为每组生成独立的路由清单文件 `.workspace/tasks/{TASK_ID}/routes-group-{N}.md`
2. **输出任务列表**：每组对应一个子任务

```json
{
  "split": true,
  "total_routes": 25,
  "groups": 3,
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/routes-group-1.md",
      "skill": "route-deep-analyzer"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/routes-group-2.md",
      "skill": "route-deep-analyzer"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/routes-group-3.md",
      "skill": "route-deep-analyzer"
    }
  ]
}
```

## 分组路由文件格式

每个 `routes-group-{N}.md` 文件内容：

```markdown
# 路由分组 {N}

## 基本信息
- **分组编号**：{N}
- **路由数量**：{count}
- **数据来源**：[原始输入文件路径]

## 路由列表

| 序号 | 方法 | 路由路径 | 源文件 | 行号 |
|------|------|------|--------|------|
| 1 | GET | /api/users | src/routes/user.js | 15 |
| 2 | POST | /api/users | src/routes/user.js | 28 |
| ... | ... | ... | ... | ... |

## 约束说明

本分组中的所有路由均来自原始输入文件，仅分析本分组列表中的路由。
```

## 注意事项

- 每组生成独立的 `routes-group-{N}.md` 文件，包含该组的完整路由信息
- 所有路由必须来自原始输入文件，子任务严格限制在该文件列出的路由范围内分析
- 分组文件需注明数据来源，便于追溯路由清单的原始出处

# 输出要求

## 1. 端点分析文件

每组路由（最多 10 个）输出到一个 md 文件，文件路径规则为：`.workspace/tasks/{TASK_ID}/route-analysis-group-{N}.md`

**约束**：仅输出输入文件中列出的路由的分析结果。

**文件内容格式**（供 `code-security-analyzer` 使用）：

```markdown
# 路由功能分析 - 分组 {N}

**分组信息**：分组编号 {N} | 端点数量 {count}

---

## 端点 1: {METHOD} {path}

**基本信息**
- 路径：{full_path}
- Handler：{file_path}:{start_line}-{end_line} `{handler_function_name}`
- 认证：{auth_required: 是/否} ({auth_type}) | 权限：{permissions} | 中间件：{middleware_list}

**参数与响应**

| 参数类型 | 名称 | 数据类型 | 必填 | 默认值 | 说明 |
|---------|------|---------|------|--------|------|
| 路径 | {name} | {type} | {✓/✗} | - | {description} |
| 查询 | {name} | {type} | {✓/✗} | {default} | {description} |
| 请求体 | {field} | {type} | {✓/✗} | - | {description} |

- 成功响应：{简短描述}
- 错误响应：{简短描述}

**功能摘要**

{function_logic_summary}

**关键代码位置**

| 文件路径 | 起始行 | 结束行 | 代码类型 |
|----------|--------|--------|----------|
| {file_path} | {start_line} | {end_line} | 路由注册 |
| {file_path} | {start_line} | {end_line} | Handler/Controller |
| {file_path} | {start_line} | {end_line} | 中间件 |
| {file_path} | {start_line} | {end_line} | 参数校验 |
| {file_path} | {start_line} | {end_line} | 业务逻辑/Service |
| {file_path} | {start_line} | {end_line} | 数据访问/DAO |
| {file_path} | {start_line} | {end_line} | 工具函数 |

---

## 端点 2: {METHOD} {path}
...
```

**格式说明**：
- 每个分组文件包含最多 10 个端点的分析结果
- 采用紧凑格式减少输出长度：
  - 分组信息使用单行展示
  - 基本信息、认证授权合并到一起
  - 参数（路径、查询、请求体）合并到统一表格
  - 响应结构使用简短描述
  - 保持关键代码位置表格完整（下游安全分析必需）
- 不输出代码片段，仅保留文件路径和行号范围
- 端点之间使用 `---` 分隔

**关键代码位置收集要求**：
- **路由注册**：路由定义、路径映射
- **Handler/Controller**：请求处理函数的完整范围
- **中间件**：认证、授权、日志、限流等中间件
- **参数校验**：输入验证、DTO/Schema 定义
- **业务逻辑**：Service 层调用的相关方法
- **数据访问**：数据库查询、ORM 操作、Repository 方法
- **工具函数**：被调用的辅助函数、工具类方法
- **外部调用**：第三方 API、内部 RPC、消息队列操作

**重要**：代码位置收集要尽可能完整，确保下游 `code-security-analyzer` 能获取足够的上下文进行安全分析。遗漏关键代码位置可能导致漏洞被忽略。

## 2. 下游任务推荐

每个分组文件对应一个 `code-security-analyzer` 任务。

**总结输出格式（JSON格式）**：
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/route-analysis-group-1.md",
            "skill": "code-security-analyzer",
            "dependencies": [
                ".workspace/tasks/{PROFILE_TASK_ID}/project-profile.md",
                ".workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md"
            ]
        },
        {
            "artifact": ".workspace/tasks/{TASK_ID}/route-analysis-group-2.md",
            "skill": "code-security-analyzer",
            "dependencies": [
                ".workspace/tasks/{PROFILE_TASK_ID}/project-profile.md",
                ".workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md"
            ]
        }
    ]
}
```

**依赖说明**：
- `{PROFILE_TASK_ID}`: 项目画像任务 ID（包含技术栈、框架信息）
- `{AUTH_TASK_ID}`: 认证分析任务 ID（包含认证机制、角色体系信息）
- 这些依赖为下游 `code-security-analyzer` 提供项目上下文，有助于更准确地识别漏洞

**注意**：
- 所有端点都必须包含在分组文件中，禁止遗漏；所有端点必须来自输入文件
- `{TASK_ID}` 需替换为实际的任务 ID（如 `orch-003`）
- `{N}` 为分组序号，从 1 开始

---

# 执行检查清单

在执行本技能前，请确认以下事项：

## 输入验证
- [ ] 已接收到输入文件路径
- [ ] 输入文件包含路由清单（方法、路径）
- [ ] 输入文件格式符合要求

## 范围控制
- [ ] 仅分析输入文件中列出的路由
- [ ] 未自行扫描项目发现新路由
- [ ] 未扩展到输入范围外的端点
- [ ] 未推测或补全缺失的路由

## 过滤规则
- [ ] 已读取认证机制分析结果
- [ ] 根据认证可绕过情况应用过滤规则
- [ ] 记录被过滤的路由及原因

## 拆分机制
- [ ] 统计过滤后的路由数量
- [ ] 超过 10 个时正确触发拆分
- [ ] 拆分文件仅包含输入范围内的路由
- [ ] 标注数据来源

## 输出质量
- [ ] 端点分析文件仅包含输入范围内的路由
- [ ] 关键代码位置收集完整
- [ ] 下游任务正确生成
- [ ] 依赖项正确传递

**核心原则**：严格遵守输入范围限制，禁止越界分析。
