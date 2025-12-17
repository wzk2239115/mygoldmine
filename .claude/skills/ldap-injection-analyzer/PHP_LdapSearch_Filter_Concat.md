# PHP ldap_search() 过滤器拼接

## Details

### 代码示例
`ldap_search()` 是最常用的 LDAP 查询函数，用于递归搜索整个子树。未转义的过滤器拼接会导致严重的注入漏洞：

```php
<?php
// 危险示例1：最常见的认证场景
$username = $_POST['username'];
$password = $_POST['password'];
$filter = "(&(uid={$username})(userPassword={$password}))";
$result = ldap_search($conn, "dc=example,dc=com", $filter);

// 危险示例2：多条件搜索
$name = $_GET['name'];
$email = $_GET['email'];
$filter = "(&(cn=*{$name}*)(mail=*{$email}*))";
$result = ldap_search($conn, $base_dn, $filter, ['dn', 'cn', 'mail']);

// 危险示例3：动态构造复杂过滤器
$criteria = $_POST['criteria'];  // 如 "department"
$value = $_POST['value'];
$filter = "(&(objectClass=person)({$criteria}={$value}))";
$result = ldap_search($conn, $base_dn, $filter);

// 危险示例4：使用 sprintf 构造
$user = $_REQUEST['user'];
$filter = sprintf("(|(uid=%s)(mail=%s))", $user, $user);
$result = ldap_search($conn, $base_dn, $filter);
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `ldap_search()` 函数调用（第三个参数为过滤器）
- 用户输入变量：`$_POST`, `$_GET`, `$_REQUEST`, `$_COOKIE`, `$_SERVER`
- 字符串拼接：`.` 操作符，`"{$var}"` 插值语法，`sprintf()`
- LDAP 过滤器模式：`(&`, `(|`, `(uid=`, `(cn=`, `(mail=`

重点检查文件：
```
app/Controllers/AuthController.php
lib/LdapAuth.php
api/v1/users.php
includes/authentication.php
services/DirectoryService.php
```

### 快速定位保护机制的技巧
**L2：跳读** - 寻找防护信号：
- `ldap_escape($var, '', LDAP_ESCAPE_FILTER)` 在过滤器构造前调用
- 输入白名单验证：`in_array($input, $whitelist)`
- 正则表达式验证：`preg_match('/^[a-zA-Z0-9]+$/', $input)`
- 过滤器构造器类或函数（如自定义的 `buildFilter()` 方法）

**L3：逐行读** - 验证防护的有效性：
```php
// 检查点1：是否所有用户输入都被转义
$user = ldap_escape($_POST['username'], '', LDAP_ESCAPE_FILTER);
$pass = ldap_escape($_POST['password'], '', LDAP_ESCAPE_FILTER);
$filter = "(&(uid={$user})(userPassword={$pass}))";  // 安全

// 检查点2：是否存在部分转义
$user = ldap_escape($_POST['user'], '', LDAP_ESCAPE_FILTER);
$filter = "(&(uid={$user})(dept={$_POST['dept']}))";  // 危险：dept未转义

// 检查点3：转义后是否重新拼接
$escaped = ldap_escape($_GET['input'], '', LDAP_ESCAPE_FILTER);
$filter = "(uid={$escaped})";  // 安全
$filter = "(uid={$escaped}" . $_GET['extra'] . ")";  // 危险
```

关键检查点：
- 过滤器字符串中的每个动态部分
- 转义函数调用的位置（必须在拼接前）
- 是否使用了正确的转义标志

## Classify

### 漏洞判定规则
- **明确漏洞**：`ldap_search()` 的过滤器参数直接包含未转义的用户输入
- **高危信号**：
  - 认证场景（uid/userPassword 过滤器）包含用户输入
  - 过滤器使用 `&`, `|`, `*`, `!` 逻辑运算符且有未转义输入
  - 使用 `sprintf()` 或字符串拼接构造过滤器，无转义
- **误报排除**：
  - 所有动态内容都经过 `ldap_escape()` 正确转义
  - 输入通过严格的白名单验证（如枚举值）
  - 使用了 ORM 或查询构造器的参数化接口

### 风险评估
- **高风险**：认证绕过、权限提升、完整目录数据泄露
- **中风险**：限定条件下的信息泄露或逻辑绕过
- **低风险**：查询范围受限，返回属性白名单化，输入长度严格限制

## Low risk

### 低风险评级的情形

1. **严格的输入白名单**
   - 输入仅允许 `['IT', 'HR', 'Finance']` 等预定义值
   - 使用 `in_array()` 验证，拒绝任意输入
   - 虽未转义，但无法注入元字符

2. **属性返回白名单**
   - `ldap_search()` 第四个参数限制返回属性：`['cn', 'displayName']`
   - 不返回敏感信息（密码哈希、私人邮箱、SSN）
   - 即使注入也无法获取关键数据

3. **查询范围限制**
   - Base DN 限定在公开子树：`ou=public,dc=example,dc=com`
   - 无法访问管理员账户或特权组
   - 搜索深度限制（scope 为 `LDAP_SCOPE_ONELEVEL`）

4. **输入长度限制**
   - 使用 `substr($input, 0, 10)` 截断
   - 长度不足以构造完整的注入 payload
   - 无法闭合括号或添加逻辑运算符

5. **仅计数或存在性检查**
   - 代码仅使用 `ldap_count_entries()` 获取结果数
   - 不解析条目属性或 DN
   - 无法提取敏感信息
