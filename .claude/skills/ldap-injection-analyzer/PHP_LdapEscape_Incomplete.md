# PHP LDAP 转义函数不完整

## Details

### 代码示例
PHP 的 `ldap_escape()` 函数提供转义功能，但使用不当时仍可能引入注入漏洞。常见问题包括仅转义部分参数、使用错误的转义标志，或未覆盖 DN 注入场景：

```php
<?php
// 危险示例1：仅转义部分参数
$username = $_POST['username'];
$department = $_POST['department'];  // 未转义

$escaped_username = ldap_escape($username, '', LDAP_ESCAPE_FILTER);
$filter = "(&(uid={$escaped_username})(department={$department}))";  // department未转义
$result = ldap_search($conn, $base_dn, $filter);

// 危险示例2：使用错误的转义标志
$dn_input = $_POST['dn'];
$escaped = ldap_escape($dn_input, '', LDAP_ESCAPE_FILTER);  // 应该用 LDAP_ESCAPE_DN
$new_dn = "cn={$escaped},ou=users,dc=example,dc=com";
ldap_add($conn, $new_dn, $entry);

// 危险示例3：转义后又拼接了未转义的内容
$escaped_user = ldap_escape($_GET['user'], '', LDAP_ESCAPE_FILTER);
$filter = "(&(uid={$escaped_user}*)(status=active))";  // 安全
$filter = "(&(uid={$escaped_user}" . $_GET['extra'] . "))";  // 危险：extra未转义
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下模式：
- `ldap_escape()` 函数调用
- `ldap_search()`, `ldap_list()`, `ldap_add()`, `ldap_modify()` 等操作
- `$_POST`, `$_GET`, `$_REQUEST`, `$_COOKIE` 等用户输入源
- 过滤器或 DN 字符串中的 `{}` 或 `.` 拼接操作

重点检查文件路径：
```
includes/auth.php
lib/ldap.php
controllers/UserController.php
api/login.php
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查转义函数的使用范围：
- 是否所有用户输入都调用了 `ldap_escape()`
- `LDAP_ESCAPE_FILTER` vs `LDAP_ESCAPE_DN` 标志是否匹配使用场景
- 转义后的变量是否被重新拼接了未转义内容

**L3：逐行读** - 验证转义的完整性：
```php
// 检查点：所有用户输入是否都被转义
$user = ldap_escape($_POST['user'], '', LDAP_ESCAPE_FILTER);
$dept = ldap_escape($_POST['dept'], '', LDAP_ESCAPE_FILTER);  // 是否遗漏？

// 检查点：DN 操作是否使用了正确的标志
$cn = ldap_escape($_POST['cn'], '', LDAP_ESCAPE_DN);  // 而非 LDAP_ESCAPE_FILTER

// 检查点：转义后是否又引入了新的拼接
$filter = "(&(uid={$escaped_user}))";  // 安全
$filter = "(&(uid={$escaped_user}{$_GET['suffix']}))";  // 危险
```

关键验证点：
- 过滤器中的所有动态内容是否都被转义
- DN 操作使用了 `LDAP_ESCAPE_DN` 而非 `LDAP_ESCAPE_FILTER`
- 转义变量后续没有被污染

## Classify

### 漏洞判定规则
- **明确漏洞**：存在未转义的用户输入直接拼接到过滤器或 DN 中
- **高危信号**：
  - 部分参数使用了 `ldap_escape()`，但同一过滤器中有其他参数未转义
  - DN 操作使用了 `LDAP_ESCAPE_FILTER` 标志
  - 转义后的变量再次拼接了未转义内容
- **误报排除**：
  - 所有用户输入都正确使用了 `ldap_escape()`，且标志匹配场景
  - 拼接的内容是常量或已转义的变量
  - 输入经过严格的白名单验证

### 风险评估
- **高风险**：关键参数（如 uid、dn）未转义，或使用错误标志，可绕过认证或权限提升
- **中风险**：非关键属性未转义，但可造成信息泄露或逻辑绕过
- **低风险**：转义覆盖主要参数，仅次要字段存在问题，且受其他因素限制

## Low risk

### 低风险评级的情形

1. **非关键字段的遗漏**
   - 仅 `description` 或 `comment` 等非敏感属性未转义
   - 这些字段不影响认证决策或权限判断
   - 搜索结果已在应用层进行二次验证

2. **上游限制已生效**
   - 输入在到达 LDAP 操作前经过了严格的正则验证（如 `^[a-zA-Z0-9]{3,16}$`）
   - 框架级别的输入过滤已阻止特殊字符
   - 虽然未使用 `ldap_escape()`，但输入已被清理

3. **查询结构固定**
   - 未转义的输入仅能影响字面值，无法改变过滤器逻辑
   - 如 `(uid=PREFIX{$unescaped}SUFFIX)` 中，前后缀限制了注入的有效性

4. **仅读操作且结果受限**
   - 仅用于 `ldap_list()` 读取有限属性
   - 返回结果不包含敏感信息，且应用不根据结果做权限决策
