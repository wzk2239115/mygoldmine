# Symfony LDAP 查询注入

## Details

### 代码示例
Symfony 提供了 `Symfony\Component\Ldap` 组件用于 LDAP 操作。如果直接拼接过滤器字符串而不使用参数化接口，仍会引入注入漏洞：

```php
<?php
use Symfony\Component\Ldap\Ldap;

// 危险示例1：直接拼接过滤器
$username = $request->get('username');
$ldap = Ldap::create('ext_ldap', ['connection_string' => 'ldap://localhost']);
$ldap->bind('cn=admin,dc=example,dc=com', 'password');

$filter = "(uid={$username})";  // 未转义
$query = $ldap->query('ou=users,dc=example,dc=com', $filter);
$results = $query->execute();

// 危险示例2：LdapUserProvider 中的自定义查询
class CustomLdapUserProvider extends LdapUserProvider {
    public function loadUserByIdentifier(string $identifier): UserInterface {
        $email = $identifier;  // 可能来自用户输入
        $filter = "(mail={$email})";  // 危险
        $query = $this->ldap->query($this->searchDn, $filter);
        // ...
    }
}

// 危险示例3：服务类中的搜索方法
class LdapService {
    public function searchUsers($department, $role) {
        $filter = "(&(department={$department})(role={$role}))";  // 危险
        $query = $this->ldap->query($this->baseDn, $filter);
        return $query->execute()->toArray();
    }
}

// 危险示例4：使用表单输入构造过滤器
public function searchAction(Request $request) {
    $searchTerm = $request->request->get('search');
    $filter = "(cn=*{$searchTerm}*)";  // 危险
    $results = $this->ldap->query($this->baseDn, $filter)->execute();
    return $this->render('results.html.twig', ['users' => $results]);
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `Ldap::create()`, `$ldap->query()`, `$ldap->bind()`
- `$request->get()`, `$request->request->get()`, `$request->query->get()`
- 字符串拼接：`"{$var}"`, `.` 操作符
- `LdapUserProvider`, `LdapUserChecker` 等认证相关类

重点检查文件：
```
src/Security/LdapUserProvider.php
src/Service/LdapService.php
src/Controller/*Controller.php
config/packages/security.yaml
src/Repository/LdapUserRepository.php
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `Symfony\Component\Ldap\Adapter\QueryInterface` 的参数化方法
- `ldap_escape()` 函数调用
- 输入验证注解：`@Assert\Regex`, `@Assert\Length`
- 表单类型的验证规则

**L3：逐行读** - 验证防护有效性：
```php
// 检查点1：是否使用了转义函数
$username = ldap_escape($request->get('username'), '', LDAP_ESCAPE_FILTER);
$filter = "(uid={$username})";

// 检查点2：是否所有输入都被转义
$dept = ldap_escape($department, '', LDAP_ESCAPE_FILTER);
$role = $request->get('role');  // 未转义！
$filter = "(&(department={$dept})(role={$role}))";

// 检查点3：是否在控制器层进行了验证
public function searchAction(Request $request) {
    $form = $this->createForm(SearchFormType::class);
    $form->handleRequest($request);
    if ($form->isValid()) {  // 检查表单验证规则
        $data = $form->getData();
        // ...
    }
}
```

关键检查点：
- 过滤器构造位置与输入验证的关系
- Symfony 表单验证是否覆盖 LDAP 特殊字符
- 自定义 UserProvider 的实现

## Classify

### 漏洞判定规则
- **明确漏洞**：`$ldap->query()` 的过滤器参数直接包含未转义的用户输入
- **高危信号**：
  - 认证提供者（UserProvider）中的自定义查询方法
  - 控制器直接获取请求参数并用于 LDAP 查询
  - 服务类中的搜索方法未验证输入
- **误报排除**：
  - 使用了 `ldap_escape()` 转义所有用户输入
  - Symfony 表单验证明确拒绝 LDAP 元字符（正则验证）
  - 输入仅从白名单选项中选择（如下拉菜单的枚举值）

### 风险评估
- **高风险**：认证绕过（UserProvider 中的注入）、权限提升、敏感数据泄露
- **中风险**：非认证场景的信息泄露或搜索结果操纵
- **低风险**：查询结果仅用于展示非敏感信息，且有表单层面的部分验证

## Low risk

### 低风险评级的情形

1. **表单验证限制**
   - Symfony 表单使用 `@Assert\Regex('/^[a-zA-Z0-9]+$/')` 限制字符集
   - 长度验证 `@Assert\Length(max=20)` 限制注入 payload 大小
   - 虽未使用 `ldap_escape()`，但表单层已阻止特殊字符

2. **ChoiceType 表单字段**
   - 输入来自 `ChoiceType` 字段，值为预定义选项
   - 用户无法提交任意值（前端和后端都有验证）
   - 实际上相当于白名单验证

3. **查询结果用途受限**
   - LDAP 查询仅用于显示用户列表，不影响认证或授权
   - 返回的属性通过 `$query->execute()->toArray()` 后仅显示 displayName 和 email
   - 不包含敏感属性（如密码哈希、管理员标志）

4. **Base DN 限定范围**
   - `$ldap->query('ou=public,dc=example,dc=com', $filter)` 限定搜索范围
   - 无法访问管理员或特权用户
   - 即使注入也无法提权

5. **服务层二次验证**
   - 虽然 LDAP 查询可能被注入，但服务层对返回结果进行了二次验证
   - 如检查 `in_array($result['role'], ['user', 'guest'])` 确保角色合法
