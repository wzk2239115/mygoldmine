# Java Spring Data MongoDB Query Injection

## Details

**漏洞成因**：Spring Data MongoDB 提供派生查询方法（如 `findByFieldName()`）和 `@Query` 注解进行查询。当使用 `@Query` 注解时，若查询字符串包含动态拼接的用户输入，或使用 `Criteria` 对象时参数未验证，攻击者可注入 MongoDB 操作符。

**代码审计焦点**：
- `@Query` 注解中的查询字符串是否包含动态参数
- `Criteria` 和 `Query` 的使用是否存在字符串拼接
- `MongoTemplate` 的 `find()` 方法参数是否来自用户输入
- 派生查询方法是否支持操作符（如 `findByFieldGreaterThan()`）

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `@Query(`、`Criteria.`、`new Query()`、`MongoTemplate` 等关键字
- **(L2: 跳读)** 检查 `@Query` 字符串是否包含用户控制的参数，确认是否使用了 `?0`、`?1` 等参数替换
- **(L3: 逐行读)** 追踪 `Criteria` 对象的构造，确认是否存在参数验证
- **(L4: 跨模块追踪)** 检查是否通过多个仓库或服务函数组合查询

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了派生查询方法而非 `@Query` 注解
- **(L2: 跳读)** 验证 `@Query` 是否使用了参数占位符 `?0`、`?1` 而非字符串拼接
- **(L3: 逐行读)** 确认 `Criteria` 对象的字段名是否为常量
- **(L4: 跨模块追踪)** 检查是否使用了 Spring Data 的查询 DSL

## Classify

**漏洞研判**：
1. 若 `@Query` 字符串通过字符串拼接包含用户输入 → 漏洞
2. 若 `Criteria` 的字段名由用户输入构造 → 漏洞
3. 若 `MongoTemplate` 的查询对象未进行参数验证 → 漏洞

**误报风险**：
1. 使用派生查询方法且无动态字段 → 低风险
2. 使用 `@Query` 的参数占位符 → 低风险
3. `Criteria` 的字段名为常量 → 低风险

## Low risk

- 仅使用 Spring Data 派生查询方法（findByFieldName）
- `@Query` 字符串使用参数占位符（?0、?1 等）
- `Criteria` 对象的字段名使用常量
- 使用 Spring Data 的查询 DSL
- 参数通过 Spring 验证框架验证

