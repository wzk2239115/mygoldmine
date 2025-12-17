# Laravel LDAP 认证注入

## Details

### 代码示例
Laravel 通常通过 `Adldap2/Adldap2-Laravel` 包或原生 PHP LDAP 扩展进行 LDAP 认证。未正确转义用户输入会导致认证绕过：

```php
<?php
// 危险示例1：自定义 LDAP 认证 Provider
namespace App\Providers;

use Illuminate\Support\Facades\Auth;

class CustomLdapAuthProvider {
    public function authenticate($username, $password) {
        $conn = ldap_connect('ldap://localhost');

        // 危险：直接拼接用户输入
        $filter = "(&(uid={$username})(userPassword={$password}))";
        $result = ldap_search($conn, 'dc=example,dc=com', $filter);

        return ldap_count_entries($conn, $result) > 0;
    }
}

// 危险示例2：使用 Adldap2 的原始查询
use Adldap\Adldap;

public function login(Request $request) {
    $username = $request->input('username');
    $ad = new Adldap($config);

    // 危险：使用 rawFilter 直接拼接
    $user = $ad->search()
        ->where('samaccountname', '=', $username)  // 看似安全
        ->rawFilter("(department={$request->input('dept')})")  // 危险！
        ->first();
}

// 危险示例3：控制器中的 LDAP 搜索
class UserController extends Controller {
    public function search(Request $request) {
        $name = $request->get('name');
        $email = $request->get('email');

        // 危险：使用原生 LDAP 函数
        $filter = "(&(cn=*{$name}*)(mail=*{$email}*))";
        $result = ldap_search($this->ldapConn, config('ldap.base_dn'), $filter);

        return response()->json(ldap_get_entries($this->ldapConn, $result));
    }
}

// 危险示例4：中间件中的 LDAP 验证
class LdapAuthMiddleware {
    public function handle($request, Closure $next) {
        $user = $request->user();
        $group = $request->header('X-Required-Group');

        // 危险：header 值未验证
        $filter = "(&(uid={$user->username})(memberOf=cn={$group},ou=groups,dc=example,dc=com))";
        $result = ldap_search($this->conn, $this->baseDn, $filter);

        if (ldap_count_entries($this->conn, $result) === 0) {
            return response('Forbidden', 403);
        }
        return $next($request);
    }
}
```

### 快速定位核心操作的技巧
**L1：关键词扫描** - 搜索以下特征：
- `ldap_search()`, `ldap_bind()`, `ldap_list()` 原生函数
- `$request->input()`, `$request->get()`, `$request->header()` 获取输入
- `Adldap\Adldap`, `->search()`, `->rawFilter()` Adldap2 相关
- 字符串拼接：`"{$var}"`, `.` 操作符，`sprintf()`

重点检查文件：
```
app/Http/Controllers/Auth/LoginController.php
app/Providers/CustomAuthServiceProvider.php
app/Http/Middleware/LdapAuth.php
app/Services/LdapService.php
config/ldap.php
```

### 快速定位保护机制的技巧
**L2：跳读** - 检查防护迹象：
- `ldap_escape($input, '', LDAP_ESCAPE_FILTER)` 调用
- Adldap2 的 `->where()` 方法（参数化查询）
- Laravel 验证规则：`$request->validate(['username' => 'regex:/^[a-zA-Z0-9]+$/'])`
- 表单请求类（FormRequest）中的验证规则

**L3：逐行读** - 验证防护的完整性：
```php
// 检查点1：验证规则是否覆盖 LDAP 特殊字符
$request->validate([
    'username' => 'required|regex:/^[a-zA-Z0-9]+$/',  // 安全
    'dept' => 'required|string',  // 不安全，未限制字符
]);

// 检查点2：Adldap2 参数化 vs 原始过滤器
$user = $ad->search()
    ->where('uid', '=', $username)  // 安全：参数化
    ->first();

$user = $ad->search()
    ->rawFilter("(uid={$username})")  // 危险：未转义
    ->first();

// 检查点3：原生 LDAP 函数是否转义
$escaped_user = ldap_escape($username, '', LDAP_ESCAPE_FILTER);
$filter = "(uid={$escaped_user})";  // 安全
```

关键检查点：
- 是否使用 Adldap2 的参数化方法而非 `rawFilter()`
- 原生 LDAP 函数是否转义所有用户输入
- Laravel 验证规则是否拒绝 LDAP 元字符

## Classify

### 漏洞判定规则
- **明确漏洞**：LDAP 过滤器直接拼接未转义的 `$request->input()` 或 `$request->header()`
- **高危信号**：
  - 认证中间件或登录控制器中的 LDAP 注入
  - 使用 `rawFilter()` 拼接用户输入
  - 原生 `ldap_search()` 无转义
- **误报排除**：
  - 使用 Adldap2 的 `->where()` 参数化方法
  - 所有输入经过 `ldap_escape()` 转义
  - Laravel 验证规则严格限制字符集

### 风险评估
- **高风险**：认证绕过、权限提升、完整 LDAP 目录遍历
- **中风险**：非认证场景的信息泄露或搜索结果操纵
- **低风险**：查询结果仅用于非敏感操作，且有部分输入验证

## Low risk

### 低风险评级的情形

1. **FormRequest 验证**
   - 使用 Laravel FormRequest 类进行验证
   - 验证规则明确拒绝特殊字符：`'username' => 'regex:/^[a-zA-Z0-9_]+$/'`
   - 长度限制：`'username' => 'max:32'`

2. **Adldap2 参数化接口**
   - 主要使用 `->where('attr', '=', $value)` 方法
   - 仅在非用户输入的地方使用 `rawFilter()`
   - 所有用户输入都通过参数化方法传递

3. **中间件层的预验证**
   - 认证中间件在 LDAP 查询前已验证用户身份
   - LDAP 查询仅用于权限检查，不影响认证决策
   - 即使注入也无法绕过 Laravel 的 Session 认证

4. **查询结果不直接授权**
   - LDAP 查询结果仅用于显示用户资料
   - 权限判断基于数据库中的 roles 表，而非 LDAP 属性
   - 注入无法提升应用内权限

5. **Base DN 范围限制**
   - 配置文件中 `base_dn` 限定为非敏感 OU
   - 如 `ou=external,dc=example,dc=com`，不包含内部员工或管理员
