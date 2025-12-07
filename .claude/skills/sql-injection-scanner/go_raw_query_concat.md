**Go - database/sql 原始查询字符串拼接**  
常出现在使用 database/sql 包时错误地使用字符串拼接（`+` 操作符）构造查询，而非使用 db.Query/Exec 的参数绑定机制，常见于用户管理、日志查询、动态条件筛选等模块。

## Details

**代码示例：**
```go
// 典型漏洞模式 - 直接拼接用户输入
userId := r.FormValue("id")
query := "SELECT * FROM users WHERE id = " + userId  // 数值拼接
rows, err := db.Query(query)

username := r.URL.Query().Get("name")
sql := "SELECT * FROM accounts WHERE name = '" + username + "'"  // 字符串拼接
db.QueryRow(sql).Scan(&account)

// 动态条件拼接
condition := c.Query("filter")
query := "DELETE FROM logs WHERE " + condition  // 整条件拼接
db.Exec(query)

// 表名/列名拼接
tableName := r.Header.Get("X-Table")
query := "SELECT * FROM " + tableName + " LIMIT 100"  // 表名拼接
```

**快速定位核心操作技巧（L1-L2）：**
- 关键词扫描：字符串 `+` 操作符后紧跟 `db.Query`、`db.Exec`、`db.QueryRow`、`tx.Query`
- 搜索模式：`"SELECT.*"\s*\+|"INSERT.*"\s*\+|"UPDATE.*"\s*\+|"DELETE.*"\s*\+`
- 追踪 HTTP 输入源：`r.FormValue`、`c.Query`、`c.Param`、`r.URL.Query().Get` 后的变量流向
- 关注多行拼接构造：`query := "SELECT *"; query += " WHERE id = " + input`
- 优先审查动态 WHERE、IN 子句、ORDER BY、表名/列名的拼接场景

**快速定位保护机制技巧（L2-L3）：**
- 检查参数化查询：`db.Query("SELECT * FROM users WHERE id = ?", userId)` 或 `$1` 占位符（PostgreSQL）
- 查找类型转换校验：`strconv.Atoi`、`strconv.ParseInt`、`strconv.ParseFloat` 强制类型转换
- 检查白名单映射：`allowedTables := map[string]bool{"users": true}` 用于表名/列名限定
- 追踪输入校验函数：`regexp.MatchString`、`strings.Contains` 检测特殊字符、枚举值比对
- 检查 SQL Builder 使用：`squirrel`、`goqu` 等库的结构化查询
- **审计等级 L2-L3**：跳读校验逻辑覆盖所有拼接变量，逐行确认白名单/类型转换完整性

## Classify

**漏洞判定：**
- 外部输入（HTTP 参数、文件内容、消息队列数据）未经校验直接字符串拼接到 SQL
- 动态拼接表名、列名、排序字段且无白名单限制
- 字符串类型输入直接拼接到 SQL 且未经转义或参数化
- 数值型输入未经类型转换直接拼接（如 `"WHERE id = " + strId`）

**误报判定：**
- 拼接内容完全来自常量、枚举、配置文件硬编码值（编译期确定）
- 输入经过严格白名单校验（如 `switch-case` 穷举所有可能值）
- 数值通过 `strconv.Atoi` 转换后再用 `strconv.Itoa` 拼接（虽不推荐但安全）
- 仅用于日志输出、调试打印而非实际执行查询

**代码异味：**
- 混合使用拼接与参数化（部分条件用 `?`，部分条件拼接）
- 依赖正则校验输入但规则过于宽松（如仅排除空格和引号）
- 多层函数传递后拼接，难以追溯输入源头
- 使用字符串替换（`strings.Replace`）尝试转义但方法不可靠

## Low risk

**低风险场景：**
- 拼接内容仅为管理员配置的数据库表名且配置存储在服务端只读文件中
- 数值型参数经 `strconv.ParseInt` 强制转换并验证错误后拼接
- 表名/列名从预定义常量映射表 `map[string]string` 查询且键验证严格
- 内部管理工具且访问受 VPN + 双因素认证保护（需评估业务敏感度）
- 查询仅用于读取非敏感统计数据且不返回给前端（信息泄露风险低）
- SQL 拼接发生在单元测试或数据迁移脚本中且不部署到生产环境