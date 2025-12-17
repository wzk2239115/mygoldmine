# PHP_Auth_SQL_Injection

**漏洞类型**: PHP 认证逻辑中用户输入直接用于数据库查询，存在 SQL 注入导致认证绕过

---

## Details

### 代码示例

```php
// 易受攻击
$email = $_POST['email'];
$password = $_POST['password'];
$query = "SELECT * FROM users WHERE email = '$email' AND password = '$password'";
$result = mysqli_query($conn, $query);

// 修复: 使用预处理语句
$stmt = $conn->prepare("SELECT * FROM users WHERE email = ? AND password = ?");
$stmt->bind_param("ss", $email, hash_password($password));
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `"SELECT * WHERE ... = '$_POST`"
- 直接拼接 `$_POST`, `$_GET`
- 预处理语句缺失

**L2 跳读定位**:
- 登录处理函数
- 查询语句构建

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 预处理语句: `prepare()`, `?` 占位符
- 参数绑定: `bind_param()`

**L3 逐行分析**:
- 所有查询使用预处理语句
- 参数通过绑定传递

---

## Classify

确认为漏洞: SQL 注入可绕过认证
误报判定: 使用预处理语句
代码异味: 混合使用安全和不安全查询

---

## Low risk

- 无法直接利用但有其他防护
- WAF 检测和阻止
