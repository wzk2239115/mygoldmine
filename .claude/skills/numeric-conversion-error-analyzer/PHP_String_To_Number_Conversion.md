# PHP_String_To_Number_Conversion

**漏洞类型**: 字符串到数字转换，字符串到整型/浮点型的自动转换

**PHP**

PHP 的弱类型系统进行字符串到数字的隐式转换时，规则复杂且容易被绕过。字符串前缀数字解析（如 `"123abc"` → 123）、科学计数法支持（如 `"1e10"` 被解析为浮点）、"魔法哈希"（如 `"0e123..." == 0` 的宽松比较）等特性导致验证绕过、权限提升、身份认证失败等安全问题。

---

## Details

### 代码示例与核心操作定位

**危险模式1：字符串前缀数字被提取，忽略尾部字符**
```php
function validateAmount($amount_str) {
    $amount = (int)$amount_str;  // PHP 自动提取前缀数字

    if ($amount < 100 && $amount > 0) {
        return processSmallAmount();
    }

    return processLargeAmount();
}

// 攻击：传入 "0admin"，被转为 0，绕过逻辑
validateAmount("0admin");   // (int)"0admin" = 0，执行 processSmallAmount
validateAmount("99999xxx"); // (int)"99999xxx" = 99999，可能绕过某些检查
```

**危险模式2：科学计数法字符串导致精度丢失**
```php
function verifyUserId($user_id_str) {
    $user_id = intval($user_id_str);  // 可能被解析为科学计数法

    // 使用 ID 执行数据库查询
    $user = getUser($user_id);
    if ($user) {
        return $user;
    }

    return null;
}

// 攻击：传入 "1e10"，被解析为 10000000000（浮点），再转为整数时精度丢失
verifyUserId("1e10");  // 被转为浮点 1e10，再转整可能溢出或精度丢失
```

**危险模式3：宽松比较中的魔法哈希**
```php
function verifyPasswordHash($provided_hash, $stored_hash) {
    // 使用宽松比较验证哈希
    if ($provided_hash == $stored_hash) {
        return true;
    }

    return false;
}

// 攻击：两个哈希都以 "0e" 开头的科学计数法
// "0e123456789..." == "0e987654321..." 都被解析为 0
verifyPasswordHash("0e123456789abcdef", "0e987654321fedcba");
// 宽松比较认为相等！
```

**危险模式4：字符串数字转换用于权限检查**
```php
function checkPermission($role_str, $required_level) {
    $role = (int)$role_str;  // 从用户输入转换

    if ($role >= $required_level) {
        return grantAccess();
    }

    return denyAccess();
}

// 攻击：传入 "2147483648" (超过 INT_MAX)
// 32 位系统中会发生溢出，32 位下 (int)"2147483648" = -2147483648
checkPermission("2147483648", 100);  // 可能导致权限提升
```

**危险模式5：SQL 注入通过字符串数字转换**
```php
function queryUser($user_id_str) {
    $user_id = intval($user_id_str);  // 自动转换

    // 虽然 intval 会将字符串转为数字，但可能有其他问题
    $query = "SELECT * FROM users WHERE id = " . $user_id;
    return db_query($query);
}

// 攻击：某些边界情况下可能绕过
// 例如大于 PHP_INT_MAX 的数字转为浮点科学计数法
queryUser("999999999999999999e10");
```

**危险模式6：字符串中的空白和特殊字符**
```php
function parsePrice($price_str) {
    $price = (float)$price_str;  // 转换包含空白的字符串

    if ($price > 10000) {
        requiresApproval();
    }

    return $price;
}

// 攻击：字符串前缀包含空白、加号、减号等字符
parsePrice("   +123");       // 被转为 123，白空被忽略
parsePrice("\t\n100");       // 转换忽略制表符和换行符
parsePrice("1e5");           // 被转为浮点 100000
```

**危险模式7：布尔值的隐式字符串转换**
```php
function processValue($value_str) {
    // 某些情况下 $value_str 可能为布尔值而不是字符串
    $value = (int)$value_str;

    if ($value == 1) {
        executeOperation();
    }

    return $value;
}

// 攻击：传入 true，被转为 1；传入 false，被转为 0
processValue(true);   // (int)true = 1，绕过检查
processValue(false);  // (int)false = 0
```

**危险模式8：十六进制字符串被解析**
```php
function parseHexValue($hex_str) {
    // PHP 自动识别十六进制前缀 0x
    $value = intval($hex_str);  // 可能被解析为十六进制

    if ($value > 1000) {
        return error();
    }

    return $value;
}

// 攻击：十六进制字符串
// intval("0xFF", 0) 自动检测为 255，不会超过 1000
parseHexValue("0xFFFFFFFF");  // 如果使用自动基数检测，可能被识别为 4294967295
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]**:
- 字符串到数字转换：`(int)$str`, `(float)$str`, `intval()`, `floatval()`
- 宽松比较操作：`$str == $number`, `$hash == $other_hash`
- 用户输入直接转换：`$_GET['id']`, `$_POST['amount']`, `$_REQUEST['value']`
- 数字字符串用于权限/安全决策：`if ((int)$role >= MIN_LEVEL)`
- 哈希或验证相关：`if ($provided_hash == $stored_hash)`
- 数组键从字符串转换：`$arr[(int)$user_input]`
- SQL/数据库查询中的字符串转数字：`WHERE id = intval($id)`
- 字符串包含 "0e" 开头的科学计数法：`"0e123..."`

**快速定位保护机制 [L2-L3]**:
- 是否使用严格类型检查：`===` 而非 `==`，`if (is_int($value))`
- 是否进行范围验证：`if ($value >= MIN && $value <= MAX)`
- 是否验证字符串格式：`if (ctype_digit($str))`，`if (preg_match('/^\d+$/', $str))`
- 是否使用参数化查询/预编译语句避免 SQL 注入
- 哈希比较是否使用 `hash_equals()`（恒定时间比较）
- 是否对浮点转换的结果进行验证
- 是否在转换前检查字符串的实际内容
- 是否禁用宽松比较，使用显式类型强制转换

---

## Classify

**研判为真漏洞的特征：**

1. **无验证的字符串到数字转换用于安全决策**：权限检查、金额验证、身份认证直接依赖 `(int)$user_input` 转换

2. **宽松比较导致认证绕过**：使用 `==` 比较哈希、令牌或身份标识，可被 "魔法哈希" 绕过

3. **字符串前缀数字提取导致逻辑错误**：`"0admin"` 被转为 0，`"2admin"` 被转为 2，绕过权限检查

4. **科学计数法导致精度丢失**：`"1e10"` 被解析为浮点，导致 ID 查询失败或精度溢出

5. **字符串包含特殊字符（空白、符号）而被意外接受**：如 `"  +123"` 被转为 123

6. **大整数溢出或布尔值隐式转换**：超过 INT_MAX 的字符串转换导致溢出，布尔值转数字导致 0/1 判断错误

**误报/代码异味的特征：**

- 使用严格比较：`if ($value === $expected_int)` 或 `if (is_int($value))`
- 字符串转换前进行格式验证：`if (ctype_digit($str) && strlen($str) <= 20)`
- 使用参数化查询或 ORM，避免手动字符串转换
- 哈希比较使用 `hash_equals($a, $b)` 进行恒定时间比较
- 数值来自应用常量或已验证的配置
- 转换结果仅用于展示/日志，不影响安全决策
- 使用类型声明强制参数类型

---

## Low risk

**以下场景可评为低风险：**

1. **严格的字符串格式验证**
   - 转换前验证格式：`if (preg_match('/^\d+$/', $str) && strlen($str) <= 20) { $id = (int)$str; }`
   - 白名单检查：`if (in_array($str, $ALLOWED_IDS, true)) { $value = (int)$str; }`
   - 拒绝非十进制格式：检查是否包含 `0x`, `0e`, `+`, `-` 等
   - 范围验证：`if ($value >= 0 && $value < PHP_INT_MAX)`

2. **使用严格比较和安全函数**
   - 恒定时间哈希比较：`hash_equals($provided, $stored)`
   - 严格类型检查：`if ($value === $int)` 而非 `==`
   - 是否为整数检查：`if (is_int($value) && $value > 0)`
   - 类型转换后验证：`$int = (int)$str; if ($int == $str) { ... }`

3. **非安全相关的数字转换**
   - 转换结果仅用于展示、统计、日志
   - 数字用于缓存键但有其他标识符保证唯一性
   - 转换结果用于 UI 渲染，不影响逻辑判断
   - 数值用于统计计算，但结果不影响权限或访问控制

4. **受信数据来源**
   - 字符串来自应用常量或配置：`const USER_IDS = [1, 2, 3];`
   - 来自已验证的内部系统
   - 来自数据库且已通过唯一性约束
   - 来自签名/加密数据，已验证完整性

5. **使用类型声明和严格类型**
   - 函数参数类型提示：`function process(int $id): void`
   - 启用 `declare(strict_types=1);`
   - 返回值类型声明
   - 使用 PHPStan/Psalm 等静态分析验证

6. **参数化查询和 ORM**
   - 使用 PDO 预编译语句：`$stmt->execute([$user_input])`
   - 使用 ORM 框架（Doctrine、Eloquent）自动处理类型转换
   - 避免字符串拼接 SQL 语句

7. **浮点转换的安全处理**
   - 科学计数法格式拒绝：`if (strpos($str, 'e') !== false) { error(); }`
   - 十六进制格式拒绝：`if (strpos($str, '0x') !== false) { error(); }`
   - 空白符拒绝：`if (trim($str) !== $str) { error(); }`
   - 显式指定转换基数：`intval($str, 10)` 而非自动检测

