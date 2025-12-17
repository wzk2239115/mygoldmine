**C/C++ - SQLite 原始查询 SQL 注入审计**  
常出现在数据库驱动层、嵌入式系统或服务端中间件中直接使用字符串拼接构造 SQL 查询的功能，包括但不限于通过 sprintf、strcat 等函数动态组装 SQL 语句的方式。  
- MySQL 原始查询接口 mysql_real_query 的风险场景，详见：c_mysql_real_query_usage.md  

---

## Details

**典型代码示例**
```c
// 危险：使用 sprintf/strcat 拼接用户输入
char sql[256];
sprintf(sql, "SELECT * FROM users WHERE name='%s'", user_input);
sqlite3_exec(db, sql, callback, 0, &err);

// 危险：使用字符串连接函数
char query[512];
strcpy(query, "DELETE FROM logs WHERE id=");
strcat(query, id_param);
sqlite3_exec(db, query, NULL, 0, NULL);
```

**快速定位核心操作技巧** (L1-L2)
- 关键 API：`sqlite3_exec()`, `sqlite3_get_table()`, `sqlite3_prepare()` 未使用绑定
- 字符串拼接函数：`sprintf()`, `snprintf()`, `strcat()`, `strcpy()`, `strncpy()` 后接 SQL 执行
- 代码模式：变量名含 `query/sql/cmd` + 字符串操作函数 + SQLite API
- IDE 搜索：`sqlite3_exec.*%s` 或 `sprintf.*SELECT|UPDATE|DELETE|INSERT`

**快速定位保护机制技巧** (L2-L3)
- 参数化查询：`sqlite3_prepare_v2()` + `sqlite3_bind_*()` 系列函数（文本用 `bind_text`，整数用 `bind_int`）
- 输入校验：调用前是否有白名单检查（如 `isdigit()`, 枚举值对比, 正则匹配）
- 转义函数：`sqlite3_mprintf("%q", input)` 中的 `%q` 可转义单引号（但不推荐）
- ORM/封装层：是否使用安全的数据库抽象层替代原始 API

---

## Classify

**漏洞判定**
- 外部输入（HTTP 参数、文件内容、IPC 数据）直接拼接到 SQL 且无校验/转义 → 确认漏洞
- 拼接变量可追溯到用户可控源头（函数参数传递链条） → 确认漏洞

**误报判定**
- 拼接内容为编译期常量、枚举值、硬编码字符串 → 误报
- 输入已通过严格白名单校验（如纯数字检查：`atoi()` 后仅操作整型，或字段名限定在固定集合） → 误报
- 仅用于构造表名/列名且已做字典映射校验 → 可能误报（需视具体校验强度）

**代码异味**
- 使用 `sqlite3_mprintf()` 的 `%q` 格式化：虽有转义能力但易误用（如整数字段用 `%d` 无保护），建议改用参数化
- 动态 SQL 构造逻辑复杂（多层字符串拼接），即使当前安全但维护性差、未来引入风险高

---

## Low risk

- **受限输入环境**：仅在本地管理工具、调试接口中使用，且明确要求管理员权限（root/admin）才可触发
- **查询结果不外传**：仅用于内部日志记录或统计，注入者无法通过返回结果或副作用获得收益
- **沙箱隔离执行**：SQLite 数据库位于独立沙箱（如容器、虚拟机、权限受限进程），且数据库仅含非敏感数据
- **输入长度极端受限**：输入被强制截断至极短长度（如 8 字符以内），且已排除特殊字符，理论上难以构造有效 Payload
- **只读数据库**：数据库以 `SQLITE_OPEN_READONLY` 模式打开，仅存在信息泄露风险而无数据篡改风险