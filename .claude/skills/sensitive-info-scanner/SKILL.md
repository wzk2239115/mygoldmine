---
name: sensitive-info-scanner
description: 专业敏感信息泄露审计工作流：以静态代码+配置+日志片段为主，优先识别未加密或未脱敏的密钥/凭据/PII 暴露、配置文件/日志泄漏，以及用户可控输入直接拼接到外部请求/存储路径导致的数据外泄；按编程语言组织的参考指南用于快速判定风险模式与修复要点。
---

## 分析目标

本技能识别两类敏感信息泄露风险：

### 1. 硬编码敏感信息（Hardcoded Secrets）
在源代码、配置文件中查找硬编码的敏感凭据：
- **云服务凭据**：AWS Access Key、GitHub Token、Google API Key
- **数据库凭据**：连接字符串、用户名密码、Redis/MongoDB URI
- **加密密钥**：RSA/SSH 私钥、JWT Secret、API Key
- **个人隐私信息（PII）**：身份证号、手机号、邮箱地址

### 2. 敏感信息泄露函数/代码点（Leaking Functions）
识别会泄露敏感信息到外部的代码：
- **环境变量导出**：`process.env` / `os.environ` 整体导出或过滤不完整
- **配置对象返回**：`app.config` / `settings` 直接序列化返回
- **敏感数据库查询**：批量查询用户表返回未脱敏的敏感字段

## 执行流程

```mermaid
graph TD
    A[开始扫描] --> B[扫描硬编码敏感信息]
    A --> C[扫描泄露函数]
    B --> D[应用过滤规则]
    C --> D
    D --> E[优先级判定]
    E --> F{类型分类}
    F -->|硬编码| G[生成 BUG 报告]
    F -->|泄露函数| H[生成分析文件]
    H --> I[创建深度分析任务]
    G --> J[输出总结]
    I --> J
```

### 步骤 1: 扫描阶段

**1.1 硬编码敏感信息扫描**

使用 Grep 和 Glob 工具搜索常见敏感信息模式：

**云服务凭据扫描**：
- AWS Access Key：使用 Grep 工具，pattern 为 `AKIA[0-9A-Z]{16}`，glob 为 `**/*.{js,ts,py,go,java,php}`，启用 `-i` 选项
- GitHub Token：使用 Grep 工具，pattern 为 `gh[ps]_[0-9a-zA-Z]{36}`，glob 为 `**/*.{js,ts,py,go,java,php}`，启用 `-i` 选项
- Google API Key：使用 Grep 工具，pattern 为 `AIza[0-9A-Za-z_-]{35}`，glob 为 `**/*.{js,ts,py,go,java,php}`，启用 `-i` 选项

**数据库凭据扫描**：
- 数据库连接字符串：使用 Grep 工具，pattern 为 `(mysql|postgresql|mongodb|redis)://[^:]+:[^@]+@`，glob 为 `**/*.{js,ts,py,go,java,env,yml,yaml}`，启用 `-i` 选项

**私钥扫描**：
- RSA/SSH 私钥：使用 Grep 工具，pattern 为 `-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----`，glob 为 `**/*`，启用 `-i` 选项

**配置文件发现**：
- 环境变量文件：使用 Glob 工具，pattern 为 `**/.env*`
- 配置目录文件：使用 Glob 工具，pattern 为 `**/config/*.{yml,yaml,json,properties}`

**1.2 泄露函数扫描**

搜索敏感数据源与输出函数的组合：

**环境变量导出检查（按语言分类）**：

按编程语言识别环境变量读取方法，使用 Grep 工具搜索以下模式：

- **Python**:
  - pattern: `(os\.environ|os\.getenv\()`
  - glob: `**/*.py`
  - 关注点: 整体导出 `os.environ` 或未过滤的批量读取

- **Node.js/JavaScript/TypeScript**:
  - pattern: `process\.env`
  - glob: `**/*.{js,ts,jsx,tsx}`
  - 关注点: 直接返回 `process.env` 对象或传递给外部

- **Java**:
  - pattern: `(System\.getenv\(|System\.getProperty\()`
  - glob: `**/*.java`
  - 关注点: `System.getenv()` 无参数调用返回全部环境变量

- **Go**:
  - pattern: `(os\.Getenv\(|os\.LookupEnv\(|os\.Environ\(|env\.List\()`
  - glob: `**/*.go`
  - 关注点: `os.Environ()`/`env.List()` 会返回全部环境变量集合

- **PHP**:
  - pattern: `(\$_ENV|\$_SERVER|getenv\()`
  - glob: `**/*.php`
  - 关注点: 直接输出 `$_ENV` 或 `$_SERVER` 超全局变量

- **Ruby**:
  - pattern: `(ENV\[|ENV\.fetch\(|ENV\.to_h)`
  - glob: `**/*.rb`
  - 关注点: `ENV.to_h` 返回全部环境变量哈希表

- **C#/.NET**:
  - pattern: `Environment\.(GetEnvironmentVariable|GetEnvironmentVariables)\(`
  - glob: `**/*.cs`
  - 关注点: `GetEnvironmentVariables()` 无参数调用

- **Rust**:
  - pattern: `(env::var\(|env::vars\()`
  - glob: `**/*.rs`
  - 关注点: `env::vars()` 返回全部环境变量迭代器

- **Shell/Bash**:
  - pattern: `(printenv|export|env\s*\||set\s*\|)`
  - glob: `**/*.{sh,bash,zsh}`
  - 关注点: `printenv` 或 `env` 命令输出到日志/响应

### 步骤 2: 过滤与判定

**2.1 误报过滤规则**

排除以下情况：
- 文件路径包含：`tests/`, `__tests__/`, `spec/`, `fixtures/`, `examples/`, `docs/`
- 值包含占位符：`YOUR_*_HERE`, `<INSERT_*>`, `REPLACE_ME`, `example`, `test`, `demo`
- 已知公开示例：`AKIAIOSFODNN7EXAMPLE`（AWS 官方示例）

**2.2 优先级判定决策树**

```
是否泄露系统级敏感信息？
├─ 是 → 私钥/数据库密码/云服务凭据/完整环境变量 → P0 Critical
└─ 否 → 是否泄露业务敏感信息？
    ├─ 是 → JWT Secret/API Key/配置信息/用户隐私 → P1 High
    └─ 否 → 低敏感信息/测试占位符/文档示例 → P2 Medium/Low
```

**优先级规则**：
- **P0 Critical**: 系统级敏感信息（私钥/DB密码/云凭据/环境变量导出）
- **P1 High**: 业务敏感信息（JWT Secret/API Key/配置/用户数据）
- **P2 Medium**: 低敏感信息、测试示例、未对外暴露的凭证

**分组规则**：
- 相同硬编码敏感信息类型的发现为一组，例如：RSA/SSH 私钥被发现，全部归为一组。

### 步骤 3: 报告生成（以分组为单位）

**3.1 硬编码敏感信息 → BUG 报告**

对于硬编码敏感信息的发现，使用 Skill 工具调用 bug-report 技能生成漏洞报告：

**调用方式**：
- 使用 `Skill` 工具，参数 `skill` 设置为 `"bug-report"`
- bug-report 技能会自动加载并按照其模板格式生成漏洞报告文件
- 确保在调用前准备好完整的漏洞上下文信息（文件路径、行号、敏感信息类型、优先级等）

**报告要求**：
- 严格遵循 bug-report 技能定义的模板格式
- 每个分组生成一个独立的漏洞报告文件
- 文件命名格式：`.workspace/tasks/{TASK_ID}/bug-{type}-{priority}.md`

**3.2 泄露函数 → 分析文件 + 下游任务**

生成中间分析文件供 `sensitive-deep-analyzer` 使用：

```markdown
文件路径：`.workspace/tasks/{TASK_ID}/sensitive-leak-{priority}-group{N}.md`

# 敏感信息扫描结果 - 泄露函数 - {Priority} 级别 (第 {N} 组)

## [FINDING-{ID}] {leaksWhat} 泄露风险点
- {file}:{line}
- {file2}:{line2}
- ...
```

**总结输出格式（JSON）**：
```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/sensitive-leak-P0-group1.md",
      "skill": "sensitive-deep-analyzer",
      "dependencies": [
        ".workspace/tasks/{WEB_AUTH_TASK_ID}/web-auth-analyzer.md",
        ".workspace/tasks/{UNAUTH_ROUTE_SCANNER_TASK_ID}/unauth-route-scanner.md",
        ".workspace/tasks/{NORMAL_ROUTE_SCANNER_TASK_ID}/normal-route-scanner.md"
      ]
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/sensitive-leak-P1-group1.md",
      "skill": "sensitive-deep-analyzer",
      "dependencies": [
        ".workspace/tasks/{WEB_AUTH_TASK_ID}/web-auth-analyzer.md",
        ".workspace/tasks/{UNAUTH_ROUTE_SCANNER_TASK_ID}/unauth-route-scanner.md",
        ".workspace/tasks/{NORMAL_ROUTE_SCANNER_TASK_ID}/normal-route-scanner.md"
      ]
    }
  ]
}
```