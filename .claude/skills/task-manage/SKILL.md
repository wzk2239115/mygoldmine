---
name: task-manage
description: 管理和跟踪任务列表的工具集。当需要创建、更新、查询任务列表，或检查任务完成情况时使用。支持通过 tasks.json 文件管理任务状态、类型、描述和详情，自动维护统计信息和 Schema 校验。
---

# Task Management Skill

任务管理工具集，提供完整的任务生命周期管理功能，包括初始化、添加、更新、查询和统计任务。

## Instructions

### 何时使用此 Skill

当您需要：
- 创建新的任务列表文件（tasks.json）
- 添加、更新或查询任务
- 检查任务完成情况统计
- 管理任务状态（pending, in_progress, completed, failed）
- 按条件过滤和查询任务

### 工具脚本位置

所有工具脚本位于 `scripts/tools/` 目录下：
- `init-task-json.sh` - 初始化任务列表
- `add-task.sh` - 添加任务
- `update-task.sh` - 更新任务
- `read-task.sh` - 读取任务详情
- `list-tasks.sh` - 列出任务（支持过滤）
- `check-task.sh` - 检查任务统计

### 使用步骤

1. **初始化任务列表**：使用 `init-task-json.sh` 创建新的 tasks.json 文件
2. **添加任务**：使用 `add-task.sh` 添加新任务
3. **查看任务**：使用 `list-tasks.sh` 或 `read-task.sh` 查看任务
4. **更新任务**：使用 `update-task.sh` 更新任务状态和详情
5. **检查进度**：使用 `check-task.sh` 查看完成情况统计

### 重要注意事项

- 所有工具自动更新 `updated_at`（中国时区 UTC+8）和 `summary` 统计
- 所有操作后进行 Schema 校验
- 任务 ID 在同一 tasks.json 中必须唯一
- 如果目录不存在，工具会自动创建

## 工具列表

1. **init-task-json.sh** - 初始化新的 tasks.json 文件
2. **add-task.sh** - 向 tasks.json 添加新任务
3. **update-task.sh** - 更新 tasks.json 中的现有任务
4. **read-task.sh** - 读取指定任务的详情
5. **list-tasks.sh** - 列出任务列表（支持过滤）
6. **check-task.sh** - 检查任务完成情况统计

所有工具自动更新 `updated_at`（中国时区 UTC+8）和 `summary` 统计，并在操作后进行 Schema 校验。

## 1. init-task-json.sh

**用法：**
```bash
scripts/tools/init-task-json.sh <tasks_json_path> <agent_task_id> [agent_name]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径，必须以 `.json` 结尾
- `agent_task_id`（必需）：任务列表唯一标识符，用于区分同一 agent 的不同任务列表
  - 只能包含字母、数字、连字符(-)和下划线(_)
  - 长度不超过 100 字符，不能为空
- `agent_name`（可选）：代理名称，默认为空字符串

**示例：**
```bash
scripts/tools/init-task-json.sh ./tasks.json "project-audit-001" "security-auditor"
```

## 2. add-task.sh

**用法：**
```bash
scripts/tools/add-task.sh <tasks_json_path> <task_id> <task_type> <description> [--optional]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `task_id`（必需）：任务唯一标识符
- `task_type`（必需）：任务类型（如 "asset_discovery", "code_scan", "vulnerability_scan"）
- `description`（必需）：任务描述，不能为空
- `--optional`（可选）：标记任务为可选

**说明：**
- 新添加的任务默认状态为 `pending`
- 任务详情 `detail` 默认为空对象 `{}`
- 使用 `update-task.sh` 可以更新任务状态和详情

**示例：**
```bash
scripts/tools/add-task.sh ./tasks.json "task-001" "asset_discovery" "识别资产位置"
scripts/tools/add-task.sh ./tasks.json "task-002" "code_scan" "扫描代码中的安全漏洞" --optional
```

## 3. update-task.sh

**用法：**
```bash
scripts/tools/update-task.sh <tasks_json_path> <task_id> --status <status> [--description <description>] [--detail <json>] [--optional <true|false>]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `task_id`（必需）：要更新的任务 ID
- `--status <status>`（必需）：更新任务状态（pending, in_progress, completed, failed）
- `--description <description>`（条件必需）：当状态为 `completed` 或 `failed` 时必需，其他状态可选
- `--detail <json>`（条件必需）：当状态为 `completed` 时必需，其他状态可选
- `--optional <true|false>`（可选）：更新任务是否可选

**示例：**
```bash
# 更新为 completed（需要 description 和 detail）
scripts/tools/update-task.sh ./tasks.json "task-001" --status "completed" --description "任务已完成" --detail '{"result": "success"}'
# 更新为 failed（需要 description，detail 可选）
scripts/tools/update-task.sh ./tasks.json "task-002" --status "failed" --description "任务执行失败：原因说明"
# 更新为其他状态（description 和 detail 可选）
scripts/tools/update-task.sh ./tasks.json "task-003" --status "in_progress"
# 同时更新多个字段
scripts/tools/update-task.sh ./tasks.json "task-004" --status "completed" --description "已完成" --detail '{"files": 100, "issues": 5}'
```

## 4. read-task.sh

**用法：**
```bash
scripts/tools/read-task.sh <tasks_json_path> <task_id> [--format <json|pretty>]
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
scripts/tools/read-task.sh ./tasks.json "task-001"
# 以 JSON 格式查看任务详情
scripts/tools/read-task.sh ./tasks.json "task-001" --format json
```

## 5. list-tasks.sh

**用法：**
```bash
scripts/tools/list-tasks.sh <tasks_json_path> [--format <json|pretty>] [--status <status>] [--type <type>] [--optional] [--required]
```

**参数：**
- `tasks_json_path`（必需）：tasks.json 文件路径
- `--format <json|pretty>`（可选）：输出格式，默认为 `pretty`
  - `json`：输出原始 JSON 数组
  - `pretty`：输出格式化的可读文本
- `--status <status>`（可选）：按状态过滤任务
  - 有效值：`pending`、`in_progress`、`completed`、`failed`
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
scripts/tools/list-tasks.sh ./tasks.json
# 列出所有已完成的任务
scripts/tools/list-tasks.sh ./tasks.json --status completed
# 列出所有待处理的任务
scripts/tools/list-tasks.sh ./tasks.json --status pending
# 列出特定类型的任务
scripts/tools/list-tasks.sh ./tasks.json --type asset_discovery
# 列出所有可选任务
scripts/tools/list-tasks.sh ./tasks.json --optional
# 列出所有必需任务
scripts/tools/list-tasks.sh ./tasks.json --required
# 组合过滤：列出已完成且类型为 code_scan 的任务
scripts/tools/list-tasks.sh ./tasks.json --status completed --type code_scan
# 以 JSON 格式输出
scripts/tools/list-tasks.sh ./tasks.json --format json
```

## 6. check-task.sh

**用法：**
```bash
scripts/tools/check-task.sh <tasks_json_path> [--show-pending] [--show-failed]
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
scripts/tools/check-task.sh ./tasks.json
# 查看统计并显示待处理任务列表
scripts/tools/check-task.sh ./tasks.json --show-pending
# 查看统计并显示失败任务列表
scripts/tools/check-task.sh ./tasks.json --show-failed
# 同时显示待处理和失败任务
scripts/tools/check-task.sh ./tasks.json --show-pending --show-failed
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
scripts/tools/init-task-json.sh ./tasks.json "project-001" "security-auditor"

# 添加多个任务
scripts/tools/add-task.sh ./tasks.json "task-001" "asset_discovery" "识别资产位置"
scripts/tools/add-task.sh ./tasks.json "task-002" "code_scan" "扫描代码中的安全漏洞"
scripts/tools/add-task.sh ./tasks.json "task-003" "vulnerability_scan" "执行漏洞扫描" --optional

# 查看所有任务
scripts/tools/list-tasks.sh ./tasks.json
```

### 示例 2：更新任务状态

```bash
# 将任务标记为进行中
scripts/tools/update-task.sh ./tasks.json "task-001" --status "in_progress"

# 完成任务并添加详情
scripts/tools/update-task.sh ./tasks.json "task-001" --status "completed" \
  --description "资产识别已完成" \
  --detail '{"config_files": 5, "databases": 3, "secrets": 10}'

# 查看任务详情
scripts/tools/read-task.sh ./tasks.json "task-001"
```

### 示例 3：查询和过滤任务

```bash
# 查看所有待处理的任务
scripts/tools/list-tasks.sh ./tasks.json --status pending

# 查看所有已完成的任务
scripts/tools/list-tasks.sh ./tasks.json --status completed

# 查看特定类型的任务
scripts/tools/list-tasks.sh ./tasks.json --type code_scan

# 组合查询：已完成且类型为 asset_discovery 的任务
scripts/tools/list-tasks.sh ./tasks.json --status completed --type asset_discovery
```

### 示例 4：检查任务完成情况

```bash
# 查看任务统计
scripts/tools/check-task.sh ./tasks.json

# 查看统计并显示待处理任务
scripts/tools/check-task.sh ./tasks.json --show-pending

# 查看统计并显示失败任务
scripts/tools/check-task.sh ./tasks.json --show-failed
```

### 示例 5：完整工作流程

```bash
# 1. 初始化任务列表
scripts/tools/init-task-json.sh ./tasks.json "project-001" "agent-name"

# 2. 添加任务
scripts/tools/add-task.sh ./tasks.json "task-001" "asset_discovery" "识别资产位置"
scripts/tools/add-task.sh ./tasks.json "task-002" "code_scan" "扫描代码漏洞"

# 3. 查看任务列表
scripts/tools/list-tasks.sh ./tasks.json

# 4. 开始执行任务
scripts/tools/update-task.sh ./tasks.json "task-001" --status "in_progress"

# 5. 完成任务
scripts/tools/update-task.sh ./tasks.json "task-001" --status "completed" \
  --description "任务已完成" \
  --detail '{"result": "success", "files": 100}'

# 6. 检查完成情况
scripts/tools/check-task.sh ./tasks.json --show-pending
```

## 工作流程

```bash
# 1. 初始化
scripts/tools/init-task-json.sh ./tasks.json "project-001" "agent-name"

# 2. 添加任务
scripts/tools/add-task.sh ./tasks.json "task-001" "type" "描述"

# 3. 查看任务列表
scripts/tools/list-tasks.sh ./tasks.json

# 4. 查看任务详情
scripts/tools/read-task.sh ./tasks.json "task-001"

# 5. 更新任务
scripts/tools/update-task.sh ./tasks.json "task-001" --status "completed" --description "任务已完成" --detail '{"result": "success"}'

# 6. 检查任务完成情况
scripts/tools/check-task.sh ./tasks.json --show-pending
```

