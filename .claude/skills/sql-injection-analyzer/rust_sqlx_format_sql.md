# Rust sqlx format! 宏格式化 SQL 注入

## Details

**代码示例：**
```rust
use sqlx::{query, query_as, PgPool};

// 危险：使用 format! 拼接表名
let table = req.query("table");
let sql = format!("SELECT * FROM {} WHERE status = $1", table);
query(&sql).bind("active").fetch_all(&pool).await?;

// 危险：使用 format! 拼接列名
let column = params.get("sort_by").unwrap();
let query_str = format!("SELECT * FROM users ORDER BY {}", column);
query_as::<_, User>(&query_str).fetch_all(&pool).await?;

// 危险：动态 WHERE 条件拼接
let field = user_input.field;
let sql = format!("SELECT * FROM data WHERE {} = $1", field);
query(&sql).bind(value).fetch_all(&pool).await?;

// 危险：混合拼接表名和条件
let table_name = get_table_from_request();
let filter = format!("SELECT id, name FROM {} WHERE created_at > $1", table_name);
query(&filter).bind(timestamp).fetch_all(&pool).await?;
```

**快速定位核心操作技巧（L1-L2）：**
- 关键词：`query(&` + `format!` / `query_as(&format!` / `query_as::<`
- 特征模式：`sqlx::query(&format!(...))` 或 `query_as::<_, T>(&format!(...))` 
- SQL 字符串变量：`query(&sql)` 中 sql 的来源追踪，向上查找 format!/String 操作
- 扫描：`use sqlx::query` 后搜索 format! 宏调用，或在 query() 附近查找 + / &str 拼接
- 审计等级：
  - L1：关键词扫描 `query(` + `format!` 组合确认存在拼接
  - L2：跳读检查 format! 参数来源，判断是否为外部输入

**快速定位保护机制技巧（L2-L3）：**
- 安全：使用 `query!` / `query_as!` 宏（编译时校验，需静态 SQL）
- 安全：仅对值使用占位符 `$1, $2` + `.bind()` 参数化，表/列名为常量
- 防护：白名单校验 `match table_name { "users" | "posts" | "logs" => ... _ => reject }`
- 防护：枚举映射 `let table = TableEnum::from_str(input)?` 转为受控字符串
- 防护：正则验证标识符 `Regex::new(r"^[a-zA-Z_][a-zA-Z0-9_]*$")?` 且长度限制
- 审计等级：
  - L2：跳读确认是否使用 bind() 且检查白名单存在性
  - L3：逐行审查白名单覆盖度、枚举映射完整性、正则规则严格性
  - L4：跨模块追踪参数来源，确认输入流从请求到 SQL 的完整路径

## Classify

**漏洞判定：**
- 外部可控输入（请求参数、表单、路径变量、header、cookie）通过 format! 直接嵌入 SQL
- 动态表名、列名、ORDER BY、LIMIT 子句使用 format! 构造且输入未经白名单验证
- 虽使用 bind() 参数化值，但表/列名仍通过字符串拼接引入
- 绕过 sqlx 的编译时检查机制（未使用 query!/query_as! 宏）

**误报判定：**
- 拼接内容为硬编码常量、静态字符串字面量或配置文件中的可信值
- 所有动态部分均使用 `$1, $2` 占位符 + bind() 参数化，无表/列名拼接
- 输入通过严格枚举类型（如 #[derive(FromStr)]）校验且穷举所有可能值
- 白名单逻辑使用 match 精确匹配，默认分支拒绝未知输入，无正则或 contains() 等模糊匹配

**代码异味：**
- 白名单通过 `if input.contains("某值")` 或正则 `.*pattern.*` 判断，存在绕过风险
- 注释标注"已验证"但实际验证代码在其他模块且无明确调用链证明
- 混用 query! 和 query()，增加维护者对安全性的误判风险
- 部分字段参数化，部分字段拼接，逻辑分散导致审计遗漏
- 自定义函数封装 format!，表面无拼接特征但深层调用链中存在

## Low risk

**以下情况可评为低风险：**
- SQL 字符串完全静态，无任何 format!、+、to_string() 等动态构造
- 动态部分仅为数值型（i32、u64）且已通过类型系统保证无字符串操作
- 输入来源为内部配置文件（TOML、JSON）且部署环境文件权限受严格控制（root only）
- 表名/列名通过不超过 5 个值的枚举映射，业务逻辑不支持新增且代码库全局搜索无扩展点
- 执行查询的数据库用户为只读权限，且目标表不含敏感数据（如公开统计表、日志表）
- 应用场景为内部运维工具、一次性数据迁移脚本，无公网暴露且需二次身份认证
- 存在多层防护：输入长度≤3、仅允许 `[a-z]`、WAF 规则、数据库审计日志完整
