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

# 输出要求

1. 每一个API端点对应一个md文件，文件路径规则为：`.workspace/tasks/{TASK_ID}/{slugified_path}-{method}-{category}.md`，命名规则：
    - 路径转 slug：`/` 与 `\` → `-`，连续分隔符合并；`{id}`/`:id`/`<id>` 统一为 `id`；`*`/`**` → `wildcard`；`[` `]` → `-`；去除空格与不可见字符，非 ASCII 与特殊符号替换为 `-`。
    - 方法前缀：HTTP 方法小写放入文件名（如 `get`/`post`），避免同路径不同方法冲突。
    - 去重策略：同名时在 `.md` 前追加短序号或短 hash（如 `-2` 或 `-a1b2`）。
    - 长度控制：文件名不超过约 120 字符，过长时截断中间，保留首尾。
