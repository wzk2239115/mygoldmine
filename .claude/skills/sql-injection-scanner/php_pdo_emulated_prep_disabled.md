# PHP PDO 模拟预处理禁用导致的 SQL 注入

## Details

### 代码示例
```php
// 风险场景 1: 模拟预处理启用（默认）
$pdo = new PDO($dsn, $user, $pass);
// 未显式设置 PDO::ATTR_EMULATE_PREPARES = false
$stmt = $pdo->prepare("SELECT * FROM users WHERE id = :id");
$stmt->execute(['id' => $user_id]);

// 风险场景 2: query() 直接拼接
$pdo = new PDO($dsn, $user, $pass);
$result = $pdo->query("SELECT * FROM users WHERE name = '$name'");

// 风险场景 3: exec() 直接拼接
$pdo->exec("UPDATE users SET status = '$status' WHERE id = $id");
```

### 快速定位核心操作的技巧（审计等级：L1-L2）
- **L1**: 关键词扫描 - 搜索 `new PDO`、`->prepare`、`->query`、`->exec`
- **L1**: 关键词扫描 - 搜索 `ATTR_EMULATE_PREPARES`（检查是否禁用模拟）
- **L2**: 跳读 - 检查 `prepare()` 后是否使用 `execute()` 传参，还是在 SQL 字符串中直接拼接
- **L2**: 跳读 - 检查 `query()`/`exec()` 的 SQL 语句是否包含变量拼接（`$`、`.`、字符串连接）

### 快速定位保护机制的技巧（审计等级：L2-L3）
- **L2**: 跳读 - 检查 PDO 初始化代码，查找 `setAttribute(PDO::ATTR_EMULATE_PREPARES, false)`
- **L2**: 跳读 - 检查配置文件或初始化脚本中的 PDO 默认设置
- **L3**: 逐行读 - 追踪参数传递链，确认是否在 `execute()` 参数中传递而非字符串拼接
- **L3**: 逐行读 - 检查是否存在输入过滤（`mysqli_real_escape_string`、`addslashes`），但注意这不是完全防护

## Classify

### 漏洞判定
- PDO 连接未设置 `PDO::ATTR_EMULATE_PREPARES = false`，且使用模拟预处理时在多字节字符集环境下可能被绕过
- 使用 `query()` 或 `exec()` 方法时 SQL 语句包含未过滤的用户输入
- 使用 `prepare()` 但在 SQL 字符串中直接拼接变量，而非通过占位符传参
- 虽使用占位符但对表名、列名、ORDER BY 字段等非值部分进行用户输入拼接

### 误报判定
- 使用真正的预处理（`PDO::ATTR_EMULATE_PREPARES = false`）且严格使用占位符传参
- 拼接的变量来自白名单映射或硬编码值，不受用户控制
- 参数已通过严格的类型转换（如 `(int)$id`、`intval()`）且用于整数字段
- 使用了框架的 ORM 层且确认底层正确使用预处理

### 代码异味
- 依赖 `addslashes`、`mysql_real_escape_string` 等转义函数而非预处理
- 混合使用预处理和字符串拼接，增加审计复杂度
- 模拟预处理启用但未在关键位置验证字符集一致性

## Low risk

### 低风险场景
- SQL 语句拼接的变量为管理员专属操作，且存在完善的权限验证机制
- 受影响的查询仅访问低敏感数据（如公开的配置、静态内容）
- 输入已通过严格白名单验证（如枚举类型、固定选项列表）且验证逻辑可靠
- 数据库用户权限受限，仅有特定表的 SELECT 权限，无法执行危险操作
- 应用运行在隔离环境中，数据库不包含敏感信息且与生产环境隔离