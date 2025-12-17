# Python PyMySQL f-string SQL 注入

## Details

**漏洞成因**：使用 Python f-string（格式化字符串字面量）或其他字符串格式化方法（`%`、`.format()`）将用户输入拼接到 SQL 语句中，而非使用 PyMySQL 的参数化查询机制，导致恶意输入可破坏 SQL 语义。

**典型代码示例**：

```python
import pymysql

# 危险：使用 f-string 拼接
username = request.form.get('username')
query = f"SELECT * FROM users WHERE username = '{username}'"
cursor.execute(query)

# 危险：使用 % 格式化
user_id = request.args.get('id')
sql = "SELECT * FROM orders WHERE user_id = %s" % user_id
cursor.execute(sql)

# 危险：使用 .format()
email = request.json.get('email')
query = "DELETE FROM sessions WHERE email = '{}'".format(email)
cursor.execute(query)

# 危险：动态拼接 WHERE 条件
keyword = request.GET.get('q')
cursor.execute(f"SELECT * FROM posts WHERE title LIKE '%{keyword}%'")

# 安全：参数化查询
cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
```

**快速定位核心操作**（L2: 跳读）：
- 搜索 `cursor.execute(`、`connection.execute(`、`.executemany(` 定位所有 SQL 执行点
- 识别 SQL 字符串构造方式：f-string（`f"`或`f'`）、`%`、`.format()`
- 回溯变量来源：向上查找是否来自 `request.form`、`request.args`、`request.json`、`request.cookies`、`flask.request`、`django request.GET/POST`
- 检查是否存在跨函数传参链条，关注函数参数未经验证直接拼接

**快速定位保护机制**（L1: 关键词扫描）：
- 参数化查询特征：`execute(sql, (param,))` 或 `execute(sql, [param])` 第二参数为元组/列表
- 输入验证函数：`re.match()`、`.isdigit()`、`.isalnum()`、`isinstance(int)`
- 类型强制转换：`int()`、`float()`、`str.strip()` + 类型检查
- 白名单校验：`if field in ['id', 'name']`、字典映射、枚举类
- ORM 使用：SQLAlchemy、Django ORM、Peewee 的 `.filter()`、`.get()` 方法（通常安全）

## Classify

**确认为漏洞**：
- SQL 语句通过 f-string、`%` 或 `.format()` 直接拼接用户可控变量
- 拼接变量直接或间接来源于 HTTP 请求参数（GET/POST/JSON/Cookie/Header）
- `cursor.execute()` 仅传入单一拼接后的 SQL 字符串，无第二参数
- 无有效的输入验证、转义或白名单校验

**判定为误报**：
- 拼接变量为常量、配置项、环境变量（如 `TABLE_NAME`）非用户输入
- 拼接内容仅为表名/列名且已通过严格白名单校验（精确匹配预定义列表）
- 输入已完成强类型转换（如 `int(user_id)`）且捕获了 `ValueError` 异常
- SQL 仅用于日志输出或调试打印，未实际执行
- 使用了参数化查询的元组/列表形式传参

**代码异味**：
- 虽有输入验证但逻辑不严密（如仅限制长度、去除空格）
- 使用正则过滤特殊字符（`re.sub()`）但规则不完整，存在绕过可能
- 混合使用参数化与拼接（部分字段参数化，部分字段拼接）
- 依赖前端校验或客户端传入的 `type` 字段判断
- 使用转义函数（如 `.replace("'", "''")` ）但未覆盖所有注入向量

## Low risk

**低风险场景**：
- 输入已通过强类型转换且异常处理完整（如 `try: int(id) except: abort(400)`）
- 变量限制在严格白名单内（如 `order in ['ASC', 'DESC']` 或 `field in ALLOWED_FIELDS`）
- 仅用于管理后台且需管理员权限，普通用户无法访问该接口
- 查询操作仅限 SELECT 且目标表不含敏感数据，数据库账户为只读权限
- 输入长度被严格限制（如 `maxlength=3` 且后端再次校验）且仅允许字母数字
- 拼接位置为 LIMIT/OFFSET 且已强制转换为整数类型，影响范围有限
- 注入点位于非关键业务流程（如日志查询、统计面板）且数据库权限受限