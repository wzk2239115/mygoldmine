---
name: error-boundary-analyzer
description: 专业的审计工作流程,通过静态代码分析识别和验证错误处理+边界条件漏洞;重点关注检测异常处理缺失、边界条件未验证、整数溢出、数组越界、空指针引用、除零错误、错误信息泄露、异常分支逻辑绕过等场景中的安全问题,从而导致攻击者触发拒绝服务、信息泄露、逻辑绕过、权限提升等安全风险;利用按编程语言组织的参考资料目录中的参考指南。
---

# 概述与边界

## 核心职责

- **聚焦**:检测错误处理逻辑和边界条件中的安全漏洞
- **输入**:项目源代码 + AST解析结果
- **输出**:错误处理漏洞清单 + 边界条件风险点 + 修复建议
- **价值**:发现"异常路径"和"边界情况"导致的安全问题

## 什么是错误处理漏洞?

**定义**:由于异常/错误处理不当,或边界条件未验证,导致的安全问题。

### 经典案例

```
错误信息泄露:
  catch (SQLException e) {
    res.send(e.message);  // 泄露数据库结构!
  }
  → 暴露表名/字段名/数据库版本

整数溢出:
  int buffer_size = user_input * 1024;  // 未检查溢出!
  char buffer[buffer_size];
  → 负数→小buffer→缓冲区溢出

异常吞噬:
  try {
    checkPermission();
  } catch (Exception e) {
    // 空catch!
  }
  executeAdminOperation();  // 权限检查被绕过!

空指针解引用:
  User user = db.findById(id);  // 可能返回null
  return user.email;  // NPE!
```

---

## 8 种核心漏洞模式

### 模式1: 错误信息泄露

```yaml
pattern: Sensitive Information in Error Messages
description: "错误消息泄露敏感技术信息"

vulnerable_patterns:
  - name: "数据库错误直接返回"
    code: |
      catch (SQLException e) {
        res.status(500).json({error: e.message});
      }
    leaked_info: "表名/字段名/SQL语句/数据库版本"
    example_error: "Duplicate entry 'admin' for key 'users.username'"

  - name: "文件路径泄露"
    code: |
      catch (FileNotFoundException e) {
        res.send(`File not found: ${e.path}`);
      }
    leaked_info: "/var/www/app/secret_config.yml"

  - name: "Stack Trace泄露"
    code: |
      catch (Exception e) {
        res.status(500).send(e.stack);
      }
    leaked_info: "代码结构/框架版本/内部路径"

detection:
  - 识别catch块直接返回异常信息
  - 检测是否包含敏感字段 (path/stack/query/version)
  - 检查生产环境是否启用详细错误

severity: MEDIUM
impact: "信息泄露,协助攻击者进一步攻击"

fix: |
  // 生产环境返回通用错误
  catch (Exception e) {
    logger.error('Database error', e);  // 日志记录详细信息
    res.status(500).json({error: 'Internal server error'});  // 用户看到通用消息
  }
```

### 模式2: 异常吞噬 (Silent Failure)

```yaml
pattern: Exception Swallowing
description: "捕获异常后未处理,导致安全检查被绕过"

vulnerable_code: |
  try {
    checkPermission(user, resource);
  } catch (PermissionDeniedException e) {
    // 空catch块!
  }

  // 继续执行敏感操作
  deleteResource(resource);

attack: "权限检查抛出异常 → 被吞噬 → 继续执行 → 未授权操作成功"

detection:
  - 识别空catch块 (无日志/无处理)
  - 检查catch块后是否继续执行敏感操作
  - 分析异常是否为安全相关 (Permission/Auth/Validation)

severity: HIGH

correct_implementation: |
  try {
    checkPermission(user, resource);
  } catch (PermissionDeniedException e) {
    logger.warn('Permission denied', {user, resource});
    throw e;  // 重新抛出!
  }

  deleteResource(resource);
```

### 模式3: 整数溢出/下溢

```yaml
pattern: Integer Overflow/Underflow
description: "算术运算导致整数溢出,产生非预期结果"

vulnerable_scenarios:
  - name: "乘法溢出"
    code: |
      int size = user_input * 1024;  // user_input = INT_MAX/512
      char buffer[size];  // size变成负数!
    result: "分配小buffer → 后续写入 → 缓冲区溢出"

  - name: "加法溢出"
    code: |
      int total = balance + amount;  // balance + amount > INT_MAX
      if (total < limit) {  // total变负数,绕过检查!
        approve();
      }
    result: "整数溢出 → 绕过限额检查"

  - name: "减法下溢"
    code: |
      unsigned int remaining = used - freed;  // freed > used
      if (remaining > 0) {  // 下溢变成大正数!
        allocate(remaining);
      }
    result: "下溢 → 过度分配资源"

detection:
  - 识别算术运算 (+, -, *, /, <<, >>)
  - 检查操作数来源 (用户输入/外部数据)
  - 检测是否有溢出检查
  - 分析结果用于敏感操作 (内存分配/数组索引/循环次数)

severity: HIGH (可导致缓冲区溢出)

fix: |
  // 检查溢出
  if (user_input > INT_MAX / 1024) {
    throw new Error('Value too large');
  }
  int size = user_input * 1024;

  // 或使用安全函数
  int size;
  if (__builtin_mul_overflow(user_input, 1024, &size)) {
    throw new Error('Integer overflow');
  }
```

### 模式4: 数组越界

```yaml
pattern: Array Out of Bounds
description: "数组索引未验证,导致越界访问"

vulnerable_code: |
  app.get('/item/:index', (req, res) => {
    const index = parseInt(req.params.index);
    const item = items[index];  // 未验证index范围!
    res.json(item);
  });

attack: |
  GET /item/-1 → 访问items[-1]
  GET /item/999999 → 数组越界

consequences:
  - 读越界: 信息泄露 (读取相邻内存)
  - 写越界: 内存损坏/代码执行

detection:
  - 识别数组访问操作 array[index]
  - 检查index是否验证范围
  - 检测index来源 (用户输入/计算结果)
  - 检查是否有边界检查

severity: HIGH

fix: |
  const index = parseInt(req.params.index);

  // 验证范围
  if (index < 0 || index >= items.length) {
    return res.status(400).json({error: 'Invalid index'});
  }

  const item = items[index];
  res.json(item);
```

### 模式5: 空指针/未定义引用

```yaml
pattern: Null Pointer / Undefined Reference
description: "未检查null/undefined,导致程序崩溃或逻辑错误"

vulnerable_patterns:
  - name: "数据库查询结果未检查"
    code: |
      const user = await db.findById(id);  // 可能返回null!
      return user.email;  // NPE!

  - name: "Optional链缺失"
    code: |
      const config = getConfig();
      const timeout = config.server.timeout;  // config可能为null!

  - name: "数组find()未检查"
    code: |
      const admin = users.find(u => u.role === 'admin');
      admin.permissions.push('DELETE');  // admin可能为undefined!

detection:
  - 识别可能返回null/undefined的函数调用
  - 检查后续是否有null检查
  - 检测属性访问/方法调用前是否验证

severity: MEDIUM (DoS风险)

fix: |
  const user = await db.findById(id);
  if (!user) {
    return res.status(404).json({error: 'User not found'});
  }
  return user.email;

  // 或使用Optional Chaining
  return user?.email ?? 'N/A';
```

### 模式6: 除零错误

```yaml
pattern: Division by Zero
description: "除数未验证,可能为零"

vulnerable_code: |
  app.post('/calculate', (req, res) => {
    const {dividend, divisor} = req.body;
    const result = dividend / divisor;  // divisor可能为0!
    res.json({result});
  });

attack: |
  POST /calculate {"dividend": 100, "divisor": 0}
  → 程序崩溃 (DoS)

detection:
  - 识别除法运算 (/, %, //)
  - 检查除数是否验证非零
  - 检测除数来源 (用户输入/计算结果)

severity: MEDIUM (DoS)

fix: |
  if (divisor === 0) {
    return res.status(400).json({error: 'Division by zero'});
  }
  const result = dividend / divisor;
```

### 模式7: 未验证的类型转换

```yaml
pattern: Unchecked Type Conversion
description: "类型转换未验证,导致非预期值"

vulnerable_patterns:
  - name: "字符串转整数"
    code: |
      const age = parseInt(req.query.age);  // 可能返回NaN!
      if (age > 18) {  // NaN > 18 === false, 绕过检查!
        grantAccess();
      }

  - name: "JSON.parse未验证"
    code: |
      const data = JSON.parse(req.body.json);  // 可能抛异常!
      processData(data);

  - name: "类型强制转换"
    code: |
      const id = +req.params.id;  // +"abc" === NaN
      db.findById(id);  // 可能导致意外行为

detection:
  - 识别类型转换函数 (parseInt/parseFloat/Number/JSON.parse)
  - 检查转换结果是否验证
  - 检测是否处理转换失败

severity: MEDIUM

fix: |
  const age = parseInt(req.query.age);
  if (isNaN(age)) {
    return res.status(400).json({error: 'Invalid age'});
  }
  if (age > 18) {
    grantAccess();
  }
```

### 模式8: 资源耗尽 (ReDoS/Zip Bomb)

```yaml
pattern: Resource Exhaustion
description: "未限制资源消耗,导致DoS"

vulnerable_patterns:
  - name: "正则表达式DoS (ReDoS)"
    code: |
      const regex = /^(a+)+$/;  // 指数时间复杂度!
      regex.test(req.body.input);  // input = "aaaaaaaaaaaaaaaaaab"
    attack: "输入特定字符串 → CPU 100% → DoS"

  - name: "无限循环"
    code: |
      const count = parseInt(req.query.count);
      for (let i = 0; i < count; i++) {  // count可能很大!
        heavyOperation();
      }

  - name: "文件大小未限制"
    code: |
      app.post('/upload', (req, res) => {
        const data = req.body.data;  // 未限制大小!
        fs.writeFileSync('upload.txt', data);  // 磁盘耗尽
      });

  - name: "Zip Bomb"
    code: |
      const zip = new AdmZip(req.file.buffer);
      zip.extractAllTo('./uploads');  // 42KB → 4.5PB!

detection:
  - 识别正则表达式复杂度
  - 检测循环次数是否可控
  - 检查文件上传大小限制
  - 检测解压操作是否验证解压后大小

severity: HIGH (DoS)

fix: |
  // ReDoS防护
  const timeoutRegex = require('timeout-regex');
  try {
    timeoutRegex(regex, input, {timeout: 1000});
  } catch (e) {
    return res.status(400).json({error: 'Invalid input'});
  }

  // 循环次数限制
  const MAX_COUNT = 1000;
  const count = Math.min(parseInt(req.query.count), MAX_COUNT);

  // 文件大小限制
  app.use(express.json({limit: '10mb'}));

  // Zip Bomb防护
  const MAX_EXTRACTED_SIZE = 100 * 1024 * 1024;  // 100MB
  let totalSize = 0;
  zip.forEach(entry => {
    totalSize += entry.uncompressedSize;
    if (totalSize > MAX_EXTRACTED_SIZE) {
      throw new Error('Zip bomb detected');
    }
  });
```

---

## 检测流程

### Step 1: 识别异常处理块

```python
def identify_error_handling(ast):
    """识别所有错误处理代码"""

    error_handlers = {
        "try_catch": [],
        "error_callbacks": [],
        "promise_catch": [],
        "result_checks": []
    }

    # Try-Catch块
    for node in ast.find_all("try_statement"):
        error_handlers["try_catch"].append({
            "location": node.location,
            "try_block": node.try_block,
            "catch_blocks": node.catch_blocks,
            "finally_block": node.finally_block
        })

    # 错误回调
    for node in ast.find_all("function_call", name=["on", "addEventListener"]):
        if "error" in node.arguments:
            error_handlers["error_callbacks"].append(node)

    # Promise.catch()
    for node in ast.find_all("method_call", name="catch"):
        error_handlers["promise_catch"].append(node)

    # 结果检查 (if (!result) ...)
    for node in ast.find_all("if_statement"):
        if is_result_check(node.condition):
            error_handlers["result_checks"].append(node)

    return error_handlers
```

### Step 2: 检测错误信息泄露

```python
def detect_error_disclosure(error_handlers):
    """检测错误信息泄露"""

    vulnerabilities = []

    for handler in error_handlers["try_catch"]:
        for catch_block in handler["catch_blocks"]:
            # 检查是否直接返回异常信息
            if returns_exception_directly(catch_block):
                vulnerabilities.append({
                    "type": "error_information_disclosure",
                    "severity": "MEDIUM",
                    "location": catch_block.location,
                    "evidence": catch_block.code,
                    "leaked_fields": extract_leaked_fields(catch_block),
                    "description": "异常信息直接返回给用户",
                    "impact": "泄露技术细节,协助攻击者"
                })

    return vulnerabilities

def extract_leaked_fields(catch_block):
    """提取泄露的敏感字段"""

    sensitive_fields = []

    code = catch_block.code

    # 检测敏感属性访问
    if re.search(r'\.stack\b', code):
        sensitive_fields.append("stack (调用栈)")
    if re.search(r'\.message\b', code):
        sensitive_fields.append("message (错误消息)")
    if re.search(r'\.sql\b', code):
        sensitive_fields.append("sql (SQL语句)")
    if re.search(r'\.query\b', code):
        sensitive_fields.append("query (查询语句)")
    if re.search(r'\.path\b', code):
        sensitive_fields.append("path (文件路径)")

    return sensitive_fields
```

### Step 3: 检测异常吞噬

```python
def detect_exception_swallowing(error_handlers):
    """检测异常吞噬"""

    vulnerabilities = []

    for handler in error_handlers["try_catch"]:
        for catch_block in handler["catch_blocks"]:
            # 检查catch块是否为空或仅有注释
            if is_empty_catch(catch_block):
                # 检查是否为安全相关异常
                exception_type = catch_block.exception_type

                if is_security_exception(exception_type):
                    severity = "HIGH"
                else:
                    severity = "MEDIUM"

                vulnerabilities.append({
                    "type": "exception_swallowing",
                    "severity": severity,
                    "location": catch_block.location,
                    "exception_type": exception_type,
                    "description": "捕获异常后未处理",
                    "risk": "安全检查可能被绕过"
                })

    return vulnerabilities

def is_security_exception(exception_type):
    """判断是否为安全相关异常"""

    security_keywords = [
        "Permission", "Auth", "Authorization",
        "Forbidden", "Unauthorized", "AccessDenied",
        "Validation", "Security"
    ]

    return any(keyword in exception_type for keyword in security_keywords)
```

### Step 4: 检测边界条件

```python
def detect_boundary_conditions(ast):
    """检测边界条件漏洞"""

    vulnerabilities = []

    # 1. 检测整数溢出
    for node in ast.find_all("binary_expression", operator=["+", "-", "*", "<<", ">>"]):
        if is_overflow_risky(node):
            vulnerabilities.append({
                "type": "integer_overflow",
                "severity": "HIGH",
                "location": node.location,
                "operation": node.code,
                "operands": [node.left, node.right],
                "description": "算术运算可能溢出",
                "has_check": has_overflow_check(node)
            })

    # 2. 检测数组越界
    for node in ast.find_all("subscript_expression"):
        array = node.object
        index = node.index

        if not has_bounds_check(array, index):
            vulnerabilities.append({
                "type": "array_out_of_bounds",
                "severity": "HIGH",
                "location": node.location,
                "array": array.name,
                "index": index.code,
                "description": "数组索引未验证范围"
            })

    # 3. 检测空指针
    for node in ast.find_all("member_expression"):
        object_node = node.object

        if can_be_null(object_node) and not has_null_check(object_node):
            vulnerabilities.append({
                "type": "null_pointer_dereference",
                "severity": "MEDIUM",
                "location": node.location,
                "object": object_node.code,
                "description": "可能为null/undefined的对象访问"
            })

    # 4. 检测除零
    for node in ast.find_all("binary_expression", operator=["/", "%", "//"]):
        divisor = node.right

        if not has_zero_check(divisor):
            vulnerabilities.append({
                "type": "division_by_zero",
                "severity": "MEDIUM",
                "location": node.location,
                "divisor": divisor.code,
                "description": "除数未验证非零"
            })

    return vulnerabilities
```

### Step 5: 检测资源耗尽

```python
def detect_resource_exhaustion(ast):
    """检测资源耗尽漏洞"""

    vulnerabilities = []

    # 1. ReDoS检测
    for node in ast.find_all("regex_literal"):
        complexity = analyze_regex_complexity(node.pattern)

        if complexity == "EXPONENTIAL":
            vulnerabilities.append({
                "type": "redos",
                "severity": "HIGH",
                "location": node.location,
                "pattern": node.pattern,
                "complexity": "O(2^n)",
                "description": "正则表达式指数时间复杂度",
                "impact": "CPU耗尽DoS"
            })

    # 2. 无限循环检测
    for node in ast.find_all("for_statement"):
        if is_user_controlled_loop(node):
            vulnerabilities.append({
                "type": "unbounded_loop",
                "severity": "HIGH",
                "location": node.location,
                "loop": node.code,
                "description": "循环次数用户可控,未限制上限"
            })

    # 3. 文件大小未限制
    for node in ast.find_all("function_call", name=["readFile", "writeFile"]):
        if not has_size_limit(node):
            vulnerabilities.append({
                "type": "unbounded_file_operation",
                "severity": "MEDIUM",
                "location": node.location,
                "description": "文件操作未限制大小"
            })

    return vulnerabilities
```

---

## 输出格式

**输出路径**: `.workspace/tasks/{TASK_ID}/error-boundary-analysis.json`

```json
{
  "dimension": "error-boundary",
  "scan_time": "2025-12-16T12:00:00Z",
  "error_handlers_found": 89,
  "vulnerabilities_found": 23,

  "vulnerabilities": [
    {
      "id": "eb-001",
      "type": "error_information_disclosure",
      "severity": "MEDIUM",
      "confidence": "HIGH",

      "location": "src/api/user.js:45",

      "vulnerable_code": |
        catch (SQLException e) {
          res.status(500).json({error: e.message});
        }

      "leaked_fields": [
        "message (包含表名/字段名)"
      ],

      "example_leak": "Duplicate entry 'admin' for key 'users.username'",

      "impact": "泄露数据库结构,协助SQL注入攻击",

      "fix_recommendation": |
        // 生产环境返回通用错误
        catch (SQLException e) {
          logger.error('Database error', e);
          res.status(500).json({error: 'Internal server error'});
        },

      "cwe": "CWE-209",
      "owasp": "A04:2021 - Insecure Design"
    },
    {
      "id": "eb-002",
      "type": "exception_swallowing",
      "severity": "HIGH",
      "confidence": "HIGH",

      "location": "src/middleware/auth.js:23",

      "vulnerable_code": |
        try {
          checkPermission(user, resource);
        } catch (PermissionDeniedException e) {
          // 空catch!
        }

        deleteResource(resource);

      "exception_type": "PermissionDeniedException",
      "is_security_exception": true,

      "issue": "权限检查异常被吞噬,继续执行敏感操作",

      "attack_scenario": "权限不足 → 抛异常 → 被吞噬 → 继续删除 → 未授权操作成功",

      "impact": "权限检查被绕过",

      "fix_recommendation": |
        catch (PermissionDeniedException e) {
          logger.warn('Permission denied', {user, resource});
          throw e;  // 重新抛出!
        },

      "cwe": "CWE-703",
      "owasp": "A01:2021 - Broken Access Control"
    },
    {
      "id": "eb-003",
      "type": "integer_overflow",
      "severity": "HIGH",
      "confidence": "HIGH",

      "location": "src/utils/buffer.js:12",

      "vulnerable_code": |
        const size = userInput * 1024;  // 未检查溢出!
        const buffer = new Buffer(size);

      "operation": "multiplication",
      "operands": ["userInput (用户可控)", "1024"],
      "has_overflow_check": false,

      "attack_scenario": "userInput = INT_MAX/512 → size溢出为负数 → 小buffer → 后续写入溢出",

      "impact": "缓冲区溢出,可能导致代码执行",

      "fix_recommendation": |
        if (userInput > Number.MAX_SAFE_INTEGER / 1024) {
          throw new Error('Value too large');
        }
        const size = userInput * 1024;,

      "cwe": "CWE-190",
      "owasp": "A04:2021 - Insecure Design"
    },
    {
      "id": "eb-004",
      "type": "array_out_of_bounds",
      "severity": "HIGH",
      "confidence": "HIGH",

      "location": "src/api/items.js:34",

      "vulnerable_code": |
        const index = parseInt(req.params.index);
        const item = items[index];  // 未验证范围!

      "array": "items",
      "index": "req.params.index (用户可控)",
      "has_bounds_check": false,

      "attack": "GET /items/-1 或 /items/999999",

      "impact": "数组越界访问,信息泄露或程序崩溃",

      "fix_recommendation": |
        const index = parseInt(req.params.index);
        if (index < 0 || index >= items.length) {
          return res.status(400).json({error: 'Invalid index'});
        }
        const item = items[index];
    },
    {
      "id": "eb-005",
      "type": "null_pointer_dereference",
      "severity": "MEDIUM",
      "confidence": "HIGH",

      "location": "src/api/profile.js:56",

      "vulnerable_code": |
        const user = await db.findById(id);  // 可能返回null!
        return user.email;  // NPE!

      "object": "user",
      "can_be_null": true,
      "has_null_check": false,

      "impact": "程序崩溃(DoS)",

      "fix_recommendation": |
        const user = await db.findById(id);
        if (!user) {
          return res.status(404).json({error: 'User not found'});
        }
        return user.email;
    },
    {
      "id": "eb-006",
      "type": "redos",
      "severity": "HIGH",
      "confidence": "HIGH",

      "location": "src/validator/email.js:12",

      "vulnerable_code": |
        const emailRegex = /^([a-zA-Z0-9]+)+@[a-zA-Z0-9]+\.[a-z]+$/;
        emailRegex.test(userInput);

      "regex_pattern": "^([a-zA-Z0-9]+)+@[a-zA-Z0-9]+\\.[a-z]+$",
      "complexity": "O(2^n)",
      "vulnerable_part": "([a-zA-Z0-9]+)+",

      "attack_payload": "aaaaaaaaaaaaaaaaaaaaaaaaaaab@test.com",

      "impact": "CPU 100%, DoS",

      "fix_recommendation": |
        // 简化正则,避免嵌套量词
        const emailRegex = /^[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-z]+$/;

        // 或使用timeout-regex库
        timeoutRegex(emailRegex, userInput, {timeout: 1000});,

      "cwe": "CWE-1333",
      "owasp": "A06:2021 - Vulnerable Components"
    }
  ],

  "statistics": {
    "total_error_handlers": 89,
    "by_type": {
      "try_catch": 67,
      "promise_catch": 18,
      "error_callbacks": 4
    },
    "vulnerabilities": {
      "error_disclosure": 5,
      "exception_swallowing": 3,
      "integer_overflow": 4,
      "array_out_of_bounds": 2,
      "null_pointer": 6,
      "division_by_zero": 1,
      "redos": 2
    },
    "severity_distribution": {
      "critical": 0,
      "high": 12,
      "medium": 11,
      "low": 0
    }
  }
}
```

---

## 下游任务

```json
{
  "tasks": [],
  "reason": "error-boundary-analyzer为分析维度,不生成下游任务"
}
```

---

## 与其他维度的协作

### 协作输出

- **dataflow-analyzer**: 整数溢出可与数据流组合检测缓冲区溢出
- **combo-pattern-analyzer**: 异常吞噬可与权限检查组合形成权限绕过

---

## 重要约束

1. ✅ **必须区分安全相关异常**: Permission/Auth异常吞噬是高危漏洞
2. ⚠️ **整数溢出检测**: 需要考虑不同语言的整数大小
3. ⚠️ **ReDoS检测**: 需要精确的正则表达式复杂度分析
4. ⚠️ **误报控制**: 并非所有空catch都是漏洞 (如预期的异常处理)

---

## 参考资料

- [CWE-209: Generation of Error Message Containing Sensitive Information](https://cwe.mitre.org/data/definitions/209.html)
- [CWE-190: Integer Overflow](https://cwe.mitre.org/data/definitions/190.html)
- [CWE-125: Out-of-bounds Read](https://cwe.mitre.org/data/definitions/125.html)
- [CWE-476: NULL Pointer Dereference](https://cwe.mitre.org/data/definitions/476.html)
- [CWE-1333: ReDoS](https://cwe.mitre.org/data/definitions/1333.html)
- [OWASP: Error Handling](https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html)
