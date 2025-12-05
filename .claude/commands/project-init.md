---
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion, TodoWrite
description: Initialize new project with best practices and standard structure
argument-hint: <project-name> [--type=<node|python|react>]
---


# 🚀 项目初始化助手（基于 PRD 自动初始化完整仓库）

## 🎯 目标

你是一名 **顶级 AI 软件工程师 + 项目初始化助手**，负责基于用户提供的 **PRD / 项目背景 / 开发目标**，一次性输出一个新的软件工程仓库的 **完整初始化结构**。

你的输出内容将被直接写入仓库，因此必须 **标准化、严谨、可直接使用**。


## 📋 PRD 解析和验证（第一步）

在开始初始化之前，必须先解析和验证 PRD 文档：

### **0.1 PRD 信息提取**

从 PRD 文档中自动提取以下关键信息：

- **技术栈识别**：
  - 从 PRD 的"技术栈"、"整体功能模块"、"非功能性需求"等章节提取
  - 识别主要编程语言（Python/Node.js/Java/Go/Rust等）
  - 识别框架和库（FastAPI/Express/Spring Boot等）
  - 识别构建工具（Maven/Gradle/npm/yarn/cargo/go mod等）

- **项目类型识别**：
  - 后端 API 服务（RESTful/GraphQL/gRPC）
  - 前端应用（Web/Mobile/Desktop）
  - 全栈应用
  - CLI 工具
  - 库/包（Library/Package）
  - 微服务
  - 其他类型

- **依赖需求提取**：
  - 数据库（PostgreSQL/MySQL/MongoDB/Redis等）
  - 消息队列（RabbitMQ/Kafka等）
  - 缓存（Redis/Memcached等）
  - 外部服务（第三方 API、云服务等）

- **部署方式识别**：
  - Docker 容器化
  - Kubernetes
  - Serverless（AWS Lambda/Cloud Functions等）
  - 传统部署
  - 混合部署

### **0.2 PRD 完整性验证**

检查 PRD 是否包含以下必要信息，如果缺失则提示用户补充：

- ✅ 技术栈信息（必须）
- ✅ 功能模块划分（必须）
- ✅ 非功能性需求（必须）
- ⚠️ 输入/输出规范（建议）
- ⚠️ 部署要求（建议）
- ⚠️ 依赖关系（建议）

如果关键信息不足，必须暂停并提示：

> "PRD 中缺少 [具体缺失项]，请补充后再继续初始化。"


## 📋 执行任务清单

当用户提供 PRD 时，你必须自动执行以下工作：

### **1. 在仓库根目录创建 `.cursor/` 目录结构**

- `.cursor/rules/*.mdc`
- `.cursor/commands/*.mdc`

包含：
- 项目级开发规则
- AI 协作规则
- TDD 规范
- Spec-Driven 开发
- 复杂功能预案机制
- backend/frontend/agent/sdk/workflow 各子规则
- 统一 instructions 格式


### **2. 生成 README.md**

包括：
- 项目介绍
- 背景与目标
- 核心特性
- 技术栈
- 仓库目录结构
- 本地开发指南
- 虚拟环境初始化步骤
- 代码规范
- 测试规范
- 贡献指南
- License


### **3. 初始化目录结构**

根据识别的技术栈和项目类型，生成对应的目录结构：

#### **Python 项目结构**

```
project-name/
├── src/                    # 主代码
│   ├── project_name/       # 项目主包
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/            # API 路由（如适用）
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   ├── utils/          # 工具函数（含 logger.py）
│   │   └── config/         # 配置模块
│   └── ...
├── tests/
│   ├── unit/               # 单元测试（与 src 目录镜像）
│   │   └── src/
│   ├── integration/        # 集成测试
│   └── fixtures/           # 测试数据
├── docs/
│   ├── specs/{feature}/    # 功能规格文档
│   └── api/                # API 文档（如适用）
├── config/                 # 配置文件
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
├── data/                   # 数据文件
├── logs/                   # 日志文件
├── scripts/                # 辅助脚本
└── ...
```

#### **Node.js/TypeScript 项目结构**

```
project-name/
├── src/
│   ├── index.ts            # 入口文件
│   ├── app.ts              # 应用主文件
│   ├── controllers/       # 控制器
│   ├── services/           # 业务逻辑
│   ├── models/             # 数据模型
│   ├── routes/             # 路由
│   ├── middleware/         # 中间件
│   ├── utils/              # 工具函数（含 logger）
│   ├── types/              # TypeScript 类型定义
│   └── config/             # 配置模块
├── tests/
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   └── fixtures/           # 测试数据
├── docs/
│   ├── specs/{feature}/
│   └── api/
├── config/
│   ├── dev.json
│   ├── staging.json
│   └── prod.json
├── public/                 # 静态资源（如适用）
├── dist/                   # 编译输出
└── ...
```

#### **Java 项目结构（Maven）**

```
project-name/
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/company/project/
│   │   │       ├── Application.java
│   │   │       ├── controller/    # 控制器
│   │   │       ├── service/       # 业务逻辑
│   │   │       ├── model/         # 数据模型
│   │   │       ├── repository/    # 数据访问
│   │   │       ├── config/        # 配置类
│   │   │       └── util/          # 工具类
│   │   └── resources/
│   │       ├── application.yml
│   │       └── ...
│   └── test/
│       ├── java/           # 测试代码（镜像 main 结构）
│       └── resources/     # 测试资源
├── docs/
│   ├── specs/{feature}/
│   └── api/
└── ...
```

#### **Go 项目结构**

```
project-name/
├── cmd/                    # 可执行文件
│   └── app/
│       └── main.go
├── internal/               # 内部包
│   ├── api/                # API 处理
│   ├── service/            # 业务逻辑
│   ├── model/              # 数据模型
│   ├── repository/         # 数据访问
│   ├── config/             # 配置
│   └── util/               # 工具函数
├── pkg/                    # 可导出的包
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── specs/{feature}/
│   └── api/
├── config/
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
└── ...
```

#### **Rust 项目结构**

```
project-name/
├── src/
│   ├── main.rs             # 可执行入口
│   ├── lib.rs              # 库入口（如适用）
│   ├── api/                # API 模块
│   ├── service/            # 业务逻辑
│   ├── model/              # 数据模型
│   ├── config/             # 配置
│   └── util/               # 工具函数
├── tests/                  # 集成测试
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── specs/{feature}/
│   └── api/
├── config/
│   ├── dev.toml
│   ├── staging.toml
│   └── prod.toml
└── ...
```

#### **通用目录（所有技术栈）**

所有项目都应包含：
- `docs/dev/{feature}/`：功能规格文档（规范驱动开发）
- `docs/api/`：API 文档（如适用）
- `config/`：配置文件目录
- `tests/unit/`：单元测试
- `tests/integration/`：集成测试
- `logs/`：日志文件目录
- `scripts/`：辅助脚本目录
- `.cursor/`：Claude Code 规则和命令配置


### **4. 初始化主要代码结构**

在创建目录结构后，根据识别的技术栈和项目类型，生成基础代码文件和模块结构：

#### **Python 项目基础代码**

- `src/{project_name}/__init__.py`：项目主包初始化文件
- `src/{project_name}/main.py`：应用入口文件（包含基础启动逻辑）
- `src/{project_name}/config/__init__.py`：配置模块
  - `config.py`：配置加载和解析
- `src/{project_name}/utils/__init__.py`：工具模块
  - `logger.py`：统一日志模块（RichHandler）
  - `exceptions.py`：自定义异常类
- `src/{project_name}/api/__init__.py`：API 模块（如适用）
  - `routes.py`：路由定义（基础结构）
- `src/{project_name}/models/__init__.py`：数据模型模块（如适用）
- `src/{project_name}/services/__init__.py`：业务逻辑模块（如适用）

所有文件都应包含：
- 基础导入语句
- 类型注解
- 文档字符串（中文）
- 符合规范的代码结构

#### **Node.js/TypeScript 项目基础代码**

- `src/index.ts`：应用入口文件（包含基础启动逻辑）
- `src/app.ts`：应用主文件（Express/NestJS 等框架初始化）
- `src/config/index.ts`：配置模块
  - 配置加载和类型定义
- `src/utils/logger.ts`：统一日志模块
- `src/utils/exceptions.ts`：自定义异常类
- `src/types/index.ts`：TypeScript 类型定义
- `src/routes/index.ts`：路由定义（基础结构，如适用）
- `src/middleware/`：中间件目录（如适用）

所有文件都应包含：
- 完整的类型注解
- JSDoc 注释
- 符合规范的代码结构

#### **Java 项目基础代码**

- `src/main/java/com/company/project/Application.java`：Spring Boot 主类（如适用）
- `src/main/java/com/company/project/config/`：配置类
  - `ApplicationConfig.java`：应用配置
- `src/main/java/com/company/project/util/`：工具类
  - `LoggerUtil.java`：日志工具类
  - `CustomException.java`：自定义异常
- `src/main/java/com/company/project/controller/`：控制器（如适用）
  - `BaseController.java`：基础控制器
- `src/main/java/com/company/project/service/`：服务层（如适用）
- `src/main/java/com/company/project/model/`：数据模型（如适用）

所有文件都应包含：
- JavaDoc 注释
- 完整的类型声明
- 符合规范的代码结构

#### **Go 项目基础代码**

- `cmd/app/main.go`：应用入口文件（包含基础启动逻辑）
- `internal/config/config.go`：配置模块
- `internal/util/logger.go`：统一日志模块
- `internal/util/errors.go`：自定义错误类型
- `internal/api/handler.go`：API 处理器（如适用）

所有文件都应包含：
- 完整的注释（godoc 格式）
- 明确的错误处理
- 符合规范的代码结构

#### **Rust 项目基础代码**

- `src/main.rs`：应用入口文件（包含基础启动逻辑）
- `src/config.rs`：配置模块
- `src/util/mod.rs`：工具模块
  - `logger.rs`：日志模块
  - `errors.rs`：错误类型

所有文件都应包含：
- 完整的文档注释（///）
- 明确的错误类型
- 符合规范的代码结构

**注意**：生成的基础代码应该是可运行的骨架代码，包含必要的导入、基础结构和注释，但不包含具体业务逻辑实现。


### **5. 生成技术设计文档**

在生成 tasks.md 之前，必须先完成技术设计文档，确保架构和设计思路清晰：

#### **5.1 生成 `docs/project/{project}/v{version}/architecture.md`（系统架构文档）

包含：
- **系统架构概览**：
  - 整体架构图（Mermaid 格式）
  - 技术栈选型说明
  - 架构设计原则

- **模块划分**：
  - 核心模块列表
  - 模块职责说明
  - 模块间依赖关系图

- **数据流设计**：
  - 数据流向图
  - 关键数据模型
  - 数据存储方案

- **接口设计**（如适用）：
  - API 接口概览
  - 接口设计原则
  - 接口版本管理策略

- **安全设计**：
  - 认证授权方案
  - 数据安全措施
  - 安全边界定义

- **性能设计**：
  - 性能目标
  - 性能优化策略
  - 缓存策略

- **可扩展性设计**：
  - 扩展点设计
  - 插件机制（如适用）
  - 水平扩展方案

#### **5.2 生成 `docs/project/{project}/v{version}/design.md`（技术设计文档）**

包含：
- **设计目标**：
  - 设计要解决的问题
  - 设计约束条件
  - 设计原则

- **技术选型**：
  - 框架选型及理由
  - 数据库选型及理由
  - 中间件选型及理由
  - 第三方服务选型及理由

- **核心模块设计**：
  - 每个核心模块的详细设计
  - 模块接口定义
  - 模块实现思路

- **数据模型设计**：
  - 数据库表结构（如适用）
  - 数据模型类设计
  - 数据关系图

- **API 设计**（如适用）：
  - API 端点列表
  - 请求/响应格式
  - 错误码定义
  - API 文档链接

- **部署架构**：
  - 部署环境说明
  - 容器化方案（如适用）
  - CI/CD 流程

- **监控和日志**：
  - 日志策略
  - 监控指标
  - 告警规则

- **风险与应对**：
  - 技术风险识别
  - 风险应对方案
  - 备选方案

**注意**：技术设计文档必须基于 PRD 生成，确保设计与需求一致。设计文档完成后，需要用户审阅确认，才能进入任务分解阶段。


### **6. 生成 DEV_GUIDE.md**

包含：
- Python 开发规范
- import 顺序
- 日志规范
- Docstring 规范（Google 风格）
- 复杂功能预案机制
- TDD 规范
- 测试组织结构
- Git 分支策略
- Commit Message 规范
- 安全规范
- 性能优化规范
- 代码审查 Checklist


### **7. 生成 tasks.md（首批开发任务）**

**重要**：只有在技术设计文档（`docs/project/{project}/v{version}/architecture.md` 和 `docs/project/{project}/v{version}/design.md`）确认后，才能生成 tasks.md。

基于 PRD 和技术设计文档自动提取：
- **模块划分**：根据 `docs/project/{project}/v{version}/architecture.md` 中的模块划分
- **每个模块的开发任务**：
  - 任务编号和名称
  - 任务描述
  - 依赖关系（前置任务）
  - 优先级（P0/P1/P2）
- **每个任务包含**：
  - 目标：任务要达成的目标
  - 输入/输出：任务的输入和输出
  - 技术方案：基于 `docs/project/{project}/v{version}/design.md` 的技术方案
  - 阶段划分：需求 → 设计 → 实现 → 测试
  - 是否触发"复杂功能预案机制"
  - 是否需要 TDD
  - 验收标准：如何验证任务完成
  - 预估工作量：人日估算

- **任务依赖关系图**：使用 Mermaid 展示任务间的依赖关系

- **里程碑规划**：
  - MVP 阶段任务
  - V1.0 阶段任务
  - 后续版本任务

**注意**：tasks.md 必须基于已确认的技术设计文档（`docs/project/{project}/v{version}/architecture.md` 和 `docs/project/{project}/v{version}/design.md`）生成，确保任务与技术设计一致。


### **8. 初始化依赖管理文件**

根据识别的技术栈自动生成对应的依赖管理文件：

#### **Python 项目**

- `requirements.txt`：基础依赖列表（包含版本号）
- `requirements-dev.txt`：开发依赖（测试工具、代码质量工具等）
- `pyproject.toml`：如果使用现代 Python 项目结构（PEP 518）
- `poetry.lock`：如果使用 Poetry 作为包管理器
- `setup.py` / `setup.cfg`：如果项目是可安装的包

包含基础依赖占位符和开发依赖占位符。

#### **Node.js/TypeScript 项目**

- `package.json`：包含项目元数据、依赖、脚本
- `package-lock.json`：npm 锁文件（如果使用 npm）
- `yarn.lock`：Yarn 锁文件（如果使用 Yarn）
- `pnpm-lock.yaml`：pnpm 锁文件（如果使用 pnpm）

包含基础依赖（如框架、数据库驱动等）和开发依赖（测试框架、代码质量工具等）。

#### **Java 项目**

- `pom.xml`：如果使用 Maven
  - 包含基础依赖（Spring Boot、数据库驱动等）
  - 包含开发依赖（测试框架、代码质量工具等）
- `build.gradle` / `build.gradle.kts`：如果使用 Gradle
  - 包含依赖配置和插件配置
- `settings.gradle`：Gradle 项目设置（如适用）

#### **Go 项目**

- `go.mod`：Go 模块定义文件
- `go.sum`：依赖校验和文件
- 包含基础依赖和开发依赖

#### **Rust 项目**

- `Cargo.toml`：Rust 项目配置文件
- `Cargo.lock`：依赖锁文件
- 包含基础依赖（dependencies）和开发依赖（dev-dependencies）

所有依赖管理文件都应包含：
- 基础运行时依赖（根据 PRD 识别的依赖需求）
- 开发工具依赖（测试框架、代码质量工具、构建工具等）
- 适当的版本约束


### **9. 初始化版本控制配置**

生成版本控制相关配置文件：

- **`.gitignore`**：根据识别的技术栈生成对应的忽略规则
  - Python: `.gitignore` 包含 `__pycache__/`, `*.pyc`, `venv/`, `.env` 等
  - Node.js: 包含 `node_modules/`, `dist/`, `.env` 等
  - Java: 包含 `target/`, `*.class`, `.idea/` 等
  - Go: 包含 `vendor/`, `*.exe` 等
  - Rust: 包含 `target/`, `Cargo.lock`（如适用）等
  - 通用: `logs/`, `.DS_Store`, `*.log` 等

- **`.gitattributes`**：统一换行符、文件属性等
  - 设置文本文件的换行符（LF）
  - 设置二进制文件的属性
  - 设置特定文件类型的处理方式

**注意**：不自动执行 `git init`，只生成配置文件，由用户决定何时初始化 Git 仓库。


### **10. 初始化环境配置**

生成环境配置文件：

- **`.env.example`**：环境变量模板文件
  - 包含必要的环境变量占位符
  - 包含注释说明每个变量的用途
  - 不包含敏感信息（密码、密钥等）

- **`config/` 目录结构**：
  - `config/dev.yaml` / `config/dev.json`：开发环境配置
  - `config/staging.yaml` / `config/staging.json`：预发布环境配置
  - `config/prod.yaml` / `config/prod.json`：生产环境配置
  - `config/base.yaml` / `config/base.json`：基础配置（可选）

- **配置加载代码示例**：
  - 根据技术栈生成对应的配置加载代码示例
  - Python: 使用 `python-dotenv` 或 `pydantic-settings`
  - Node.js: 使用 `dotenv` 或配置管理库
  - Java: 使用 Spring Boot 配置或自定义配置加载
  - Go: 使用 `viper` 或标准库
  - Rust: 使用 `config` 或 `dotenv`


### **11. 生成可选的工程基础设施**

根据识别的技术栈和项目需求，自动生成以下基础设施配置：

#### **代码质量工具配置**

**Python 项目**：
- `.editorconfig`：编辑器配置（统一缩进、换行符等）
- `.prettierrc`：如果使用 Prettier（可选）
- `.flake8` / `setup.cfg`：Flake8 配置
- `.pylintrc`：Pylint 配置（可选）
- `ruff.toml`：Ruff 配置（如果使用 Ruff）
- `mypy.ini`：mypy 类型检查配置
- `.bandit`：Bandit 安全扫描配置
- `.pre-commit-config.yaml`：pre-commit 钩子配置

**Node.js/TypeScript 项目**：
- `.editorconfig`：编辑器配置
- `.prettierrc` / `.prettierrc.json`：Prettier 配置
- `.prettierignore`：Prettier 忽略文件
- `.eslintrc.js` / `.eslintrc.json`：ESLint 配置
- `.eslintignore`：ESLint 忽略文件
- `tsconfig.json`：TypeScript 配置（如果使用 TypeScript）
- `.husky/`：Git hooks 配置（如果使用 Husky）

**Java 项目**：
- `.editorconfig`：编辑器配置
- `checkstyle.xml`：Checkstyle 配置
- `spotbugs-exclude.xml`：SpotBugs 排除配置
- `pom.xml` 或 `build.gradle` 中的插件配置

**Go 项目**：
- `.editorconfig`：编辑器配置
- `.golangci.yml`：golangci-lint 配置
- `.golangci.yml` 中的规则配置

**Rust 项目**：
- `.editorconfig`：编辑器配置
- `rustfmt.toml`：rustfmt 配置
- `clippy.toml`：Clippy 配置
- `.cargo/config.toml`：Cargo 配置（可选）

#### **测试框架配置**

**Python 项目**：
- `pytest.ini` / `pyproject.toml`：pytest 配置
  - 包含 fast/slow test 标记配置
  - 覆盖率配置
  - 测试发现规则
- `conftest.py`：pytest 共享配置和 fixture
- `tox.ini`：tox 多环境测试配置（可选）
- `.coveragerc`：覆盖率报告配置

**Node.js/TypeScript 项目**：
- `jest.config.js` / `jest.config.ts`：Jest 配置
- `vitest.config.ts`：Vitest 配置（如果使用 Vitest）
- `setupTests.ts` / `setupTests.js`：测试环境设置
- `.nycrc.json`：代码覆盖率配置（如果使用 nyc）

**Java 项目**：
- `pom.xml` 中的测试配置（JUnit 5、TestNG 等）
- `build.gradle` 中的测试配置
- `src/test/resources/`：测试资源目录

**Go 项目**：
- `*_test.go` 模板和测试工具配置
- 测试辅助工具配置（如 `testify`）

**Rust 项目**：
- `Cargo.toml` 中的测试配置
- 测试工具和宏的使用示例

#### **容器化配置**

如 PRD 涉及容器化部署：
- `Dockerfile`：根据技术栈生成对应的 Dockerfile
- `docker-compose.yml`：开发环境容器编排
- `.dockerignore`：Docker 构建忽略文件

#### **CI/CD 配置**

如 PRD 涉及 CI/CD：
- `.github/workflows/`：GitHub Actions 工作流
  - `ci.yml`：持续集成配置
  - `cd.yml`：持续部署配置（如适用）
- `.gitlab-ci.yml`：GitLab CI 配置（如适用）
- 根据技术栈生成对应的构建、测试、部署步骤

#### **其他基础设施**

- `Makefile`：常用命令快捷方式（可选）
- `scripts/`：辅助脚本目录
- `docs/`：文档目录结构

所有配置文件都应包含注释说明，保持简洁但完整。


### **12. 初始化 API 文档工具（如果项目是 API 服务）**

如果 PRD 中识别出项目是 API 服务（RESTful/GraphQL/gRPC），则自动生成 API 文档相关配置：

#### **Python API 项目**

**FastAPI**：
- `docs/api/`：API 文档目录
- OpenAPI/Swagger 自动生成配置（FastAPI 内置）
- `docs/api/openapi.json`：OpenAPI 规范文件（可选）
- API 路由示例和文档字符串模板

**Flask**：
- `docs/api/`：API 文档目录
- Flask-RESTX 或 Flask-Swagger-UI 配置
- OpenAPI/Swagger 配置
- API 路由示例和文档字符串模板

**Django REST Framework**：
- `docs/api/`：API 文档目录
- DRF 的 OpenAPI 配置
- API 视图示例和文档模板

#### **Node.js/TypeScript API 项目**

**Express**：
- `docs/api/`：API 文档目录
- Swagger/OpenAPI 配置（使用 `swagger-jsdoc` 或 `swagger-ui-express`）
- `swagger.yaml` / `swagger.json`：OpenAPI 规范文件
- API 路由示例和 JSDoc 注释模板

**NestJS**：
- `docs/api/`：API 文档目录
- Swagger/OpenAPI 配置（使用 `@nestjs/swagger`）
- API 装饰器和文档示例

**Koa**：
- `docs/api/`：API 文档目录
- Swagger/OpenAPI 配置
- API 路由示例和文档模板

#### **Java API 项目**

**Spring Boot**：
- `docs/api/`：API 文档目录
- SpringDoc OpenAPI 配置（`springdoc-openapi-ui`）
- `application.yml` 中的 Swagger 配置
- API 控制器示例和注解模板

**JAX-RS**：
- `docs/api/`：API 文档目录
- Swagger/OpenAPI 配置
- API 资源类示例和注解模板

#### **通用 API 文档配置**

所有 API 项目都应包含：
- `docs/api/README.md`：API 文档说明
- API 文档生成脚本或配置
- API 版本管理说明（如适用）
- API 认证/授权文档模板（如适用）

#### **GraphQL API 项目**

如果识别为 GraphQL API：
- `docs/api/schema.graphql`：GraphQL Schema 文件
- GraphQL 文档工具配置（如 GraphQL Playground、GraphiQL）
- Schema 文档生成配置

#### **gRPC API 项目**

如果识别为 gRPC API：
- `proto/`：Protocol Buffers 定义目录
- `docs/api/`：gRPC API 文档目录
- gRPC 文档生成工具配置


### **13. 初始化数据库迁移工具（如果项目涉及数据库）**

如果 PRD 中识别出项目使用数据库，则自动生成数据库迁移工具配置：

#### **Python 项目**

**SQLAlchemy + Alembic**：
- `alembic.ini`：Alembic 配置文件
- `alembic/`：迁移脚本目录
  - `alembic/env.py`：迁移环境配置
  - `alembic/script.py.mako`：迁移脚本模板
  - `alembic/versions/`：迁移版本目录
- `alembic/versions/001_initial.py`：初始迁移脚本模板
- 数据库连接配置示例

**Django**：
- Django 内置迁移系统配置
- `migrations/` 目录结构
- 初始迁移脚本模板

#### **Node.js/TypeScript 项目**

**TypeORM**：
- `ormconfig.js` / `ormconfig.ts`：TypeORM 配置
- `src/migrations/`：迁移脚本目录
- 迁移脚本模板

**Sequelize**：
- `sequelize.config.js`：Sequelize 配置
- `migrations/`：迁移脚本目录
- 迁移脚本模板

**Prisma**：
- `prisma/schema.prisma`：Prisma Schema 文件
- `prisma/migrations/`：迁移脚本目录
- Prisma 客户端生成配置

#### **Java 项目**

**Flyway**：
- `src/main/resources/db/migration/`：Flyway 迁移脚本目录
- `V1__Initial_schema.sql`：初始迁移脚本模板
- `application.yml` 中的 Flyway 配置

**Liquibase**：
- `src/main/resources/db/changelog/`：Liquibase 变更日志目录
- `db.changelog-master.xml`：主变更日志文件
- `application.yml` 中的 Liquibase 配置

#### **Go 项目**

**golang-migrate**：
- `migrations/`：迁移脚本目录
  - `000001_initial.up.sql`：初始迁移（向上）
  - `000001_initial.down.sql`：初始迁移（向下）
- 迁移工具配置示例

**GORM AutoMigrate**：
- 自动迁移配置示例
- 迁移脚本模板（如需要手动迁移）

#### **通用数据库迁移配置**

所有项目都应包含：
- 数据库连接配置示例
- 迁移命令说明（README 或 Makefile）
- 回滚策略说明
- 迁移版本管理说明


### **14. 初始化健康检查端点（如果项目是 API 服务）**

如果项目是 API 服务，自动生成健康检查相关端点：

#### **Python API 项目**

**FastAPI**：
- `src/{project_name}/api/health.py`：健康检查路由
  - `/health`：基础健康检查
  - `/ready`：就绪检查（检查数据库连接等）
  - `/live`：存活检查
- 健康检查响应格式（JSON）

**Flask**：
- `src/{project_name}/api/health.py`：健康检查蓝图
- 健康检查路由和响应格式

**Django**：
- `src/{project_name}/api/views/health.py`：健康检查视图
- URL 配置

#### **Node.js/TypeScript API 项目**

**Express**：
- `src/routes/health.ts`：健康检查路由
- 健康检查中间件（如适用）

**NestJS**：
- `src/health/health.controller.ts`：健康检查控制器
- `@nestjs/terminus` 配置（如使用）

#### **Java API 项目**

**Spring Boot**：
- `src/main/java/.../controller/HealthController.java`：健康检查控制器
- Spring Boot Actuator 配置（如使用）
  - `/actuator/health`：健康检查端点
  - `/actuator/info`：应用信息端点

#### **Go API 项目**

- `internal/api/health.go`：健康检查处理器
- 健康检查路由配置

#### **通用健康检查配置**

所有 API 项目都应包含：
- 健康检查响应格式标准（JSON）
- 健康检查状态码定义（200/503 等）
- 依赖检查逻辑（数据库、缓存、外部服务等）
- 健康检查文档说明


### **15. 生成 LICENSE 和 CHANGELOG**

#### **LICENSE 文件**

根据项目需求生成合适的许可证文件：
- `LICENSE` 或 `LICENSE.txt`：许可证文件
- 常见许可证选项：
  - MIT License（推荐用于开源项目）
  - Apache License 2.0
  - GPL v3
  - 商业许可证（如适用）
- 在 README.md 中引用许可证

#### **CHANGELOG.md**

生成变更日志模板：
- `CHANGELOG.md`：变更日志文件
- 遵循 [Keep a Changelog](https://keepachangelog.com/) 格式
- 包含以下部分：
  - `[Unreleased]`：未发布版本
  - `[版本号] - YYYY-MM-DD`：已发布版本
  - 变更类型：
    - `Added`：新增功能
    - `Changed`：变更
    - `Deprecated`：废弃
    - `Removed`：移除
    - `Fixed`：修复
    - `Security`：安全相关
- 初始版本占位符


### **16. 初始化 GitHub/GitLab 模板**

#### **GitHub 模板**

如果项目使用 GitHub，生成以下模板：

**Issue 模板**：
- `.github/ISSUE_TEMPLATE/`：Issue 模板目录
  - `bug_report.md`：Bug 报告模板
  - `feature_request.md`：功能请求模板
  - `config.yml`：Issue 模板配置（可选）

**PR 模板**：
- `.github/pull_request_template.md`：PR 模板
  - 包含：变更描述、测试说明、检查清单等

**安全策略**：
- `.github/SECURITY.md`：安全策略文档
  - 安全漏洞报告流程
  - 联系方式

**贡献指南**：
- `CONTRIBUTING.md`：贡献指南（如果 README 中未详细说明）
  - 开发环境设置
  - 代码提交规范
  - PR 流程
  - 代码审查指南

#### **GitLab 模板**

如果项目使用 GitLab，生成以下模板：

**Issue 模板**：
- `.gitlab/issue_templates/`：Issue 模板目录
  - `bug.md`：Bug 报告模板
  - `feature.md`：功能请求模板

**Merge Request 模板**：
- `.gitlab/merge_request_templates/`：MR 模板目录
  - `default.md`：默认 MR 模板

**贡献指南**：
- `CONTRIBUTING.md`：贡献指南


### **17. 初始化监控和可观测性基础配置**

根据 PRD 中的可观测性需求，生成监控和日志配置：

#### **日志配置**

**Python 项目**：
- 统一日志格式配置（JSON 格式，便于日志聚合）
- 日志级别配置（DEBUG/INFO/WARNING/ERROR）
- 日志轮转配置（RotatingFileHandler）
- 结构化日志示例（使用 `structlog` 或类似库）

**Node.js/TypeScript 项目**：
- Winston 或 Pino 配置
- 日志格式配置（JSON）
- 日志级别和输出配置

**Java 项目**：
- Logback 或 Log4j2 配置
- `logback-spring.xml` 或 `log4j2.xml`
- 日志格式和级别配置

**Go 项目**：
- 日志库配置（logrus/zap）
- 日志格式和级别配置

**Rust 项目**：
- tracing 或 log 配置
- 日志格式和级别配置

#### **指标监控配置**

**Prometheus 指标**：
- 如果使用 Prometheus，生成指标收集配置
- Python: `prometheus_client` 配置示例
- Node.js: `prom-client` 配置示例
- Java: Micrometer 配置示例
- Go: Prometheus Go 客户端配置示例

**应用指标**：
- HTTP 请求指标（请求数、延迟、错误率）
- 业务指标（自定义指标）
- 系统指标（CPU、内存、磁盘等）

#### **分布式追踪配置（如适用）**

如果项目涉及微服务或分布式系统：
- OpenTelemetry 配置
- Jaeger 或 Zipkin 配置示例
- 追踪采样配置

#### **告警配置模板**

- `alerts/`：告警规则目录（如适用）
- Prometheus Alertmanager 规则示例
- 告警规则模板（CPU、内存、错误率等）

#### **监控仪表板配置（如适用）**

- Grafana 仪表板 JSON 配置示例（如使用 Grafana）
- 关键指标可视化配置

#### **APM 工具配置（如适用）**

如果使用 APM 工具（如 New Relic、Datadog、Elastic APM）：
- APM 工具配置示例
- 集成说明


## 🔥 绝对约束：所有生成内容必须符合以下规范

### **1️⃣ 语言规范**

- 所有文档/注释使用 **简体中文**
- 代码变量/类名/函数名使用英文
- API 文档中英双语（中文为主）


### **2️⃣ 技术栈开发规范**

根据识别的技术栈，应用对应的开发规范：

#### **Python 开发规范**

1. 所有 import 均写在文件最顶部
2. 使用统一 logger 模块（RichHandler）
3. 禁止 print
4. Black + Ruff + mypy
5. 公共函数必须：
   - 类型注解
   - Google-Style Docstring

#### **Node.js/TypeScript 开发规范**

1. 使用 TypeScript（除非明确要求 JavaScript）
2. 严格模式（strict: true）
3. ESLint + Prettier 代码格式化
4. 使用统一的日志库（winston/pino）
5. 公共函数/类必须：
   - 完整的类型注解
   - JSDoc 注释
6. 遵循 Node.js 最佳实践（错误处理、异步模式）

#### **Java 开发规范**

1. 遵循 Java 编码规范（Google Java Style Guide 或项目规范）
2. 使用 Lombok 减少样板代码（如适用）
3. 使用统一的日志框架（SLF4J + Logback/Log4j2）
4. Checkstyle + SpotBugs 代码质量检查
5. 公共类/方法必须：
   - JavaDoc 注释
   - 完整的类型声明
6. 遵循 Spring Boot 最佳实践（如使用 Spring）

#### **Go 开发规范**

1. 遵循 Go 官方代码规范（gofmt）
2. 使用统一的日志库（logrus/zap）
3. golangci-lint 代码检查
4. 公共函数必须：
   - 完整的注释（godoc 格式）
   - 明确的错误处理
5. 遵循 Go 最佳实践（错误处理、接口设计）

#### **Rust 开发规范**

1. 使用 rustfmt 格式化代码
2. 使用 clippy 进行代码检查
3. 使用统一的日志库（tracing/log）
4. 公共函数必须：
   - 完整的文档注释（///）
   - 明确的错误类型
5. 遵循 Rust 最佳实践（所有权、错误处理）

#### **通用规范（所有技术栈）**

1. 代码必须可直接运行（避免伪代码）
2. 遵循各语言的最佳实践和约定
3. 保持代码风格一致性
4. 适当的错误处理和日志记录


### **3️⃣ 复杂功能预案机制（必须遵守）**

当用户需求满足以下任意条件：
- 涉及新数据模型
- 涉及跨模块功能
- 外部依赖
- 并发/性能/安全
- 工作量 > 0.5 人日

必须先输出：

```
复杂功能的实施思路已提交，请审阅。确认后我将按此方案实现。
```

并附：
- 目标与边界
- 方案概览
- 数据模型变更
- 错误处理
- 性能/并发方案
- 风险与替代方案
- 对现有模块影响

**未经明确确认禁止进入编码阶段。**


### **4️⃣ TDD（测试驱动开发）**

流程：
- Red：先生成测试文件结构 + 测试用例
- Green：实现最小代码使其通过
- Refactor：清理结构但不能破坏测试

测试目录结构必须镜像 src：

```
src/utils/misc.py
→ tests/unit/src/utils/test_misc.py
```

测试覆盖率≥80%。


### **5️⃣ LLM-first Dev 规则**

AI 必须：
- 每个功能在实现前生成测试文件路径
- 代码必须可直接运行（避免伪代码）
- 每个步骤保持最小变更

AI 不得：
- 跳过测试去写实现
- 跳过复杂功能预案
- 添加"仅用于测试"的逻辑
- 修改现有接口以适配测试
- 自动执行危险命令（push/main/dev）


### **6️⃣ Git 工作流规范**

- 禁止直接推送到 dev/main
- 只能通过 PR
- 紧急情况需二次确认
- Commit Message 使用 Conventional Commits


## 🔧 输出格式模板（必须遵循）

当用户给 PRD 后，必须一次性输出以下结构：

```text
📁 仓库初始化内容开始
----------------------------------------
0. PRD 解析结果
   - 识别的技术栈：[Python/Node.js/Java/Go/Rust等]
   - 项目类型：[后端API/前端应用/全栈/CLI工具等]
   - 依赖需求：[数据库/消息队列/缓存等]
   - 部署方式：[Docker/K8s/Serverless等]

1. .cursor/rules/
   - project.mdc
   - backend.mdc（如适用）
   - frontend.mdc（如适用）
   - workflow.mdc
   - ...

2. README.md
   - 项目介绍（基于 PRD）
   - 技术栈说明
   - 目录结构
   - 开发指南

3. 项目目录结构（tree 格式）
   - 根据技术栈生成对应的目录结构

4. 依赖管理文件
   - requirements.txt / pyproject.toml（Python）
   - package.json / package-lock.json（Node.js）
   - pom.xml / build.gradle（Java）
   - go.mod / go.sum（Go）
   - Cargo.toml / Cargo.lock（Rust）

5. 版本控制配置
   - .gitignore（根据技术栈生成）
   - .gitattributes

6. 环境配置文件
   - .env.example
   - config/
     - dev.yaml / dev.json
     - staging.yaml / staging.json
     - prod.yaml / prod.json

7. 代码质量工具配置
   - .editorconfig
   - .prettierrc / .eslintrc.js（如适用）
   - .flake8 / .pylintrc（Python）
   - checkstyle.xml（Java）
   - .golangci.yml（Go）
   - rustfmt.toml / clippy.toml（Rust）
   - .pre-commit-config.yaml（如适用）

8. 测试框架配置
   - pytest.ini / conftest.py（Python）
   - jest.config.js / vitest.config.ts（Node.js）
   - pom.xml / build.gradle 中的测试配置（Java）
   - *_test.go 模板（Go）
   - Cargo.toml 中的测试配置（Rust）

9. 主要代码结构
   - 根据技术栈生成的基础代码文件
   - 入口文件、配置模块、工具模块等
   - 所有文件包含基础结构和注释

10. docs/DEV_GUIDE.md
    - 技术栈开发规范
    - 代码规范
    - 测试规范
    - Git 工作流
    - 复杂功能预案机制

11. docs/project/{project}/
    - v{version}/（版本化目录，如 v1.0/, v2.0/）
      - prd.md（如果 PRD 需要保存）
      - architecture.md（系统架构文档）
      - design.md（技术设计文档）
      - tasks.md（首批开发任务，需在架构和设计确认后生成）

12. API 文档配置（如果项目是 API 服务）
    - docs/api/
    - OpenAPI/Swagger 配置
    - API 文档模板

13. 数据库迁移工具（如果项目涉及数据库）
    - Alembic/Flyway/Liquibase 等配置
    - migrations/ 目录和初始迁移脚本
    - 数据库连接配置示例

14. 健康检查端点（如果项目是 API 服务）
    - /health、/ready、/live 端点
    - 健康检查响应格式
    - 依赖检查逻辑

15. LICENSE 和 CHANGELOG
    - LICENSE 文件（MIT/Apache/GPL 等）
    - CHANGELOG.md 模板

16. GitHub/GitLab 模板
    - .github/ISSUE_TEMPLATE/ 或 .gitlab/issue_templates/
    - PR/MR 模板
    - SECURITY.md
    - CONTRIBUTING.md（如需要）

17. 监控和可观测性配置
    - 日志配置（结构化日志、日志级别）
    - Prometheus 指标配置（如适用）
    - 分布式追踪配置（如适用）
    - 告警规则模板（如适用）

18. 工程基础设施（如 PRD 涉及）
    - Dockerfile
    - docker-compose.yml
    - .github/workflows/ 或 .gitlab-ci.yml
    - Makefile（可选）
    - scripts/（可选）

----------------------------------------
📁 仓库初始化内容结束
```


## 📌 最后必须提示用户

输出末尾必须包含：

**"仓库初始化已完成，请审阅以下内容：**
1. **技术设计文档**（architecture.md 和 design.md）：请确认架构和设计是否符合预期
2. **基础代码结构**：请确认代码结构是否合理
3. **目录结构**：请确认目录组织是否符合项目需求

**若技术设计文档确认无误，我将基于设计文档生成首批开发任务（tasks.md）。"**


## 使用方式

在 Claude Code 中通过命令面板（Cmd+Shift+P）或直接引用此命令，AI 将帮助你：

1. **解析 PRD**：自动从 PRD 中提取技术栈、项目类型、依赖需求等关键信息
2. **验证完整性**：检查 PRD 是否包含必要的技术信息，如有缺失会提示补充
3. **识别技术栈**：自动识别项目使用的编程语言和框架（Python/Node.js/Java/Go/Rust等）
4. **生成完整结构**：根据技术栈自动创建符合规范的目录结构和配置文件
5. **初始化主要代码结构**：生成基础代码文件（入口文件、配置模块、工具模块等），包含可运行的骨架代码
6. **生成技术设计文档**：创建系统架构文档（architecture.md）和技术设计文档（design.md），确保架构和设计思路清晰
7. **初始化依赖管理**：生成对应技术栈的依赖管理文件（requirements.txt/package.json/pom.xml/go.mod等）
8. **配置开发环境**：生成版本控制配置、环境配置文件、代码质量工具配置等
9. **生成开发文档**：创建 README、开发指南等
10. **生成任务清单**：基于确认的技术设计文档生成首批开发任务（tasks.md）
11. **初始化规则**：创建 `.cursor/rules/` 和 `.cursor/commands/` 配置
12. **生成基础设施**：根据需求生成 Docker、CI/CD、API 文档等配置文件
13. **数据库迁移工具**：如果涉及数据库，初始化迁移工具配置（Alembic/Flyway/Liquibase 等）
14. **健康检查端点**：如果项目是 API 服务，生成健康检查端点（/health、/ready、/live）
15. **项目文档**：生成 LICENSE、CHANGELOG.md 等文档
16. **协作模板**：生成 GitHub/GitLab 的 Issue、PR 模板和贡献指南
17. **监控配置**：生成日志、指标、追踪等可观测性配置

**多技术栈支持**：本命令支持 Python、Node.js/TypeScript、Java、Go、Rust 等多种技术栈，会根据 PRD 自动识别并生成对应的项目结构。

## 注意事项

- **PRD 完整性**：PRD 必须包含技术栈信息、功能模块划分和非功能性需求，否则会提示补充
- **技术栈识别**：基于 PRD 自动识别技术栈，无需手动指定
- **标准化输出**：所有生成内容必须标准化、严谨、可直接使用
- **符合规范**：严格遵循各技术栈的开发规范、TDD 规范等
- **设计优先**：必须先完成技术设计文档（architecture.md 和 design.md）并确认，才能生成 tasks.md
- **代码结构**：生成的基础代码应该是可运行的骨架代码，包含必要的导入、基础结构和注释
- **复杂功能预案**：涉及复杂功能时必须先提交预案，经确认后才能实施
- **测试驱动**：遵循 TDD 流程，确保测试覆盖率≥80%
- **Git 工作流**：禁止直接推送到主分支，必须通过 PR；不自动执行 `git init`，只生成配置文件
- **多环境支持**：自动生成开发、预发布、生产环境的配置文件
- **数据库迁移**：如果项目涉及数据库，自动初始化迁移工具（Alembic/Flyway/Liquibase 等）
- **健康检查**：API 服务自动包含健康检查端点（/health、/ready、/live）
- **可观测性**：根据需求生成日志、指标、追踪等监控配置
- **数据库迁移**：如果项目涉及数据库，自动初始化迁移工具
- **健康检查**：API 服务自动包含健康检查端点
- **可观测性**：根据需求生成日志、指标、追踪等监控配置

## 相关命令

- `project-prd`: 创建项目级别 PRD 文档
- `test-governance`: 执行测试治理任务
- `code-review`: 代码审查
- `commit`: 提交变更


**最后更新**：2025-11-30 16:10:35
**维护者**：Architecture Team
**版本**：**4.0**（多技术栈支持）
