# PHP ldap_list() 读操作注入

## Details

### 代码示例
`ldap_list()` 用于从 LDAP 目录读取单层条目，但如果过滤器参数包含未转义的用户输入，同样会导致注入攻击：

```php
<?php
// 危险示例1：基本的过滤器拼接
$department = $_GET['dept'];
$filter = "(department={$department})";
$result = ldap_list($conn, "ou=users,dc=example,dc=com", $filter);

// 危险示例2：复杂过滤器的部分拼接
$role = $_POST['role'];
$status = $_POST['status'];
$filter = "(&(role={$role})(status={$status}))";
$result = ldap_list($conn, $base_dn, $filter, ['cn', 'mail']);

// 危险示例3：Base DN 中包含用户输入
$ou = $_REQUEST['ou'];
$base = "ou={$ou},dc=example,dc=com";  // DN 注入风险
$result = ldap_list($conn, $base, "(objectClass=*)");

// 危险示例4：从 Cookie 获取输入
$group = $_COOKIE['preferred_group'];
$filter = "(memberOf=cn={$group},ou=groups,dc=example,dc=com)";
$result = ldap_list($conn, $base_dn, $filter);
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `ldap_list()` 函数调用（第三个参数为过滤器）
- `$_GET`, `$_POST`, `$_REQUEST`, `$_COOKIE` 等用户输入
- 字符串拼接操作符 `.` 或插值语法 `{}`
- LDAP 过滤器特殊字符 `(`, `)`, `&`, `|`, `*`, `=`

重点检查位置：
```
controllers/DirectoryController.php
api/ldap/search.php
includes/directory_helper.php
admin/user_list.php
```

### 快速定位保护机制的技巧
**L2：跳读** - 寻找防护迹象：
- `ldap_escape($input, '', LDAP_ESCAPE_FILTER)` 调用
- 输入验证函数（如 `preg_match()`, `filter_var()`）
- 白名单映射（如 `$allowed_depts = ['IT', 'HR']`）
- 自定义的过滤器构造函数

**L3：逐行读** - 验证防护完整性：
```php
// 检查点1：是否所有动态内容都被转义
$dept = ldap_escape($_GET['dept'], '', LDAP_ESCAPE_FILTER);
$filter = "(department={$dept})";

// 检查点2：Base DN 是否包含未转义输入
$ou = ldap_escape($_GET['ou'], '', LDAP_ESCAPE_DN);  // 注意使用 LDAP_ESCAPE_DN
$base = "ou={$ou},dc=example,dc=com";

// 检查点3：是否存在部分转义
$role = ldap_escape($_POST['role'], '', LDAP_ESCAPE_FILTER);
$filter = "(&(role={$role})(status={$_POST['status']}))";  // status未转义！
```

关键验证点：
- 过滤器字符串中的所有变量来源
- Base DN 参数是否包含用户输入
- 转义函数的第三个参数是否正确

## Classify

### 漏洞判定规则
- **明确漏洞**：`ldap_list()` 的过滤器或 base DN 参数直接拼接未转义的用户输入
- **高危信号**：
  - HTTP 请求参数或 Cookie 直接用于构造过滤器
  - 过滤器中包含 `&`, `|`, `*` 等逻辑运算符，且有未转义的输入
  - Base DN 包含来自用户的 OU 或 CN 组件
- **误报排除**：
  - 所有用户输入都经过 `ldap_escape()` 正确转义
  - 输入通过严格的白名单验证
  - 使用了查询构造器库（如 Symfony LDAP）的参数化接口

### 风险评估
- **高风险**：可通过注入改变过滤器逻辑，访问未授权的目录条目或绕过访问控制
- **中风险**：仅能影响部分过滤器条件，但仍可能泄露敏感属性
- **低风险**：读取范围受限（如仅返回公开属性），且输入受长度或字符集限制

## Low risk

### 低风险评级的情形

1. **返回属性白名单限制**
   - `ldap_list()` 的第四个参数明确指定仅返回非敏感属性（如 `['cn', 'displayName']`）
   - 即使注入成功，攻击者也无法获取敏感信息（如密码哈希、邮箱）

2. **上下文隔离**
   - Base DN 已限定在非敏感的子树（如 `ou=public,dc=example,dc=com`）
   - 过滤器注入无法访问特权账户或管理员信息

3. **结果数量限制**
   - 使用了 `ldap_list()` 而非 `ldap_search()`，仅返回单层条目
   - 配合 PHP 的 `ldap_set_option($conn, LDAP_OPT_SIZELIMIT, 10)` 限制结果集

4. **输入长度严格限制**
   - 通过 `substr($_GET['dept'], 0, 8)` 截断输入
   - 长度不足以构造有效的注入 payload（如无法完成括号闭合）

5. **仅用于存在性检查**
   - 代码仅检查 `ldap_count_entries()` 是否大于 0
   - 不解析具体的条目内容，攻击者无法获取数据
