# Java MongoDB BasicDBObject Injection

## Details

**漏洞成因**：Java 的 MongoDB 驱动使用 `BasicDBObject` 构造查询条件。当用户输入直接用于构造键值对时，攻击者可注入 MongoDB 操作符。特别是在使用 `put()` 方法时，若键或值由用户控制，将导致注入漏洞。

**代码审计焦点**：
- 是否使用 `new BasicDBObject()` 构造查询条件
- `put()` 方法的参数是否来自用户输入
- 是否使用了 `Filters` 工具类进行参数化查询
- JSON 反序列化是否用于构造查询条件

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `BasicDBObject`、`.put(`、`find(`、`JSON.parse` 等关键字
- **(L2: 跳读)** 检查 `put()` 的参数是否来自 `request.getParameter()` 等不可信源
- **(L3: 逐行读)** 追踪 BasicDBObject 的构造和使用，确认是否进行了参数验证
- **(L4: 跨模块追踪)** 检查是否通过多个函数或 DAO 层组合查询

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 `Filters` 工具类而非 `BasicDBObject`
- **(L2: 跳读)** 验证参数是否通过白名单验证
- **(L3: 逐行读)** 确认参数是否通过 Java 类型检查
- **(L4: 跨模块追踪)** 检查是否使用了 Spring Data MongoDB

## Classify

**漏洞研判**：
1. 若 BasicDBObject 的键由用户输入直接构造 → 漏洞
2. 若值为用户输入且允许操作符格式 → 漏洞
3. 若通过 JSON 反序列化构造 BasicDBObject → 漏洞

**误报风险**：
1. 使用 `Filters` 工具类且字段为常量 → 低风险
2. 参数通过白名单验证 → 低风险
3. 使用 Spring Data MongoDB → 低风险

## Low risk

- 使用 `Filters` 工具类而非 BasicDBObject
- 字段名使用常量或枚举
- 参数通过白名单验证和类型检查
- 使用 Spring Data MongoDB 的派生查询
- 数据库连接权限受限

