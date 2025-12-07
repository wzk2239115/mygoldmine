# Python sqlite3 .format()/f-string SQL 注入

## Details

**漏洞成因**：使用 Python 的 `.format()` 或 f-string（格式化字符串字面量）将用户输入拼接到 SQL 语句中，而非使用 sqlite3 的参数化查询机制（`?` 占位符），导致恶意输入可破坏 SQL 语义。

**典型代码示例**：

```python
import sqlite3

# 危险：使用 f-string 拼接
username = request.form.get('username')
query = f"SELECT * FROM users WHERE username = '{username}'"
cursor.execute(query)

# 危险：使用 .format()
user_id = request.args.get('id')
query = "SELECT * FROM users WHERE id = {}".format(user_id)
cursor.execute(query)

# 危险：使用 % 格式化
email = request.json.get('email')
sql = "SELECT * FROM accounts WHERE email = '%s'" % email
conn.execute(sql)

# 危险：动态拼接 WHERE 条件
keyword = request.GET.get('search')
cursor.execute(f"SELECT * FROM posts WHERE title LIKE '%{keyword}%'")

# 安全：参数化查询（使用 ? 占位符）
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
```

**快速定位核心操作**（L2: 跳读）：
- 搜索 `cursor.execute(`、`connection.execute(`、`conn.execute(`、`.executemany(`、`.executescript(` 定位所有 SQL 执行点
- 识别 SQL 字符串构造方式：f-string（`f"`或`f'`）、`.format()`、`%` 格式化操作符
- 回溯变量来源：向上查找是否来自 `request.form`、`request.args`、`request.json`、`request.GET/POST`、`flask.request`、用户输入函数（`input()`）
- 检查是否存在跨函数传参链条，关注函数参数未经验证直接拼接到 SQL

**快速定位保护机制**（L1: 关键词扫描）：
- 参数化查询特征：`execute(sql, (param,))` 或 `execute(sql, [param])` 使用 `?` 占位符且第二参数为元组/列表
- 输入验证函数：`re.match()`、`.isdigit()`、`.isalnum()`、`isinstance(x, int)`
- 类型强制转换：`int()`、`float()`、`bool()` + 异常捕获
- 白名单校验：`if field in ['id', 'name', 'email']`、字典映射、枚举值检查
- ORM 使用：SQLAlchemy、peewee、Django ORM 的 `.filter()`、`.get()` 方法（通常安全）

## Classify

**确认为漏洞**：
- SQL 语句通过 f-string、`.format()` 或 `%` 直接拼接用户可控变量
- 拼接变量直接或间接来源于外部输入（HTTP 请求参数、表单数据、文件读取、命令行参数）
- `cursor.execute()` 仅传入单一拼接后的 SQL 字符串，未使用 `?` 占位符和第二参数
- 无有效的输入验证、类型转换或白名单校验

**判定为误报**：
- 拼接变量为常量、硬编码字符串、配置项、环境变量（如 `TABLE_NAME = 'users'`）非用户输入
- 拼接内容仅为表名/列名且已通过严格白名单校验（精确匹配预定义列表，如 `if table in ALLOWED_TABLES`）
- 输入已完成强类型转换（如 `int(user_id)`）且捕获了 `ValueError`/`TypeError` 异常
- SQL 仅用于日志记录、调试输出或注释，未实际执行
- 已使用参数化查询的 `?` 占位符形式传参

**代码异味**：
- 虽有输入验证但逻辑不严密（如仅限制长度、去除首尾空格、简单正则过滤）
- 使用 `re.sub()` 过滤特殊字符但规则不完整，存在绕过可能（如遗漏大小写、Unicode 字符）
- 混合使用参数化与拼接（部分字段使用 `?` 占位符，部分字段直接拼接）
- 依赖前端校验、客户端传入的 `type` 字段或 JavaScript 验证
- 使用自定义转义函数（如 `.replace("'", "''")` ）但未覆盖所有注入向量（如 `--`、`;`、换行符）

## Low risk

**低风险场景**：
- 输入已通过强类型转换且异常处理完整（如 `try: int(id) except ValueError: return error`）
- 变量限制在严格白名单内（如 `order_by in ['ASC', 'DESC']` 或 `column in ALLOWED_COLUMNS`）
- 仅用于本地脚本、CLI 工具或单用户桌面应用，无网络暴露且非多用户环境
- 查询操作仅限 SELECT 且目标表不含敏感数据（如日志表、统计表），数据库文件为只读权限
- 输入长度被严格限制（如 `maxlength=3` 且后端二次校验）且仅允许字母数字（`[a-zA-Z0-9]`）
- 拼接位置为 LIMIT/OFFSET 且已强制转换为整数类型，影响范围仅限查询数量
- 注入点位于非关键业务流程（如搜索历史、浏览记录）且应用为离线工具或内部系统