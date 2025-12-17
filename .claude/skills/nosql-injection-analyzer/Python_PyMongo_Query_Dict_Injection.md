# Python PyMongo Query Dict Injection

## Details

**漏洞成因**：PyMongo 通过字典构造 MongoDB 查询条件。当用户输入直接用于构造查询字典的键或值时，攻击者可通过注入 MongoDB 操作符实现查询逻辑绕过。典型场景为：使用字典展开（`**userInput`）、动态键构造或 `json.loads()` 反序列化构造查询条件。

**代码审计焦点**：
- 是否使用 `collection.find()`、`collection.find_one()` 时直接传递用户字典
- 查询字典是否通过 `**userInput` 展开式或 `dict()` 合并用户输入
- 是否使用 `json.loads()`、`ast.literal_eval()` 等方式反序列化用户输入为查询条件
- 查询条件中的动态键（字段名）是否由用户控制
- 是否有针对查询键的验证或过滤机制

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `.find(`、`.find_one(`、`.update(`、`json.loads`、`**user`、`dict(` 等关键字
- **(L2: 跳读)** 检查查询字典参数是否来自 `request.args`、`request.json`、`request.form` 等不可信源
- **(L3: 逐行读)** 追踪字典构造过程，确认是否包含白名单验证或字段过滤（如 `only()` 或字段名常量化）
- **(L4: 跨模块追踪)** 检查是否通过多个函数或 ORM 层间接拼接查询条件

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 ORM（MongoEngine、Motor 等）而非原生 PyMongo
- **(L2: 跳读)** 验证查询是否使用了参数化方法（如 MongoEngine 的 `Q` 对象）
- **(L3: 逐行读)** 确认字段名是否使用常量、枚举或白名单映射，值是否类型检查
- **(L4: 跨模块追踪)** 检查是否存在输入验证层（Pydantic DTO、marshmallow schema 等）

## Classify

**漏洞研判**：
1. 若查询字典由用户输入直接构造且未白名单过滤 → **漏洞**（攻击者可注入 `{"$where": ...}` 等操作符）
2. 若使用 `**userInput` 展开或 `dict.update(userInput)` 合并用户输入 → **漏洞**（允许任意键注入）
3. 若 `json.loads()` 反序列化用户输入后直接作为查询字典 → **漏洞**（格式灵活，易于注入）
4. 若字段名由用户动态构造（如 `{user_field: value}`）且无约束 → **漏洞**（可访问内部字段）
5. 若值来自用户输入但不过滤操作符形式（如 `{"$gt": ...}`）→ **漏洞**（可改变查询逻辑）

**误报风险**：
1. 查询条件通过白名单字段映射（如 `{field: user_input for field in ALLOWED_FIELDS if field in user_input}`）→ 低风险
2. 字段名使用常量或 Enum，值通过类型检查或模式验证 → 低风险
3. 使用 MongoEngine/Motor 等 ORM 的参数化查询方法 → 低风险
4. 使用 Pydantic、marshmallow 等 DTO 框架进行严格输入校验 → 低风险
5. 数据库连接权限仅限特定操作（如只读或无聚合权限） → 可控制风险

## Low risk

- 使用 MongoEngine、Motor 等 ORM 而非原生 PyMongo
- 字段名使用常量、Enum 或静态白名单（如 `{"name": user_input}` 中 `"name"` 是常量）
- 查询条件通过 Pydantic BaseModel、marshmallow Schema 等 DTO 框架进行严格验证
- 值通过类型检查和范围约束（如 `int()` 转换、日期格式验证）
- 查询对象在服务层构造，用户输入仅作为原始值传入（分层架构隔离）
- 使用参数化查询的专用方法（MongoEngine 的 `__` 双下划线语法、Motor 的 async 参数化方法）
- 数据库用户权限受限（如仅允许 find 操作，无 `mapReduce` 或 `$where` 权限）
