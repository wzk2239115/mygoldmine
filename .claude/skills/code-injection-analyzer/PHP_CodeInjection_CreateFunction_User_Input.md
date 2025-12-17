# PHP create_function() 代码执行注入

## 漏洞成因

PHP 的 `create_function()` 函数通过字符串动态创建匿名函数。当用户可控的输入被用于构造函数参数时，攻击者可注入恶意代码在应用上下文中执行任意代码。虽然 PHP 7.2.0+ 已弃用此函数，但仍有大量遗留代码在使用，且 `eval()` 仍然活跃。create_function 的危险性在于其隐蔽的字符串拼接方式，容易被忽视。

---

## Details

### 代码示例

```php
<?php
// 危险模式1：直接使用用户输入作为函数体
$operation = $_POST['op'];
$fn = create_function('$x', $operation);  // 危险：$operation 完全可控
echo $fn(10);

// 危险模式2：使用用户输入拼接函数体
$rule = $_GET['rule'];
$validator = create_function('$data', "return {$rule};");  // 危险
$result = $validator($_POST['input']);

// 危险模式3：使用用户输入作为函数参数名
$paramName = $_POST['param'];
$fn = create_function("${paramName}", 'return $' . $paramName . ' * 2;');  // 危险
echo $fn(5);

// 危险模式4：从数据库值构造函数
$sql = "SELECT code FROM rules WHERE id = ?";
$rule = $db->query($sql, [$_GET['id']])->fetchArray();
if ($rule) {
    $fn = create_function('$input', $rule['code']);  // 危险：数据库可被污染
    echo $fn($_POST['data']);
}

// 危险模式5：回调函数中使用 create_function
$operators = [];
foreach ($_POST['ops'] as $op) {
    // 危险：循环中构造函数，大量用户输入可导致内存溢出或代码注入
    $operators[$op] = create_function('$a, $b', "return \$a $op \$b;");
}

// 危险模式6：与 array_map 结合
$formulas = $_POST['formulas'];
$results = array_map(
    create_function('$x', "return {$formulas};"),  // 危险
    [1, 2, 3, 4, 5]
);

// 危险模式7：与 usort 结合
$sortRule = $_GET['sortby'];
$data = [['id' => 3], ['id' => 1], ['id' => 2]];
usort($data, create_function(
    '$a, $b',
    "return \$a['id'] - \$b['id']; // {$sortRule} ignored"  // 危险
));

// 危险模式8：错误处理中的隐藏 create_function
try {
    $code = $_POST['handler'];
    $handler = @create_function('', $code);  // 危险：@ 符号隐藏错误
    $handler();
} catch (Exception $e) {
    // 处理异常
}
?>
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `create_function(`
- 搜索 `create_function` 的相关变量赋值
- 搜索字符串拼接或双引号字符串内插用于参数构造：`"...$variable..."`、`'...' . $variable . '...'`
- 搜索与用户参数相关的变量在 create_function 参数中的使用
- 注意：create_function 已弃用，搜索时检查 PHP 版本和废弃警告

**L2 跳读**：
- 定位所有 `create_function(` 调用，记录行号和上下文
- 检查第一个参数（函数参数列表）来源：`$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE`、`$_SERVER`、`$_FILES`
- 检查第二个参数（函数体）来源和构造方式
- 检查是否使用了字符串拼接、heredoc、nowdoc、变量内插等字符串构造
- 检查返回的函数变量是否被直接调用或传递给其他函数（如 array_map、usort、call_user_func）
- 追踪是否在循环中使用 create_function（可能导致函数命名空间污染）

**L3 逐行读**：
- 确认用户输入的确切来源及完整传输路径
- 检查参数被传入 create_function 之前是否进行了处理（stripslashes、htmlspecialchars、addslashes 等）
- 逐行追踪所有影响 create_function 参数的中间变量赋值和修改
- 检查是否使用了正则表达式、黑名单、白名单进行验证
- 检查是否有条件判断在 create_function 调用前执行验证
- 验证创建的函数返回值是否被正确处理
- 检查是否存在无意中暴露的全局变量（`$GLOBALS`、`global` 关键字等）

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查 create_function 前是否有严格的条件判断：`if`、`switch`、白名单检查
- 搜索黑名单关键词：`eval`、`assert`、`system`、`exec`、`passthru`、`shell_exec`、`proc_open`、`pcntl_exec`、`var_dump`、`print_r`、`phpinfo`
- 搜索白名单：`allowedFunctions`、`PERMITTED_OPERATIONS`、`validExpressions`
- 检查是否对参数长度、复杂度有限制
- 检查是否在 create_function 前使用了正则表达式验证参数

**L3 逐行读**：
- 分析白名单实现：精确匹配还是前缀/后缀匹配？是否可被绕过？
- 分析黑名单实现：是否全面？可否被大小写、URL 编码、HTML 编码等绕过？
- 检查验证逻辑执行的位置：是否在 create_function 调用前？是否存在 TOCTOU 漏洞？
- 检查字符串处理函数：`preg_replace`、`str_replace` 等的使用是否正确
- 分析 PHP 版本：PHP 7.2.0+ 应该使用匿名函数替代 create_function，仍使用表示代码陈旧
- 检查是否对函数参数名进行了验证（第一个参数）

**L4 跨模块追踪**：
- 追踪自定义验证函数的实现：`validateCode()`、`isSafeExpression()`、`sanitizeInput()` 等
- 检查是否使用了 PHP 的 tokenizer 扩展进行代码 token 分析
- 查找是否有全局中间件或钩子对所有动态代码执行进行拦截
- 检查是否使用了沙箱机制（如 runkit、uopz 扩展，但这些方案本身风险高）
- 追踪是否使用了 disable_functions 配置来禁用危险函数
- 检查是否有自定义的代码安全检查库

---

## Classify

### 漏洞判定

- **直接使用用户输入作为函数参数名** → **确认漏洞**
  - 示例：`create_function($_POST['param'], 'return $var;')`

- **直接使用用户输入作为函数体** → **确认漏洞**
  - 示例：`create_function('$x', $_GET['code'])`

- **使用用户输入拼接函数体** → **确认漏洞**
  - 示例：`create_function('$x', "return {$_POST['rule']};")` 或 `'...' . $_GET['code'] . '...'`

- **使用用户输入拼接函数参数名** → **确认漏洞**
  - 示例：`create_function("$" . $_POST['param'], '...')`

- **从不可信源（数据库、缓存、外部 API）获取函数体，无进一步验证** → **确认漏洞**
  - 即使来自数据库，若数据库可被用户影响（如自定义规则、用户上传的代码），仍需验证

- **白名单验证不完整或可被绕过**（大小写敏感、编码、URL 编码、HTML 编码等）→ **确认漏洞**
  - 示例：`if (strpos($code, 'system') === false) create_function(...)` 可被大小写绕过

- **使用黑名单而非白名单** → **高风险**
  - 黑名单容易被绕过，需考虑 PHP 动态特性（如变量变量 `$$var`、可变函数 `$func()`）

### 误报判定

- **函数体完全来自硬编码常量或不可变配置文件** → **误报**
  - 示例：`$templates = ['add' => 'return $a + $b', 'mul' => 'return $a * $b']; create_function('$a, $b', $templates[$key])`

- **严格的白名单，且白名单本身不可被用户篡改** → **误报**
  - 示例：`$safe = ['sum', 'mul']; if (!in_array($rule, $safe, true)) throw new Exception(); create_function('$a, $b', "return \$a $rule \$b;")`

- **使用严格的正则表达式验证，确保仅允许安全字符** → **误报**
  - 示例：`if (!preg_match('/^[a-zA-Z0-9+\-*\/() ]+$/', $code)) throw new Exception(); create_function('$x', "return {$code};")`

- **参数来源完全受控**：仅来自配置文件、环境变量、或已验证的管理员输入 → **误报**
  - 示例：功能仅限管理员使用，权限检查无提升漏洞

- **PHP 版本 7.2.0+ 且使用了匿名函数替代 create_function** → **不适用**
  - 示例：`$fn = function($x) { return ...; }` 替代了 create_function

### 代码异味

- **使用黑名单检查危险函数名** → **需进一步测试**
  - 可被大小写、URL 编码、变量变量（`$$var`）、可变函数等绕过

- **仅检查当前参数中的关键字** → **需检查完整的拼接结果**
  - 示例：`if (strpos($code, 'system') === false) create_function(...)` 未检查拼接后的完整字符串

- **使用 stripslashes、htmlspecialchars 等防护** → **无效**
  - 这些函数用于编码/解码，不用于代码验证

- **验证后又进行了字符串处理** → **需追踪完整数据流**
  - 示例：先验证再进行 stripslashes、urldecode 等操作

- **仅在前端验证** → **确认可绕过**
  - 后端未验证，可直接请求绕过

- **PHP 版本低于 7.2.0 且仍在使用 create_function** → **需升级**
  - 虽然函数有效，但已弃用，应使用匿名函数或闭包替代

- **在循环中使用 create_function** → **潜在风险**
  - 每次创建新函数会生成新的函数名（如 `__lambda_1`、`__lambda_2` 等），可能导致内存泄漏或函数命名空间污染

### 审计等级

- **L1**：关键词扫描，快速定位所有 create_function 调用
- **L2**：跳读确认参数来源、字符串拼接方式、基本防护
- **L3**：逐行读取数据流、详细分析验证逻辑
- **L4**：跨模块追踪自定义验证、tokenizer 使用、disable_functions 配置

---

## Low risk

### 低风险场景

- **函数体完全来自硬编码常量**：所有可能的函数体在代码中明确列举，无用户输入
  - 示例：`$templates = ['sum' => 'return $a + $b', 'mul' => 'return $a * $b']; $fn = create_function('$a, $b', $templates[$template])`

- **严格的白名单验证**：使用 `in_array($val, $whitelist, true)` 进行精确匹配，白名单不可被用户修改
  - 示例：`$allowed = ['add', 'sub', 'mul']; if (!in_array($rule, $allowed, true)) throw new Exception(); create_function('$a, $b', "return \$a $rule \$b;")`

- **完整的正则表达式验证**：使用严格的正则表达式确保仅包含安全字符
  - 示例：`if (!preg_match('/^[a-zA-Z0-9+\-*\/() ]+$/', $code)) throw new Exception(); create_function('$x', "return {$code};")`

- **使用匿名函数替代 create_function**：PHP 5.3+ 支持闭包，应优先使用
  - 示例：`$fn = function($x) { return {$safenessVerifiedExpression}; }` 而非 create_function

- **参数来源完全受控**：参数仅来自配置文件、环境变量、或已验证的管理员输入
  - 示例：功能仅限管理员使用，权限检查无提升漏洞

- **功能权限隔离**：此功能仅在特定权限等级下可用
  - 示例：`if (!$user->isAdmin()) throw new AccessDeniedException();`

- **完整的审计日志和监控**：所有 create_function 调用被记录，包含参数、调用者、时间戳
  - 示例：记录每次调用的完整上下文，支持实时告警

- **严格限制函数类型和参数**：仅允许数字、布尔值等基础类型参与构造
  - 示例：验证参数仅为数字，如 `if (!is_numeric($input)) throw new Exception();`

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- `create_function()` 已在 PHP 7.2.0 中弃用，PHP 8.0.0 中移除，建议迁移到匿名函数（闭包）或使用预定义函数库
- 应定期审查白名单内容和权限配置，确保无权限提升漏洞
- 应建立完整的测试覆盖，确保绕过场景（大小写、编码变体、变量变量、可变函数）被充分检验
- 应评估业务场景是否真的需要动态函数创建，是否可以使用配置驱动的逻辑或策略模式替代
- 若使用了正则表达式验证，应使用 `preg_match` 而非 `strpos`，且确保验证完整性
- 检查是否在循环中使用 create_function，这会导致大量匿名函数堆积在内存中
- 应使用 `disable_functions` 禁用危险函数（如 `eval`、`assert`、`system` 等），作为纵深防御的一部分
- PHP 版本应升级至 7.4+ 或 8.0+，利用新的语言特性（如短闭包、命名参数等）简化代码
