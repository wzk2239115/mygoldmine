---
name: task-manage
description: 基于 tasks.json 的任务管理工具集。用于创建、跟踪和管理多步骤工作流的任务列表。提供 6 个 CLI 工具：init-task-json、add-task、update-task、read-task、list-tasks、check-task。支持任务状态流转（pending→in_progress→completed/failed）、按条件过滤查询、完成情况统计。适用于需要持久化任务状态的复杂工作流场景。
---

# Task Management Skill

任务管理工具集，提供完整的任务生命周期管理功能，包括初始化、添加、更新、查询和统计任务。

## Instructions

### 何时使用此 Skill

当您需要：
- 创建新的任务列表文件（tasks.json）
- 添加、更新或查询任务
- 检查任务完成情况统计
- 管理任务状态（pending, in_progress, completed, failed, skipped）
- 按条件过滤和查询任务

### 工具脚本位置

所有工具脚本位于 `scripts/tools/` 目录下（已经添加到 PATH 环境变量中）：
- `init-task-json` / `init-task-json.sh` - 初始化任务列表
- `add-task` / `add-task.sh` - 添加单个任务
- `add-tasks` / `add-tasks.sh` - 批量添加任务
- `update-task` / `update-task.sh` - 更新任务
- `read-task` / `read-task.sh` - 读取任务详情
- `list-tasks` / `list-tasks.sh` - 列出任务（支持过滤）
- `check-task` / `check-task.sh` - 检查任务统计
- `delete-task` / `delete-task.sh` - 删除任务

**注意**：所有脚本都提供了不带 `.sh` 后缀的符号链接，两种调用方式都可以使用。

**工具说明**：`init-task-json`、`add-task`、`add-tasks`、`list-tasks`、`read-task`、`update-task` 等命令均为系统内置的任务管理命令，可直接调用，无需额外安装。

### 使用步骤

1. **初始化任务列表**：使用 `init-task-json` 创建新的 tasks.json 文件
2. **添加任务**：使用 `add-task` 添加新任务或使用 `add-tasks` 批量添加任务
3. **查看任务**：使用 `list-tasks` 或 `read-task` 查看任务
4. **更新任务**：使用 `update-task` 更新任务状态和详情
5. **删除任务**：使用 `delete-task` 删除指定任务
6. **检查进度**：使用 `check-task` 查看完成情况统计

### 重要注意事项

- 所有工具自动更新 `updated_at`（中国时区 UTC+8）和 `summary` 统计
- 所有操作后进行 Schema 校验
- 任务 ID 在同一 tasks.json 中必须唯一
- 如果目录不存在，工具会自动创建

## 工具列表

1. **init-task-json** - 初始化新的 tasks.json 文件
2. **add-task** - 向 tasks.json 添加单个任务
3. **add-tasks** - 批量向 tasks.json 添加多个任务
4. **update-task** - 更新 tasks.json 中的现有任务
5. **read-task** - 读取指定任务的详情
6. **list-tasks** - 列出任务列表（支持过滤）
7. **check-task** - 检查任务完成情况
8. **delete-task** - 删除指定任务

所有工具自动更新 `updated_at`（中国时区 UTC+8）和 `summary` 统计，并在操作后进行 Schema 校验。

## 1. init-task-json

**用法：**
```bash
init-task-json <tasks_json_path> <agent_task_id> <agent_name> --description "<text>" [--tasks <json>]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径，必须以 `.json` 结尾
- `agent_task_id`（必需）：任务列表唯一标识符，用于区分同一 agent 的不同任务列表
  - 只能包含字母、数字、连字符(-)和下划线(_)
  - 长度不超过 100 字符，不能为空
- `agent_name`（必需）：代理名称
  - 只能包含字母、数字、连字符(-)和下划线(_)
  - 长度不超过 100 字符，不能为空
  - 不能以连字符(-)或下划线(_)开头或结尾
- `--description "<text>"`（必需）：任务列表描述
  - 不能为空，不含控制字符，建议长度 ≤ 1024
- `--tasks <json>`（可选）：初始任务列表的 JSON 字符串
  - 格式：`'[{"id":"task-001","description":"任务描述"},{"id":"task-002","description":"任务描述2","type":"code_scan"}]'`
  - 每个任务对象需要包含：
    - `id`（必需）：任务 ID
    - `description`（必需）：任务描述
    - `type`（可选）：任务类型，默认 `"general"`
    - `optional`（可选）：是否可选，默认 `false`

**示例：**
```bash
# 创建空任务列表
init-task-json ./tasks.json "project-audit-001" "security-auditor" --description "项目审计任务列表"

# 创建带初始任务的任务列表
init-task-json ./tasks.json "project-audit-001" "security-auditor" --description "项目审计任务列表" --tasks '[
  {"id":"task-001","description":"项目分析"},
  {"id":"task-002","description":"漏洞扫描","type":"vulnerability_scan"}
]'
```

**注意：** `agent_name` 是必需参数，不能省略。

## 2. add-task

**用法：**
```bash
add-task <tasks_json_path> <task_id> <task_type> <description> [--optional] [--before <task_id>]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `task_id`（必需）：任务唯一标识符
- `task_type`（必需）：任务类型（如 "asset_discovery", "code_scan", "vulnerability_scan"）
- `description`（必需）：任务描述，不能为空
- `--optional`（可选）：标记任务为可选
- `--before <task_id>`（可选）：指定新任务必须在此任务之前完成（用于控制插入顺序）
  - 如果指定，新任务将插入到指定任务之前
  - 如果未指定，新任务将追加到任务列表末尾
  - 指定的任务 ID 必须已存在于 tasks.json 中

**说明：**
- 新添加的任务默认状态为 `pending`
- 任务详情 `detail` 默认为空对象 `{}`
- 使用 `update-task` 可以更新任务状态和详情
- `--before` 选项仅用于控制任务的插入顺序，不会在 tasks.json 中保存此信息

**示例：**
```bash
# 添加任务到末尾（默认行为）
add-task ./tasks.json "task-001" "asset_discovery" "识别资产位置"

# 添加可选任务
add-task ./tasks.json "task-002" "code_scan" "扫描代码中的安全漏洞" --optional

# 添加任务到指定任务之前
add-task ./tasks.json "task-003" "vulnerability_scan" "执行漏洞扫描" --before "task-002"

# 组合使用：添加可选任务并指定插入位置
add-task ./tasks.json "task-004" "report_generation" "生成报告" --optional --before "task-002"
```

## 3. add-tasks

**用法：**
```bash
add-tasks <tasks_json_path> <tasks_json_file>
add-tasks <tasks_json_path> --json <tasks_json_string>
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `tasks_json_file`（方式1）：包含任务数组的 JSON 文件路径
- `--json <tasks_json_string>`（方式2）：直接提供任务数组的 JSON 字符串

**任务 JSON 格式：**
```json
[
  {
    "id": "task-001",
    "type": "asset_discovery",
    "description": "识别资产位置",
    "optional": false,
    "before": "task-002"  // 可选，指定插入位置
  },
  {
    "id": "task-002",
    "type": "code_scan",
    "description": "扫描代码",
    "optional": true
  }
]
```

**字段说明：**
- `id`（必需）：任务唯一标识符
- `type`（必需）：任务类型
- `description`（必需）：任务描述，不能为空
- `optional`（可选）：是否可选，默认 `false`
- `before`（可选）：指定插入位置的任务 ID，如果指定，新任务将插入到该任务之前

**说明：**
- 批量添加多个任务，适合一次性添加多个相关任务
- 支持两种输入方式：从文件读取或直接提供 JSON 字符串
- 每个任务都会进行验证，失败的任务会跳过并记录
- 显示批量添加的进度和统计信息（总计、成功、失败）
- 如果所有任务都成功添加，返回退出码 0；如果有失败，返回退出码 1

**示例：**
```bash
# 方式1：从 JSON 文件批量添加任务
add-tasks ./tasks.json tasks-to-add.json

# 方式2：直接提供 JSON 字符串
add-tasks ./tasks.json --json '[
  {"id":"task-001","type":"asset_discovery","description":"识别资产位置"},
  {"id":"task-002","type":"code_scan","description":"扫描代码","optional":true,"before":"task-001"}
]'

# 任务文件示例（tasks-to-add.json）
# [
#   {
#     "id": "task-001",
#     "type": "code_scan",
#     "description": "扫描代码中的安全漏洞",
#     "optional": false
#   },
#   {
#     "id": "task-002",
#     "type": "vulnerability_scan",
#     "description": "执行漏洞扫描",
#     "optional": true,
#     "before": "task-001"
#   }
# ]
```

## 4. update-task

**用法：**
```bash
update-task <tasks_json_path> <task_id> --status <status> [--description <description>] [--detail <json>] [--optional <true|false>]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `task_id`（必需）：要更新的任务 ID
- `--status <status>`（必需）：更新任务状态（pending, in_progress, completed, failed, skipped）
- `--description <description>`（条件必需）：当状态为 `completed` 或 `failed` 时必需，其他状态可选
- `--detail <json>`（条件必需）：当状态为 `completed` 时必需，其他状态可选
- `--optional <true|false>`（可选）：更新任务是否可选

**示例：**
```bash
# 更新为 completed（需要 description 和 detail）
update-task ./tasks.json "task-001" --status "completed" --description "任务已完成" --detail '{"result": "success"}'
# 更新为 failed（需要 description，detail 可选）
update-task ./tasks.json "task-002" --status "failed" --description "任务执行失败：原因说明"
# 更新为其他状态（description 和 detail 可选）
update-task ./tasks.json "task-003" --status "in_progress"
# 同时更新多个字段
update-task ./tasks.json "task-004" --status "completed" --description "已完成" --detail '{"files": 100, "issues": 5}'
```

## 5. read-task

**用法：**
```bash
read-task <tasks_json_path> <task_id> [--format <json|pretty>]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `task_id`（必需）：要读取的任务 ID
- `--format <json|pretty>`（可选）：输出格式，默认为 `pretty`
  - `json`：输出原始 JSON 格式
  - `pretty`：输出格式化的可读文本

**说明：**
- 用于查看单个任务的完整信息，包括 ID、类型、状态、描述、是否可选和详情

**示例：**
```bash
# 以可读格式查看任务详情
read-task ./tasks.json "task-001"
# 以 JSON 格式查看任务详情
read-task ./tasks.json "task-001" --format json
```

## 6. list-tasks

**用法：**
```bash
list-tasks <tasks_json_path> [--format <json|pretty>] [--status <status>] [--type <type>] [--optional] [--required]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `--format <json|pretty>`（可选）：输出格式，默认为 `pretty`
  - `json`：输出原始 JSON 数组
  - `pretty`：输出格式化的可读文本
- `--status <status>`（可选）：按状态过滤任务
  - 有效值：`pending`、`in_progress`、`completed`、`failed`、`skipped`
- `--type <type>`（可选）：按任务类型过滤（如 "asset_discovery", "code_scan"）
- `--optional`（可选）：只显示可选任务
- `--required`（可选）：只显示必需任务（非可选）
  - 注意：`--optional` 和 `--required` 不能同时使用

**说明：**
- 支持多个过滤条件组合使用
- 如果没有匹配的任务，会显示"没有找到匹配的任务"

**示例：**
```bash
# 列出所有任务
list-tasks ./tasks.json
# 列出所有已完成的任务
list-tasks ./tasks.json --status completed
# 列出所有待处理的任务
list-tasks ./tasks.json --status pending
# 列出特定类型的任务
list-tasks ./tasks.json --type asset_discovery
# 列出所有可选任务
list-tasks ./tasks.json --optional
# 列出所有必需任务
list-tasks ./tasks.json --required
# 组合过滤：列出已完成且类型为 code_scan 的任务
list-tasks ./tasks.json --status completed --type code_scan
# 以 JSON 格式输出
list-tasks ./tasks.json --format json
```

## 7. check-task

**用法：**
```bash
check-task <tasks_json_path> [--show-pending] [--show-failed]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `--show-pending`（可选）：显示待处理的任务列表
- `--show-failed`（可选）：显示失败的任务列表

**说明：**
- 显示任务完成情况的统计信息，包括总任务数、已完成、进行中、待处理、失败数量和完成率
- 根据完成情况返回不同的退出码：
  - `0`：所有任务已完成
  - `1`：有未完成任务（pending 或 in_progress）
  - `2`：有失败任务

**示例：**
```bash
# 查看任务完成情况统计
check-task ./tasks.json
# 查看统计并显示待处理任务列表
check-task ./tasks.json --show-pending
# 查看统计并显示失败任务列表
check-task ./tasks.json --show-failed
# 同时显示待处理和失败任务
check-task ./tasks.json --show-pending --show-failed
```

## 8. delete-task

**用法：**
```bash
delete-task <tasks_json_path> <task_id>
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `task_id`（必需）：要删除的任务 ID

**说明：**
- 删除指定任务，自动更新 `updated_at`（UTC+8）与 `summary` 统计。
- 如果任务 ID 不存在会报错，不会修改文件。
- 操作完成后执行 Schema 校验，失败则回滚。

**示例：**
```bash
# 删除 task-005
delete-task ./tasks.json "task-005"

# 删除前可先查看列表
list-tasks ./tasks.json --status pending
```

## 重要说明

- **agent_task_id**：用于区分同一 agent 创建的不同任务列表，必须唯一且非空
- **时间戳格式**：使用中国时区（UTC+8），格式为 `YYYY-MM-DDTHH:MM:SS+08:00`
- **Schema 校验**：所有操作后自动校验，失败会报错
- **任务 ID**：在同一 tasks.json 中必须唯一
- **文件路径**：如果目录不存在，工具会自动创建

## Examples

### 示例 1：创建新项目任务列表

```bash
# 初始化任务列表
init-task-json ./tasks.json "project-001" "security-auditor" --description "项目任务列表"

# 添加多个任务（方式1：逐个添加）
add-task ./tasks.json "task-001" "asset_discovery" "识别资产位置"
add-task ./tasks.json "task-002" "code_scan" "扫描代码中的安全漏洞"
# 使用 --before 控制任务顺序：task-003 将在 task-002 之前
add-task ./tasks.json "task-003" "vulnerability_scan" "执行漏洞扫描" --before "task-002" --optional

# 添加多个任务（方式2：批量添加）
add-tasks ./tasks.json tasks-to-add.json

# 查看所有任务
list-tasks ./tasks.json
```

### 示例 2：更新任务状态

```bash
# 将任务标记为进行中
update-task ./tasks.json "task-001" --status "in_progress"

# 完成任务并添加详情
update-task ./tasks.json "task-001" --status "completed" \
  --description "资产识别已完成" \
  --detail '{"config_files": 5, "databases": 3, "secrets": 10}'

# 查看任务详情
read-task ./tasks.json "task-001"
```

### 示例 3：查询和过滤任务

```bash
# 查看所有待处理的任务
list-tasks ./tasks.json --status pending

# 查看所有已完成的任务
list-tasks ./tasks.json --status completed

# 查看特定类型的任务
list-tasks ./tasks.json --type code_scan

# 组合查询：已完成且类型为 asset_discovery 的任务
list-tasks ./tasks.json --status completed --type asset_discovery
```

### 示例 4：检查任务完成情况

```bash
# 查看任务统计
check-task ./tasks.json

# 查看统计并显示待处理任务
check-task ./tasks.json --show-pending

# 查看统计并显示失败任务
check-task ./tasks.json --show-failed
```

### 示例 5：完整工作流程

```bash
# 1. 初始化任务列表
init-task-json ./tasks.json "project-001" "agent-name" --description "示例工作流"

# 2. 添加任务（可以指定插入顺序）
add-task ./tasks.json "task-001" "asset_discovery" "识别资产位置"
add-task ./tasks.json "task-002" "code_scan" "扫描代码漏洞"
# 在 task-002 之前插入新任务
add-task ./tasks.json "task-003" "preparation" "准备工作" --before "task-002"

# 3. 查看任务列表
list-tasks ./tasks.json

# 4. 开始执行任务
update-task ./tasks.json "task-001" --status "in_progress"

# 5. 完成任务
update-task ./tasks.json "task-001" --status "completed" \
  --description "任务已完成" \
  --detail '{"result": "success", "files": 100}'

# 6. 检查完成情况
check-task ./tasks.json --show-pending
```

## 工作流程

```bash
# 1. 初始化
init-task-json ./tasks.json "project-001" "agent-name" --description "示例工作流"

# 2. 添加任务
add-task ./tasks.json "task-001" "type" "描述"

# 3. 查看任务列表
list-tasks ./tasks.json

# 4. 查看任务详情
read-task ./tasks.json "task-001"

# 5. 更新任务
update-task ./tasks.json "task-001" --status "completed" --description "任务已完成" --detail '{"result": "success"}'

# 6. 检查任务完成情况
check-task ./tasks.json --show-pending
```

