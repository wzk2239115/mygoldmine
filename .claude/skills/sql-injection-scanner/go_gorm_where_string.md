**Go - GORM Where 条件字符串拼接**  
常出现在 GORM 框架中使用 Where/Raw 方法时错误地使用字符串拼接或 fmt.Sprintf 构造条件，而非使用参数化查询机制，常见于动态条件查询、多条件搜索等模块。

## Details

**代码示例：**
```go
// 典型漏洞模式
username := c.Query("username")
db.Where("username = '" + username + "'").First(&user)  // 字符串拼接

status := c.Query("status")
db.Where(fmt.Sprintf("status = '%s'", status)).Find(&orders)  // Sprintf 拼接

// Raw 查询拼接
keyword := r.FormValue("keyword")
db.Raw("SELECT * FROM products WHERE name LIKE '%" + keyword + "%'").Scan(&results)

// 动态排序拼接
sortBy := c.Query("sort")
db.Order(sortBy).Find(&items)  // 无白名单的列名拼接
```

**快速定位核心操作技巧（L1-L2）：**
- 关键词扫描：`.Where(`、`.Raw(`、`.Order(`、`.Group(` 后接字符串拼接 `+` 或 `fmt.Sprintf`
- 搜索模式：`\.Where\(.*\+\s*|\.Where\(fmt\.Sprintf|\.Raw\(.*\+\s*`
- 关注 HTTP 参数（`c.Query`、`c.Param`、`r.FormValue`）直接流入 GORM 方法调用
- 优先审查多条件动态查询、列表筛选、排序、分组功能
- 注意 `db.Exec()` 方法与原始 SQL 拼接的组合使用

**快速定位保护机制技巧（L2-L3）：**
- 检查是否使用 GORM 参数化：`db.Where("name = ?", username)` 或 `db.Where("age > ? AND status = ?", age, status)`
- 查找结构化条件：`db.Where(&User{Name: name})` 或 `db.Where(map[string]interface{}{"status": status})`
- 检查白名单映射：`allowedFields := map[string]bool{"name": true, "age": true}` 用于列名校验
- 追踪输入校验：`strconv.Atoi`、正则匹配、枚举类型转换
- 检查 Scopes 方法封装：`db.Scopes(FilterByStatus(status))` 可能内含安全处理
- **审计等级 L2-L3**：跳读白名单逻辑覆盖度，逐行确认参数化调用是否完整

## Classify

**漏洞判定：**
- 外部输入（HTTP 参数、表单、JSON 字段）未经校验直接拼接到 Where/Raw/Order 条件
- 动态列名、表名、排序字段无白名单限制直接拼接
- 使用 `fmt.Sprintf` 或 `+` 拼接用户可控内容到 SQL 片段
- Raw 查询中拼接 LIKE 模糊查询关键词、IN 子句数组

**误报判定：**
- 拼接内容完全来自常量、枚举、配置文件硬编码值
- 列名/字段通过严格 `switch-case` 或 `map` 白名单映射后拼接
- 条件值已通过 GORM 参数化（`?` 占位符）传递
- 仅在单元测试或工具脚本中使用且不涉及生产数据

**代码异味：**
- 混合参数化与拼接（部分条件用 `?`，部分条件拼接）
- 依赖前端传递固定值但后端未二次校验
- 动态条件构造逻辑分散在多个函数，追踪困难
- 使用正则校验列名但允许范围过宽（如允许所有字母数字组合）

## Low risk

**低风险场景：**
- 列名从预定义结构体字段映射且映射表不可外部修改
- 排序方向限定为 `"ASC"` 或 `"DESC"` 且通过 `strings.ToUpper` 标准化后白名单匹配
- 数值型 ID 经 `strconv.ParseInt` 强制类型转换后用于条件
- 内部管理后台且已通过角色权限二次鉴权（需评估业务敏感度）
- 拼接内容用于非关键业务的日志查询且结果不包含敏感字段
- GORM Debug 模式日志输出的拼接（仅用于开发调试）