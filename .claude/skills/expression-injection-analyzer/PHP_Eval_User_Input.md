# PHP eval 函数用户输入注入

**漏洞成因**：PHP 的 `eval()` 函数可以执行字符串形式的 PHP 代码。当应用将用户输入直接传递给 `eval()` 时，攻击者可构造恶意代码执行任意 PHP 语句，包括文件操作、系统命令执行、数据库操作、远程文件包含等，导致完全的服务器控制权限丢失。常见于动态代码执行、模板渲染、配置解析、插件系统等场景。

---

## Details

**代码示例**：
```php
// 危险：直接使用 eval() 执行用户输入
$userInput = $_GET['code'];
eval($userInput); // 危险：用户可注入任意 PHP 代码

// 危险：使用 create_function() (PHP 7.2 前)
$func = create_function('$x', $_POST['body']); // 危险：动态创建函数
$func(10);

// 危险：使用 assert() 作为回调
assert($_GET['expr']); // 危险：assert 可执行代码（PHP 7 前）

// 危险：使用 preg_replace() 的 /e 修饰符（PHP 7 前）
preg_replace('/(.*)/e', $_GET['replace'], $input); // /e 会执行替换内容

// 攻击载荷示例
// system('calc')
// exec('calc')
// file_get_contents('/etc/passwd')
// eval(base64_decode('PHNjcmlwdD4uLi4='))
// file_put_contents('shell.php', '<?php system($_GET["cmd"]); ?>')

// 较安全：避免使用 eval()，使用其他安全的替代方案
// 例如：使用配置数组而非动态代码
$config = [
    'action1' => function() { /* 安全的代码 */ },
    'action2' => function() { /* 安全的代码 */ }
];
$action = $_GET['action'];
if (isset($config[$action])) {
    $config[$action]();
}

// 较安全：使用表达式白名单
$allowed = ['1+1', '2*3', '10/2'];
if (in_array($userInput, $allowed, true)) {
    eval("\$result = $userInput;");
}

// 较安全：使用安全的表达式求值库
// 例如：symfony/expression-language
use Symfony\Component\ExpressionLanguage\ExpressionLanguage;
$language = new ExpressionLanguage();
$result = $language.evaluate($userInput, ['x' => 10]); // 限制表达式能力
```

**快速定位核心操作**：
- 关键词：`eval(`、`create_function(`、`assert(`、`preg_replace` with `/e`、`call_user_func`
- 查找 `eval()` 函数的调用位置
- 追踪 `eval()` 的参数来源，判断是否包含用户输入
- 检查 `assert()` 的使用（PHP 7 前可执行代码）
- 关注 `preg_replace()` 的 `/e` 修饰符（PHP 7 前）
- 搜索 `create_function()` 的使用（PHP 7.2 前）
- 关注动态函数调用：`call_user_func()`、`$$variable()`

**快速定位保护机制**：
- 是否完全避免使用 `eval()`、`create_function()`、`assert()`
- 是否使用了配置数组或策略模式替代动态代码
- 是否对用户输入进行了严格的白名单验证
- 是否使用了安全的表达式求值库（如 Symfony ExpressionLanguage）
- PHP 版本是否为 7.0+（禁用了部分危险特性）
- 是否启用了 `disable_functions` 禁用危险函数
- 是否使用了 Suhosin 等安全扩展

**审计等级**：**L1-L3**
- **L1**：关键词扫描，快速识别 `eval(`、`assert(`、`create_function(` 的使用
- **L2**：跳读函数调用上下文，判断参数来源
- **L3**：逐行验证是否存在输入验证和替代方案

---

## Classify

**确认为漏洞**：
- 直接使用 `eval()` 执行用户输入的字符串
- 使用 `assert()` 作为回调执行用户输入（PHP 7 前）
- 使用 `preg_replace()` 的 `/e` 修饰符处理用户输入（PHP 7 前）
- 使用 `create_function()` 且函数体包含用户输入
- 用户输入未经任何验证或过滤

**误报**：
- 完全避免使用 `eval()` 和相关危险函数
- 使用配置数组或策略模式替代动态代码执行
- 用户输入经过严格的白名单验证，仅允许安全的操作
- 使用安全的表达式求值库且配置正确
- PHP 版本为 7.0+ 且禁用了危险函数

**代码异味**：
- 使用 `eval()` 处理动态逻辑，即使当前输入不可控
- 通过字符串拼接构造 PHP 代码
- 使用 `call_user_func()` 执行动态函数名
- 缺乏代码执行的审计日志

---

## Low Risk

以下情况可评为低风险：
- **完全避免 eval**：不使用 `eval()`、`create_function()`、`assert()` 等危险函数
- **配置数组方案**：使用配置数组或策略模式替代动态代码
- **表达式白名单**：用户输入必须匹配预定义的安全操作集合
- **安全求值库**：使用 Symfony ExpressionLanguage 等安全的表达式求值库
- **disable_functions**：在 `php.ini` 中禁用 `eval`、`system`、`exec` 等危险函数
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有动态代码执行均记录日志并实时监控

**注意**：PHP 的 `eval()` 是最危险的函数之一，应完全避免使用。即使在受限环境中也极易被绕过。
