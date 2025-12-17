# PHP_Integer_Float_Conversion

**漏洞类型**: 整型与浮点转换，int 与 float 之间的转换精度问题

**PHP**

PHP 中整数与浮点数的转换涉及精度丢失、四舍五入行为不同、溢出和下溢等问题。浮点数的 IEEE 754 表示导致精度有限，转为整数时可能出现意外截断。整数超过浮点精度范围时会失去精度。这类问题常在金额计算、权限判断、密钥长度等安全相关操作中导致漏洞。

---

## Details

### 代码示例与核心操作定位

**危险模式1：浮点金额转整数时的精度丢失**
```php
function processPayment($amount_float) {
    // 用户输入的浮点数金额
    $amount_cents = (int)($amount_float * 100);  // 浮点精度丢失

    if ($amount_cents > 1000000) {  // 金额阈值检查
        requiresApproval();
    }

    charge($amount_cents);
}

// 浮点精度问题导致金额计算错误
processPayment(123.455);  // 期望 12345，实际可能 12344 或 12346
```

**危险模式2：比较操作中的浮点精度**
```php
function verifyDiscount($original_price, $discount_rate) {
    $discounted = $original_price * $discount_rate;  // 浮点运算
    $int_discounted = (int)$discounted;

    // 权限检查依赖于转换结果
    if ($int_discounted < 1000) {
        allowMaxDiscount();  // 精度丢失导致权限提升
    }

    return $int_discounted;
}

verifyDiscount(1000.1, 0.999999);  // 浮点精度可能通过检查
```

**危险模式3：数组大小参数的浮点转整**
```php
function allocateBuffer($size_float) {
    $size = (int)$size_float;  // 浮点截断
    $buffer = array_fill(0, $size, 0);  // 分配内存

    return $buffer;
}

// 浮点数被截断，导致分配大小与预期不符
allocateBuffer(1024.9);  // 分配 1024，期望 1025
```

**危险模式4：循环计数器的浮点使用**
```php
function processItems($count_float) {
    $count = (int)$count_float;

    for ($i = 0; $i < $count; $i++) {
        // 精度丢失导致循环次数错误
        processItem($i);
    }

    return $count;
}

processItems(10.99);  // 只循环 10 次，期望 11 次
```

**危险模式5：整数超过浮点精度范围**
```php
function verifyTransaction($transaction_id_str) {
    $id_int = intval($transaction_id_str);
    $id_float = (float)$id_int;

    // 大整数转浮点后精度丢失
    if ($id_float == $id_int) {  // 可能为 false！
        confirmTransaction();
    }

    return $id_int;
}

// 64 位大整数精度超出浮点范围 (2^53)
verifyTransaction('9007199254740993');  // 精度丢失后比较失败
```

**危险模式6：浮点运算中的累积误差**
```php
function calculateTotal($items_array) {
    $total = 0.0;

    foreach ($items_array as $price) {
        $total += (float)$price;  // 浮点加法的累积误差
    }

    $total_cents = (int)($total * 100);  // 误差被放大
    return $total_cents;
}

$prices = [0.1, 0.2, 0.3];
$result = calculateTotal($prices);  // 精度问题导致总金额错误
```

**危险模式7：权限计算中的浮点转整**
```php
function calculatePermissionLevel($score_float) {
    $level = (int)$score_float;  // 精度丢失

    $permissions = [
        0 => 'guest',
        1 => 'user',
        2 => 'moderator',
        3 => 'admin'
    ];

    // 数组键访问依赖于转换精度
    return $permissions[$level] ?? 'none';
}

// 浮点精度导致权限提升
calculatePermissionLevel(2.99);  // 返回 'moderator'，期望 'user'
```

**危险模式8：密钥导出中的浮点参数**
```php
function deriveKey($iteration_count_float, $salt) {
    $iterations = (int)$iteration_count_float;  // 精度丢失

    // 密钥强度依赖于迭代次数
    $key = pbkdf2('sha256', $password, $salt, $iterations, 32);
    return $key;
}

deriveKey(100000.5, 'salt');  // 迭代次数被截断为 100000
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]**:
- 浮点到整数转换：`(int)$float`, `intval($float)`, `floor()`, `ceil()`, `round()`
- 浮点运算：`$a * $b`, `$a + $b`, `$a / $b` 后转整数
- 金额相关：`$amount * 100`, `price * discount_rate`, `total += price`
- 数组大小参数：`array_fill(0, (int)$size, ...)`, `array_pad(..., (int)$count, ...)`
- 权限/阈值比较：`if ((int)$score > threshold)`, `$level = (int)$value`
- 整数转浮点再比较：`(float)$int == $int`, `$float === $int`
- 密钥/安全参数：`pbkdf2(..., (int)$iterations, ...)`, `openssl_*` 参数

**快速定位保护机制 [L2-L3]**:
- 是否在转换前验证精度范围：`if (is_finite($float) && $float >= 0)`
- 是否使用字符串计算保持精度：`bcmul()`, `bcadd()` 等 BCMath 函数
- 是否进行四舍五入而非直接截断：`round($float, 2)` 后转整
- 是否验证转换后的值与原值是否一致：`$int === (int)$float`
- 是否对数值范围进行二次验证：`if ($value >= MIN && $value <= MAX)`
- 金额计算是否使用专用库：Decimal 库、Money 库
- 是否避免浮点比较：使用 `bccomp()`, `gmp_cmp()` 进行比较

---

## Classify

**研判为真漏洞的特征：**

1. **安全决策依赖浮点转整**：权限判断、金额验证、阈值检查依赖 `(int)$float` 转换，无精度验证

2. **浮点运算后直接使用**：如 `$price * $discount` 或 `$total += $price` 后转整，未进行精度检查

3. **大整数精度超出浮点范围**：超过 2^53 的整数转浮点后精度丢失，用于身份验证或比较

4. **金额计算无法保证精度**：使用浮点做金额运算，未用 BCMath 或 Decimal 库

5. **累积浮点误差导致阈值绕过**：循环中浮点加法累积误差后转整，导致最终结果与预期不符

6. **密钥导出强度削弱**：密钥派生函数的迭代次数、长度等参数由浮点转整导致实际强度不足

**误报/代码异味的特征：**

- 浮点转整前进行完整验证：`if (is_finite($float) && $float === (int)$float)`
- 使用 BCMath 或专用库处理精度敏感操作：`bcmul($a, $b)` 保持字符串
- 数值来自应用常量或配置，不涉及浮点运算：`const ITERATIONS = 100000;`
- 转换结果用于展示/日志，未用于逻辑判断或安全决策
- 显式指定四舍五入方式：`round($value, 2)` 后进行明确的阈值检查
- 使用专用金额/货币库处理：Money 库、Decimal 库
- 函数有类型声明且明确期望整数参数

---

## Low risk

**以下场景可评为低风险：**

1. **完整的精度验证**
   - 转换前验证浮点精度：`if (is_finite($float) && $float === (int)$float) { $int = (int)$float; }`
   - 转换后验证结果：`$int = (int)$float; if ($int !== $float) { throw new Exception(); }`
   - 金额使用四舍五入后验证：`round($price, 2); if (abs($rounded - $price) > 0.01) { error(); }`

2. **使用精度保持的工具**
   - BCMath 函数处理：`$total = bcadd($a, $b);` 保持为字符串
   - Decimal/Money 库：应用统一使用 Decimal 对象处理金额
   - 字符串计算：所有数值保持为字符串格式进行 SQL 参数化

3. **数值来源受控**
   - 浮点数来自应用常量：`const DISCOUNT_RATE = 0.9;`
   - 来自配置文件的硬编码值
   - 来自数据库且已验证的值
   - 完全内部生成的数据

4. **非安全相关的操作**
   - 浮点转整用于展示、统计、日志：`printf("%.0f", $value)`
   - 数值仅用于计数显示，不影响权限或金额逻辑
   - 转换结果用于缓存键而非逻辑判断
   - UI 表示或格式化，未用于后续计算

5. **安全参数的完整验证**
   - 密钥长度为预定义常量：`const RSA_BITS = 2048;`
   - 迭代次数来自已验证的配置：从受信配置文件读取后再验证范围
   - PBKDF2 参数完整检查：`if ($iterations >= 100000 && $iterations <= 10000000)`

6. **类型声明和严格比较**
   - 函数参数有类型提示：`function process(int $count): void`
   - 启用 `declare(strict_types=1);`
   - 显式类型检查：`assert(is_int($result))`
   - 使用精确比较：`$value === $int` 而非 `==`

