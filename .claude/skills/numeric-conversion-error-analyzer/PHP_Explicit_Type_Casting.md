# PHP_Explicit_Type_Casting

**漏洞类型**: 类型强制转换错误，显式类型转换 (int)、(float) 时的精度丢失、溢出、无符号数误解

**漏洞成因**

PHP 中显式类型转换存在以下风险：
- 浮点数转整型 `(int)` 时精度丢失、截断，用于数组索引或内存操作
- 大整数超出 PHP_INT_MAX 被转为浮点，再转整时精度丢失
- 字符串到数字转换时的格式歧义（十六进制前缀未识别）
- 浮点特殊值（INF、NAN）转整后行为未定义或返回 PHP_INT_MIN
- 布尔值转整后的值对比（true → 1, false → 0）
- 数组键的隐式类型转换导致数组元素覆盖或越界
- 从数据库/JSON 返回的大数值字符串经 (int) 转换后精度丢失

---

## Details

### 代码示例

**危险模式1：浮点直接转整作为数组索引**
```php
function processIndex($userInput) {
    $index = (int)floatval($userInput);  // "3.9" → 3.9 → 3
    $array = [1, 2, 3, 4, 5];
    return $array[$index];              // 精度丢失，访问错误元素
}

processIndex("3.9");  // 实际想访问索引 3 或 4，但 3.9 被截断为 3
```

**危险模式2：大整数转整丢失精度**
```php
function processLargeNumber($value) {
    // 大于 PHP_INT_MAX (2^63-1) 的数转浮点再转整
    $int_val = (int)$value;  // 12345678901234567890 → 浮点 → 精度丢失
    $buffer = str_pad("", $int_val);  // 内存分配异常
    return $buffer;
}

processLargeNumber("12345678901234567890");
```

**危险模式3：浮点特殊值的转换**
```php
function handleMeasurement($stringValue) {
    $value = (float)$stringValue;
    $size = (int)$value;  // INF → PHP_INT_MIN, NAN → 0
    $array = array_fill(0, $size, null);  // 分配异常大小或为负
    return $array;
}

handleMeasurement("INF");   // (int)INF = PHP_INT_MIN (负数)
handleMeasurement("NAN");   // (int)NAN = 0
```

**危险模式4：布尔值转整的逻辑错误**
```php
function checkPermission($isAdmin) {
    $level = (int)$isAdmin;  // true → 1, false → 0
    if ($level == 1) {
        grantAccess();
    }
}

checkPermission(true);   // 权限提升
checkPermission("0");    // "0" 转 bool 为 false，再转 int 为 0，权限拒绝
```

**危险模式5：数组键隐式类型转换导致覆盖**
```php
function storeInArray($arr, $key) {
    // 数组键被隐式转换：浮点 → int, string → int
    $arr[(int)$key] = "value";  // "1.5" → 1, "2xyz" → 2
    $arr[(float)$key] = "other";  // 同一个数组键，导致值覆盖
    return $arr;
}

$data = [];
storeInArray($data, "1.5");   // 键被转为 1
```

**危险模式6：字符串进制转换的歧义**
```php
function parseNumber($hexString) {
    // PHP 会自动识别 "0x" 前缀，但 (int) 不会
    $value = (int)$hexString;  // "0x10" → 0 (非数字开头)
    if ($value > 100) {
        grantAdmin();
    }
    return $value;
}

parseNumber("0x10");  // 作为十六进制是 16，作为 (int) 转换是 0
```

**危险模式7：类型强制转换在计算中的累积误差**
```php
function calculateDiscount($price, $percentageStr) {
    $percentage = (float)$percentageStr;  // "33.33"
    $discount = (int)($price * $percentage / 100);  // 舍入误差
    return $price - $discount;  // 多次计算时误差放大
}

calculateDiscount(100, "33.33");  // 99 vs 100 的差异
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `(int)` 或 `(float)` 或 `(bool)` 直接作用于变量或函数返回值
- `intval()`、`floatval()`、`boolval()` 等函数
- 数组索引使用浮点或字符串值：`$arr[(int)$float_idx]`
- 从数据库或 JSON 返回的值直接强制转换
- 使用 `===` 或 `==` 比较转换后的值
- `is_int()`、`is_float()` 等类型检查后紧跟转换
- 字符串包含数值前缀但转换方式不对（如 "0x10"）

**快速定位保护机制 [L2-L3]**
- 转换前是否检查浮点有限性：`is_finite()` 或 `is_nan()` 或 `is_infinite()`
- 是否验证转换后值在合理范围内
- 是否使用 `filter_var()` 等安全转换函数
- 是否在数组访问时检查键的有效性
- 是否对浮点计算启用舍入或精度检查
- 是否使用 `bcmath` 或 `gmp` 库处理大数字
- 是否通过单元测试覆盖边界值（0、负数、浮点特殊值）

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接转整 `(int)` 无检查，用作数组索引或数组长度参数
2. 大整数或来自外部的数值直接强制转整，无范围验证
3. 浮点特殊值（INF、NAN）未检查直接转整用于内存/循环
4. 数组键的隐式转换导致元素覆盖或逻辑混淆
5. 类型转换在循环或多次计算中导致精度误差累积
6. 字符串到数字的转换中格式歧义导致值误解

**误报/代码异味的特征：**
- 类型转换来自内部代码生成的字符串，格式和范围已控制
- 转换前有完整的范围验证：`if (is_finite($val) && $val > MIN && $val < MAX)`
- 使用 `filter_var($val, FILTER_VALIDATE_INT)` 等安全函数
- 转换结果仅用于非关键路径（显示、日志）
- 明确指定进制避免歧义：`intval($str, 16)` for 十六进制
- 使用 `bcmath` 或 `gmp` 库处理需要高精度的计算

---

## Low risk

**以下场景可评为低风险：**

1. **完整的有效性检查**
   - 转换前验证：`if (is_numeric($val) && is_finite((float)$val))`
   - 范围检查后转换：`if ($val >= PHP_INT_MIN && $val <= PHP_INT_MAX)`
   - 超出范围时有明确处理

2. **使用安全的转换函数**
   - 采用 `filter_var($val, FILTER_VALIDATE_INT)` 或 `filter_var($val, FILTER_VALIDATE_FLOAT)`
   - 使用 `bcmath` 库：`bcmath` 保留精度
   - 使用 `gmp` 库：处理任意精度整数

3. **内部生成的值转换**
   - 类型转换应用于内部生成或完全受控的值
   - 范围已在代码逻辑上确保合理
   - 如：`(int)count($array)` 或已限制范围的计算结果

4. **非关键路径的转换**
   - 转换结果仅用于显示、日志、统计
   - 不影响数组访问、内存分配、权限决策
   - 错误的转换不导致数据泄露或权限提升

5. **明确指定转换格式**
   - 使用 `intval($str, 16)` 明确十六进制转换
   - JSON 中数值类型与字符串分离
   - 数据格式已在协议层验证

