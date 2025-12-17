# TypeScript TypeORM MongoDB Raw Query

## Details

**漏洞成因**：TypeORM 支持 MongoDB，提供 Repository API 和原生查询接口。当使用原生查询（Raw Query）或 `findRaw()` 方法时，若查询对象由用户输入构造，攻击者可注入 MongoDB 操作符绕过查询逻辑。

**代码审计焦点**：
- 是否使用 `find()`、`findOne()` 等 Repository 方法还是原生查询
- 查询对象是否通过对象字面量或用户输入构造
- 是否使用了 `findRaw()` 或 `aggregate()` 等低级 API
- 查询条件的验证机制

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `repository.find(`、`findRaw(`、`aggregate(` 等关键字
- **(L2: 跳读)** 检查查询对象是否来自 `req.body`、`req.query` 等不可信源
- **(L3: 逐行读)** 追踪查询条件从构造到执行的过程，确认是否进行了验证
- **(L4: 跨模块追踪)** 检查是否通过多个服务函数组合查询

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否仅使用 Repository 的高级 API
- **(L2: 跳读)** 验证查询对象是否通过 DTO 和验证装饰器验证
- **(L3: 逐行读)** 确认字段名是否通过白名单
- **(L4: 跨模块追踪)** 检查是否使用了 QueryBuilder 的参数化接口

## Classify

**漏洞研判**：
1. 若查询对象由用户输入直接构造且未验证 → 漏洞
2. 若使用 `findRaw()` 或 `aggregate()` 时参数未验证 → 漏洞
3. 若允许用户控制操作符 → 漏洞

**误报风险**：
1. 仅使用 Repository 高级 API 且字段为常量 → 低风险
2. 查询对象通过 DTO 和验证装饰器验证 → 低风险
3. QueryBuilder 使用参数化接口 → 低风险

## Low risk

- 仅使用 TypeORM Repository 的高级 API（find、findOne）
- 使用 DTO + class-validator 验证查询对象
- QueryBuilder 使用参数化接口（`where('field = :value')`）
- 字段名使用常量或枚举
- 数据库连接权限受限

