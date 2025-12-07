**Go - fmt.Sprintf 构造 SQL 查询**  
常出现在使用 database/sql 包时错误地使用 fmt.Sprintf 或字符串拼接构造查询，而非使用 db.Query/Exec 的参数绑定机制，常见于用户管理、日志查询等模块。

## Details

**代码示例：**
```go
// 典型漏洞模式
username := r.FormValue("username")
query := fmt.Sprintf("SELECT * FROM users WHERE username = '%s'", username)
rows, err := db.Query(query)

// 常见变体
query := "SELECT * FROM logs WHERE id = " + userId  // 直接拼接
query := fmt.Sprintf("DELETE FROM %s WHERE id = %d", tableName, id)  // 表名拼接
```

**快速定位核心操作技巧（L1-L2）：**
- 关键词扫描：`fmt.Sprintf`、`fmt.Sprint`、字符串 `+` 拼接后紧跟 `db.Query`、`db.Exec`、`db.QueryRow`
- 搜索模式：`fmt.Sprintf.*SELECT|INSERT|UPDATE|DELETE`
- 关注 HTTP 参数/用户输入后直接进入格式化字符串的流向
- 优先审查动态构造 WHERE、ORDER BY、LIMIT 子句的代码

**快速定位保护机制技巧（L2-L3）：**
- 检查是否使用占位符 `?` 搭配参数数组：`db.Query("SELECT * FROM users WHERE id = ?", userId)`
- 查找输入校验函数：`regexp.MatchString`、`strconv.Atoi`、白名单映射
- 检查 ORM 使用：`gorm.DB`、`sqlx` 的 `NamedQuery`
- 追踪字符串转义函数（少见但可能存在自定义转义）
- **审计等级 L2-L3**：跳读保护逻辑是否完整覆盖所有拼接点，逐行确认校验有效性

## Classify

**漏洞判定：**
- 外部输入（HTTP 参数、文件、配置）未经校验直接用于 `fmt.Sprintf` 构造 SQL
- 动态拼接表名、列名、ORDER BY 方向等无法使用占位符的场景且无白名单
- 数值类型未进行类型转换（`strconv.Atoi`）直接拼接

**误报判定：**
- 拼接内容完全来自常量、枚举、硬编码字符串
- 输入经过严格白名单校验（如 `switch-case` 限定值域）
- 仅用于日志记录、调试输出而非执行

**代码异味：**
- 即使有校验但拼接方式本身脆弱，易在后续维护中引入漏洞
- 混合使用占位符与拼接（部分参数安全，部分不安全）
- 过度依赖正则校验而非结构化方法

## Low risk

**低风险场景：**
- 拼接内容仅限于管理员配置且配置文件不可写（如数据库配置表名）
- 数值型 ID 经过 `strconv.Atoi` 或 `strconv.ParseInt` 强制类型转换后拼接
- 表名/列名从预定义的 `map[string]string` 白名单映射且键验证严格
- 内部后台功能且调用者身份已通过强认证（需结合业务风险评估）
- SQL 仅用于读取非敏感数据且查询结果不返回给用户（信息泄露风险低）