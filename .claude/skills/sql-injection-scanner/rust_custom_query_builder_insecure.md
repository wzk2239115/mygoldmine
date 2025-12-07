# Rust 自定义查询构建器不安全实现

## Details

### 代码示例
```rust
// 不安全：使用 format! 宏拼接 SQL
let table_name = req.query_param("table");
let query = format!("SELECT * FROM {} WHERE id = ?", table_name);
sqlx::query(&query).bind(id).fetch_all(&pool).await?;

// 不安全：字符串拼接构建动态列名
let sort_column = params.get("sort").unwrap();
let sql = format!("SELECT * FROM users ORDER BY {}", sort_column);
sqlx::query_as::<_, User>(&sql).fetch_all(&pool).await?;

// 不安全：自定义 QueryBuilder 使用字符串插值
impl QueryBuilder {
    fn add_filter(&mut self, field: &str, value: &str) {
        self.where_clause.push_str(&format!("{} = '{}'", field, value));
    }
}

// 不安全：diesel 动态 SQL 拼接
let raw_sql = format!("SELECT * FROM {} WHERE status = 'active'", table);
diesel::sql_query(raw_sql).load::<Record>(&conn)?;
```

### 快速定位核心操作（L2：跳读）
- 搜索 `format!` + SQL 关键字组合（SELECT/INSERT/UPDATE/DELETE/WHERE/ORDER BY）
- 定位 `sqlx::query(&string_var)` 中 string_var 的来源
- 追踪 `diesel::sql_query()` 的参数构建过程
- 查找自定义 struct 中包含 `query`/`sql`/`where`/`filter` 字段的字符串操作
- 检查 `.push_str()` / `String::from()` / `to_string()` 后直接传入执行函数

### 快速定位保护机制（L3：逐行读）
- 检查是否使用 `query!` 宏（编译时检查）而非 `query()` 函数
- 确认 `bind()` 调用是否覆盖所有动态参数（仅值参数，不含表/列名）
- 识别白名单验证：`match`/`if let` 限定合法值集合
- 查找 `regex` crate 对标识符的严格校验（`^[a-zA-Z_][a-zA-Z0-9_]*$`）
- diesel 中检查是否使用 `.filter(dsl::column.eq(bind_value))` 而非字符串拼接
- 追踪变量是否来自常量/静态配置而非外部输入

## Classify

**漏洞判定标准：**
- 外部输入（HTTP 参数、文件、环境变量）流入 SQL 字符串拼接路径且无有效验证
- 动态表名/列名/ORDER BY 子句使用 `format!` 构建，即使值参数已参数化
- 自定义查询构建器在 `impl` 块中直接操作字符串字段，未隔离危险操作

**误报识别：**
- 所有动态部分均来自硬编码常量或枚举类型的 `match` 分支
- 白名单校验逻辑完整且在 SQL 构建前执行（需确认白名单不可绕过）
- 使用类型安全的查询构建器（如 diesel 的 DSL）且未调用 `sql_query`

**代码异味：**
- 字符串拼接存在但当前输入受控，未来可能引入新输入源
- 复杂的字符串操作逻辑缺乏安全注释，维护者可能误判安全性
- 混用参数化查询和字符串拼接，增加审计复杂度

## Low risk

**降低风险评级的场景：**
- 动态部分仅限内部配置文件读取，且部署环境限制配置文件修改权限
- 输入经过严格枚举校验，穷举所有可能值且数量≤10，业务逻辑不支持扩展
- 查询仅用于日志记录或监控统计，不返回敏感数据且不影响业务逻辑
- 存在多层防护：WAF 规则、数据库用户权限最小化、只读从库执行
- 受影响表为临时表或测试表，生产环境未启用该功能模块