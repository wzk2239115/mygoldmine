# TypeScript MongoDB 类型不安全查询注入

## Details

### 漏洞成因

TypeScript 的类型系统仅在编译期存在，运行时完全被擦除。开发者可能会错误地认为 TypeScript 类型检查能防止 NoSQL 注入。当使用 MongoDB 驱动时，若直接将用户输入或不可信数据作为查询对象的键名或值，而未经过参数化处理，攻击者可构造恶意查询对象改变查询逻辑。

核心风险点：`db.collection.find(query)` 中的 `query` 参数若由用户输入直接构成，其键名和键值都可被注入。特别是当 `query` 通过对象字面量动态构造（如 `{[userInput]: value}` 或 `{key: userInput}`）时，MongoDB 操作符如 `{$ne: null}`、`{$regex: /pattern/}`、`{$where: function()}` 等可被恶意注入。

---

### 核心操作定位 (L1: 关键词扫描)

扫描以下关键词和模式：
- **MongoDB 驱动方法**：`.find()`、`.findOne()`、`.updateOne()`、`.deleteOne()`、`.aggregate()`、`.updateMany()`、`.deleteMany()`
- **查询对象构造**：直接传递对象字面量或动态对象，如 `collection.find({field: req.query.field})` 或 `{[key]: value}`
- **对象操作符赋值**：`query[userKey] = userValue`、`Object.assign(query, userInput)`
- **JSON 反序列化**：`JSON.parse(userInput)`、`body-parser` 直接解析的请求体
- **字段名直接用户输入**：`{[req.query.field]: value}`、`{$gt: req.body.value}`

---

### 保护机制定位 (L2: 跳读)

检查以下保护层：
- **参数化查询/白名单**：预定义允许的字段集合，如 `const allowedFields = ['username', 'email']; if (!allowedFields.includes(userField))`
- **操作符过滤**：检查查询对象键名是否以 `$` 开头，`Object.keys(query).some(k => k.startsWith('$'))`
- **输入验证框架**：使用 `joi`、`zod` 或 `class-validator` 进行严格的 Schema 验证
- **类型守卫**：虽然 TypeScript 类型注解本身无法防护（运行时被擦除），但结合 `as const` 或 `satisfies` 约束可增加可读性
- **对象过滤函数**：自定义过滤函数检查并清理对象的键和值
- **隔离层/ORM**：使用 Mongoose、TypeORM 等 ORM 框架提供的类型安全查询方法（如 `.findById()` 而非原始 `find()`）

---

## Classify

### 漏洞认定标准

**确认为漏洞（High/Critical）**：
1. 用户输入（GET/POST 参数、请求头、JSON 体等）直接作为查询对象的键名或值，无任何验证
2. 使用计算属性名 `{[userInput]: value}` 或 `query[userInput] = value` 且 `userInput` 来自外部
3. 反序列化 `JSON.parse(userInput)` 后直接用于查询，无中间验证
4. 动态构造的 `$` 开头操作符查询（如 `{$ne: userValue}`）
5. 使用 `.aggregate()` 时 `$lookup`、`$redact` 等阶段接收用户输入

**确认为代码异味（Medium）**：
1. 使用了验证框架（如 joi、zod）但验证规则过于宽松，允许嵌套对象或未明确限制字段
2. 存在手写白名单检查但逻辑不完整，仅检查键名未检查值类型
3. TypeScript 定义了严格的 Interface 但 `as any` 或 `as unknown as MyType` 绕过了类型检查

**误报情况**：
1. 预定义查询对象，所有参数来自常量或内部逻辑，无用户可控输入
2. 使用 ORM 框架（Mongoose、TypeORM）的类型安全查询接口，如 `User.findById(id)` 且 id 已验证
3. 严格的 Schema 验证且通过了 Zod/Joi 的 `parse()` 返回类型化对象

---

## Low risk

### 低风险评级场景

- **字段值注入**：用户只能控制字段值，而字段名由应用硬编码。即使值被注入为操作符对象 `{$ne: null}`，由于 MongoDB 的序列化规则，也可能被当作普通值处理而非操作符
- **原始类型值**：字段值被严格验证为特定原始类型（字符串、数字、布尔值），经过 Schema 验证如 `Joi.string().required()`
- **ObjectId 查询**：使用 `new ObjectId(userInput)` 且 ObjectId 构造函数会抛出错误进行隔离，程序级异常捕获
- **特定 ORM 方法**：Mongoose 的 `.findById()`、`.findByIdAndUpdate()` 等方法内部已参数化，直接使用 Mongoose 的查询构建器
- **非查询操作**：虽然存在用户输入，但不涉及 MongoDB 查询构造，如日志记录、缓存 Key、模板渲染等

---
