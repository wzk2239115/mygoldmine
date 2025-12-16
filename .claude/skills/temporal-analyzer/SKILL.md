---
name: temporal-analyzer
description: 专业的审计工作流程,通过静态代码分析识别和验证时间维度安全漏洞;重点关注检测Token/Session过期验证缺失、时间戳验证不当、重放攻击风险、竞态条件时间窗口、时区处理错误、时钟偏移容忍度、时序攻击(侧信道)等场景中的安全问题,从而导致攻击者绕过过期机制、重放请求、利用竞态窗口、实施时序攻击等安全风险;利用按编程语言组织的参考资料目录中的参考指南。
---

# 概述与边界

## 核心职责

- **聚焦**:检测与时间相关的安全漏洞
- **输入**:项目源代码 + AST解析结果
- **输出**:时间维度漏洞清单 + 时序攻击风险 + 修复建议
- **价值**:发现"时间假设"导致的安全问题

## 什么是时间维度漏洞?

**定义**:由于时间相关逻辑处理不当,导致的安全问题。

### 经典案例

```
JWT永不过期:
  const token = jwt.sign({user_id: 123}, SECRET);  // 未设置exp!
  → Token永久有效,泄露后无法撤销

重放攻击:
  POST /transfer {from: A, to: B, amount: 100}
  → 重复发送请求 → 重复转账

时间戳验证缺失:
  if (timestamp < Date.now()) {  // 仅检查过去!
    reject();
  }
  → 攻击者提供未来时间戳 → 绕过验证

时序攻击:
  if (password === stored_password) {  // 字符串比较!
    login();
  }
  → 通过响应时间推测密码
```

---

## 8 种核心漏洞模式

### 模式1: Token/Session过期验证缺失

```yaml
pattern: Missing Expiration Validation
description: "Token/Session未设置或未验证过期时间"

vulnerable_patterns:
  - name: "JWT未设置exp"
    code: |
      const token = jwt.sign({
        user_id: user.id,
        role: user.role
        // 缺少 exp!
      }, SECRET);
    risk: "Token永不过期,泄露后无法撤销"

  - name: "Session未设置maxAge"
    code: |
      req.session.user = user;  // 未设置过期时间!
    risk: "Session永不过期"

  - name: "验证码未设置过期时间"
    code: |
      redis.set(`otp:${phone}`, code);  // 未设置TTL!
    risk: "验证码永久有效,可被重复使用"

  - name: "验证时未检查exp"
    code: |
      const decoded = jwt.decode(token);  // 仅解码,未验证!
      if (decoded.user_id) {
        login(decoded.user_id);
      }
    risk: "过期Token仍然有效"

detection:
  - 识别Token生成函数 (jwt.sign/createToken)
  - 检查是否设置exp/expiresIn参数
  - 识别Token验证函数
  - 检查是否验证exp字段

severity: HIGH

fix: |
  // 生成时设置过期
  const token = jwt.sign({
    user_id: user.id,
    exp: Math.floor(Date.now() / 1000) + (60 * 60)  // 1小时
  }, SECRET);

  // 验证时检查过期
  try {
    const decoded = jwt.verify(token, SECRET);  // 自动验证exp
    login(decoded.user_id);
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({error: 'Token expired'});
    }
  }
```

### 模式2: 重放攻击防护缺失

```yaml
pattern: Replay Attack
description: "请求可被重复发送,缺少防重放机制"

vulnerable_code: |
  app.post('/transfer', (req, res) => {
    const {from, to, amount} = req.body;

    // 无防重放机制!
    db.transfer(from, to, amount);
  });

attack: |
  抓包: POST /transfer {from: "alice", to: "bob", amount: 100}
  重放10次 → 转账1000元!

防重放机制:
  - name: "Nonce (一次性随机数)"
    implementation: |
      app.post('/api', (req, res) => {
        const {nonce, ...data} = req.body;

        // 检查nonce是否已使用
        if (await redis.get(`nonce:${nonce}`)) {
          return res.status(400).json({error: 'Nonce already used'});
        }

        // 标记nonce已使用 (设置TTL防止Redis膨胀)
        await redis.setex(`nonce:${nonce}`, 300, '1');  // 5分钟

        processRequest(data);
      });

  - name: "Timestamp + Window"
    implementation: |
      const WINDOW = 5 * 60 * 1000;  // 5分钟窗口

      app.post('/api', (req, res) => {
        const {timestamp, ...data} = req.body;

        // 验证时间戳在窗口内
        const now = Date.now();
        if (Math.abs(now - timestamp) > WINDOW) {
          return res.status(400).json({error: 'Request expired'});
        }

        // 结合nonce防止窗口内重放
        const key = `${req.user.id}:${timestamp}`;
        if (await redis.get(key)) {
          return res.status(400).json({error: 'Duplicate request'});
        }
        await redis.setex(key, WINDOW / 1000, '1');

        processRequest(data);
      });

  - name: "Idempotency Key"
    implementation: |
      app.post('/payment', async (req, res) => {
        const {idempotency_key, ...data} = req.body;

        // 检查是否已处理
        const cached = await redis.get(`idem:${idempotency_key}`);
        if (cached) {
          return res.json(JSON.parse(cached));  // 返回缓存结果
        }

        // 处理请求
        const result = await processPayment(data);

        // 缓存结果(24小时)
        await redis.setex(`idem:${idempotency_key}`, 86400, JSON.stringify(result));

        res.json(result);
      });

detection:
  - 识别敏感操作 (转账/支付/修改密码)
  - 检查是否有防重放机制 (nonce/timestamp/idempotency_key)
  - 检测是否验证请求唯一性

severity: CRITICAL
```

### 模式3: 时间戳验证不当

```yaml
pattern: Improper Timestamp Validation
description: "时间戳验证逻辑错误"

vulnerable_patterns:
  - name: "仅检查过去,未检查未来"
    code: |
      if (timestamp < Date.now()) {
        return res.status(400).json({error: 'Expired'});
      }
      // 未检查timestamp是否过大!
    attack: "提供timestamp = Date.now() + 1000年 → 绕过过期检查"

  - name: "使用客户端时间"
    code: |
      const clientTime = new Date(req.body.timestamp);
      if (clientTime > new Date()) {
        reject();
      }
    risk: "客户端时间可伪造"

  - name: "时间窗口过大"
    code: |
      const WINDOW = 24 * 60 * 60 * 1000;  // 24小时!
      if (Math.abs(Date.now() - timestamp) < WINDOW) {
        accept();
      }
    risk: "24小时内可重放"

detection:
  - 识别时间戳验证逻辑
  - 检查是否双向验证 (过去+未来)
  - 检查时间窗口大小 (>10分钟认为过大)
  - 检测是否信任客户端时间

severity: HIGH

fix: |
  const WINDOW = 5 * 60 * 1000;  // 5分钟窗口
  const now = Date.now();
  const diff = Math.abs(now - timestamp);

  // 双向验证
  if (diff > WINDOW) {
    return res.status(400).json({error: 'Timestamp out of range'});
  }
```

### 模式4: 时区处理错误

```yaml
pattern: Timezone Handling Issues
description: "时区转换错误导致安全问题"

vulnerable_scenarios:
  - name: "未考虑时区的时间比较"
    code: |
      const deadline = new Date('2025-01-01 00:00:00');  // 哪个时区?
      if (new Date() > deadline) {
        reject();
      }
    risk: "用户时区不同,导致判断错误"

  - name: "时区混淆"
    code: |
      const loginTime = new Date(req.body.time);  // 客户端时区
      const dbTime = user.last_login;  // UTC时区
      if (loginTime > dbTime) {  // 错误比较!
        updateLastLogin();
      }

detection:
  - 识别Date对象创建和比较
  - 检查是否明确时区
  - 检测是否使用UTC统一时区

severity: MEDIUM

fix: |
  // 统一使用UTC
  const deadline = new Date('2025-01-01T00:00:00Z');  // ISO 8601 UTC
  const now = new Date();  // 内部始终UTC
  if (now > deadline) {
    reject();
  }

  // 或使用timestamp (无时区问题)
  const deadline_ts = 1735689600000;
  if (Date.now() > deadline_ts) {
    reject();
  }
```

### 模式5: 时钟偏移容忍度

```yaml
pattern: Clock Skew Tolerance
description: "未考虑分布式系统的时钟偏移"

problem: |
  服务器A时间: 2025-01-01 12:00:00
  服务器B时间: 2025-01-01 12:05:00 (慢5分钟)
  → JWT在A生成,在B验证时可能已"过期"

vulnerable_code: |
  // 严格验证,不容忍时钟偏移
  if (decoded.exp < Date.now() / 1000) {
    throw new Error('Token expired');
  }

correct_implementation: |
  const CLOCK_SKEW = 60;  // 容忍60秒偏移

  const now = Math.floor(Date.now() / 1000);
  if (decoded.exp + CLOCK_SKEW < now) {
    throw new Error('Token expired');
  }

detection:
  - 识别分布式系统的时间验证
  - 检查是否有时钟偏移容忍度
  - 检测容忍度是否合理 (推荐60-300秒)

severity: LOW (可用性问题,但也可被利用延长Token有效期)
```

### 模式6: 竞态窗口时序分析

```yaml
pattern: Race Condition Time Window
description: "精确计算竞态条件的时间窗口大小"

analysis: |
  app.delete('/resource/:id', async (req, res) => {
    const resource = await db.findById(req.params.id);  // T1: 查询

    if (resource.owner_id !== req.user.id) {  // T2: 检查 (10ms)
      return res.status(403).json({error: 'Forbidden'});
    }

    // T3: [竞态窗口 = T4 - T2]

    await someAsyncOperation();  // T3: 异步操作 (50ms)

    await db.delete(resource.id);  // T4: 删除
  });

time_window_calculation: |
  window_start = T2 (权限检查完成)
  window_end = T4 (操作执行)
  window_size = (T4.line - T2.line) × avg_line_time + async_operations_time

  estimated_window = (4 lines × 5ms) + 50ms = 70ms

risk_assessment: |
  if window_size < 10ms: LOW_RISK
  elif window_size < 50ms: MEDIUM_RISK
  elif window_size < 100ms: HIGH_RISK
  else: CRITICAL_RISK

detection:
  - 识别Check → Use模式
  - 计算中间代码行数
  - 检测异步操作 (await/setTimeout/Promise)
  - 计算异步操作预期耗时
  - 评估窗口大小

severity: 根据窗口大小动态评估
```

### 模式7: 时序攻击 (Timing Attack)

```yaml
pattern: Timing Attack (Side-Channel)
description: "通过响应时间推测敏感信息"

vulnerable_code: |
  // 字符串逐字符比较,提前返回!
  function verifyPassword(input, stored) {
    if (input.length !== stored.length) {
      return false;
    }

    for (let i = 0; i < input.length; i++) {
      if (input[i] !== stored[i]) {
        return false;  // 提前返回,泄露位置信息!
      }
    }

    return true;
  }

attack_process: |
  尝试 "a" + "0"*31 → 响应时间: 1ms (第1位错误,立即返回)
  尝试 "b" + "0"*31 → 响应时间: 1ms
  尝试 "p" + "0"*31 → 响应时间: 2ms (第1位正确,继续比较)
  → 确定第1位是 'p'

  尝试 "pa" + "0"*30 → 响应时间: 2ms
  尝试 "ps" + "0"*30 → 响应时间: 3ms
  → 确定第2位是 's'

  逐位爆破 → 恢复完整密码!

vulnerable_operations:
  - "密码/Token比较"
  - "HMAC签名验证"
  - "API Key验证"
  - "OTP验证"

detection:
  - 识别字符串比较操作
  - 检查比较对象是否为敏感数据
  - 检测是否使用constant-time比较

severity: MEDIUM (需要大量请求,但可行)

fix: |
  // 使用constant-time比较
  const crypto = require('crypto');

  function verifyPassword(input, stored) {
    // 确保长度相同
    const inputBuf = Buffer.from(input);
    const storedBuf = Buffer.from(stored);

    // 使用timingSafeEqual (constant-time比较)
    if (inputBuf.length !== storedBuf.length) {
      // 即使长度不同,也要执行一次比较防止泄露长度
      crypto.timingSafeEqual(Buffer.alloc(32), Buffer.alloc(32));
      return false;
    }

    return crypto.timingSafeEqual(inputBuf, storedBuf);
  }
```

### 模式8: 延迟执行风险

```yaml
pattern: Delayed Execution Risk
description: "定时任务/延迟执行中的安全问题"

vulnerable_patterns:
  - name: "延迟执行时未重新验证权限"
    code: |
      app.post('/schedule-delete', (req, res) => {
        const {resource_id, delay} = req.body;

        // T1: 检查权限
        if (!canDelete(req.user, resource_id)) {
          return res.status(403).json({error: 'Forbidden'});
        }

        // T2: 设置延迟执行
        setTimeout(() => {
          db.delete(resource_id);  // 未重新检查权限!
        }, delay);
      });
    attack: |
      1. 用户A拥有资源,调度删除(delay=1小时)
      2. 管理员将资源转移给用户B
      3. 1小时后,延迟任务执行,删除了B的资源!

  - name: "Cron任务使用过期凭证"
    code: |
      cron.schedule('0 * * * *', async () => {
        const token = process.env.API_TOKEN;  // 可能已过期!
        await fetch('https://api.example.com', {
          headers: {Authorization: `Bearer ${token}`}
        });
      });

detection:
  - 识别延迟执行 (setTimeout/setInterval/cron)
  - 检查延迟任务是否重新验证权限/凭证
  - 检测任务执行时间与权限检查时间的差距

severity: MEDIUM

fix: |
  setTimeout(async () => {
    // 重新验证权限
    const resource = await db.findById(resource_id);
    if (!canDelete(req.user, resource_id)) {
      logger.warn('Permission changed, skip delete');
      return;
    }

    db.delete(resource_id);
  }, delay);
```

---

## 检测流程

### Step 1: 识别时间相关操作

```python
def identify_time_operations(ast):
    """识别所有时间相关操作"""

    time_ops = {
        "token_generation": [],
        "token_validation": [],
        "timestamp_checks": [],
        "date_comparisons": [],
        "delayed_execution": [],
        "string_comparisons": []
    }

    # Token生成
    for node in ast.find_all("function_call", name=["jwt.sign", "createToken"]):
        time_ops["token_generation"].append(node)

    # Token验证
    for node in ast.find_all("function_call", name=["jwt.verify", "jwt.decode"]):
        time_ops["token_validation"].append(node)

    # 时间戳检查
    for node in ast.find_all("binary_expression"):
        if involves_timestamp(node):
            time_ops["timestamp_checks"].append(node)

    # Date比较
    for node in ast.find_all("binary_expression", operator=[">", "<", ">=", "<="]):
        if is_date_comparison(node):
            time_ops["date_comparisons"].append(node)

    # 延迟执行
    for node in ast.find_all("function_call", name=["setTimeout", "setInterval"]):
        time_ops["delayed_execution"].append(node)

    # 字符串比较 (潜在时序攻击)
    for node in ast.find_all("binary_expression", operator=["===", "=="]):
        if is_sensitive_string_comparison(node):
            time_ops["string_comparisons"].append(node)

    return time_ops
```

### Step 2: 检测Token过期问题

```python
def detect_token_expiration_issues(time_ops):
    """检测Token过期相关问题"""

    vulnerabilities = []

    # 检测Token生成时未设置exp
    for node in time_ops["token_generation"]:
        payload = node.arguments[0]

        if not has_expiration_field(payload):
            vulnerabilities.append({
                "type": "missing_token_expiration",
                "severity": "HIGH",
                "location": node.location,
                "code": node.code,
                "issue": "Token未设置过期时间",
                "impact": "Token永久有效,泄露后无法撤销"
            })

    # 检测Token验证时未检查exp
    for node in time_ops["token_validation"]:
        if node.function_name == "jwt.decode":  # 仅解码,不验证
            vulnerabilities.append({
                "type": "token_expiration_not_verified",
                "severity": "HIGH",
                "location": node.location,
                "issue": "使用jwt.decode而非jwt.verify",
                "risk": "未验证Token过期时间"
            })

    return vulnerabilities
```

### Step 3: 检测重放攻击风险

```python
def detect_replay_attack_risks(ast):
    """检测重放攻击风险"""

    vulnerabilities = []

    # 识别敏感操作端点
    sensitive_endpoints = find_sensitive_endpoints(ast)

    for endpoint in sensitive_endpoints:
        # 检查是否有防重放机制
        has_nonce = uses_nonce(endpoint)
        has_timestamp_window = uses_timestamp_window(endpoint)
        has_idempotency_key = uses_idempotency_key(endpoint)

        if not (has_nonce or has_timestamp_window or has_idempotency_key):
            vulnerabilities.append({
                "type": "replay_attack_risk",
                "severity": "CRITICAL" if is_financial_operation(endpoint) else "HIGH",
                "location": endpoint.location,
                "endpoint": endpoint.path,
                "operation": endpoint.operation_type,
                "issue": "缺少防重放机制",
                "impact": "请求可被重复发送"
            })

    return vulnerabilities

def is_financial_operation(endpoint):
    """判断是否为财务操作"""
    financial_keywords = ["transfer", "payment", "pay", "withdraw", "deposit"]
    return any(kw in endpoint.path.lower() for kw in financial_keywords)
```

### Step 4: 检测时序攻击风险

```python
def detect_timing_attacks(time_ops):
    """检测时序攻击风险"""

    vulnerabilities = []

    for node in time_ops["string_comparisons"]:
        # 检查是否为敏感数据比较
        if is_sensitive_comparison(node):
            # 检查是否使用constant-time比较
            if not uses_constant_time_comparison(node):
                vulnerabilities.append({
                    "type": "timing_attack",
                    "severity": "MEDIUM",
                    "location": node.location,
                    "code": node.code,
                    "compared_data": identify_compared_data(node),
                    "issue": "使用普通字符串比较,存在时序侧信道",
                    "impact": "攻击者可通过响应时间推测密码/Token"
                })

    return vulnerabilities

def is_sensitive_comparison(node):
    """判断是否为敏感数据比较"""
    sensitive_keywords = [
        "password", "token", "secret", "key",
        "signature", "hmac", "otp", "code"
    ]

    left = node.left.name.lower()
    right = node.right.name.lower()

    return any(kw in left or kw in right for kw in sensitive_keywords)
```

### Step 5: 计算竞态时间窗口

```python
def calculate_race_windows(ast):
    """计算竞态条件的时间窗口"""

    race_conditions = []

    # 识别Check → Use模式
    check_use_pairs = find_check_use_patterns(ast)

    for pair in check_use_pairs:
        check_node = pair["check"]
        use_node = pair["use"]

        # 计算时间窗口
        window = calculate_time_window_detailed(check_node, use_node)

        # 评估风险
        risk_level = assess_race_risk(window)

        if risk_level in ["MEDIUM", "HIGH", "CRITICAL"]:
            race_conditions.append({
                "type": "race_condition_time_window",
                "severity": risk_level,
                "check_location": check_node.location,
                "use_location": use_node.location,
                "time_window": window,
                "description": f"竞态窗口约{window['estimated_ms']}ms"
            })

    return race_conditions

def calculate_time_window_detailed(check_node, use_node):
    """详细计算时间窗口"""

    lines_between = use_node.location.line - check_node.location.line

    # 统计异步操作
    async_ops = count_async_operations_between(check_node, use_node)

    # 估算时间
    base_time = lines_between * 5  # 每行5ms
    async_time = sum(op.estimated_time for op in async_ops)

    total_time = base_time + async_time

    return {
        "lines_between": lines_between,
        "async_operations": async_ops,
        "base_time_ms": base_time,
        "async_time_ms": async_time,
        "estimated_ms": total_time
    }

def assess_race_risk(window):
    """评估竞态风险"""
    time_ms = window["estimated_ms"]

    if time_ms < 10:
        return "LOW"
    elif time_ms < 50:
        return "MEDIUM"
    elif time_ms < 100:
        return "HIGH"
    else:
        return "CRITICAL"
```

---

## 输出格式

**输出路径**: `.workspace/tasks/{TASK_ID}/temporal-analysis.json`

```json
{
  "dimension": "temporal",
  "scan_time": "2025-12-16T12:00:00Z",
  "time_operations_found": 67,
  "vulnerabilities_found": 15,

  "vulnerabilities": [
    {
      "id": "temp-001",
      "type": "missing_token_expiration",
      "severity": "HIGH",
      "confidence": "HIGH",

      "location": "src/auth/jwt.js:23",

      "vulnerable_code": |
        const token = jwt.sign({
          user_id: user.id,
          role: user.role
        }, SECRET);

      "issue": "JWT未设置过期时间",

      "impact": "Token永久有效,泄露后无法撤销",

      "fix_recommendation": |
        const token = jwt.sign({
          user_id: user.id,
          role: user.role,
          exp: Math.floor(Date.now() / 1000) + (60 * 60)  // 1小时
        }, SECRET);,

      "cwe": "CWE-613",
      "owasp": "A07:2021 - Identification and Authentication Failures"
    },
    {
      "id": "temp-002",
      "type": "replay_attack_risk",
      "severity": "CRITICAL",
      "confidence": "HIGH",

      "location": "src/api/payment.js:45",
      "endpoint": "POST /api/payment/transfer",

      "issue": "缺少防重放机制",

      "vulnerable_code": |
        app.post('/api/payment/transfer', (req, res) => {
          const {from, to, amount} = req.body;
          db.transfer(from, to, amount);  // 无防重放!
        });

      "impact": "请求可被重复发送,导致重复转账",

      "attack_scenario": "抓包 → 重放10次 → 转账金额×10",

      "fix_recommendation": [
        "实施Idempotency Key机制",
        "或使用Nonce + Timestamp组合"
      ],

      "cwe": "CWE-294",
      "owasp": "A04:2021 - Insecure Design"
    },
    {
      "id": "temp-003",
      "type": "timing_attack",
      "severity": "MEDIUM",
      "confidence": "HIGH",

      "location": "src/auth/password.js:34",

      "vulnerable_code": |
        function verifyPassword(input, stored) {
          for (let i = 0; i < input.length; i++) {
            if (input[i] !== stored[i]) {
              return false;  // 提前返回!
            }
          }
          return true;
        }

      "compared_data": "password",

      "issue": "使用字符串逐字符比较,存在时序侧信道",

      "impact": "攻击者可通过响应时间逐位爆破密码",

      "fix_recommendation": |
        const crypto = require('crypto');
        function verifyPassword(input, stored) {
          return crypto.timingSafeEqual(
            Buffer.from(input),
            Buffer.from(stored)
          );
        },

      "cwe": "CWE-208",
      "owasp": "A02:2021 - Cryptographic Failures"
    },
    {
      "id": "temp-004",
      "type": "race_condition_time_window",
      "severity": "HIGH",
      "confidence": "HIGH",

      "check_location": "src/api/resource.js:78",
      "use_location": "src/api/resource.js:89",

      "time_window": {
        "lines_between": 11,
        "base_time_ms": 55,
        "async_operations": [
          {"type": "database_query", "estimated_time_ms": 20},
          {"type": "cache_check", "estimated_time_ms": 5}
        ],
        "async_time_ms": 25,
        "estimated_ms": 80
      },

      "description": "竞态窗口约80ms",

      "check_code": "if (resource.owner_id !== req.user.id)",
      "use_code": "await db.delete(resource.id)",

      "attack_scenario": "线程1检查权限 → 线程2修改owner_id → 线程1删除",

      "impact": "可删除其他用户的资源",

      "fix_recommendation": "使用原子操作: db.deleteWhere({id, owner_id})"
    },
    {
      "id": "temp-005",
      "type": "improper_timestamp_validation",
      "severity": "HIGH",
      "confidence": "HIGH",

      "location": "src/api/voucher.js:23",

      "vulnerable_code": |
        if (voucher.expiry < Date.now()) {
          return res.status(400).json({error: 'Expired'});
        }
        // 未检查expiry是否过大!

      "issue": "仅检查过去时间,未检查未来时间",

      "attack": "设置expiry = Date.now() + 100年 → 绕过过期检查",

      "fix_recommendation": |
        const MAX_VALIDITY = 365 * 24 * 60 * 60 * 1000;  // 最多1年
        const now = Date.now();

        if (voucher.expiry < now) {
          return res.status(400).json({error: 'Expired'});
        }
        if (voucher.expiry > now + MAX_VALIDITY) {
          return res.status(400).json({error: 'Invalid expiry'});
        }
    }
  ],

  "statistics": {
    "total_time_operations": 67,
    "by_type": {
      "token_generation": 12,
      "token_validation": 15,
      "timestamp_checks": 23,
      "date_comparisons": 8,
      "delayed_execution": 5,
      "string_comparisons": 4
    },
    "vulnerabilities": {
      "missing_expiration": 3,
      "replay_attacks": 2,
      "timing_attacks": 1,
      "race_windows": 7,
      "timestamp_validation": 2
    },
    "severity_distribution": {
      "critical": 2,
      "high": 8,
      "medium": 5,
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
  "reason": "temporal-analyzer为分析维度,不生成下游任务"
}
```

---

## 与其他维度的协作

### 前置依赖

- **state-machine-analyzer**: 提供TOCTOU竞态检测基础

### 协作输出

- **combo-pattern-analyzer**: 时间维度漏洞可与IDOR组合形成TOCTOU攻击链

---

## 重要约束

1. ✅ **必须区分安全相关时间操作**: Token/Password比较是高优先级
2. ⚠️ **时序攻击需要大量统计**: 单次请求时间差异可能仅微秒级
3. ⚠️ **竞态窗口计算**: 需要考虑异步操作的实际耗时
4. ⚠️ **误报控制**: 并非所有字符串比较都需要constant-time

---

## 参考资料

- [CWE-613: Insufficient Session Expiration](https://cwe.mitre.org/data/definitions/613.html)
- [CWE-294: Replay Attack](https://cwe.mitre.org/data/definitions/294.html)
- [CWE-208: Timing Attack](https://cwe.mitre.org/data/definitions/208.html)
- [OWASP: Insufficient Anti-automation](https://owasp.org/www-community/controls/Blocking_Brute_Force_Attacks)
- [Node.js crypto.timingSafeEqual](https://nodejs.org/api/crypto.html#cryptotimingsafeequala-b)
