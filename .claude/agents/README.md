# 子代理

> 在 Claude Code 中创建和使用专门的 AI 子代理，用于特定任务工作流和改进的上下文管理。

Claude Code 中的自定义子代理是专门的 AI 助手，可以被调用来处理特定类型的任务。它们通过提供具有自定义系统提示、工具和独立上下文窗口的特定任务配置，实现更高效的问题解决。

## 什么是子代理？

子代理是预配置的 AI 人格，Claude Code 可以将任务委派给它们。每个子代理：

* 具有特定的目的和专业领域
* 使用与主对话分离的自己的上下文窗口
* 可以配置为允许使用特定工具
* 包含指导其行为的自定义系统提示

当 Claude Code 遇到与子代理专业领域相匹配的任务时，它可以将该任务委派给专门的子代理，该子代理独立工作并返回结果。

## 主要优势

<CardGroup cols={2}>
  <Card title="上下文保留" icon="layer-group">
    每个子代理在自己的上下文中运行，防止主对话被污染，并使其专注于高级目标。
  </Card>

  <Card title="专业化专业知识" icon="brain">
    子代理可以使用特定领域的详细说明进行微调，从而提高指定任务的成功率。
  </Card>

  <Card title="可重用性" icon="rotate">
    创建后，子代理可以在不同项目中使用，并与您的团队共享以实现一致的工作流。
  </Card>

  <Card title="灵活的权限" icon="shield-check">
    每个子代理可以具有不同的工具访问级别，允许您将强大的工具限制为特定的子代理类型。
  </Card>
</CardGroup>

## 快速开始

要创建您的第一个子代理：

<Steps>
  <Step title="打开子代理界面">
    运行以下命令：

    ```
    /agents
    ```
  </Step>

  <Step title="选择&#x22;创建新代理&#x22;">
    选择是创建项目级别还是用户级别的子代理
  </Step>

  <Step title="定义子代理">
    * **推荐**：先使用 Claude 生成，然后自定义以使其成为您自己的
    * 详细描述您的子代理及其应该何时使用
    * 选择您想要授予访问权限的工具（或留空以继承所有工具）
    * 该界面显示所有可用工具，使选择变得容易
    * 如果您使用 Claude 生成，您也可以通过按 `e` 在自己的编辑器中编辑系统提示
  </Step>

  <Step title="保存并使用">
    您的子代理现在可用！Claude 会在适当时自动使用它，或者您可以显式调用它：

    ```
    > Use the code-reviewer subagent to check my recent changes
    ```
  </Step>
</Steps>

## 子代理配置

### 文件位置

子代理存储为具有 YAML 前置内容的 Markdown 文件，位置有两个：

| 类型        | 位置                  | 范围       | 优先级 |
| :-------- | :------------------ | :------- | :-- |
| **项目子代理** | `.claude/agents/`   | 在当前项目中可用 | 最高  |
| **用户子代理** | `~/.claude/agents/` | 在所有项目中可用 | 较低  |

当子代理名称冲突时，项目级别的子代理优先于用户级别的子代理。

### 插件代理

[插件](/zh-CN/plugins)可以提供与 Claude Code 无缝集成的自定义子代理。插件代理的工作方式与用户定义的代理相同，并在 `/agents` 界面中显示。

**插件代理位置**：插件在其 `agents/` 目录中包含代理（或插件清单中指定的自定义路径）。

**使用插件代理**：

* 插件代理与您的自定义代理一起显示在 `/agents` 中
* 可以显式调用："Use the code-reviewer agent from the security-plugin"
* 可以在适当时由 Claude 自动调用
* 可以通过 `/agents` 界面进行管理（查看、检查）

有关创建插件代理的详细信息，请参阅[插件组件参考](/zh-CN/plugins-reference#agents)。

### 基于 CLI 的配置

您也可以使用 `--agents` CLI 标志动态定义子代理，该标志接受 JSON 对象：

```bash  theme={null}
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

**优先级**：CLI 定义的子代理的优先级低于项目级别的子代理，但高于用户级别的子代理。

**用例**：此方法适用于：

* 快速测试子代理配置
* 不需要保存的会话特定子代理
* 需要自定义子代理的自动化脚本
* 在文档或脚本中共享子代理定义

有关 JSON 格式和所有可用选项的详细信息，请参阅 [CLI 参考文档](/zh-CN/cli-reference#agents-flag-format)。

### 文件格式

每个子代理在具有以下结构的 Markdown 文件中定义：

```markdown  theme={null}
---
name: your-sub-agent-name
description: Description of when this subagent should be invoked
tools: tool1, tool2, tool3  # Optional - inherits all tools if omitted
model: sonnet  # Optional - specify model alias or 'inherit'
---

Your subagent's system prompt goes here. This can be multiple paragraphs
and should clearly define the subagent's role, capabilities, and approach
to solving problems.

Include specific instructions, best practices, and any constraints
the subagent should follow.
```

#### 配置字段

| 字段            | 必需 | 描述                                                                                                        |
| :------------ | :- | :-------------------------------------------------------------------------------------------------------- |
| `name`        | 是  | 使用小写字母和连字符的唯一标识符                                                                                          |
| `description` | 是  | 子代理目的的自然语言描述                                                                                              |
| `tools`       | 否  | 特定工具的逗号分隔列表。如果省略，继承主线程中的所有工具                                                                              |
| `model`       | 否  | 用于此子代理的模型。可以是模型别名（`sonnet`、`opus`、`haiku`）或 `'inherit'` 以使用主对话的模型。如果省略，默认为[配置的子代理模型](/zh-CN/model-config) |

### 模型选择

`model` 字段允许您控制子代理使用的 [AI 模型](/zh-CN/model-config)：

* **模型别名**：使用可用别名之一：`sonnet`、`opus` 或 `haiku`
* **`'inherit'`**：使用与主对话相同的模型（对于一致性很有用）
* **省略**：如果未指定，使用为子代理配置的默认模型（`sonnet`）

<Note>
  当您希望子代理适应主对话的模型选择，确保整个会话中的功能和响应风格一致时，使用 `'inherit'` 特别有用。
</Note>

### 可用工具

子代理可以被授予访问 Claude Code 任何内部工具的权限。有关可用工具的完整列表，请参阅[工具文档](/zh-CN/settings#tools-available-to-claude)。

<Tip>
  **推荐**：使用 `/agents` 命令修改工具访问权限 - 它提供了一个交互式界面，列出所有可用工具，包括任何连接的 MCP 服务器工具，使选择所需工具变得更容易。
</Tip>

您有两个选项来配置工具：

* **省略 `tools` 字段**以继承主线程中的所有工具（默认），包括 MCP 工具
* **指定单个工具**作为逗号分隔列表以获得更精细的控制（可以手动编辑或通过 `/agents` 编辑）

**MCP 工具**：子代理可以访问来自配置的 MCP 服务器的 MCP 工具。当省略 `tools` 字段时，子代理继承主线程可用的所有 MCP 工具。

## 管理子代理

### 使用 /agents 命令（推荐）

`/agents` 命令提供了一个全面的子代理管理界面：

```
/agents
```

这打开了一个交互式菜单，您可以在其中：

* 查看所有可用的子代理（内置、用户和项目）
* 使用引导式设置创建新子代理
* 编辑现有的自定义子代理，包括其工具访问权限
* 删除自定义子代理
* 查看存在重复项时哪些子代理处于活动状态
* **轻松管理工具权限**，包含所有可用工具的完整列表

### 直接文件管理

您也可以通过直接处理子代理的文件来管理它们：

```bash  theme={null}
# Create a project subagent
mkdir -p .claude/agents
echo '---
name: test-runner
description: Use proactively to run tests and fix failures
---

You are a test automation expert. When you see code changes, proactively run the appropriate tests. If tests fail, analyze the failures and fix them while preserving the original test intent.' > .claude/agents/test-runner.md

# Create a user subagent
mkdir -p ~/.claude/agents
# ... create subagent file
```

## 有效使用子代理

### 自动委派

Claude Code 根据以下因素主动委派任务：

* 您请求中的任务描述
* 子代理配置中的 `description` 字段
* 当前上下文和可用工具

<Tip>
  为了鼓励更多主动的子代理使用，在您的 `description` 字段中包含"use PROACTIVELY"或"MUST BE USED"之类的短语。
</Tip>

### 显式调用

通过在您的命令中提及特定子代理来请求它：

```
> Use the test-runner subagent to fix failing tests
> Have the code-reviewer subagent look at my recent changes
> Ask the debugger subagent to investigate this error
```

## 内置子代理

Claude Code 包括开箱即用的内置子代理：

### Plan 子代理

Plan 子代理是一个专门的内置代理，设计用于计划模式期间使用。当 Claude 在计划模式（非执行模式）中运行时，它使用 Plan 子代理进行研究并收集有关您的代码库的信息，然后再呈现计划。

**主要特征：**

* **模型**：使用 Sonnet 进行更强大的分析
* **工具**：可以访问 Read、Glob、Grep 和 Bash 工具以进行代码库探索
* **目的**：搜索文件、分析代码结构和收集上下文
* **自动调用**：当 Claude 处于计划模式并需要研究代码库时，它会自动使用此代理

**工作原理：**
当您处于计划模式，Claude 需要理解您的代码库以创建计划时，它将研究任务委派给 Plan 子代理。这防止了代理的无限嵌套（子代理不能生成其他子代理），同时仍然允许 Claude 收集必要的上下文。

**示例场景：**

```
User: [In plan mode] Help me refactor the authentication module

Claude: Let me research your authentication implementation first...
[Internally invokes Plan subagent to explore auth-related files]
[Plan subagent searches codebase and returns findings]
Claude: Based on my research, here's my proposed plan...
```

<Tip>
  Plan 子代理仅在计划模式中使用。在正常执行模式中，Claude 使用通用代理或您创建的其他自定义子代理。
</Tip>

## 示例子代理

### 代码审查员

```markdown  theme={null}
---
name: code-reviewer
description: Expert code review specialist. Proactively reviews code for quality, security, and maintainability. Use immediately after writing or modifying code.
tools: Read, Grep, Glob, Bash
model: inherit
---

You are a senior code reviewer ensuring high standards of code quality and security.

When invoked:
1. Run git diff to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:
- Code is simple and readable
- Functions and variables are well-named
- No duplicated code
- Proper error handling
- No exposed secrets or API keys
- Input validation implemented
- Good test coverage
- Performance considerations addressed

Provide feedback organized by priority:
- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider improving)

Include specific examples of how to fix issues.
```

### 调试器

```markdown  theme={null}
---
name: debugger
description: Debugging specialist for errors, test failures, and unexpected behavior. Use proactively when encountering any issues.
tools: Read, Edit, Bash, Grep, Glob
---

You are an expert debugger specializing in root cause analysis.

When invoked:
1. Capture error message and stack trace
2. Identify reproduction steps
3. Isolate the failure location
4. Implement minimal fix
5. Verify solution works

Debugging process:
- Analyze error messages and logs
- Check recent code changes
- Form and test hypotheses
- Add strategic debug logging
- Inspect variable states

For each issue, provide:
- Root cause explanation
- Evidence supporting the diagnosis
- Specific code fix
- Testing approach
- Prevention recommendations

Focus on fixing the underlying issue, not just symptoms.
```

### 数据科学家

```markdown  theme={null}
---
name: data-scientist
description: Data analysis expert for SQL queries, BigQuery operations, and data insights. Use proactively for data analysis tasks and queries.
tools: Bash, Read, Write
model: sonnet
---

You are a data scientist specializing in SQL and BigQuery analysis.

When invoked:
1. Understand the data analysis requirement
2. Write efficient SQL queries
3. Use BigQuery command line tools (bq) when appropriate
4. Analyze and summarize results
5. Present findings clearly

Key practices:
- Write optimized SQL queries with proper filters
- Use appropriate aggregations and joins
- Include comments explaining complex logic
- Format results for readability
- Provide data-driven recommendations

For each analysis:
- Explain the query approach
- Document any assumptions
- Highlight key findings
- Suggest next steps based on data

Always ensure queries are efficient and cost-effective.
```

## 最佳实践

* **从 Claude 生成的代理开始**：我们强烈建议使用 Claude 生成您的初始子代理，然后对其进行迭代以使其成为您自己的。这种方法给您最好的结果 - 一个坚实的基础，您可以自定义以满足您的特定需求。

* **设计专注的子代理**：创建具有单一、明确职责的子代理，而不是尝试让一个子代理做所有事情。这提高了性能并使子代理更可预测。

* **编写详细的提示**：在您的系统提示中包含具体的说明、示例和约束。您提供的指导越多，子代理的表现就越好。

* **限制工具访问**：仅授予子代理目的所需的工具。这提高了安全性并帮助子代理专注于相关操作。

* **版本控制**：将项目子代理检查到版本控制中，以便您的团队可以从中受益并协作改进它们。

## 高级用法

### 链接子代理

对于复杂的工作流，您可以链接多个子代理：

```
> First use the code-analyzer subagent to find performance issues, then use the optimizer subagent to fix them
```

### 动态子代理选择

Claude Code 根据上下文智能地选择子代理。使您的 `description` 字段具体且面向行动以获得最佳结果。

### 可恢复的子代理

子代理可以被恢复以继续之前的对话，这对于需要在多个调用中继续的长期运行的研究或分析任务特别有用。

**工作原理：**

* 每个子代理执行都被分配一个唯一的 `agentId`
* 代理的对话存储在单独的记录文件中：`agent-{agentId}.jsonl`
* 您可以通过 `resume` 参数提供其 `agentId` 来恢复之前的代理
* 恢复时，代理继续使用其之前对话的完整上下文

**示例工作流：**

初始调用：

```
> Use the code-analyzer agent to start reviewing the authentication module

[Agent completes initial analysis and returns agentId: "abc123"]
```

恢复代理：

```
> Resume agent abc123 and now analyze the authorization logic as well

[Agent continues with full context from previous conversation]
```

**用例：**

* **长期运行的研究**：将大型代码库分析分解为多个会话
* **迭代细化**：继续细化子代理的工作而不失去上下文
* **多步工作流**：让子代理在保持上下文的同时顺序处理相关任务

**技术细节：**

* 代理记录存储在您的项目目录中
* 在恢复期间禁用记录以避免重复消息
* 同步和异步代理都可以被恢复
* `resume` 参数接受来自之前执行的代理 ID

**程序化用法：**

如果您使用 Agent SDK 或直接与 AgentTool 交互，您可以传递 `resume` 参数：

```typescript  theme={null}
{
  "description": "Continue analysis",
  "prompt": "Now examine the error handling patterns",
  "subagent_type": "code-analyzer",
  "resume": "abc123"  // Agent ID from previous execution
}
```

<Tip>
  跟踪您可能想要稍后恢复的任务的代理 ID。Claude Code 在子代理完成其工作时显示代理 ID。
</Tip>

## 性能考虑

* **上下文效率**：代理帮助保留主上下文，实现更长的整体会话
* **延迟**：子代理每次调用时都从干净的状态开始，并且可能会增加延迟，因为它们收集有效完成工作所需的上下文。

## 相关文档

* [插件](/zh-CN/plugins) - 通过插件使用自定义代理扩展 Claude Code
* [斜杠命令](/zh-CN/slash-commands) - 了解其他内置命令
* [设置](/zh-CN/settings) - 配置 Claude Code 行为
* [钩子](/zh-CN/hooks) - 使用事件处理程序自动化工作流


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://code.claude.com/docs/llms.txt