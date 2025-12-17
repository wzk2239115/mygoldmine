# PHP_Array_Index_Conversion

**漏洞类型**: 数组索引转换错误，数组索引计算中的类型转换导致越界或数据混淆

**漏洞成因**

PHP 中数组索引涉及类型转换存在以下风险：
- 浮点数直接作为数组索引被截断为整数
- 大整数超过 PHP_INT_MAX 后被转为浮点，再用于索引精度丢失
- 字符串索引的隐式转换（"10abc" → 10）导致访问错误元素
- 布尔值作为数组键被转换为 0 或 1
- 数组键类型混淆：`$arr[1]` 与 `$arr["1"]` 指向同一元素，但转换时差异
- 负数作为索引时的处理差异（某些函数支持负索引，某些不支持）
- 类型杂糅的数组键导致数据覆盖或逻辑混乱

---

## Details

### 代码示例

**危险模式1：浮点索引被截断**
```php
function accessArray($index) {
    $arr = ['apple', 'banana', 'cherry', 'date'];
    $idx = (int)$index;  // 或隐式转换：$arr[$index]
    return $arr[$idx];
}

accessArray(2.9);  // 返回 'cherry'（2.9 → 2），期望可能是 'date'
```

**危险模式2：字符串索引的隐式转换**
```php
function getUserData($userId) {
    $users = [];
    $users[10] = ['name' => 'Alice'];
    $users[20] = ['name' => 'Bob'];

    // 字符串 "10" 被自动转为整数 10
    $data = $users[$userId];  // $userId = "10" 或 10，结果相同
    return $data;
}

getUserData("10");      // 访问 users[10]
getUserData("10abc");   // "10abc" → 10，仍访问 users[10]（字符串转整）
```

**危险模式3：大整数超出范围导致精度丢失**
```php
function processLargeIndex($index_str) {
    $large_idx = (int)$index_str;  // 大于 PHP_INT_MAX 时转为浮点
    $data = range(1, 100);
    if ($large_idx < count($data)) {
        return $data[$large_idx];
    }
    return null;
}

// 在 64 位系统，PHP_INT_MAX ≈ 9.2e18
processLargeIndex('9223372036854775808');  // 超出范围，精度丢失
```

**危险模式4：布尔值作为数组键**
```php
function configArray($enabled) {
    $config = [];
    $config[true] = 'enabled';   // true 转为键 1
    $config[false] = 'disabled';  // false 转为键 0

    // 访问时类型混淆
    return $config[$enabled];  // $enabled = true 返回 'enabled'
}

configArray(1);      // 1 === true，但访问 $config[1]，结果相同
configArray("1");    // "1" → 1，访问 $config[1]，结果相同
configArray(true);   // 返回 'enabled'
```

**危险模式5：数组键类型混淆导致覆盖**
```php
function storeUserData($data) {
    $store = [];
    foreach ($data as $id => $info) {
        $store[(int)$id] = $info;  // 整数键
    }

    // 后续访问
    $store["1"] = 'updated';  // "1" 被转为键 1，覆盖 $store[1]
    return $store;
}

$data = [1 => 'Alice', "1" => 'Bob'];  // 同一键，后者覆盖前者
storeUserData($data);  // 混淆导致数据丢失
```

**危险模式6：负数索引的差异**
```php
function reverseAccess($index) {
    $arr = ['a' => 1, 'b' => 2, 'c' => 3];
    // PHP array_slice() 等函数支持负索引，但直接访问不支持
    if ($index < 0) {
        return end($arr);  // 期望访问最后一个，但 $arr[-1] 未定义
    }
    return $arr[$index];
}

reverseAccess(-1);  // 期望得到最后元素，但 $arr[-1] 返回 null
```

**危险模式7：多维数组索引转换**
```php
function accessMatrix($row_str, $col_str) {
    $matrix = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9]
    ];

    $row = (int)$row_str;   // "1.9" → 1
    $col = (int)$col_str;   // "1.9" → 1
    return $matrix[$row][$col];  // 精度丢失
}

accessMatrix("1.9", "1.9");  // 返回 5（索引 [1][1]），期望可能是 6（[1.9][1.9]）
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- 直接使用浮点或字符串作为数组索引：`$arr[$float_idx]`、`$arr[$str_idx]`
- `(int)` 或 `intval()` 强制转换作用于数组索引
- 数组索引来自 `$_GET`、`$_POST` 或用户输入
- 索引计算涉及浮点运算或大数计算
- 多维数组访问中任何维度的索引有类型转换
- `in_array()` 等函数中的索引类型检查
- 数组键的隐式转换（布尔、null 等特殊值）

**快速定位保护机制 [L2-L3]**
- 是否在索引使用前验证类型：`if (is_int($idx))`
- 是否检查索引范围：`if ($idx >= 0 && $idx < count($arr))`
- 是否对字符串索引进行格式验证：`ctype_digit()`、`is_numeric()`
- 是否使用 `isset()` 或 `array_key_exists()` 而非直接访问
- 是否对大数值进行特殊处理
- 是否启用类型提示或类型检查
- 是否有单元测试覆盖边界值

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接作为数组索引，无截断检查，用于关键操作
2. 用户输入的字符串或数值直接作为数组索引，无验证
3. 大整数或浮点运算结果作为索引，精度丢失导致访问错误元素
4. 布尔值或特殊类型作为索引，导致键碰撞或逻辑混乱
5. 多维数组多个维度的索引有转换且无验证

**误报/代码异味的特征：**
- 索引来自内部循环计数器或明确限制范围的计算
- 索引使用前有完整验证：`is_int($idx) && $idx >= 0 && $idx < count($arr)`
- 使用 `isset()` 或 `array_key_exists()` 安全访问
- 索引来自内部常量或配置
- 使用类型提示强制整数索引

---

## Low risk

**以下场景可评为低风险：**

1. **完整的索引验证**
   - 索引使用前检查类型：`if (!is_int($idx)) { return error(); }`
   - 索引范围检查：`if ($idx >= 0 && $idx < count($arr))`
   - 使用 `isset()` 或 `array_key_exists()` 安全访问

2. **内部受控的索引**
   - 索引来自 `for` 循环计数器：`for ($i = 0; $i < count($arr); $i++)`
   - 索引来自内部常量或配置
   - 索引范围由代码逻辑保证

3. **安全的索引方法**
   - 使用 `array_slice()`、`array_splice()` 等内置函数，自动处理索引
   - 使用集合类或 SPL 接口，强制类型

4. **非关键操作**
   - 索引越界仅导致 warning 或返回 null，无后续风险
   - 索引仅用于显示或统计，不影响安全决策

5. **类型提示**
   - 使用 PHP 7+ 的类型提示：`function access(int $idx)`
   - 或通过 PHPStan/Psalm 进行静态类型检查

