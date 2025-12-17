# Java - 二阶 SQL 注入

## Details

### 什么是二阶 SQL 注入

二阶 SQL 注入（Second-Order SQL Injection）是指恶意 SQL 代码被存储到数据库中，然后在后续的数据检索或处理时被执行的漏洞。与一阶注入不同，二阶注入的触发点和注入点不是同一个地方。

**攻击流程：**
1. **数据存储阶段**：用户输入被安全地存储到数据库（未被立即执行）
2. **数据查询阶段**：应用从数据库中读取数据，并将其用于构造 SQL 查询
3. **漏洞触发**：由于第二步中对数据的处理不当，导致 SQL 注入

### 典型场景一：用户信息存储后作为搜索条件

**第一步：用户信息注册（看起来安全，使用了 PreparedStatement）**
```java
@PostMapping("/register")
public String register(String username, String email) {
    String sql = "INSERT INTO users (username, email) VALUES (?, ?)";
    jdbcTemplate.update(sql, username, email);
    return "User registered";
}
```

用户输入：`username: "admin' OR '1'='1"` 被安全地存储到数据库。

**第二步：搜索用户（漏洞发生）**
```java
@GetMapping("/search")
public List<User> searchByName(String keyword) {
    // 从数据库读取用户信息
    String sql = "SELECT * FROM users WHERE username LIKE ?";
    List<User> users = jdbcTemplate.query(sql, rs -> {
        // ... 处理结果集
    }, keyword);

    // 危险：将从数据库读出的用户名用于构造新的 SQL 查询
    String usernames = users.stream()
        .map(u -> u.getUsername())
        .collect(Collectors.joining("','"));

    String reportSql = "SELECT * FROM logs WHERE user IN ('" + usernames + "')";
    // 执行构造的 SQL，此时 admin' OR '1'='1 被执行
    List<Log> logs = jdbcTemplate.queryForList(reportSql, Log.class);
    return logs;
}
```

### 典型场景二：日志检索

**第一步：记录用户操作（安全存储）**
```java
@PostMapping("/api/action")
public void logAction(String action, String userId) {
    String sql = "INSERT INTO audit_log (action, user_id) VALUES (?, ?)";
    jdbcTemplate.update(sql, action, userId);
}
```

用户输入：`action: "DELETE FROM users WHERE 1=1; --"`

**第二步：日志导出功能（漏洞发生）**
```java
@GetMapping("/export-logs")
public List<Log> exportLogs(String userId) {
    // 获取用户的日志记录
    String sql = "SELECT * FROM audit_log WHERE user_id = ?";
    List<Log> logs = jdbcTemplate.query(sql, new LogRowMapper(), userId);

    // 危险：直接将日志内容用于 SQL 查询
    for (Log log : logs) {
        String action = log.getAction();  // 从数据库读出的数据
        String detailSql = "SELECT detail FROM action_details WHERE action_name = '" + action + "'";
        List<String> details = jdbcTemplate.queryForList(detailSql, String.class);
        log.setDetails(details);
    }
    return logs;
}
```

### 典型场景三：报告生成

**存储用户提供的过滤条件（不安全）**
```java
@PostMapping("/create-report")
public void createReport(String filterId, String filterCondition) {
    // filterId 用于存储报告标识
    // filterCondition 被存储但稍后会被执行
    String sql = "INSERT INTO reports (filter_id, filter_condition) VALUES (?, ?)";
    jdbcTemplate.update(sql, filterId, filterCondition);
}
```

用户输入：`filterCondition: "department='Sales' OR '1'='1"`

**生成报告时重新使用过滤条件（漏洞触发）**
```java
@GetMapping("/generate-report")
public List<Employee> generateReport(String filterId) {
    // 从数据库读取过滤条件
    String sql = "SELECT filter_condition FROM reports WHERE filter_id = ?";
    String condition = jdbcTemplate.queryForObject(sql, String.class, filterId);

    // 危险：直接拼接读出的条件到 SQL
    String reportSql = "SELECT * FROM employees WHERE " + condition;
    List<Employee> employees = jdbcTemplate.query(reportSql, new EmployeeRowMapper());
    return employees;
}
```

### 快速定位核心操作（L1: 关键词扫描）

**危险的数据流：**
1. 数据从数据库读出
2. 数据未进行二次验证或清理
3. 数据直接参与 SQL 查询构造

**关键代码模式：**
```
// 模式 1：从 ResultSet 读出数据后直接拼接
String value = resultSet.getString("column");
String newSql = "SELECT * FROM table WHERE condition = '" + value + "'";

// 模式 2：使用 Stream 构造 SQL
List<String> items = queryDatabase();
String ids = items.stream().collect(Collectors.joining("','"));
String sql = "SELECT * FROM table WHERE id IN ('" + ids + "')";

// 模式 3：循环读取数据库结果后构造 SQL
for (Item item : items) {
    String sql = "SELECT * FROM table WHERE name = '" + item.getName() + "'";
}

// 模式 4：配置或用户设置值被存储后再次使用
String filter = getStoredFilter();  // 从数据库读出
String sql = "SELECT * FROM data WHERE filter = '" + filter + "'";
```

**关键库函数：**
```
jdbcTemplate.queryForObject()
jdbcTemplate.query()
jdbcTemplate.queryForList()
connection.createStatement().executeQuery()
resultSet.getString()
resultSet.getInt()
```

### 快速定位保护机制（L2: 跳读）

**正确的防护方式（使用 PreparedStatement）：**
```java
@GetMapping("/safe-search")
public List<Employee> safeSearch(String department) {
    // 从数据库读取过滤条件
    String sql = "SELECT filter_condition FROM reports WHERE filter_id = ?";
    String condition = jdbcTemplate.queryForObject(sql, String.class, filterId);

    // 正确：使用 PreparedStatement
    String reportSql = "SELECT * FROM employees WHERE " + condition + " AND department = ?";
    List<Employee> employees = jdbcTemplate.query(
        reportSql,
        new EmployeeRowMapper(),
        department  // 参数化
    );
    return employees;
}
```

**防护的关键点：**
```java
// 检查是否使用了参数化查询
PreparedStatement ps = connection.prepareStatement("SELECT * FROM users WHERE id = ?");
ps.setInt(1, userId);  // 参数化

// 检查是否使用了命名参数
JdbcTemplate template = new JdbcTemplate();
template.query("SELECT * FROM users WHERE id = :id",
    Collections.singletonMap("id", userId),
    new RowMapper<User>() { ... });

// 检查是否使用了 ORM 框架
// Hibernate/JPA 的 Criteria API 或 QueryDSL
CriteriaBuilder cb = entityManager.getCriteriaBuilder();
CriteriaQuery<User> query = cb.createQuery(User.class);
Root<User> root = query.from(User.class);
query.where(cb.equal(root.get("id"), userId));
```

**输入验证（不够但有帮助）：**
```java
// 白名单验证（如果条件是预定义的）
String[] ALLOWED_FILTERS = {"active", "inactive", "pending"};
if (!Arrays.asList(ALLOWED_FILTERS).contains(condition)) {
    throw new IllegalArgumentException("Invalid filter");
}

// 长度限制
if (condition.length() > 100) {
    throw new IllegalArgumentException("Input too long");
}
```

**审计技巧（L3: 逐行读）：**
- 追踪从数据库查询出来的数据
- 检查这些数据是否被用于后续的 SQL 查询构造
- 关注字符串拼接（`+`, `String.format()`, 模板）
- 验证是否使用了 PreparedStatement 的参数化

**跨模块保护（L4: 跨模块追踪）：**
- 数据持久层是否统一使用 ORM（Hibernate、JPA）
- 是否存在 SQL 查询的全局拦截器
- 框架层面是否提供了安全的查询构造方法

## Classify

### 确认为漏洞

- 从数据库读出的数据被用于构造 SQL 查询
- 构造 SQL 时使用了字符串拼接而非参数化查询
- 虽然初始存储时使用了参数化，但读出后的数据未再次参数化
- 可以通过两步 PoC 验证：注入恶意数据 → 查询或处理数据时触发

### 误报场景

- 读出的数据仅用于展示/返回，不参与 SQL 查询
- 数据被读出后经过了严格的验证/清理
- 后续 SQL 查询使用了参数化绑定
- 数据来自系统内部可信来源（如配置文件），非用户输入

### 代码异味

- 数据库查询结果与 SQL 构造没有清晰的边界
- 应用中存在多个位置进行类似的不安全数据流转
- 没有统一的数据验证层
- 使用了字符串拼接的动态 SQL，但缺乏参数化

## Low risk

### 降级为低风险的情况

- **严格的输入验证**：初始数据存储时经过白名单验证，后续使用时再次验证
- **数据类型限制**：存储的数据只包含数字或已知安全的固定值
- **长度限制**：存储数据的长度严格限制，无法容纳 SQL 注入 payload
- **读权限限制**：能读取这些数据的用户角色权限受限
- **使用 ORM**：应用统一使用 Hibernate/JPA 的参数化查询，排除手动 SQL 构造

### 需要额外评估的因素

- 被注入数据能否访问关键表（users、admin、credentials）
- 注入的 SQL 能否修改数据或导致数据泄露
- 是否存在存储的过程/触发器用于数据处理
- 数据库账户的权限级别（是否有 DROP TABLE 权限）
