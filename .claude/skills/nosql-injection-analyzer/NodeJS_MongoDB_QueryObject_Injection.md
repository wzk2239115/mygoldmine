# NodeJS MongoDB QueryObject Injection

## Details

**漏洞成因**：Node.js 的 MongoDB 驱动通过对象字面量构造查询条件。当用户输入直接用于构造查询对象的键或值时，攻击者可注入 MongoDB 操作符。特别是在使用对象展开（`...userInput`）或 `Object.assign()` 时，若未进行字段过滤。

**代码审计焦点**：
- 是否使用 `collection.find()`、`collection.findOne()` 时直接传递用户对象
- 查询条件是否通过对象展开或 `Object.assign()` 构造
- 是否使用了 JSON 反序列化构造查询对象
- 查询条件的字段验证机制

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `.find(`、`.findOne(`、`...userInput`、`Object.assign` 等关键字
- **(L2: 跳读)** 检查查询对象是否来自 `req.query`、`req.body` 等不可信源
- **(L3: 逐行读)** 追踪查询条件的构造，确认是否进行了字段过滤
- **(L4: 跨模块追踪)** 检查是否通过多个函数组合查询条件

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 DTO 和验证装饰器
- **(L2: 跳读)** 验证查询对象是否通过白名单字段映射
- **(L3: 逐行读)** 确认是否有字段过滤逻辑（`pick()`、`omit()等`）
- **(L4: 跨模块追踪)** 检查是否使用了 ORM（如 Mongoose）而非原生驱动

## Classify

**漏洞研判**：
1. 若查询对象由用户输入直接构造且未过滤 → 漏洞
2. 若使用对象展开或 `Object.assign()` 合并用户输入 → 漏洞
3. 若允许用户控制查询中的操作符键 → 漏洞

**误报风险**：
1. 查询条件通过白名单字段映射 → 低风险
2. 使用 DTO + 验证装饰器 → 低风险
3. 使用 Mongoose 等 ORM → 低风险

## Low risk

- 查询对象通过白名单字段映射（如 `pick(userInput, ['name', 'email'])`）
- 使用 DTO + class-validator 等验证库
- Mongoose 使用参数化查询
- 字段名使用常量或枚举
- 数据库连接权限受限

