# NoSQL Injection - General Overview

## 漏洞本质

NoSQL 注入是一类通过向 NoSQL 数据库查询中注入恶意操作符或代码片段，实现查询逻辑绕过、数据泄露或修改的漏洞。与 SQL 注入不同，NoSQL 注入的形式多样，因数据库和驱动库的差异而变化。

## 常见场景分类

### 1. MongoDB 操作符注入

**特征**：用户输入包含 `$` 开头的 MongoDB 操作符（如 `$ne`, `$where`, `$regex` 等）

**风险等级**：高

**典型漏洞**：
- 字段名直接来自用户输入：`{username: userInput}` 攻击者可输入 `{$ne: null}`
- 值允许嵌套对象：`{age: userInput}` 攻击者可输入 `{$gt: 18}`
- 使用危险操作符：`$where` 允许代码执行，`$function` 也可能造成 RCE

**审计要点**：
- 搜索所有 `find()`、`findOne()`、`updateOne()` 等查询方法
- 确认参数是否通过白名单字段映射
- 检查是否使用了参数化查询接口
- 验证是否禁用了危险操作符（`$where`、`$function`）

### 2. Redis 命令注入

**特征**：用户输入被用于构造 Redis 命令参数

**风险等级**：高

**典型漏洞**：
- redis.set(userKey, userValue) 若 userKey 包含空格会被解析为多个命令
- redis.eval(userScript) 允许执行任意 Lua 代码
- redis.call() 或 redis.send_command() 允许执行任意命令

**审计要点**：
- 检查是否使用 eval()、evalsha() 等脚本执行方法
- 确认命令参数是否通过验证
- 检查是否禁用了危险命令（FLUSHDB、KEYS、CONFIG）
- 验证 Redis 连接是否启用认证

### 3. 其他 NoSQL 数据库注入

**CouchDB/Mango 查询注入**：选择器对象的字段名或操作符由用户控制

**Cassandra CQL 注入**：CQL 查询通过字符串拼接包含用户输入

**自定义查询构造器**：应用实现的 NoSQL 查询解析器存在逻辑漏洞

## 审计方法论

### L0: 快速跳过

- 后端硬编码所有查询条件，用户仅输入值
- 数据库连接使用只读账户
- 严格的权限隔离，即使注入也无实际危害

### L1: 关键词扫描

搜索不同语言、框架的关键操作：
- **MongoDB**：find()、findOne()、bson.M{}、Filters.、db.
- **Redis**：redis.、.eval()、.call()、send_command()
- **ORM**：@Query、whereRaw()、plainToClass()、Object.assign()
- **危险函数**：eval()、exec()、JSON.parse()、sprintf()、strcpy()

### L2: 跳读

关键词定位后，快速检查：
- 参数来源（req.query、req.body、stdin 等）
- 是否存在明显的参数验证（黑名单、白名单、类型检查）
- 是否使用了参数化查询接口

### L3: 逐行读

深入分析参数流：
- 参数从接收到数据库查询的完整链路
- 是否存在绕过措施的逻辑缺陷
- 关键的字段过滤或验证点

### L4: 跨模块追踪

对于复杂应用：
- 追踪参数跨越多个文件、模块的处理流程
- 检查中间件、装饰器、拦截器的参数处理
- 验证多层防护的有效性

## 低风险指标

- 使用参数化查询接口（PreparedStatement、参数占位符 ?、对象参数化）
- 字段名白名单映射，值通过类型检查
- ORM 框架提供的高级 API（派生查询方法）
- 严格的输入验证（DTO 验证、Schema 验证、validator 库）
- 数据库账户权限受限（只读、特定表/操作权限）
- 连接认证和加密（SSL/TLS、密码认证、ACL）

## 高风险指标

- 字符串拼接构造查询条件
- eval()、exec() 等动态代码执行
- 用户输入直接作为 MongoDB 操作符的键
- 使用 $where、$function 等代码执行操作符
- 原生驱动 API 未进行参数验证
- 无认证或权限无限制的数据库连接

## 修复优先级

1. **P0 - 立即修复**：代码执行漏洞（$where、eval()）
2. **P1 - 本周修复**：逻辑绕过（操作符注入）
3. **P2 - 本月修复**：信息泄露（引起数据可见性扩大）
4. **P3 - 积压修复**：权限限制缓解的注入（降级处理）
