---
name: state-machine-analyzer
description: 专业的审计工作流程,通过静态代码分析识别和验证生命周期+状态机漏洞;重点关注���测对象状态转换、生命周期管理、并发状态修改等场景中的安全问题,包括状态转换未验证前置条件、TOCTOU竞态条件、多步骤流程可跳过中间环节、状态回滚失败、并发修改导致状态不一致、资源未正确释放等,从而导致攻击者绕过业务流程、权限提升、数据损坏等安全问题;利用按编程语言组织的参考资料目录中的参考指南。
---

# 概述与边界

## 核心职责

- **聚焦**:检测状态机转换和对象生命周期管理中的安全漏洞
- **输入**:项目源代码 + AST解析结果
- **输出**:状态机漏洞清单 + 状态转换图 + 竞态窗口分析
- **价值**:发现"状态一致性假设"导致的安全漏洞

## 什么是状态机漏洞?

**定义**:由于状态转换逻辑缺陷、并发访问控制不足、生命周期管理错误导致的安全问题。

### 经典案例

```
IDOR + TOCTOU:
  T1: 检查资源所有权 (owner_id == current_user) ✓
  T2: [竞态窗口] 并发修改owner_id
  T3: 执行删除操作 (已通过检查) → 删除他人资源

支付双花:
  T1: 检查余额 >= 金额 ✓
  T2: [竞态窗口] 并发重复扣款
  T3: 扣款操作 → 余额为负

工作流状态跳过:
  draft → pending → approved → published
  攻击: 直接从draft跳到published,绕过审批
```

---

## 7 种核心漏洞模式

### 模式1: 状态转换未验证前置条件

```yaml
pattern: State Transition Without Precondition Check
description: "状态流转时未验证当前状态或前置条件"

vulnerable_code: |
  // 工作流状态转换
  app.post('/workflow/:id/publish', async (req, res) => {
    const workflow = await db.findById(req.params.id);

    // 错误:未检查当前状态!
    workflow.status = 'published';
    await workflow.save();
  });

expected_flow: |
  draft → pending → approved → published

attack: |
  POST /workflow/123/publish
  → 直接从draft跳到published,绕过审批

correct_implementation: |
  app.post('/workflow/:id/publish', async (req, res) => {
    const workflow = await db.findById(req.params.id);

    // 验证前置条件
    if (workflow.status !== 'approved') {
      return res.status(400).json({error: 'Workflow must be approved first'});
    }

    workflow.status = 'published';
    await workflow.save();
  });

detection:
  - 识别状态字段修改操作
  - 检查是否验证当前状态
  - 检查是否验证状态转换的合法性

severity: HIGH
cwe: "CWE-841: Improper Enforcement of Behavioral Workflow"
```

### 模式2: TOCTOU (Time-of-Check-Time-of-Use)

```yaml
pattern: TOCTOU Race Condition
description: "检查和使用之间存在时间窗口,可被并发操作利用"

vulnerable_code: |
  app.delete('/resource/:id', async (req, res) => {
    const resource = await db.findById(req.params.id);

    // T1: 检查权限
    if (resource.owner_id !== req.user.id) {
      return res.status(403).json({error: 'Forbidden'});
    }

    // T2: [竞态窗口 ~50ms]
    // 攻击者可在此期间并发修改owner_id

    // T3: 执行删除
    await db.delete(resource.id);
  });

attack_scenario: |
  线程1: 检查权限 (resource.owner_id == attacker_id) ✓
  线程2: 并发更新 owner_id = victim_id
  线程1: 执行删除 → 删除了受害者的资源!

correct_implementation: |
  app.delete('/resource/:id', async (req, res) => {
    // 使用原子操作,在数据库层面保证一致性
    const result = await db.deleteWhere({
      id: req.params.id,
      owner_id: req.user.id  // 条件删除
    });

    if (result.affectedRows === 0) {
      return res.status(404).json({error: 'Resource not found or forbidden'});
    }
  });

detection:
  - 识别Check → Use模式
  - 计算时间窗口大小 (代码行数 × 平均执行时间)
  - 检查是否有锁/事务保护
  - 检查是否使用原子操作

time_window_calculation: |
  lines_between = use_location.line - check_location.line
  estimated_time_ms = lines_between * 5  # 假设每行5ms
  if estimated_time_ms > 10:  # >10ms认为有竞态风险
    report_vulnerability()

severity: HIGH
cwe: "CWE-367: Time-of-check Time-of-use (TOCTOU) Race Condition"
```

### 模式3: 多步骤流程可跳过

```yaml
pattern: Multi-Step Process Bypass
description: "多步骤业务流程中,中间步骤可被跳过"

vulnerable_code: |
  // 步骤1: 创建订单
  app.post('/order', (req, res) => {
    const order = db.createOrder({
      items: req.body.items,
      status: 'pending_payment'
    });
    res.json({order_id: order.id});
  });

  // 步骤2: 支付 (可跳过!)
  app.post('/order/:id/pay', (req, res) => {
    db.updateOrder(req.params.id, {status: 'paid'});
  });

  // 步骤3: 发货 (未验证是否支付!)
  app.post('/order/:id/ship', (req, res) => {
    const order = db.findById(req.params.id);
    // 错误:未检查payment_status!
    shipOrder(order);
  });

attack: |
  POST /order → order_id=123
  POST /order/123/ship → 未支付就发货!

correct_implementation: |
  app.post('/order/:id/ship', (req, res) => {
    const order = db.findById(req.params.id);

    // 验证必经步骤
    if (order.status !== 'paid') {
      return res.status(400).json({error: 'Order must be paid first'});
    }

    shipOrder(order);
  });

detection:
  - 识别多步骤流程 (状态机有 >2 个状态)
  - 检查每个步骤是否验证前置状态
  - 构建状态转换图,检测非法路径

severity: CRITICAL
business_impact: "未付款直接发货,造成财务损失"
```

### 模式4: 并发状态修改冲突

```yaml
pattern: Concurrent State Modification Conflict
description: "多个并发操作修改同一对象状态,导致状态不一致"

vulnerable_code: |
  app.post('/inventory/:id/reserve', async (req, res) => {
    const item = await db.findById(req.params.id);

    // T1: 读取库存
    const available = item.stock;

    // T2: [竞态窗口]
    // 多个并发请求同时读到 stock=10

    // T3: 更新库存
    if (available >= req.body.quantity) {
      item.stock = available - req.body.quantity;
      await item.save();  // 多个请求都会保存!
    }
  });

attack_scenario: |
  初始库存: 10
  请求1: reserve 8 → 读到10, 保存2
  请求2: reserve 8 → 读到10, 保存2
  结果: 库存=2, 但实际预留了16件! (超卖)

correct_implementation: |
  // 方案1: 数据库原子操作
  await db.query(
    'UPDATE inventory SET stock = stock - ? WHERE id = ? AND stock >= ?',
    [quantity, id, quantity]
  );

  // 方案2: 悲观锁
  const item = await db.findById(id, {lock: 'FOR UPDATE'});
  item.stock -= quantity;
  await item.save();

  // 方案3: 乐观锁
  const updated = await db.updateWhere({
    id: id,
    version: item.version
  }, {
    stock: item.stock - quantity,
    version: item.version + 1
  });
  if (!updated) throw new Error('Conflict, please retry');

detection:
  - 识别 Read → Modify → Write 模式
  - 检查是否有并发控制机制 (锁/原子操作/版本号)
  - 分析临界资源 (库存/余额/配额等)

severity: CRITICAL
business_impact: "库存超卖/余额负数/资源过度分配"
```

### 模式5: 状态回滚失败

```yaml
pattern: State Rollback Failure
description: "操作失败时,状态未正确回滚,导致不一致"

vulnerable_code: |
  app.post('/transfer', async (req, res) => {
    const {from, to, amount} = req.body;

    // 步骤1: 扣款
    await db.updateAccount(from, {balance: balance - amount});

    // 步骤2: 加款 (可能失败!)
    try {
      await db.updateAccount(to, {balance: balance + amount});
    } catch (err) {
      // 错误:步骤1未回滚!
      return res.status(500).json({error: 'Transfer failed'});
    }
  });

attack_scenario: |
  扣款成功 → 加款失败 → 钱凭空消失!

correct_implementation: |
  app.post('/transfer', async (req, res) => {
    const transaction = await db.beginTransaction();

    try {
      await transaction.updateAccount(from, {balance: balance - amount});
      await transaction.updateAccount(to, {balance: balance + amount});
      await transaction.commit();
    } catch (err) {
      await transaction.rollback();  // 自动回滚
      return res.status(500).json({error: 'Transfer failed'});
    }
  });

detection:
  - 识别多步骤状态修改操作
  - 检查是否使用事务
  - 检查异常处理中是否有回滚逻辑
  - 检测 "孤儿状态" (中间状态无法恢复)

severity: HIGH
business_impact: "数据不一致,财务损失"
```

### 模式6: 生命周期钩子缺失

```yaml
pattern: Missing Lifecycle Hooks
description: "对象初始化/销毁时缺少必要的安全检查或资源清理"

vulnerable_patterns:
  - name: "未初始化就使用"
    code: |
      class Session {
        authenticate() {
          // 错误:未检查是否已初始化!
          return this.user.id;  // this.user可能为null
        }
      }

  - name: "资源未释放"
    code: |
      function processFile(path) {
        const fd = fs.openSync(path);
        const data = fs.readSync(fd);
        // 错误:未关闭文件描述符!
        return data;
      }

  - name: "敏感数据未清理"
    code: |
      class CreditCardForm {
        submit() {
          sendToServer(this.cardNumber);
          // 错误:未清除内存中的卡号!
        }
      }

detection:
  - 识别对象构造函数/析构函数
  - 检查资源分配是否配对释放
  - 检测敏感数据是否在使用后清零
  - 识别初始化标志检查

severity: MEDIUM
impact: "内存泄漏/句柄耗尽/敏感数据残留"
```

### 模式7: 状态依赖的权限检查

```yaml
pattern: State-Dependent Permission Check
description: "权限检查依赖对象状态,但状态可被篡改"

vulnerable_code: |
  app.post('/document/:id/publish', async (req, res) => {
    const doc = await db.findById(req.params.id);

    // 权限检查依赖状态
    if (doc.status === 'draft') {
      // draft状态:仅作者可发布
      if (doc.author_id !== req.user.id) {
        return res.status(403).json({error: 'Forbidden'});
      }
    }

    // 发布
    doc.status = 'published';
    await doc.save();
  });

attack: |
  1. 攻击者将文档状态改为 'pending' (绕过draft检查)
  2. POST /document/123/publish → 成功发布他人文档!

correct_implementation: |
  app.post('/document/:id/publish', async (req, res) => {
    const doc = await db.findById(req.params.id);

    // 权限检查不依赖状态
    if (doc.author_id !== req.user.id && !req.user.isAdmin) {
      return res.status(403).json({error: 'Forbidden'});
    }

    // 然后验证状态转换
    if (doc.status !== 'approved') {
      return res.status(400).json({error: 'Document must be approved first'});
    }

    doc.status = 'published';
    await doc.save();
  });

detection:
  - 识别权限检查逻辑
  - 检查权限判断是否依赖可变状态
  - 检测状态字段是否可被用户篡改

severity: HIGH
```

---

## 检测流程

### Step 1: 识别状态机

```python
def identify_state_machines(ast):
    """识别代码中的状态机"""

    state_machines = []

    # 1. 识别状态字段
    for class_def in ast.find_all("class_definition"):
        state_fields = []

        for field in class_def.fields:
            # 状态字段特征
            if is_state_field(field.name):  # status, state, phase, stage等
                state_fields.append(field)

        if state_fields:
            state_machines.append({
                "class": class_def.name,
                "state_fields": state_fields,
                "transitions": find_state_transitions(class_def)
            })

    # 2. 识别状态转换函数
    for func in ast.find_all("function_definition"):
        if modifies_state_field(func):
            state_machines.append({
                "type": "functional",
                "function": func.name,
                "state_transitions": extract_transitions(func)
            })

    return state_machines

def is_state_field(name):
    """判断是否为状态字段"""
    state_keywords = [
        "status", "state", "phase", "stage", "step",
        "mode", "lifecycle", "workflow_state"
    ]
    return any(keyword in name.lower() for keyword in state_keywords)
```

### Step 2: 构建状态转换图

```python
def build_state_transition_graph(state_machine):
    """构建状态转换图"""

    graph = {
        "states": set(),
        "transitions": []
    }

    # 提取所有状态值
    for transition in state_machine.transitions:
        graph["states"].add(transition.from_state)
        graph["states"].add(transition.to_state)

        graph["transitions"].append({
            "from": transition.from_state,
            "to": transition.to_state,
            "trigger": transition.trigger,  # 触发函数
            "preconditions": transition.preconditions,  # 前置条件
            "location": transition.location
        })

    return graph
```

### Step 3: 检测状态转换漏洞

```python
def detect_state_transition_vulnerabilities(state_machine, graph):
    """检测状态转换漏洞"""

    vulnerabilities = []

    for transition in graph["transitions"]:
        # 检测1: 前置条件缺失
        if not transition["preconditions"]:
            vulnerabilities.append({
                "type": "missing_precondition_check",
                "severity": "HIGH",
                "transition": f"{transition['from']} → {transition['to']}",
                "location": transition["location"],
                "description": "状态转换未验证前置条件",
                "evidence": f"函数 {transition['trigger']} 直接修改状态,未检查当前状态"
            })

        # 检测2: 非法状态跳转
        illegal_jump = is_illegal_transition(transition, graph)
        if illegal_jump:
            vulnerabilities.append({
                "type": "illegal_state_transition",
                "severity": "HIGH",
                "transition": f"{transition['from']} → {transition['to']}",
                "expected_path": illegal_jump["expected_path"],
                "actual_jump": illegal_jump["shortcut"],
                "description": "允许跳过中间状态"
            })

    return vulnerabilities

def is_illegal_transition(transition, graph):
    """检测是否为非法状态跳转"""

    # 使用BFS查找最短合法路径
    legal_path = find_shortest_path(
        graph,
        transition["from"],
        transition["to"]
    )

    # 如果存在合法路径且长度>1,说明允许跳过中间步骤
    if legal_path and len(legal_path) > 2:
        return {
            "expected_path": " → ".join(legal_path),
            "shortcut": f"{transition['from']} → {transition['to']}"
        }

    return None
```

### Step 4: 检测TOCTOU竞态

```python
def detect_toctou_vulnerabilities(ast):
    """检测TOCTOU竞态条件"""

    vulnerabilities = []

    # 识别Check → Use模式
    for function in ast.find_all("function_definition"):
        check_use_pairs = find_check_use_patterns(function)

        for pair in check_use_pairs:
            check_node = pair["check"]
            use_node = pair["use"]

            # 计算时间窗口
            time_window = calculate_time_window(check_node, use_node)

            # 检查是否有并发保护
            has_lock = check_concurrent_protection(check_node, use_node)

            if time_window > 10 and not has_lock:  # >10ms且无锁
                vulnerabilities.append({
                    "type": "toctou_race_condition",
                    "severity": "HIGH",
                    "location": use_node.location,
                    "check_location": check_node.location,
                    "time_window_ms": time_window,
                    "description": "检查和使用之间存在竞态窗口",
                    "evidence": {
                        "check": check_node.code,
                        "use": use_node.code,
                        "window_size": f"{time_window}ms",
                        "concurrent_protection": has_lock
                    }
                })

    return vulnerabilities

def calculate_time_window(check_node, use_node):
    """计算时间窗口大小"""
    lines_between = use_node.location.line - check_node.location.line
    estimated_time_ms = lines_between * 5  # 假设每行5ms
    return estimated_time_ms

def check_concurrent_protection(check_node, use_node):
    """检查是否有并发保护机制"""

    # 检查是否在事务中
    if is_in_transaction(check_node, use_node):
        return True

    # 检查是否有锁
    if has_lock_between(check_node, use_node):
        return True

    # 检查是否使用原子操作
    if is_atomic_operation(use_node):
        return True

    return False
```

### Step 5: 检测并发状态修改

```python
def detect_concurrent_state_conflicts(ast):
    """检测并发状态修改冲突"""

    vulnerabilities = []

    # 识别 Read → Modify → Write 模式
    for function in ast.find_all("function_definition"):
        rmw_patterns = find_read_modify_write_patterns(function)

        for pattern in rmw_patterns:
            # 检查是否有并发控制
            has_concurrency_control = (
                has_pessimistic_lock(pattern) or
                has_optimistic_lock(pattern) or
                is_atomic_rmw(pattern)
            )

            if not has_concurrency_control:
                vulnerabilities.append({
                    "type": "concurrent_state_modification",
                    "severity": "CRITICAL",
                    "location": pattern.write.location,
                    "description": "并发Read-Modify-Write无并发控制",
                    "evidence": {
                        "read": pattern.read.code,
                        "modify": pattern.modify.code,
                        "write": pattern.write.code
                    },
                    "impact": "可能导致状态不一致(如库存超卖)"
                })

    return vulnerabilities
```

---

## 输出格式

**输出路径**: `.workspace/tasks/{TASK_ID}/state-machine-analysis.json`

```json
{
  "dimension": "state-machine",
  "scan_time": "2025-12-16T12:00:00Z",
  "state_machines_found": 12,
  "vulnerabilities_found": 5,

  "state_machines": [
    {
      "id": "sm-001",
      "type": "class_based",
      "class": "Order",
      "state_field": "status",
      "states": ["pending", "paid", "shipped", "delivered", "cancelled"],
      "transitions": [
        {
          "from": "pending",
          "to": "paid",
          "trigger": "processPayment()",
          "location": "src/models/Order.js:45",
          "has_precondition_check": true
        },
        {
          "from": "paid",
          "to": "shipped",
          "trigger": "shipOrder()",
          "location": "src/models/Order.js:67",
          "has_precondition_check": false,
          "vulnerability": "sm-vuln-001"
        }
      ]
    }
  ],

  "vulnerabilities": [
    {
      "id": "sm-vuln-001",
      "type": "missing_precondition_check",
      "pattern": "状态转换未验证前置条件",
      "severity": "HIGH",
      "confidence": "HIGH",

      "state_machine": "sm-001",
      "transition": "paid → shipped",
      "trigger_function": "shipOrder()",
      "location": "src/models/Order.js:67",

      "issue": "状态转换未检查当前状态,可直接跳转",

      "vulnerable_code": |
        shipOrder() {
          this.status = 'shipped';  // 未检查当前状态!
          this.save();
        }

      "attack_scenario": {
        "step1": "创建订单 → status='pending'",
        "step2": "调用shipOrder() → status='shipped'",
        "result": "未付款就发货!"
      },

      "impact": "攻击者可绕过支付,直接发货",

      "fix_recommendation": |
        shipOrder() {
          if (this.status !== 'paid') {
            throw new Error('Order must be paid before shipping');
          }
          this.status = 'shipped';
          this.save();
        },

      "cwe": "CWE-841",
      "owasp": "A04:2021 - Insecure Design"
    },
    {
      "id": "sm-vuln-002",
      "type": "toctou_race_condition",
      "pattern": "IDOR + TOCTOU",
      "severity": "HIGH",
      "confidence": "HIGH",

      "location": "src/api/resource.js:89",
      "check_location": "src/api/resource.js:78",

      "check_code": |
        // Line 78: 检查权限
        if (resource.owner_id !== req.user.id) {
          return res.status(403).json({error: 'Forbidden'});
        }

      "use_code": |
        // Line 89: 执行删除
        await db.delete(resource.id);

      "time_window": {
        "lines_between": 11,
        "estimated_time_ms": 55,
        "concurrent_protection": false
      },

      "attack_scenario": {
        "thread1": "检查权限 (owner_id == attacker)",
        "thread2": "并发修改 owner_id = victim",
        "thread1_continue": "执行删除 → 删除了受害者的资源"
      },

      "impact": "攻击者可通过竞态条件删除其他用户的资源",

      "fix_recommendation": |
        // 使用原子操作
        const result = await db.deleteWhere({
          id: req.params.id,
          owner_id: req.user.id
        });

      "cwe": "CWE-367",
      "owasp": "A01:2021 - Broken Access Control"
    },
    {
      "id": "sm-vuln-003",
      "type": "concurrent_state_modification",
      "pattern": "库存超卖(并发RMW)",
      "severity": "CRITICAL",
      "confidence": "HIGH",

      "location": "src/api/inventory.js:45",

      "vulnerable_pattern": {
        "read": "const available = item.stock;  // Line 34",
        "modify": "item.stock = available - quantity;  // Line 42",
        "write": "await item.save();  // Line 45"
      },

      "concurrency_control": {
        "has_lock": false,
        "has_transaction": false,
        "is_atomic": false,
        "has_version_field": false
      },

      "attack_scenario": {
        "initial_stock": 10,
        "request1": "reserve 8 → read 10, write 2",
        "request2": "reserve 8 → read 10, write 2",
        "result": "库存=2, 但实际预留了16件 (超卖6件)"
      },

      "impact": "库存超卖,导致无法履行订单或财务损失",

      "fix_recommendation": [
        "方案1: 使用数据库原子操作 UPDATE inventory SET stock = stock - ? WHERE id = ? AND stock >= ?",
        "方案2: 使用悲观锁 SELECT ... FOR UPDATE",
        "方案3: 使用乐观锁 (version字段)"
      ],

      "cwe": "CWE-362",
      "owasp": "A04:2021 - Insecure Design"
    },
    {
      "id": "sm-vuln-004",
      "type": "state_rollback_failure",
      "pattern": "状态回滚失败",
      "severity": "HIGH",
      "confidence": "MEDIUM",

      "location": "src/api/transfer.js:34",

      "multi_step_operations": [
        {
          "step": 1,
          "operation": "deduct from account A",
          "location": "src/api/transfer.js:23",
          "status": "success"
        },
        {
          "step": 2,
          "operation": "add to account B",
          "location": "src/api/transfer.js:34",
          "status": "failed",
          "error_handling": "return error (no rollback!)"
        }
      ],

      "issue": "步骤2失败时,步骤1未回滚,导致金额丢失",

      "impact": "资金凭空消失,数据不一致",

      "fix_recommendation": "使用数据库事务包裹所有步骤,失败时自动回滚",

      "cwe": "CWE-662"
    },
    {
      "id": "sm-vuln-005",
      "type": "lifecycle_hook_missing",
      "pattern": "资源未释放",
      "severity": "MEDIUM",
      "confidence": "HIGH",

      "location": "src/utils/file.js:23",

      "resource_allocation": {
        "type": "file_descriptor",
        "allocation": "const fd = fs.openSync(path);  // Line 12",
        "usage": "fs.readSync(fd);  // Line 23",
        "release": null
      },

      "issue": "文件描述符未关闭",

      "impact": "文件句柄泄漏,最终耗尽系统资源",

      "fix_recommendation": |
        try {
          const fd = fs.openSync(path);
          const data = fs.readSync(fd);
          return data;
        } finally {
          if (fd) fs.closeSync(fd);
        }
    }
  ],

  "state_transition_graphs": [
    {
      "state_machine": "sm-001",
      "format": "mermaid",
      "diagram": |
        stateDiagram-v2
          [*] --> pending
          pending --> paid: processPayment()
          paid --> shipped: shipOrder() ⚠️
          shipped --> delivered: confirmDelivery()
          pending --> cancelled: cancel()
          paid --> cancelled: refund()

          note right of shipped: ⚠️ 未验证前置条件
    }
  ],

  "statistics": {
    "total_state_machines": 12,
    "total_transitions": 47,
    "validated_transitions": 32,
    "unvalidated_transitions": 15,
    "toctou_patterns": 3,
    "concurrent_rmw_patterns": 5,
    "vulnerabilities": {
      "critical": 1,
      "high": 3,
      "medium": 1
    }
  }
}
```

---

## 下游任务

```json
{
  "tasks": [],
  "reason": "state-machine-analyzer为分析维度,不生成下游任务"
}
```

---

## 与其他维度的协作

### 协作输出

- **combo-pattern-analyzer**: 状态机漏洞可与IDOR组合形成TOCTOU攻击链
- **temporal-analyzer**: 时间维度可提供更精确的竞态窗口分析

---

## 重要约束

1. ✅ **必须构建完整状态转换图**: 识别所有可能的状态和转换
2. ⚠️ **TOCTOU检测需要精确计算时间窗口**: 考虑异步操作和网络延迟
3. ⚠️ **并发控制检测**: 区分悲观锁/乐观锁/原子操作
4. ⚠️ **误报控制**: 并非所有RMW都需要并发控制(如单线程环境)

---

## 参考资料

- [CWE-367: TOCTOU Race Condition](https://cwe.mitre.org/data/definitions/367.html)
- [CWE-362: Concurrent Execution using Shared Resource](https://cwe.mitre.org/data/definitions/362.html)
- [CWE-841: Improper Enforcement of Behavioral Workflow](https://cwe.mitre.org/data/definitions/841.html)
- [OWASP: Race Conditions](https://owasp.org/www-community/vulnerabilities/Race_Conditions)
