# Vul-AI-V2

基于 Claude Code 的自动化安全审计框架，通过 AI 智能体协作完成代码安全扫描。

## 安装

```bash
# HTTPS 方式
git clone --recursive https://github.com/Clouditera/Vul-AI-V2.git

# SSH 方式
git clone --recursive git@github.com:Clouditera/Vul-AI-V2.git

# 已克隆后初始化子模块
git submodule update --init --recursive
```

## 快速开始

### 1. 链接配置到目标工程

```bash
cd /path/to/target-project
ln -s /path/to/Vul-AI-V2/.claude .claude
source .claude/skills/task-manage/scripts/setup.sh
```

### 2. 启动 Claude Code 并执行审计

```bash
claude
```

在 Claude Code 中输入：

```
@.claude/agents/security-orchestrator.md 审计当前项目
```

系统会自动调用 `security-orchestrator` 智能体进行全流程安全扫描。

## Security Orchestrator

核心编排智能体，负责统筹项目分类并协调子智能体执行安全扫描任务。

### 输入参数

| 参数 | 必填 | 说明 |
|------|------|------|
| 代码仓库 | 是 | 当前工作目录 |
| 扫描器白名单 | 否 | 指定启用的扫描器，如"只启用 sql-injection-analyzer" |
| 扫描器黑名单 | 否 | 指定禁用的扫描器，如"禁用 sensitive-info-scanner" |
| `SCAN_RANGE` | 否 | 子工程分析范围，如"分析前10个子工程"，默认分析前 5 个 |

### 执行流程

```
STEP 1: 工作区扫描 (workspace-scanner)
    ↓
    判断单一项目 / Monorepo
    ↓
STEP 2: 项目画像 (project-profiler)
    ↓
    识别技术栈，推荐扫描器
    ↓
STEP 3: 漏洞扫描 (各类 analyzer)
    ↓
    并行执行推荐的扫描任务
    ↓
STEP 4: 报告生成 (report-generator)
    ↓
    输出 audit-report.md / audit-report.json
```

### 支持的扫描器

| 扫描器 | 检测能力 |
|--------|----------|
| `sql-injection-analyzer` | SQL 注入 |
| `xss-analyzer` | 跨站脚本攻击 |
| `command-injection-analyzer` | 命令注入 |
| `code-injection-analyzer` | 代码注入 |
| `ssrf-analyzer` | 服务端请求伪造 |
| `xxe-analyzer` | XML 外部实体注入 |
| `csrf-analyzer` | 跨站请求伪造 |
| `idor-analyzer` | 不安全的直接对象引用 |
| `path-traversal-lfi-rfi-analyzer` | 路径遍历 / 文件包含 |
| `open-redirect-analyzer` | 开放重定向 |
| `ldap-injection-analyzer` | LDAP 注入 |
| `xml-xpath-injection-analyzer` | XPath 注入 |
| `http-header-injection-analyzer` | HTTP 头注入 |
| `insecure-file-uploads-analyzer` | 不安全文件上传 |
| `sensitive-info-scanner` | 敏感信息泄露 |
| `authentication-analyzer` | 认证机制缺陷 |

### 输出产物

```
.workspace/
├── tasks/
│   └── security-orchestrator-tasks.json  # 任务清单
├── results/                               # 扫描结果
├── findings/                              # 漏洞发现
└── reports/
    ├── audit-report.md                    # 可读报告
    └── audit-report.json                  # 机器可读报告
```

### 使用示例

```
# 完整扫描
@.claude/agents/security-orchestrator.md 审计当前项目

# 指定扫描器
@.claude/agents/security-orchestrator.md 只使用 sql-injection-analyzer 和 xss-analyzer 进行扫描

# Monorepo 指定分析范围
@.claude/agents/security-orchestrator.md 安全审计，分析前10个子工程

# 排除特定扫描器
@.claude/agents/security-orchestrator.md 安全审计，禁用 sensitive-info-scanner
```

## 技能推荐关系图

```mermaid
flowchart TB
    subgraph Agent["智能体层"]
        SO[security-orchestrator]
    end

    subgraph Discovery["发现层"]
        WS[workspace-scanner]
        PP[project-profiler]
    end

    subgraph Analysis["分析层"]
        RS[route-scanner]
        RFA[route-function-analyzer]
        AA[authentication-analyzer]
        VTR[vtr-scanner]
        CSA[code-security-analyzer]
    end

    subgraph Scanners["漏洞扫描层"]
        SQLI[sql-injection-analyzer]
        CMDI[command-injection-analyzer]
        XSS[xss-analyzer]
        SSRF[ssrf-analyzer]
        XXE[xxe-analyzer]
        CSRF[csrf-analyzer]
        IDOR[idor-analyzer]
        REDIRECT[open-redirect-analyzer]
        PATH[path-traversal-lfi-rfi-analyzer]
        LDAPI[ldap-injection-analyzer]
        CODEI[code-injection-analyzer]
        UPLOAD[insecure-file-uploads-analyzer]
    end

    subgraph Output["输出层"]
        BR[bug-report]
        RG[report-generator]
    end

    %% 主流程
    SO --> WS
    WS -->|"子工程"| PP

    %% 项目画像分支
    PP -->|"HTTP服务"| RS
    PP -->|"HTTP服务"| AA
    PP -->|"安全靶场"| VTR

    %% 路由分析流程
    RS --> RFA
    RFA --> CSA

    %% 代码安全分析激活漏洞扫描器
    CSA -.->|"SQL查询"| SQLI
    CSA -.->|"命令执行"| CMDI
    CSA -.->|"页面渲染"| XSS
    CSA -.->|"HTTP请求"| SSRF
    CSA -.->|"XML解析"| XXE
    CSA -.->|"表单提交"| CSRF
    CSA -.->|"资源访问"| IDOR
    CSA -.->|"URL跳转"| REDIRECT
    CSA -.->|"文件操作"| PATH
    CSA -.->|"LDAP查询"| LDAPI
    CSA -.->|"代码执行"| CODEI
    CSA -.->|"文件上传"| UPLOAD

    %% 靶场扫描直接推荐漏洞分析器
    VTR -.->|"题目类型"| SQLI
    VTR -.->|"题目类型"| CMDI
    VTR -.->|"题目类型"| XSS
    VTR -.->|"题目类型"| SSRF
    VTR -.->|"题目类型"| XXE
    VTR -.->|"题目类型"| CSRF
    VTR -.->|"题目类型"| IDOR
    VTR -.->|"题目类型"| REDIRECT
    VTR -.->|"题目类型"| PATH
    VTR -.->|"题目类型"| LDAPI
    VTR -.->|"题目类型"| CODEI
    VTR -.->|"题目类型"| UPLOAD

    %% 漏洞报告输出
    SQLI --> BR
    CMDI --> BR
    XSS --> BR
    SSRF --> BR
    XXE --> BR
    CSRF --> BR
    IDOR --> BR
    REDIRECT --> BR
    PATH --> BR
    LDAPI --> BR
    CODEI --> BR
    UPLOAD --> BR

    %% 最终报告
    BR --> RG

    %% 样式
    classDef agent fill:#e1f5fe,stroke:#01579b
    classDef discovery fill:#f3e5f5,stroke:#4a148c
    classDef analysis fill:#e8f5e9,stroke:#1b5e20
    classDef scanner fill:#fff3e0,stroke:#e65100
    classDef output fill:#fce4ec,stroke:#880e4f

    class SO agent
    class WS,PP discovery
    class RS,RFA,AA,VTR,CSA analysis
    class SQLI,CMDI,XSS,SSRF,XXE,CSRF,IDOR,REDIRECT,PATH,LDAPI,CODEI,UPLOAD scanner
    class BR,RG output
```

### 推荐关系说明

| 上游技能 | 下游技能 | 触发条件 |
|---------|---------|---------|
| workspace-scanner | project-profiler | 每个子工程 |
| project-profiler | route-scanner | HTTP 服务类型 |
| project-profiler | authentication-analyzer | HTTP 服务类型 |
| project-profiler | vtr-scanner | 安全靶场类型 |
| route-scanner | route-function-analyzer | 每个路由文件 |
| route-function-analyzer | code-security-analyzer | 每个 API 端点 |
| code-security-analyzer | 漏洞分析器 | 根据代码风险点激活 |
| vtr-scanner | 漏洞分析器 | 根据靶场题目类型推荐 |
| 漏洞分析器 | bug-report | 发现漏洞时 |

## 目录结构

```
.claude/
├── agents/
│   └── security-orchestrator.md    # 编排智能体
└── skills/
    ├── workspace-scanner/          # 工作区扫描
    ├── project-profiler/           # 项目画像
    ├── route-scanner/              # 路由扫描
    ├── route-function-analyzer/    # 路由功能分析
    ├── code-security-analyzer/     # 代码安全分析
    ├── bug-report/                 # 漏洞报告模板
    ├── report-generator/           # 报告生成
    └── TOP14/                      # 漏洞扫描器
        ├── sql-injection-analyzer/
        ├── xss-analyzer/
        ├── command-injection-analyzer/
        └── ...
```

## License

MIT
