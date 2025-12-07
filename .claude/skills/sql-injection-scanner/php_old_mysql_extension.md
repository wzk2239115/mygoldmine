# PHP 旧式 mysql 扩展 SQL 注入

## 成因
PHP 5.x 的 `mysql_*` 系列函数（已在 PHP 7.0 移除）不支持原生预处理，开发者习惯字符串拼接构造查询，导致用户输入直接进入 SQL 上下文。

## Details

### 代码示例
```php
// 典型注入点
$query = "SELECT * FROM users WHERE id = " . $_GET['id'];
mysql_query($query);

// 字符串拼接登录
$sql = "SELECT * FROM admin WHERE user='" . $_POST['user'] . "' AND pass='" . $_POST['pass'] . "'";
$result = mysql_query($sql, $conn);

// 搜索场景
$keyword = $_REQUEST['keyword'];
$query = "SELECT * FROM products WHERE name LIKE '%" . $keyword . "%'";
```

### 快速定位核心操作（L1-L2）
**关键函数特征**：
- `mysql_query()` - 执行查询的核心函数
- `mysql_db_query()` - 指定数据库执行
- `mysql_unbuffered_query()` - 无缓冲查询

**定位技巧（L1）**：
- 全局搜索 `mysql_query\(` 定位所有执行点
- 反向追踪第一参数来源，查找字符串拼接符 `.` 或双引号变量插值 `"$var"`
- 重点关注 `$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE` 是否直接参与拼接

**SQL 构造模式识别（L2）**：
- 数值型注入：`WHERE id = " . $var` 或 `WHERE id = $var`
- 字符型注入：`WHERE name = '" . $var . "'` 或 `WHERE name = '$var'`
- LIKE 模糊查询：`LIKE '%" . $var . "%'` 或 `LIKE '%$var%'`

### 快速定位保护机制（L2-L4）

**转义函数检查（L2）**：
- `mysql_real_escape_string($var)` - 唯一有效的官方转义
- `mysql_escape_string($var)` - 已废弃，不考虑字符集
- `addslashes($var)` - 不可靠，字符集绕过风险

**审计要点**：
1. **转义缺失（L2）**：拼接前未调用任何转义函数
2. **转义错位（L3）**：转义后又经过其他处理（如 `stripslashes`、`trim`、正则替换）
3. **连接句柄缺失（L3）**：`mysql_real_escape_string($var)` 未传入连接参数，可能使用错误字符集
4. **数值型误判（L2）**：整数参数未使用 `intval()` 或 `(int)` 强制转换
5. **多层传递（L4）**：跨函数/文件传递时中途丢失转义或重复解码

**保护机制失效场景**：
- GBK 字符集 + `addslashes` 宽字节注入
- `magic_quotes_gpc = On` 自动转义被 `stripslashes` 反转义
- 二次编码：先 `urldecode` 再拼接

## Classify

**确认漏洞**：
- 用户输入直接拼接到 SQL 语句且无任何转义或转义不当（如仅使用 `addslashes` 在 GBK 环境）
- 数值型参数未强制类型转换直接参与查询
- 转义函数在逻辑链路中被后续操作破坏

**误报**：
- 输入源是硬编码常量、配置文件读取或数据库查询结果（非外部可控）
- 已通过白名单校验且白名单规则严格（如 `in_array($var, ['admin', 'user'], true)`）
- 虽有拼接但变量来源于 `session` 且 session 值在设置时已做严格过滤

**代码异味**：
- 使用了正确的 `mysql_real_escape_string` 但代码结构混乱难以验证覆盖性
- 存在部分转义但逻辑分支复杂，某些条件下可能绕过
- 动态表名/字段名拼接（即使转义也无法完全防御）

## Low risk

**低风险评级适用场景**：
- **输入约束强**：参数已通过严格正则限制（如 `preg_match('/^\d{1,8}$/', $id)` 且置于数值上下文）
- **影响面有限**：注入点位于管理后台且需高权限账号访问
- **查询只读**：SELECT 查询且数据库账号权限被严格限制为只读，无文件操作权限
- **历史遗留代码**：系统运行在 PHP 5.x 且计划近期下线或重构
- **外层防护**：虽代码层面存在注入但 WAF/IPS 已有明确规则拦截且验证有效

**注意**：即使评为低风险也应标记为缺陷，低风险不等于无风险。