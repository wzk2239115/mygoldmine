# Rust Diesel 原始 SQL 字符串拼接

## Details

**代码示例：**
```rust
use diesel::sql_query;
use diesel::prelude::*;

// 危险：使用 format! 拼接用户输入
let table_name = req.query("table");
let query = format!("SELECT * FROM {} WHERE id = 1", table_name);
sql_query(&query).execute(conn)?;

// 危险：使用字符串拼接
let user_input = get_user_input();
let sql = "SELECT * FROM users WHERE name = '".to_string() + &user_input + "'";
sql_query(sql).load::<User>(conn)?;

// 危险：在 sql_query 中使用动态字符串
sql_query(format!("DELETE FROM {} WHERE status = '{}'", table, status))
    .execute(conn)?;
```

**快速定位核心操作技巧（L1-L2）：**
- 关键词：`sql_query(` + `format!` / `+` / `&` / `to_string()`
- 模式：`sql_query(format!` 或 `sql_query(&format!` 或 `sql_query(String::from`
- 特征：diesel::sql_query 接收动态构造的字符串参数
- 扫描：在 `use diesel::sql_query` 附近搜索字符串拼接操作

**快速定位保护机制技巧（L2-L3）：**
- 安全：`sql_query(...).bind::<Text, _>(user_input)` 使用参数绑定
- 安全：通过 diesel 的 DSL 构造查询（如 `users.filter(name.eq(input))`）
- 防护：输入在 format! 前经过白名单验证（如 `match table_name { "users" | "posts" => ... }`）
- 防护：使用常量或枚举映射表名/列名，而非直接拼接
- 审计等级：
  - L1：确认存在 `sql_query(format!` 组合
  - L2：跳读参数来源是否为外部输入
  - L3：逐行检查是否有 bind 调用或白名单验证
  - L4：追踪参数跨函数传递，确认输入源头

## Classify

**漏洞判定：**
- 外部可控数据（用户输入、请求参数、环境变量等）通过 format!、字符串拼接直接嵌入 sql_query
- 动态表名/列名来自不可信源且未白名单校验
- 绕过 diesel 类型安全机制，直接操作原始 SQL 字符串

**误报判定：**
- 拼接内容为硬编码常量或配置文件中的可信值
- 使用 bind 进行参数化查询：`sql_query(...).bind::<Type, _>(param)`
- 输入已通过严格白名单验证（如枚举映射）

**代码异味：**
- 虽使用白名单但逻辑复杂，存在绕过风险
- 部分参数使用 bind，但表名/列名仍拼接
- 注释标注"已验证"但无实际检查代码

## Low risk

**以下情况可评为低风险：**
- SQL 字符串完全静态，无任何动态部分
- 动态部分仅为数值型且已通过类型系统保证（如 `format!("LIMIT {}", limit: i32)`）
- 输入来源受严格访问控制（如仅管理员可调用，且有二次认证）
- 表名/列名通过穷举枚举映射，不可能注入其他值
- 使用场景为内部工具、一次性脚本，非面向公网服务