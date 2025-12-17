# Python psycopg2 % 格式化 SQL 注入

## Details

**漏洞成因**：使用 Python 字符串格式化（`%`、`%s`、`.format()`、f-string）拼接用户输入到 SQL 语句，而非使用 psycopg2 的参数化查询机制。

**典型代码示例**：

```python
# 危险：使用 % 格式化
query = "SELECT * FROM users WHERE username = '%s'" % user_input
cursor.execute(query)

# 危险：使用 .format()
query = "SELECT * FROM users WHERE id = {}".format(user_id)
cursor.execute(query)

# 危险：使用 f-string
query = f"SELECT * FROM users WHERE email = '{email}'"
cursor.execute(query)

# 安全：参数化查询
cursor.execute("SELECT * FROM users WHERE username = %s", (user_input,))
```

**快速定位核心操作**（L2: 跳读）：
- 搜索 `cursor.execute(`、`conn.execute(`
- 关注第一个参数是否为变量拼接或格式化字符串
- 检查 SQL 字符串构造位置，向上追溯是否存在 `%`、`.format()`、f-string（`f"`）

**快速定位保护机制**（L1: 关键词扫描）：
- 检查是否使用参数化查询：`execute(sql, (param,))` 或 `execute(sql, [param])`
- 搜索输入验证函数：`re.match`、`isdigit()`、白名单检查
- 搜索 ORM 调用：`Session.query`、`Model.objects.filter` 通常安全
- 检查输入来源：`request.args`、`request.form`、`request.json` 等

## Classify

**确认为漏洞**：
- SQL 语句通过字符串拼接或格式化构造
- 拼接的变量直接或间接来源于用户可控输入（GET/POST/Cookie/Header）
- 无有效的输入验证或过滤
- execute() 仅传入一个参数（拼接后的 SQL 字符串）

**判定为误报**：
- 拼接的变量为硬编码常量或配置项（非用户输入）
- 拼接变量仅为表名/字段名且有严格白名单校验
- 输入已通过类型转换（如 `int(user_id)`）且转换成功
- 仅用于日志记录或调试，不实际执行

**代码异味**：
- 虽有输入验证但验证逻辑不够严格（如简单的长度限制）
- 使用正则过滤危险字符但可能存在绕过
- 混合使用参数化和字符串拼接

## Low risk

**低风险场景**：
- 拼接的变量已经过强类型转换（如 `int()`、`float()`）且捕获了异常
- 输入限制在严格的白名单范围内（如 `if order in ['ASC', 'DESC']`）
- 仅用于构造 DDL 语句（CREATE/ALTER TABLE）且在管理后台，非普通用户可访问
- 查询结果不返回给用户，仅用于内部统计且数据库权限受限（只读账户）
- 输入长度被严格限制（如仅允许 1-2 个字符）且经过字符类型校验