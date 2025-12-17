# Java Cassandra CQL Injection

## Details

**漏洞成因**：Java 的 Cassandra 驱动（DataStax Java Driver）在执行 CQL 查询时，若使用字符串拼接构造查询语句且包含用户输入，攻击者可注入 CQL 命令。虽然 CQL 注入的风险相对 SQL 较低，但仍可能导致数据泄露或修改。

**代码审计焦点**：
- 是否使用字符串拼接或 `String.format()` 构造 CQL 查询
- `session.execute()` 的参数是否来自用户输入
- 是否使用了参数化查询（`PreparedStatement`）
- 查询条件的验证机制

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `session.execute(`、`String.format`、`+` 字符串拼接等关键字
- **(L2: 跳读)** 检查查询字符串是否包含用户输入
- **(L3: 逐行读)** 追踪参数从接收到查询执行的过程，确认是否使用了 PreparedStatement
- **(L4: 跨模块追踪)** 检查是否通过多个函数或服务组合构造查询

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 `PreparedStatement` 进行参数化
- **(L2: 跳读)** 验证参数是否通过白名单验证
- **(L3: 逐行读)** 确认是否使用了类型检查
- **(L4: 跨模块追踪)** 检查 Cassandra 连接是否启用了认证

## Classify

**漏洞研判**：
1. 若 CQL 查询通过字符串拼接包含用户输入 → 漏洞
2. 若使用 `String.format()` 构造查询且包含不可信数据 → 漏洞
3. 若未使用 PreparedStatement → 漏洞

**误报风险**：
1. 使用 PreparedStatement 进行参数化查询 → 低风险
2. 参数通过白名单和类型检查 → 低风险
3. 查询条件由后端硬编码 → 低风险

## Low risk

- 仅使用 PreparedStatement 进行参数化查询
- 参数通过白名单验证
- 参数类型通过 Java 类型检查
- Cassandra 连接启用认证
- 连接使用 SSL/TLS 加密

