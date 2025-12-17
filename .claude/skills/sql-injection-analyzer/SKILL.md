---
name: sql-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 SQL 注入漏洞；重点关注检测不安全的 SQL 查询构造，即用户可控输入未经适当的参数化或清理直接拼接到 SQL 语句中；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**  
当项目中存在将用户可控输入未经安全处理直接拼接到 SQL 查询语句中的行为时，极易引发 SQL 注入漏洞。此类问题通常出现在涉及数据库交互的业务模块，如用户登录认证、数据查询（搜索、列表展示）、订单/商品管理、配置读写等动态构造 SQL 的场景中，需重点审计动态拼接 SQL 的代码路径。

**Early exit**

**在开始审计之前，必须首先运行 SQL 注入扫描脚本完成初步检索**，识别潜在的 SQL 注入风险点。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行 SQL 注入扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

**快速退出条件：**

若项目完全未使用关系型数据库（如仅使用 NoSQL 且无 SQL 接口）、或所有数据库操作均通过完全参数化查询/ORM 框架（且确保无原生 SQL 拼接）、或前端为纯静态页面无后端逻辑，则可快速退出对该漏洞类型的审计。

---

## 通用 SQL 注入漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：字符串拼接构造 SQL 查询（直接拼接、WHERE/ORDER BY/GROUP BY 子句注入，绕过详见[bypassTricks.md - ORDER BY注入](bypassTricks.md#order-by注入)）、参数化查询未正确使用（未使用占位符、预编译语句配置错误）、动态表名和列名拼接（表名/列名由用户输入决定、无白名单）、ORM 原生 SQL 查询不安全使用（raw 查询拼接、特定语法滥用）、二阶 SQL 注入（绕过详见[bypassTricks.md - 二阶SQL注入](bypassTricks.md#二阶sql注入)）、存储过程和函数调用注入（参数拼接、动态名称）、SQL 语句类型特定注入（INSERT、UPDATE、DELETE）、复杂查询构造注入（绕过详见[bypassTricks.md - 堆叠查询注入](bypassTricks.md#堆叠查询注入)）、输入验证和过滤不足（绕过详见[bypassTricks.md - 高级过滤绕过](bypassTricks.md#高级过滤绕过)、[编码绕过](bypassTricks.md#编码绕过)、[宽字节注入](bypassTricks.md#宽字节注入)）、盲注相关场景（绕过详见[bypassTricks.md - 盲注加速](bypassTricks.md#盲注加速)）

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的数据库操作实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
常出现在使用 JDBC、MyBatis（非 #{} 参数化方式）或 Hibernate 原生 SQL 查询的业务逻辑中，包括但不限于通过字符串拼接构建查询条件、动态表名或列名的方式。  
- JDBC Statement 对象直接拼接用户输入，详见：[java_jdbc_statement_concat.md](java_jdbc_statement_concat.md)  
- MyBatis 使用 ${} 或字符串拼接而非 #{} 参数化，详见：[java_mybatis_concat.md](java_mybatis_concat.md)  
- Hibernate 原生 SQL 查询中的字符串拼接，详见：[java_hibernate_create_query.md](java_hibernate_create_query.md)
- 从数据库查询用户数据后，再次将查询结果拼接到 SQL 中，详见：[java_second_order_sql_injection.md](java_second_order_sql_injection.md)
- 缓存中读取的数据用于构造新的查询，详见：[java_cache_based_sql_injection.md](java_cache_based_sql_injection.md)

**Python**  
常出现在使用 sqlite3、PyMySQL、psycopg2 等库执行 SQL 时错误地使用字符串格式化（如 %、.format() 或 f-string）而非参数化查询的场景，包括但不限于 Web 后端搜索、用户信息查询等接口。  
- sqlite3 使用 .format() 或 f-string 格式化 SQL，详见：[python_sqlite_format.md](python_sqlite_format.md)  
- PyMySQL 使用 f-string 拼接查询字符串，详见：[python_pymysql_fstring.md](python_pymysql_fstring.md)  
- psycopg2 使用 % 格式化而非参数化查询，详见：[python_psycopg2_percent.md](python_psycopg2_percent.md)
- Django ORM 查询结果用于构造原生 SQL，详见：[python_django_queryset_to_sql.md](python_django_queryset_to_sql.md)
- SQLAlchemy 会话中的数据用于拼接新查询，详见：[python_sqlalchemy_session_injection.md](python_sqlalchemy_session_injection.md)

**Go**  
常出现在使用 database/sql 包时错误地使用 fmt.Sprintf 或字符串拼接构造查询，而非使用 db.Query/Exec 的参数绑定机制，常见于用户管理、日志查询等模块。  
- 使用 fmt.Sprintf 格式化 SQL 查询字符串，详见：[go_fmt_sprintf_sql.md](go_fmt_sprintf_sql.md)  
- 直接字符串拼接构造原始查询，详见：[go_raw_query_concat.md](go_raw_query_concat.md)  
- GORM 框架中 Where 条件的字符串拼接，详见：[go_gorm_where_string.md](go_gorm_where_string.md)
- 数据库查询结果用于构造新的 SQL 语句，详见：[go_query_result_to_sql.md](go_query_result_to_sql.md)

**PHP**  
常出现在使用 mysqli、PDO（未启用预处理）或旧式 mysql 扩展时直接拼接用户输入到 SQL 语句中，包括但不限于登录、搜索、内容管理等功能。  
- mysqli_query 直接拼接用户输入，详见：[php_mysqli_query_concat.md](php_mysqli_query_concat.md)  
- PDO 未启用预处理或模拟预处理的风险，详见：[php_pdo_emulated_prep_disabled.md](php_pdo_emulated_prep_disabled.md)  
- 旧式 mysql 扩展的不安全使用，详见：[php_old_mysql_extension.md](php_old_mysql_extension.md)
- Laravel Eloquent 模型数据用于构造原生查询，详见：[php_eloquent_to_raw_sql.md](php_eloquent_to_raw_sql.md)
- 从数据库读取的数据用于 $_GET/$_POST 处理逻辑，详见：[php_db_to_user_input.md](php_db_to_user_input.md)

**JavaScript (Node.js)**  
常出现在使用 mysql、pg、sqlite3 等数据库驱动时通过模板字符串或 + 拼接 SQL，而非使用参数化查询占位符的场景，常见于 REST API 的数据获取与更新逻辑。  
- mysql 驱动使用模板字符串拼接 SQL，详见：[js_mysql_template_literal.md](js_mysql_template_literal.md)  
- pg (PostgreSQL) 驱动直接拼接查询，详见：[js_pg_query_concat.md](js_pg_query_concat.md)  
- sqlite3 驱动的字符串拼接风险，详见：[js_sqlite3_string_concat.md](js_sqlite3_string_concat.md)
- ORM 查询结果用于构造原生 SQL 查询，详见：[js_orm_result_to_raw_sql.md](js_orm_result_to_raw_sql.md)

**TypeScript**  
与 JavaScript 类似，常出现在 TypeScript 编写的后端服务中错误使用字符串插值构造 SQL，尤其在未严格校验 ORM（如 TypeORM）原始查询用法时。  
- TypeORM 原始 SQL 查询中的拼接风险，详见：[ts_typeorm_raw_sql.md](ts_typeorm_raw_sql.md)  
- pg 驱动未使用参数化而直接拼接，详见：[ts_pg_parameter_not_used.md](ts_pg_parameter_not_used.md)  
- Knex.js raw() 方法的字符串拼接，详见：[ts_knex_raw_concat.md](ts_knex_raw_concat.md)
- Redis 或内存缓存中读取的数据用于 SQL 拼接，详见：[ts_cache_to_sql_injection.md](ts_cache_to_sql_injection.md)

**C/C++**  
常出现在数据库驱动层、嵌入式系统或服务端中间件中直接使用字符串拼接构造 SQL 查询的功能，包括但不限于通过 sprintf、strcat 等函数动态组装 SQL 语句的方式。  
- 使用 sprintf/strcat 等函数动态拼接 SQL 语句，详见：[c_dynamic_sql_concat.md](c_dynamic_sql_concat.md)  
- SQLite 原始查询接口的不安全使用，详见：[c_sqlite_raw_query.md](c_sqlite_raw_query.md)  
- MySQL 原始查询接口 mysql_real_query 的风险场景，详见：[c_mysql_real_query_usage.md](c_mysql_real_query_usage.md)

**Rust**  
常出现在使用 sqlx、diesel 等 crate 时绕过类型安全机制，通过 format! 或字符串拼接构造动态查询，尤其在需要动态表名或列名的复杂业务逻辑中。  
- sqlx 使用 format! 宏格式化 SQL 字符串，详见：[rust_sqlx_format_sql.md](rust_sqlx_format_sql.md)
- diesel ORM 原始 SQL 的字符串拼接，详见：[rust_diesel_raw_sql_concat.md](rust_diesel_raw_sql_concat.md)
- 自定义查询构建器的不安全实现，详见：[rust_custom_query_builder_insecure.md](rust_custom_query_builder_insecure.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注数据库交互相关的实现：**

- 查阅项目文档，重点关注数据库架构和数据访问层设计
- 理解业务领域和核心功能，识别涉及数据库查询的场景
- 识别关键组件、模块及其关系，特别是数据访问层、业务逻辑层、API 接口层
- 梳理应用流程（重点：用户输入处理流程、数据查询流程、数据过滤与验证机制）
- 识别关键业务功能（用户登录、搜索查询、数据列表展示、条件过滤、订单管理、配置读写等）
- 理解所用技术栈和框架（数据库类型、ORM框架、数据库驱动及版本，如 JDBC、MyBatis、SQLAlchemy、database/sql、TypeORM 等）
- 查阅配置文件以理解系统行为（数据库连接配置、ORM 配置、查询日志设置等）
- 定位 SQL 查询的构造位置（查询函数、SQL 拼接点、动态查询构建器）
- 定位输入验证与过滤位置（参数校验逻辑、输入清理函数、白名单验证）
- 识别用户输入来源（HTTP 请求参数、请求体、路径参数、Header、Cookie 等）

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如完全未使用关系型数据库、所有查询均已完全参数化、或仅为纯静态页面等），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目存在数据库交互并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 SQL 注入漏洞的参考指南

SQL 注入漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用 SQL 注入漏洞模式（所有项目必审）**

在 **通用 SQL 注入漏洞模式** 章节中，列举了所有涉及数据库操作的应用都必须审计的 SQL 注入问题：
- 字符串拼接构造 SQL 查询（直接拼接、WHERE/ORDER BY/GROUP BY 子句注入）
- 参数化查询未正确使用（未使用占位符、预编译语句配置错误）
- 动态表名和列名拼接（表名/列名由用户输入决定、无白名单）
- ORM 原生 SQL 查询不安全使用（raw 查询拼接、特定语法滥用）
- 二阶 SQL 注入（查询结果、缓存/会话数据、特定业务场景），绕过技巧详见：[bypassTricks.md - 二阶SQL注入](bypassTricks.md#二阶sql注入)
- 存储过程和函数调用注入（参数拼接、动态名称）
- SQL 语句类型特定注入（INSERT、UPDATE、DELETE）
- 复杂查询构造注入（子查询、JOIN、UNION），绕过技巧详见：[bypassTricks.md - 堆叠查询注入](bypassTricks.md#堆叠查询注入)
- 输入验证和过滤不足（仅客户端验证、黑名单不完整、转义错误），绕过技巧详见：[bypassTricks.md - 高级过滤绕过](bypassTricks.md#高级过滤绕过)、[编码绕过](bypassTricks.md#编码绕过)、[宽字节注入](bypassTricks.md#宽字节注入)
- 盲注相关场景（布尔盲注、时间盲注），绕过技巧详见：[bypassTricks.md - 盲注加速](bypassTricks.md#盲注加速)

这些问题与编程语言无关，是 SQL 查询构造安全层面的通用缺陷，任何数据库应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言数据库操作实现方式的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript、TypeScript、C/C++、Rust）
- 列出该语言数据库驱动、ORM 框架的典型 SQL 注入缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 SQL 注入漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `sql_string_concatenation.md`、`java_jdbc_statement_concat.md`、`python_sqlite_format.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

## 审计等级定义

SQL 注入漏洞审计采用分层的审计等级制度，根据查询构造方式和参数化程度来指导审计深度。

| 等级 | 名称 | 时间 | 查询特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 完全参数化：占位符绑定、ORM 安全查询、无动态拼接 |
| **L1** | 快速扫描 | 3-5 分钟 | 参数化为主 + 需确认：需验证占位符使用正确性和动态表名处理 |
| **L2** | 跳读 | 5-10 分钟 | 部分拼接 + 有过滤：需验证过滤规则完整性和白名单机制 |
| **L3** | 逐行读 | 15-30 分钟 | 直接拼接无防护：字符串拼接、未转义、黑名单过滤不完整 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：二阶注入、ORM raw 查询、存储过程、多文件追踪 |

### 快速判断流程

**第 1 步：是否存在 SQL 查询？**
- 无数据库交互 → L0 跳过
- 有数据库查询 → 继续第 2 步

**第 2 步：查询构造方式是什么？**
- 完全参数化（占位符 `?` 或 `$1`） → 继续第 3 步
- 字符串拼接或格式化 → **L3+**

**第 3 步：是否有动态表名/列名或特殊查询？**
- 纯参数化无动态部分 → **L0**
- 参数化 + 动态表名有白名单 → **L1**
- 参数化 + 动态部分有过滤 → **L2**
- ORM raw 查询或存储过程 → **L3-L4**

### 各等级操作指南

**L0**：完全参数化
```java
// 占位符绑定
PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");
ps.setInt(1, userId);

// ORM 安全查询
userRepository.findById(userId);
```

**L1**：参数化 + 动态部分
- 确认占位符使用正确（`?` 或 `$1`，非 `${}`）
- 检查动态表名/列名是否有白名单验证
- 验证预编译语句是否正确启用

**L2**：部分拼接 + 过滤
- 定位过滤逻辑：黑名单还是白名单？
- 核实过滤规则是否覆盖所有特殊字符：`'";--#/**/`，绕过技巧详见：[bypassTricks.md - 注释和空格替代](bypassTricks.md#注释和空格替代)、[编码绕过](bypassTricks.md#编码绕过)
- 检查 ORDER BY、GROUP BY 等子句的处理，绕过技巧详见：[bypassTricks.md - ORDER BY注入](bypassTricks.md#order-by注入)
- 验证数字类型是否强制转换，绕过技巧详见：[bypassTricks.md - 类型混淆注入](bypassTricks.md#类型混淆注入)

**L3**：直接拼接
```java
// 字符串拼接
String sql = "SELECT * FROM users WHERE name = '" + userName + "'";

// 格式化字符串
String sql = String.format("SELECT * FROM %s WHERE id = %s", table, id);

// MyBatis ${} 插值
<select id="getUser">
  SELECT * FROM users WHERE name = '${userName}'
</select>
```
完整分析查询构造和执行流程，追踪数据流，确认注入点

**L4**：复杂链路
- 二阶注入：数据库查询结果 → 再次拼接到 SQL，绕过技巧详见：[bypassTricks.md - 二阶SQL注入](bypassTricks.md#二阶sql注入)
- ORM raw 查询：`em.createNativeQuery("SELECT * FROM " + table)`
- 存储过程注入：动态参数拼接
- 缓存/会话数据用于 SQL 构造，绕过技巧详见：[bypassTricks.md - 二阶SQL注入](bypassTricks.md#二阶sql注入)
- 多文件追踪：用户输入 → 数据处理 → SQL 拼接

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 完全参数化 | L0 | 无风险 |
| 参数化 + 动态表名白名单 | L1 | 验证白名单 |
| 拼接 + 过滤 | L2 | 验证过滤规则，绕过技巧详见：[bypassTricks.md - 高级过滤绕过](bypassTricks.md#高级过滤绕过) |
| 直接拼接无防护 | L3 | 高风险 |
| MyBatis ${} 或格式化字符串 | L3 | 高风险 |
| 二阶注入或 ORM raw | L4 | 完整追踪，绕过技巧详见：[bypassTricks.md - 二阶SQL注入](bypassTricks.md#二阶sql注入) |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（不可信输入）→ 处理逻辑 → 危险操作 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（如参数化查询、输入过滤等）
- 遇到保护机制时的绕过技巧参考：
  - 字符串过滤绕过：[bypassTricks.md - 高级过滤绕过](bypassTricks.md#高级过滤绕过)、[编码绕过](bypassTricks.md#编码绕过)
  - ORDER BY 限制绕过：[bypassTricks.md - ORDER BY注入](bypassTricks.md#order-by注入)
  - 宽字节编码绕过：[bypassTricks.md - 宽字节注入](bypassTricks.md#宽字节注入)
  - 类型检查绕过：[bypassTricks.md - 类型混淆注入](bypassTricks.md#类型混淆注入)
  - 二阶注入利用：[bypassTricks.md - 二阶SQL注入](bypassTricks.md#二阶sql注入)
  - 盲注场景利用：[bypassTricks.md - 盲注加速](bypassTricks.md#盲注加速)、[堆叠查询注入](bypassTricks.md#堆叠查询注入)
  - UDF 提权利用：[bypassTricks.md - UDF注入](bypassTricks.md#udf注入)
  - NoSQL 注入：[bypassTricks.md - NoSQL注入](bypassTricks.md#nosql注入)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-sql-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
