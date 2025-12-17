# C/C++ MySQL 原始查询接口 mysql_real_query 风险

## Details

### 漏洞成因
`mysql_real_query()` 是 MySQL C API 中执行原始 SQL 查询的底层接口，接收任意字符串形式的 SQL 语句。当开发者使用 `sprintf`、`snprintf`、`strcat` 等函数将用户输入动态拼接到 SQL 语句后直接传递给 `mysql_real_query()` 执行时，若未进行参数化处理或适当转义，攻击者可通过构造特殊输入注入恶意 SQL 代码。该函数本身不提供参数绑定机制，完全依赖开发者手动保护输入安全性。

### 代码示例

**易受攻击的代码：**
```c
// 场景：商品搜索接口
MYSQL *conn;
char query[512];
char search_keyword[128];

// 从 HTTP 请求获取搜索关键词
get_http_param("keyword", search_keyword, sizeof(search_keyword));

// 不安全的 SQL 拼接
sprintf(query, "SELECT id, name, price FROM products WHERE name LIKE '%%%s%%'", 
        search_keyword);

// 直接执行原始查询
if (mysql_real_query(conn, query, strlen(query)) != 0) {
    fprintf(stderr, "Query failed: %s\n", mysql_error(conn));
}
```

**另一个风险示例（使用 strcat）：**
```c
char sql[1024] = "UPDATE users SET email='";
strcat(sql, new_email);  // new_email 来自用户输入
strcat(sql, "' WHERE id=");
strcat(sql, user_id);    // user_id 可能来自 Cookie 或 URL 参数
mysql_real_query(conn, sql, strlen(sql));
```

**第三方封装函数中的隐藏风险：**
```c
// 自定义数据库查询函数
int db_exec_query(MYSQL *conn, const char *table, const char *condition) {
    char buffer[2048];
    snprintf(buffer, sizeof(buffer), "SELECT * FROM %s WHERE %s", table, condition);
    return mysql_real_query(conn, buffer, strlen(buffer));
}

// 调用处将用户输入直接传递
db_exec_query(conn, "orders", user_supplied_filter);  // 高风险
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描（L1）：**
- **主要目标函数：** `mysql_real_query`、`mysql_query`
- **辅助拼接函数：** `sprintf`、`snprintf`、`strcat`、`strncat`、`strcpy`、`memcpy`
- **C++ 拼接方式：** `std::string::append`、`std::stringstream`、`operator+`

**定位步骤：**
1. 全局搜索 `mysql_real_query` 和 `mysql_query` 的所有调用点
2. 对每个调用点，回溯其第二个参数（SQL 字符串）的构造过程
3. 过滤出使用拼接函数构造的 SQL 语句（跳读 L2）
4. 重点关注 SQL 中包含 `WHERE`、`LIKE`、`ORDER BY` 等可控条件的查询

#### 保护机制定位（审计等级：L2-L4）
**检查是否存在以下安全措施：**

- **预编译语句替代（推荐方案）：**
  - `mysql_stmt_init` + `mysql_stmt_prepare` + `mysql_stmt_bind_param` + `mysql_stmt_execute`
  - 若已使用此方案，审计等级为 **L0（快速跳过）**

- **转义函数调用（次优方案）：**
  - `mysql_real_escape_string(conn, escaped_buf, user_input, strlen(user_input))`
  - 检查是否在拼接前对所有外部输入调用了此函数
  - 若存在转义，审计等级降为 **L2（跳读）**，需验证转义是否完整覆盖

- **输入验证与白名单：**
  - 数值型参数的类型转换：`atoi`、`strtol`、`strtoull`
  - 白名单校验：枚举值匹配、正则表达式限制字符集（如 `^[a-zA-Z0-9_]+$`）
  - 长度限制检查（但单独的长度限制不足以防御 SQL 注入）

**审计等级决策树：**

| 场景描述 | 审计等级 | 审计重点 |
|---------|---------|---------|
| 完全使用 `mysql_stmt_*` 预编译 API | **L0（快速跳过）** | 无需深入分析 |
| SQL 常量拼接，无变量插入 | **L0（快速跳过）** | 确认是否真的无变量 |
| 拼接数值且使用 `atoi` 等转换 | **L1（关键词扫描）** | 确认转换后未再拼接其他字符串 |
| 使用 `mysql_real_escape_string` 转义 | **L2（跳读）** | 验证所有拼接点均已转义 |
| 拼接来自外部输入但无保护 | **L3（逐行读）** | 追踪输入来源，确认可控性 |
| 输入经多函数传递后拼接 | **L4（跨模块追踪）** | 跨文件追踪数据流，检查是否在某层被清理 |
| 第三方封装函数（如 `db_exec_query`） | **L4（跨模块追踪）** | 追踪封装函数的所有调用点 |

#### 特殊关注点
- **动态表名/列名：** `SELECT * FROM %s` 中的表名拼接无法使用预编译，必须使用严格白名单验证
- **二次编码问题：** 注意输入是否先经过 URL 解码、Base64 解码等处理，可能绕过简单的字符过滤
- **连接字符集：** 若连接字符集与转义函数字符集不一致，可能导致多字节字符绕过 `mysql_real_escape_string`

## Classify

### 研判标准

#### 确认漏洞
同时满足以下三个条件时，判定为 SQL 注入漏洞：
1. **使用原始查询接口：** 通过 `mysql_real_query` 或 `mysql_query` 执行 SQL
2. **存在动态拼接：** SQL 语句包含通过字符串拼接方式插入的变量
3. **输入可控且无保护：**
   - 变量来源可追溯到外部输入（HTTP 参数、命令行参数、配置文件、文件内容、网络数据包）
   - 未使用预编译语句
   - 未调用 `mysql_real_escape_string` 或调用不完整
   - 无有效白名单验证

#### 误报
以下情况可排除为误报：
1. **拼接内容为常量或内部配置：** 变量值为硬编码字符串常量、宏定义、或从受控配置文件读取的固定枚举值
2. **已正确使用转义函数：** 在拼接前对所有外部输入调用了 `mysql_real_escape_string`，且确保：
   - 连接已通过 `mysql_real_connect` 建立
   - 转义使用的连接句柄与执行查询的句柄一致
   - 转义缓冲区大小足够（至少为 `strlen(input) * 2 + 1`）
3. **严格的类型检查与白名单：**
   - 对于数值型参数，使用 `strtol` 并检查转换错误，且未拼接其他字符串
   - 对于标识符（表名、列名），通过数组枚举或哈希表进行白名单匹配

#### 代码异味
即使暂时不构成可利用漏洞，以下情况也应标记为代码异味（需重构）：
1. **部分转义：** 只对部分输入变量进行了转义，其他变量仍直接拼接
2. **自定义转义逻辑：** 使用自行编写的字符替换函数而非 `mysql_real_escape_string`，容易遗漏特殊字符
3. **混用拼接与预编译：** 同一项目中部分代码使用预编译，部分代码使用拼接，缺乏统一规范
4. **依赖客户端过滤：** 假定前端或中间件已做输入验证，后端未再次检查
5. **动态拼接 SQL 结构：** 拼接 `ORDER BY`、`GROUP BY`、`LIMIT` 等子句，即使参数本身安全，也可能导致逻辑漏洞

## Low risk

### 低风险评级场景

#### 1. 输入来源受限且可信
- **场景：** 拼接的变量来自管理员配置文件、环境变量或内部服务调用（非用户直接输入）
- **风险评估：** 攻击面较小，需要攻击者先获得配置文件写权限或管理员权限
- **注意事项：** 若配置文件权限管理不当或管理后台存在其他漏洞，仍可能被利用

#### 2. 数值型参数经类型转换
- **场景：** 使用 `atoi`、`strtol` 将字符串强制转换为整数，然后使用 `%d` 或 `%ld` 格式化到 SQL 中
- **风险评估：** 大幅降低注入风险，因为转换后的值不会包含 SQL 特殊字符
- **注意事项：** 仍需确保转换后未与其他字符串直接拼接，且未使用 `%s` 格式化原始字符串

#### 3. 查询对象权限受限
- **场景：** 存在注入点，但数据库连接使用的账户仅有特定表的只读权限，无法访问敏感表或执行写操作
- **风险评估：** 潜在危害受限，但仍可能导致数据泄露、逻辑绕过或拒绝服务攻击（如 `UNION` 查询大量数据）
- **注意事项：** 不应依赖数据库权限控制作为主要防护手段

#### 4. 部署环境存在外部防护
- **场景：** 虽然代码存在拼接，但部署时配置了 Web 应用防火墙（WAF）、入侵检测系统（IDS）或数据库审计工具
- **风险评估：** 外部防护可能被绕过（如编码混淆、分段注入），不应作为长期安全依赖
- **修复建议：** 应优先修复代码层面的问题，外部防护仅作为纵深防御的一环

#### 5. 输入长度极度受限
- **场景：** 输入参数经过严格的长度限制（如仅允许 3-5 个字符），且查询结构简单
- **风险评估：** 攻击者构造复杂 Payload 的空间受限，但短小精悍的注入仍可能成功（如 `' OR 1#`）
- **注意事项：** 长度限制不能替代参数化查询或转义

### 风险降级条件总结
| 条件 | 降级理由 | 仍需修复优先级 |
|------|----------|---------------|
| 输入仅来自管理员/配置 | 攻击面小，需前置权限 | 中 |
| 数值型参数+类型转换 | 注入难度高，特殊字符被消除 | 中 |
| 数据库账户权限受限 | 影响范围可控 | 低 |
| 存在 WAF/IDS 等外部防护 | 有缓解措施但可能被绕过 | 高（代码仍需修复）|
| 输入长度极度受限 | 攻击 Payload 空间受限 | 中 |