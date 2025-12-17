# Python Django MongoDB Query Injection

## Details

**漏洞成因**：Django 虽然主要用于 SQL 数据库，但通过 mongoengine 或 djongo 集成 MongoDB。当使用这些库进行查询时，若条件由用户输入动态构造而未使用参数化方法，攻击者可注入 MongoDB 操作符。

**代码审计焦点**：
- 是否使用了 mongoengine 或 djongo 进行 MongoDB 查询
- 查询条件是否通过字符串拼接或动态构造
- 是否使用了 `Q()` 对象进行参数化查询
- Django ORM 的查询方法是否支持参数化

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `.filter(`、`.get(`、`Q(`、`request.GET` 等关键字
- **(L2: 跳读)** 检查查询条件是否来自用户输入
- **(L3: 逐行读)** 追踪条件从接收到查询执行的过程，确认是否使用了参数化
- **(L4: 跨模块追踪)** 检查是否通过多个模块或视图组合查询

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 `Q()` 对象进行参数化
- **(L2: 跳读)** 验证字段名是否通过白名单
- **(L3: 逐行读)** 确认值是否通过 Django 字段验证
- **(L4: 跨模块追踪)** 检查是否使用了 Django Forms 或 Serializers 进行验证

## Classify

**漏洞研判**：
1. 若查询条件通过字符串拼接构造 → 漏洞
2. 若 `Q()` 对象的参数直接来自用户输入 → 漏洞
3. 若不使用 Django ORM 的参数化方法 → 漏洞

**误报风险**：
1. 使用 `Q()` 对象进行参数化查询 → 低风险
2. 字段名使用常量或白名单 → 低风险
3. 使用 Django Forms/Serializers 验证 → 低风险

## Low risk

- 仅使用 Django ORM 的 `Q()` 对象参数化查询
- 字段名使用常量或白名单映射
- 使用 Django Forms 或 DRF Serializers 进行验证
- MongoDB 连接启用认证
- 数据库权限受限

