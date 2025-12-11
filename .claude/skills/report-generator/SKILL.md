---
name: report-generator
description: 专业报告生成技能：汇总各扫描器的发现，生成面向人工的 Markdown 报告和机器可读的 JSON 报告。
---

## 概述与边界

- 聚焦报告生成：收集并合并所有扫描器智能体的结果，生成综合审计报告
- 不做：漏洞扫描、代码分析、威胁建模

## 输入文件（上游产物）

报告生成器需要读取以下上游产物：

| 产物类型 | 路径 | 说明 |
|----------|------|------|
| 任务清单 | `.workspace/tasks/security-orchestrator-tasks.json` | 扫描器执行状态 |
| 项目基本信息 | `.workspace/tasks/{PROFILE_TASK_ID}/project-profile.md` | 项目分类、技术栈、代码统计等 |
| 认证分析结果 | `.workspace/tasks/{AUTH_TASK_ID}/web-auth-analyzer.md` | 认证机制和角色体系分析 |
| 未授权路由 | `.workspace/tasks/{UNAUTH_SCANNER_TASK_ID}/unauth-route-scanner.md` | 无需认证的API端点列表 |
| 普通用户路由 | `.workspace/tasks/{NORMAL_SCANNER_TASK_ID}/normal-route-scanner.md` | 普通用户可访问的API端点列表 |
| 端点分析结果 | `.workspace/tasks/{ROUTE_ANALYZER_TASK_ID}/route-analysis-group-*.md` | 各端点功能分析 |
| 漏洞扫描结果（tasks） | `.workspace/tasks/{SCANNER_TASK_ID}/*-analyzer-result*.md` | 各扫描器的漏洞发现结果（tasks目录） |
| 漏洞扫描结果（findings） | `.workspace/findings/**/*.md` | 各扫描器的漏洞发现结果（findings目录） |
| 靶场扫描结果 | `.workspace/tasks/{VTR_TASK_ID}/vtr-scanner-result*.md` | 靶场类型识别结果 |

**路径说明**：
- 各产物路径使用明确的任务 ID 变量，与其他技能保持一致：
  - `{PROFILE_TASK_ID}`: 项目画像任务 ID
  - `{AUTH_TASK_ID}`: 认证分析任务 ID
  - `{UNAUTH_SCANNER_TASK_ID}`: 未授权路由扫描任务 ID
  - `{NORMAL_SCANNER_TASK_ID}`: 普通用户路由扫描任务 ID
  - `{ROUTE_ANALYZER_TASK_ID}`: 路由深度分析任务 ID
  - `{SCANNER_TASK_ID}`: 漏洞扫描器任务 ID（可能有多个）
  - `{VTR_TASK_ID}`: 靶场扫描任务 ID
- 实际执行时，需要从 `security-orchestrator-tasks.json` 读取各任务的实际 ID（如 `orch-001`, `orch-002` 等）
- 产物收集策略：
  - **tasks 目录**：遍历 `.workspace/tasks/` 下所有以 `orch-` 开头的子目录
  - **findings 目录**：递归扫描 `.workspace/findings/` 下所有 `.md` 文件（漏洞报告）
  - 两个目录的漏洞结果需要合并去重

## 核心职责

1. **结果聚合**：收集并合并所有扫描器智能体的结果
2. **严重程度组织**：按严重程度（Critical/High/Medium/Low）组织漏洞
3. **报告生成**：创建 Markdown（人类可读）和 JSON（机器可读）两种格式的报告
4. **风险评估**：计算整体风险级别并提供建议

## 报告生成流程

### 前置检查：确认上游任务完成

在开始生成报告之前，必须检查 orchestrator 的所有扫描任务是否已完成：

```bash
check-task .workspace/tasks/security-orchestrator-tasks.json
```

**检查结果处理**：
- 如果所有任务已完成（退出码 0）：继续执行报告生成
- 如果存在未完成任务（退出码 1）：记录警告，仍然生成报告但在报告中注明"部分任务未完成"
- 如果存在失败任务（退出码 2）：记录警告，在报告中列出失败的任务

```bash
# 查看未完成和失败的任务详情
check-task .workspace/tasks/security-orchestrator-tasks.json --show-pending --show-failed
```

### 步骤 1: 读取所有结果文件

**读取步骤**：
1. **读取任务清单**：读取 `.workspace/tasks/security-orchestrator-tasks.json` 获取所有已完成任务列表
2. **读取 tasks 目录产物**：遍历每个任务目录，根据技能名称（skill字段）和产物文件名识别产物类型：
   - `project-profiler` 技能 → `project-profile.md`（项目基本信息）
   - `web-auth-analyzer` 技能 → `web-auth-analyzer.md`（认证分析结果）
   - `unauth-route-scanner` 技能 → `unauth-route-scanner.md`（未授权路由清单）
   - `normal-route-scanner` 技能 → `normal-route-scanner.md`（普通用户路由清单）
   - `route-deep-analyzer` 技能 → `route-analysis-group-*.md`（端点深度分析结果）
   - 各扫描器技能（`*-analyzer`）→ `*-analyzer-result*.md`（漏洞扫描结果）
   - `vtr-scanner` 技能 → `vtr-scanner-result*.md`（靶场扫描结果）
3. **读取 findings 目录产物**：递归扫描 `.workspace/findings/` 目录下所有 `.md` 文件（漏洞报告）
   - 识别文件名模式（如 `sql-injection-*.md`, `xss-*.md` 等）确定漏洞类型
   - 解析 Markdown 文件提取漏洞信息（位置、严重程度、描述等）
4. **映射任务 ID**：将任务 ID 映射到相应的变量名（如 `orch-001` → `{PROFILE_TASK_ID}`）

**去重逻辑**：
- **同一SKILL多任务去重**：如果发现多个任务使用相同的SKILL（通过文件名前缀识别，如 `sql-injection-analyzer`）
- **tasks 与 findings 目录去重**：来自 tasks 目录和 findings 目录的漏洞结果也需要去重
- **去重规则**：相同文件路径 + 相同行号 + 相同漏洞类型 = 相同漏洞
- **冲突处理**：如果多个来源报告了相同的漏洞，只保留一个（优先保留严重程度最高的）

### 步骤 2: 聚合漏洞

**漏洞收集源**：
- **tasks 目录**：遍历各 `{SCANNER_TASK_ID}` 目录下的 `*-analyzer-result*.md` 文件
- **findings 目录**：递归扫描 `.workspace/findings/` 下所有 `.md` 文件

**聚合流程**：
1. 从两个目录收集所有漏洞
2. 应用去重规则：相同文件路径 + 相同行号 + 相同漏洞类型 = 相同漏洞
3. 冲突处理：如果多个来源报告了相同的漏洞，只保留一个（优先保留严重程度最高的）
4. 按严重程度排序（Critical > High > Medium > Low）
5. 分配全局漏洞 ID（VULN-001, VULN-002, 等）

**特殊情况处理**：
- 若未执行定制扫描（tasks 和 findings 目录下均无漏洞报告），仍需生成报告
- 统计值为 0，风险级别默认为 Low
- 在执行摘要中注明"未执行定制扫描（无推荐扫描器或扫描被跳过）"

### 步骤 3: 计算风险评估

**整体风险级别**：
- 如果存在任何 Critical 漏洞 → 风险级别：Critical
- 否则如果存在任何 High 漏洞 → 风险级别：High
- 否则如果存在任何 Medium 漏洞 → 风险级别：Medium
- 否则 → 风险级别：Low

**风险分数**：CVSS 分数的加权平均值（如果可用），或基于严重程度的评分

**风险因素**：列出最令人担忧的 3-5 个发现

### 步骤 4: 生成统计信息

- 按严重程度统计的漏洞总数
- 按类型统计的漏洞总数
- 包含漏洞的文件数量
- 扫描器执行状态和耗时

### 步骤 5: 按严重程度组织

- **Critical**：完整详情，包含代码示例、利用方式、修复建议
- **High**：完整详情，包含代码示例
- **Medium**：表格格式，包含关键信息
- **Low**：表格格式，包含关键信息

### 步骤 6: 生成 JSON 报告

生成到 `.workspace/reports/audit-report.json`：

```json
{
  "report_version": "1.0",
  "generated_at": "ISO 8601 timestamp",

  "metadata": {
    "project_name": "string",
    "project_root": "string",
    "scan_scope": "string",
    "scan_duration_ms": 0,
    "total_files_scanned": 0,
    "total_lines_scanned": 0
  },

  "risk_assessment": {
    "overall_risk_level": "Critical|High|Medium|Low",
    "risk_score": 0.0,
    "risk_factors": ["array"]
  },

  "summary": {
    "total_vulnerabilities": 0,
    "by_severity": {
      "critical": 0,
      "high": 0,
      "medium": 0,
      "low": 0
    },
    "by_type": {
      "SQL Injection": 0,
      "Command Injection": 0
    }
  },

  "vulnerabilities": [
    {
      "id": "string",
      "scanner": "string",
      "type": "string",
      "severity": "string",
      "cvss_score": 0.0,
      "cwe_id": "string",
      "location": {
        "file": "string",
        "line": 0,
        "column": 0
      },
      "description": "string",
      "exploit": "string",
      "remediation": "string",
      "fixed_code": "string"
    }
  ],

  "scanner_results": {
    "scanner-name": {
      "status": "completed|failed",
      "duration_ms": 0,
      "vulnerabilities_found": 0
    }
  },

  "project_analysis": {
    "tech_stack": {},
    "code_statistics": {}
  }
}
```

### 步骤 7: 生成 Markdown 报告

**使用 Python 脚本转换**：

```bash
# 从 JSON 报告生成 Markdown 报告
python .claude/skills/report-generator/json2md.py .workspace/reports/audit-report.json .workspace/reports/audit-report.md
```

脚本会自动：
- 解析 JSON 报告中的漏洞数据
- 按严重程度分组（Critical/High 详细展示，Medium/Low 表格展示）
- 生成执行摘要、风险评估、修复优先级建议
- 输出格式化的 Markdown 报告

生成到 `.workspace/reports/audit-report.md`：

```markdown
# 代码安全审计报告

## 报告元信息
[Metadata table]

## 执行摘要
[Risk assessment, statistics, key findings]

## 项目概况
[Tech stack, scan coverage]

## Critical 级别漏洞（必须立即修复）
[Detailed vulnerability entries with code examples]

## High 级别漏洞（需要紧急处理）
[Detailed vulnerability entries]

## Medium 级别漏洞（计划修复）
[Table format]

## Low 级别漏洞（后续修复）
[Table format]

## 修复优先级建议
[Action items organized by timeline]

## 扫描器执行详情
[Scanner status table]

## 附录
[Configuration, exclusions, glossary]
```

对于每个 Critical/High 漏洞，包含：

- **基本信息**：类型、CVSS、CWE、位置
- **问题描述**：详细描述
- **漏洞代码**：包含上下文的代码片段
- **利用方式**：利用描述和 PoC
- **修复建议**：修复建议
- **修复后代码**：修复后的代码示例
- **参考链接**：OWASP/CWE 参考

### 步骤 8: 生成优先级建议

**立即行动（24 小时内）**：
- 所有 Critical 漏洞
- 入口点中的 High 漏洞

**短期（1 周内）**：
- 剩余的 High 漏洞
- 关键的 Medium 漏洞

**中期（1 个月内）**：
- 剩余的 Medium 和 Low 漏洞

## 输出要求

### 1. 报告文件

| 文件 | 路径 | 说明 |
|------|------|------|
| Markdown 报告 | `.workspace/reports/audit-report.md` | 面向人工的报告 |
| JSON 报告 | `.workspace/reports/audit-report.json` | 机器可读的报告 |

### 2. 后续任务推荐

报告生成通常是流程终点，无后续任务：

```json
{
  "tasks": []
}
```

**产物流向**：
- 最终审计报告供 orchestrator/人工审阅使用，为后续修复或复验提供依据
