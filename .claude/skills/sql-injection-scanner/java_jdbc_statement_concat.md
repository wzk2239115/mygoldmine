# Java JDBC Statement SQL 注入审计

## Details

### 代码特征
使用 `Statement` 对象执行拼接用户输入的 SQL 语句，典型模式：
```java
String userId = request.getParameter("id");
Statement stmt = conn.createStatement();
String sql = "SELECT * FROM users WHERE id = '" + userId + "'";
ResultSet rs = stmt.executeQuery(sql);
```

### 快速定位核心操作 (L1-L2)
**L1 关键词扫描：**
- `Statement.executeQuery(` / `executeUpdate(` / `execute(`
- `createStatement()` + 字符串拼接符 `+` / `concat(`
- `String sql = ` 后跟变量拼接
- `StringBuilder` / `StringBuffer` 构建 SQL

**L2 跳读追踪：**
- 向上溯源 SQL 字符串构建过程，识别是否有外部输入参与拼接
- 关注 `request.getParameter`、`request.getHeader`、`@RequestParam`、`@PathVariable` 等输入源
- 检查变量名包含：`param`、`input`、`user`、`id`、`name`、`query`、`keyword`

### 快速定位保护机制 (L2-L3)
**L2 跳读识别：**
- 检查是否切换为 `PreparedStatement.setXxx()` 参数化
- 搜索输入校验函数：`validate`、`check`、`sanitize`、`filter`
- 识别白名单映射：`Map<String, String>` / `switch-case` 结构

**L3 逐行验证保护有效性：**
- 白名单是否完整覆盖（无 `default` 分支或兜底逻辑）
- 正则校验是否足够严格（如：`^[a-zA-Z0-9_]+$`）
- 转义函数是否针对目标数据库（MySQL 的 `\` 转义与 PostgreSQL 的 `'` 转义不同）
- 保护逻辑是否在拼接之前执行

## Classify

### 真实漏洞
- 用户可控输入（HTTP 参数、请求头、路径变量、Cookie）直接拼接进 SQL
- 保护机制缺失或可绕过（如仅校验非空、长度限制）
- 动态表名/列名拼接且无白名单限制

### 误报
- 拼接的是硬编码常量或枚举值
- 输入已通过严格白名单过滤（如：仅允许数字且已转换为 `Integer`）
- 使用 `PreparedStatement` 且仅动态拼接 SQL 结构（如 `ORDER BY` 字段名已白名单映射）

### 代码异味
- 虽有校验但逻辑不够严谨（如：仅阻止单引号但未阻止注释符）
- 依赖前端校验或客户端过滤
- 使用自定义转义函数但未经充分测试

## Low risk

- **只读操作 + 低敏感数据**：查询日志表、公开配置表等非核心业务数据
- **输入已强类型转换**：如 `Integer.parseInt()` 且捕获异常，确保非数字输入无法进入 SQL
- **输出不可见**：仅用于内部统计，攻击者无法通过响应判断注入是否成功
- **受限执行环境**：数据库账号仅有 `SELECT` 权限且无敏感表访问权
- **额外防御层**：WAF、数据库防火墙已拦截常见 SQL 注入模式（需确认规则有效性）