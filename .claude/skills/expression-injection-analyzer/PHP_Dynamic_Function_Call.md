# PHP 动态函数调用注入

**漏洞成因**：使用用户输入直接作为函数名称进行函数调用，或通过 `call_user_func` 等动态函数调用机制执行用户指定的函数，导致任意函数执行。常见于路由分发、回调处理、插件系统等场景。

---

## Details

**代码示例**：
```php
// 危险：直接使用用户输入作为函数名
$function = $_GET['action'];
$function();  // 用户可调用任意函数

// 危险：call_user_func 执行任意函数
$callback = $_POST['callback'];
call_user_func($callback, $data);  // 用户可执行危险函数

// 危险：call_user_func_array 执行任意函数
$method = $_GET['method'];
$args = $_GET['args'];
call_user_func_array($method, $args);

// 较安全：函数白名单
$actions = [
    'list' => 'list_users',
    'create' => 'create_user',
    'delete' => 'delete_user'
];
$action = $_GET['action'];
if (isset($actions[$action])) {
    call_user_func($actions[$action]);
}

// 较安全：使用对象方法而非全局函数
$controller = new UserController();
$method = $_GET['method'];
if (method_exists($controller, $method)) {
    $controller->$method();  // 仍需验证方法白名单
}
```

**快速定位核心操作**：
- 关键词：`call_user_func`、`call_user_func_array`、函数变量调用 `$func()`、`$$var`、动态方法调用
- 查看函数名称或方法名称来源是否为用户可控
- 追踪是否存在函数/方法白名单
- 检查是否使用了 `method_exists`、`function_exists` 等验证
- 关注是否存在通过反射调用私有或受保护方法的风险

**快速定位保护机制**：
- 是否维护了可调用函数的白名单
- 是否使用 `method_exists` 或 `function_exists` 进行验证
- 是否限制了可调用方法的作用域（如仅公开方法）
- 是否对函数参数进行了验证和转义
- 是否使用了反射 API 进行安全访问控制检查

**审计等级**：**L2-L3**
- **L2**：跳读动态函数调用代码，识别用户控制的函数名称
- **L3**：逐行验证白名单实现和参数验证

---

## Classify

**确认为漏洞**：
- 用户输入直接用作函数或方法名称
- 不存在函数/方法白名单限制
- 可调用内置危险函数（如 `system`、`exec`、`eval` 等）
- 参数验证不完整

**误报**：
- 函数名称完全由应用内部定义
- 存在严格的白名单限制，用户仅能调用预定义的函数
- 仅允许调用特定类的公开方法，且参数验证完整

**代码异味**：
- 存在 `$$var` 这样的可变变量调用
- 使用了反射 API 但缺少安全检查

---

## Low Risk

以下情况可评为低风险：
- **完整白名单**：仅允许调用预定义的安全函数
- **方法作用域限制**：仅允许调用公开方法（非受保护或私有）
- **参数验证严格**：函数参数经过充分验证和转义
- **内网应用**：仅由内部可信用户访问
- **权限控制**：函数调用受权限系统保护

**注意**：动态函数调用的风险等级高，需要完善的白名单机制。
