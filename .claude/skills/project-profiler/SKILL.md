---
name: project-profiler
description: 项目画像技能：构建项目画像，分析技术栈与项目类型，并推荐后续分析技能。
---

# 概述与边界

- 聚焦项目基础信息收集, 快速判定优先, 可选分类如下：
1. 后端HTTP服务（主流应用类型, 通过HTTP协议提供服务）
2. 前端WEB应用（浏览器上的运行的代码，通常由HTML、CSS、JavaScript等技术栈开发）
3. 智能合约项目（区块链应用，包含Solidity/Rust/Move/Go/Vyper等智能合约代码）
4. 安全测试靶场（用于安全测试的靶场，通常包含多个不同类型的漏洞代码示例）

## 基础设施画像（v2，优先使用）

除了上面的 Web/合约分类，还要识别 AI 基础设施类型：

```bash
python3 ./quick-scan.py {source_dir} --json --output .workspace/tasks/{TASK_ID}/project-profile.json
```

`--json` 输出包含：

- `project_types`：`agent-harness` / `inference-engine` / `training-framework` / `model-serving`（可叠加 Web 类型）
- `entrypoints.infra`：HTTP/gRPC/CLI/IPC/model/exec 入口（file:line）
- `trust_boundaries`：http / grpc / model-file / ipc / sandbox / distributed / config ...
- `recommended_skills`：按类型给出的 track 技能，不再默认只给 web-auth/sensitive-info
- `infra_evidence`：类型判定依据

**路由规则**：

- 如果 `project_types` 含上述基础设施类型，走 **Agentic Infra Track**：
  `infra-analyst`（按 boundary 并行）→ `hypothesis-critic` → `report-generator` →
  `verify-agent` → `knowledge-scribe`。
- 不要默认先跑 40+ 个 Web analyzer；只按 boundary 选技能。
- `security-lab` 仍是互斥分类，但只有多信号（README 强信号 + 目录 + flag/submit 文件）
  才判定，单凭 `lab`/`benchmark` 不算。
- `scripts/experimental/infra_surface_index.py` 只能当索引，不能当 finding。

**分类约束规则**：
- 后端HTTP服务、前端WEB应用、智能合约项目可以同时勾选（一个项目可以同时包含多种类型）
- `agent-harness` / `inference-engine` / `training-framework` / `model-serving` 也可叠加
- **安全测试靶场为互斥分类**：如果判定为靶场类型，则**不能**同时勾选其他分类，只能单独勾选靶场

# 分类方法

**识别后端HTTP服务分类方法（快速判定）：**

运行 `quick-scan.py` 脚本进行快速扫描，并生成项目画像。
```bash
python3 ./quick-scan.py {source_dir}
python3 ./quick-scan.py .
```

**脚本覆盖范围**：
- ✅ **项目结构分析**：自动识别项目目录结构、主要文件类型
- ✅ **技术栈识别**：自动识别编程语言、框架、包管理器
- ✅ **代码统计**：自动统计文件数量、代码行数
- ✅ **入口点识别**：自动识别主入口文件、路由入口文件
- ❌ **项目分类判定**：项目分类（后端HTTP服务/前端WEB应用/安全测试靶场）需要结合脚本结果进行手动判定
- ❌ **分类依据说明**：分类依据需要结合项目特征进行手动分析

**对于后端 HTTP 服务，后续分析需要使用的基础技能列表如下（不要添加与此无关的技能）: **
- web-auth-analyzer 技能：分析API端点认证要求和用户角色体系。
- sensitive-info-scanner 技能：扫描敏感信息泄露风险。

**AI 基础设施条件任务（在基础列表之外按特征追加，满足任一即可）: **
- 依赖或代码含 `transformers`、`torch`、`vllm`、`sglang`、`verl`、`peft`、`accelerate`，或出现 `from_pretrained`、`trust_remote_code`、`auto_map`、`get_class_from_dynamic_module`、`torch.load` → 追加 `model-loading-analyzer`。
- 存在 `.mcp.json`、`.codex/config.toml`、`.claude/settings.json`、`AGENTS.md`、`CLAUDE.md`，或出现 `mcpServers`、`approval_policy`、`allow_prefix`、`PrefixRule`、`core.hooksPath`、`fsmonitor` → 追加 `agent-config-analyzer`。
- 条件任务只追加，不替换基础任务；判定依据写入项目画像的「分类依据」或附加章节，并保持 `-scanner`/`-analyzer` 命名规则。

**总结输出格式（JSON格式）：**
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "web-auth-analyzer"
        },
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "sensitive-info-scanner"
        }
    ]
}
```

**说明**：
- `{TASK_ID}` 为当前任务 ID
- web-auth-analyzer 会根据分析结果自动触发下游任务（unauth-route-scanner / normal-route-scanner）
- 命中 AI 基础设施特征时，在上述 JSON 的 `tasks` 数组中继续追加 `model-loading-analyzer` / `agent-config-analyzer` 任务，artifact 相同

2. 前端 WEB 应用

**识别 WEB 应用方法（快速判定优先）：**
- 快速判定一：查依赖/锁文件中常见 Web 框架关键字。
- 快速判定二：查入口/路由特征调用（如 React、Vue、Angular、Svelte、Next、Nuxt）。
- 若快速判定失败，再做深搜。

**对于前端WEB应用，目前不需要继续分析，直接跳过。**

3. 智能合约项目

**识别智能合约项目方法（快速判定优先）：**
- 快速判定一：查依赖/锁文件中是否包含合约开发框架（hardhat、truffle、foundry、anchor 等）。
- 快速判定二：查项目根目录或src目录是否包含合约配置文件（hardhat.config.js、truffle-config.js、foundry.toml、Anchor.toml）。
- 快速判定三：检查源代码中是否包含 `.sol`、`.rs`、`.move`、`.vy` 等合约文件，或检查代码中的合约特征关键词（pragma solidity、contract {}、#[program]）。

**对于智能合约项目，后续分析需要使用的技能列表如下（禁止添加其他技能）: **
- blockchain-goldmine-analyzer 技能：识别合约编程语言，生成合约审计建议。

**总结输出格式（JSON格式）：**
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "blockchain-goldmine-analyzer"
        }
    ]
}
```

4. 安全测试靶场

**识别安全测试靶场方法（快速判定优先）：**
- 快速判定一：项目说明文档通常会明确指出是项目靶场为出于教学目的而构建的安全测试靶场, 可以重点关注。
- 快速判定二: 项目目录结构中会包含多个不同类型的漏洞代码示例。

**对于安全测试靶场，后续分析需要使用的技能列表如下（禁止添加其他技能）: **
- vtr-scanner 技能：扫描靶场类型，识别测试类型。

**总结输出格式（JSON格式）：**
```json
{
    "tasks": [
        {
            "artifact": ".workspace/tasks/{TASK_ID}/project-profile.md",
            "skill": "vtr-scanner"
        }
    ]
}
```

# 输出要求

## 1. 项目画像文件

**输出路径**：`.workspace/tasks/{TASK_ID}/project-profile.md`（如用户指定了输出路径则优先使用）

**文件内容格式**：
```markdown
# 项目画像

## 基本信息
- **项目名称**：{project_name}
- **项目路径**：{project_root}
- **扫描时间**：{scan_time}

## 项目分类
<!-- 约束：安全测试靶场为互斥分类，勾选后不能同时勾选其他类型 -->
- [ ] 后端HTTP服务
- [ ] 前端WEB应用
- [ ] 智能合约项目
- [ ] 安全测试靶场（互斥）

## 技术栈
- **主要语言**：{language}
- **框架**：{framework}
- **包管理器**：{package_manager}

## 代码统计
- **文件数量**：{file_count}
- **代码行数**：{lines_of_code}
- **主要目录结构**：
  - src/
  - tests/
  - ...

## 入口点
- **主入口文件**：{entry_file}
- **路由入口**：{router_files}

## 分类依据
{classification_evidence}
```

## 2. 必需包含内容

| 字段 | 必需 | 说明 |
|------|------|------|
| 项目分类 | 是 | 至少勾选一个分类 |
| 主要语言 | 是 | 项目使用的主要编程语言 |
| 框架 | 是 | 使用的Web框架（如有） |
| 文件数量 | 是 | 扫描范围内的文件总数 |
| 分类依据 | 是 | 说明判定分类的依据 |

## 3. 后续任务推荐

根据项目分类，按照对应的「总结输出格式」返回任务列表。

**注意**：
- `{TASK_ID}` 由上游 orchestrator 传入，需替换为实际值（如 `orch-001`）
- 如果项目同时属于多个非互斥分类（后端HTTP服务 + 前端WEB应用 + 智能合约项目），合并所有分类对应的任务列表
  - 例如：后端 + 合约 → 返回 `web-auth-analyzer`、`sensitive-info-scanner`、`blockchain-goldmine-analyzer` 三个任务
- **如果判定为安全测试靶场，只返回 vtr-scanner 任务，不返回其他任务**
