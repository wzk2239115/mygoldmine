# Java Morphia Query Injection

## Details

**漏洞成因**：Morphia 是 MongoDB 的 Java ODM 框架。当构造查询条件时，若直接使用用户输入构造字段名或值，攻击者可注入 MongoDB 操作符绕过查询逻辑。

**代码审计焦点**：
- 是否使用 `Filters.eq()`、`Filters.ne()` 等查询构造器方法
- 字段名是否由用户输入动态构造
- 查询条件是否通过字符串拼接生成
- 是否使用了反射或动态代理进行字段访问

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `Filters.`、`query()`、`find()` 等关键字
- **(L2: 跳读)** 检查 Filters 方法的参数是否来自 `request.getParameter()` 等不可信源
- **(L3: 逐行读)** 追踪查询条件从构造到执行的过程，确认是否存在参数验证
- **(L4: 跨模块追踪)** 检查是否使用了自定义查询构造辅助函数

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 Filters 的参数化接口
- **(L2: 跳读)** 验证字段名是否通过白名单验证
- **(L3: 逐行读)** 确认参数值是否通过 Morphia 字段验证
- **(L4: 跨模块追踪)** 检查是否使用了 Spring Data MongoDB 等更高级 ORM

## Classify

**漏洞研判**：
1. 若字段名由用户输入动态构造 → 漏洞
2. 若使用字符串拼接构造查询条件 → 漏洞
3. 若 Filters 方法的参数直接来自用户输入 → 漏洞

**误报风险**：
1. 使用 Filters 的参数化接口且字段名为常量 → 低风险
2. 参数值通过 Morphia 字段验证 → 低风险
3. 使用 Spring Data MongoDB 的派生查询方法 → 低风险

## Low risk

- 使用 Morphia 的 Filters 参数化查询接口
- 字段名使用硬编码常量或枚举
- 参数值通过 Morphia 字段类型验证
- 使用 Spring Data MongoDB 避免手动构造
- 数据库连接权限受限

