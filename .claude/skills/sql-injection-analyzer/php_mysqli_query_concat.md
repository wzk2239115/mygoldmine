# PHP mysqli_query 直接拼接用户输入

## Details

**典型代码模式：**
```php
$username = $_POST['username'];
$sql = "SELECT * FROM users WHERE username = '" . $username . "'";
mysqli_query($conn, $sql);

// 或使用双引号变量插值
$sql = "SELECT * FROM users WHERE id = $id";
mysqli_query($conn, $sql);
```

**快速定位核心操作（L2-跳读）：**
- 搜索 `mysqli_query`、`mysqli_multi_query`、`$conn->query`
- 定位 SQL 语句构造位置，关注字符串拼接操作符：`.`、双引号内变量插值 `"$var"`
- 回溯变量来源：`$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE`、`$_SERVER`
- 检查是否存在中间赋值或传参链条

**快速定位保护机制（L1-关键词扫描）：**
- 是否使用预处理：`prepare()`、`bind_param()`、`execute()`
- 是否调用转义函数：`mysqli_real_escape_string()`、`addslashes()`（注意：不完全有效）
- 是否使用 ORM/Query Builder：如 Laravel Eloquent、Doctrine
- 是否存在白名单校验：`in_array()`、`switch/case` 匹配
- 是否存在类型强制转换：`intval()`、`(int)`、`floatval()` 等

## Classify

**真实漏洞：**
- 外部输入直接拼接到 SQL 语句中，无任何过滤或转义
- 仅使用 `addslashes()` 或客户端过滤，可被绕过
- 字符集设置不当（如 GBK）导致宽字节注入绕过 `mysqli_real_escape_string()`
- 数值型注入未强制类型转换

**误报：**
- 拼接的变量来自代码硬编码常量或配置文件
- 变量经过严格白名单校验（如表名、字段名从预定义数组中取值）
- 数值参数已通过 `intval()` 等强制类型转换
- 使用了完整的预处理语句（参数通过 `bind_param()` 绑定）

**代码异味：**
- 使用 `mysqli_real_escape_string()` 但未设置正确字符集
- 动态拼接表名/字段名虽有白名单但实现不严谨
- 混用预处理和字符串拼接（部分参数绑定，部分拼接）

## Low risk

- **受限注入点**：输入长度严格限制（如 `maxlength=5`）且无法突破，仅允许有限字符集
- **低价值数据**：查询不涉及敏感信息（如公开文章列表），且数据库权限受限（只读账号）
- **内网隔离**：应用仅部署在内网测试环境，无外部访问入口
- **盲注难利用**：无错误回显、无布尔差异、响应时间不稳定，攻击成本极高
- **次要功能**：影响范围仅限管理员后台的边缘功能，需高权限账号才能触发