---
name: route-function-analyzer
description: |
    专业路由功能分析技能：分析API端点功能，包括请求参数、响应数据、权限要求等。
    依赖上游任务authentication-analyzer的分析结果，需要给定该任务产物路径作为输入。
---

# 概述与边界

- 聚焦API端点功能分析：分析API端点功能，包括请求参数、响应数据、权限要求等。

# 主流语言/框架路由识别方法

### 通用思路（从单个入口展开）
- 锁定入口：从已知单个路由声明/控制器/文件出发，确认其所在分组、前缀与注册方式（router/app/server/subrouter）。
- 路径拼装：向上溯源 `group/prefix/subrouter/namespace/Area/MapControllerRoute`，拼出完整路径模板，记录动态参数/通配符。
- 方法与参数：明确 HTTP 方法；枚举路径参数、查询参数、Body/表单/文件上传、Header 依赖（如版本、租户）。
- 中间件上下文：列出命中链路的 auth/role/guard/interceptor/validator/rate-limit/logging 等，记录触发顺序与作用点。
- 处理逻辑：阅读 handler（或控制器方法），归纳功能类别（查询/创建/更新/删除/导出/登录/文件/调度/后台任务/管理操作等）。
- 外部交互：标注 DB/缓存/消息队列/第三方服务/内部 RPC 调用及关键参数；注意软删除/幂等/事务。


### 识别步骤（单入口展开）
1) 入口与定位：锁定当前路由声明（或控制器方法），确认其所在文件、分组、注册点。
2) 路径复原：自入口向上收集 `prefix/group/namespace/include/Area`，拼接完整路径，标注动态参数/正则/通配符。
3) 方法与输入：确认 HTTP 方法；列出路径/查询/Body/表单/文件/Headers 需求及默认值。
4) 中间件链路：梳理全局/分组/端点级中间件与 filters/guards/interceptors/validators/rate-limit/logging，记录顺序与影响（含认证授权提示）。
5) 功能归类：阅读 handler 逻辑，识别 CRUD/导入导出/登录注册/文件处理/任务调度/管理操作等，注明关键分支与副作用。
6) 外部依赖：列出 DB/缓存/消息队列/第三方 API/内部 RPC 调用，记录核心参数与错误处理/事务/幂等策略。
7) 输出要点：形成条目 `method/path/file/line/group_prefix/middlewares/inputs/function_summary/risks`，标注高风险（debug/admin/config/internal/批量写入/文件上传/脚本执行）。

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
- 路由路径包含：`/admin/`、`/management/`、`/internal/`、`/superuser/`
- 中间件/装饰器包含：`@admin_required`、`@superuser_only`、`AdminGuard`、`RoleGuard('admin')`
- 权限注解包含：`roles=['admin']`、`permission='admin'`、`is_staff=True`、`is_superuser=True`

### 过滤记录

当触发过滤时，在总结文档（summary.md）中说明被过滤的接口信息，包括：
- 过滤原因
- 被过滤的接口数量
- 被过滤的接口列表（方法、路径、所需权限）

**重要**：被过滤的路由不生成端点分析文件，也不推荐下游任务。只有未被过滤的路由才会出现在 `tasks` 列表中。

# 路由数量限制与拆分机制

## 触发条件

当待分析的路由数量超过 **10 个**时，触发拆分机制。

## 处理流程

1. **立即停止分析**：不执行任何路由的详细分析
2. **按组拆分**：将路由按每 10 个一组进行拆分
3. **生成子任务**：为每一组创建一个新的 `route-function-analyzer` 任务

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
      "skill": "route-function-analyzer"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/routes-group-2.md",
      "skill": "route-function-analyzer"
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/routes-group-3.md",
      "skill": "route-function-analyzer"
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

## 路由列表

| 序号 | 方法 | 路由路径 | 源文件 | 行号 |
|------|------|------|--------|------|
| 1 | GET | /api/users | src/routes/user.js | 15 |
| 2 | POST | /api/users | src/routes/user.js | 28 |
| ... | ... | ... | ... | ... |
```

## 注意事项

- 每组生成独立的 `routes-group-{N}.md` 文件，包含该组的完整路由信息
- 子任务读取对应的分组文件，仅分析其中列出的路由

# 输出要求

## 1. 端点分析文件

每一个API端点对应一个md文件，文件路径规则为：`.workspace/tasks/{TASK_ID}/{slugified_path}-{method}.md`

**命名规则**：
- 路径转 slug：`/` 与 `\` → `-`，连续分隔符合并；`{id}`/`:id`/`<id>` 统一为 `id`；`*`/`**` → `wildcard`；`[` `]` → `-`；去除空格与不可见字符，非 ASCII 与特殊符号替换为 `-`。
- 方法前缀：HTTP 方法小写放入文件名（如 `get`/`post`），避免同路径不同方法冲突。
- 去重策略：同名时在 `.md` 前追加短序号或短 hash（如 `-2` 或 `-a1b2`）。
- 长度控制：文件名不超过约 120 字符，过长时截断中间，保留首尾。

**文件内容格式**（供 `code-security-analyzer` 使用）：

```markdown
# {METHOD} {path}

## 基本信息
- **路由路径**：{full_path}
- **HTTP 方法**：{method}
- **源文件**：{file_path}:{line_number}
- **函数名称**：{handler_function_name}

## 认证与授权
- **认证要求**：{auth_required: 是/否}
- **认证方式**：{auth_type: JWT/Session/API Key/无}
- **权限要求**：{permissions}
- **中间件链**：{middleware_list}

## 请求参数
### 路径参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| {name} | {type} | {required} | {description} |

### 查询参数
| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|

### 请求体
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|

## 响应结构
- **成功响应**：{success_response_structure}
- **错误响应**：{error_response_structure}

## 函数逻辑摘要
{function_logic_summary}

## 关键代码片段

### {file_path}
\`\`\`{language}
// L{start_line}-L{end_line}
{line_number}: {code_line}
{line_number}: {code_line}
...
\`\`\`

**示例**：
\`\`\`javascript
// src/controllers/userController.js L42-L58
42: async function getUser(req, res) {
43:   const userId = req.params.id;
44:   const query = `SELECT * FROM users WHERE id = ${userId}`;
45:   const result = await db.query(query);
46:   res.json(result);
47: }
\`\`\`
```

## 2. 下游任务推荐

每个端点分析文件对应一个 `code-security-analyzer` 任务，用于对该路由函数进行代码安全分析。

**总结输出格式（JSON格式）**：
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/api-users-get.md",
            "skill": "code-security-analyzer"
        },
        {
            "artifact": ".workspace/tasks/{TASK_ID}/api-users-post.md",
            "skill": "code-security-analyzer"
        }
    ]
}
```

**注意**：
- 每个端点分析文件都必须生成对应的 `code-security-analyzer` 任务，禁止省略
- `{TASK_ID}` 需替换为实际的任务 ID（如 `orch-003`）
