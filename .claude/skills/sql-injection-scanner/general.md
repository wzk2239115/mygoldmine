# SQL 注入通用审计小抄

SQL 注入漏洞的本质：**用户可控输入未经参数化直接拼接到 SQL 语句中**。以下是所有项目必审的通用模式，与编程语言无关。

## 快速定位核心操作

**L1 - 关键词扫描**（所有 SQL 执行函数）：
- Java: `Statement.executeQuery()`、`PreparedStatement`、`createStatement()`
- Python: `cursor.execute()`、`conn.execute()`、`connection.query()`
- Go: `db.Query()`、`db.Exec()`、`fmt.Sprintf`
- PHP: `mysqli_query()`、`$pdo->query()`、`PDO::prepare()`
- JS/TS: `query()`、`execute()`、`connection.query()`、模板字符串

**L2 - 溯源变量来源**：
- HTTP 请求参数：`request.getParameter`、`request.args`、`request.form`
- 路径变量、Query 参数、Header、Cookie
- 数据库查询结果（二阶注入）、缓存/会话数据

**L3 - 识别拼接方式**：
- 字符串拼接：`+`、`.concat()`、字符串连接符
- 格式化函数：`sprintf()`、`.format()`、`f-string`、`%` 操作符、模板字符串
- 动态 SQL 构造：`StringBuilder`、字符串插值

## 漏洞模式速查表

| 模式 | 危险代码特征 | 定位方法 |
|------|-----------|--------|
| **直接拼接** | `sql = "SELECT * FROM users WHERE id = '" + userId + "'"` | 搜索 `+`、`.concat()`、`f""`、`.format()` |
| **WHERE 条件注入** | `WHERE name = '{name}'`、`IN ({list})` | 搜索 WHERE、IN、LIKE 后跟变量 |
| **ORDER BY/GROUP BY** | `ORDER BY {sortField}`、`GROUP BY {field}` | 这类动态字段需强制白名单 |
| **动态表名/列名** | `FROM {tableName}`、`SELECT {columns}` | 表名/列名无白名单则必为漏洞 |
| **参数化未使用** | `query(sql)` 单参数，未使用占位符 | 检查是否有 `?`、`:name`、`$1` 占位符 |
| **ORM 原生查询** | `raw()` 或 `.execute()`、MyBatis `${}`、Hibernate `createQuery()` | 搜索 `raw`、`createQuery`、`${}`、`%s` |
| **二阶注入** | 从数据库读取数据后再次拼接 SQL | 追踪 `query()`、`fetch()` 返回值的使用 |

## 快速定位保护机制

**参数化查询特征**（安全）：
- `execute(sql, [param])` 或 `execute(sql, (param,))` - 占位符 + 参数分离
- `PreparedStatement.setXxx()` - 绑定参数
- `.filter()`、`.get()`、`#{}` (MyBatis) - ORM 参数化

**输入验证特征**（需逐行验证）：
- 白名单校验：`if field in ALLOWED_FIELDS` 或 `switch-case` 映射（必须完整，无 default 兜底）
- 类型转换：`int(id)`、`Integer.parseInt()` 且需异常捕获
- 正则校验：`^[a-zA-Z0-9_]+$` （需足够严格）

**防御不足的特征**（代码异味）：
- 仅前端验证，服务端无校验
- 黑名单过滤：`.replace("'", "''")` - 易绕过，不如参数化
- 混合方案：部分参数化 + 部分拼接
- 自定义转义函数，未经充分测试

## 研判标准

**确认为漏洞**：
1. SQL 语句通过拼接、格式化或插值构造
2. 拼接变量直接或间接来自用户输入
3. 无有效的参数化查询（未使用占位符 + 参数分离）
4. 无严格的输入验证（白名单完整 + 类型转换 + 异常捕获）

**判定为误报**：
1. 拼接变量为常量、硬编码字符串、环境变量
2. 拼接仅为表名/列名且通过完整白名单校验（精确匹配预定义列表）
3. 输入已完成强类型转换且捕获异常
4. SQL 仅用于日志/调试，未实际执行

**低风险场景**：
- 操作仅为 SELECT，目标表无敏感数据（日志表、统计表）
- 输入已强类型转换（`int()`）且有异常处理
- 变量限制在严格白名单内（`if x in ['ASC', 'DESC']`）
- 仅本地脚本、CLI 工具或非公网暴露的内部系统

---

**Language-specific patterns**: See language files (java_jdbc_*.md, python_*.md, go_*.md, php_*.md, js_*.md, ts_*.md, rust_*.md, c_*.md)