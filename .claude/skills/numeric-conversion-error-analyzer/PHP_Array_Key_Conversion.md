# PHP_Array_Key_Conversion

**漏洞类型**: 数组键类型转换，数组键的类型转换和比较问题导致的数据混淆和逻辑漏洞

**PHP**

PHP 中数组键类型转换是一个隐蔽但高危的漏洞点。PHP 的弱类型系统自动将浮点数、字符串、布尔值等类型转换为数组键，导致密钥碰撞、数据覆盖、权限绕过等安全问题。特别是在使用用户输入作为数组键时，攻击者可以利用类型转换规则访问或修改非预期的数据。

---

## Details

### 代码示例与核心操作定位

**危险模式1：浮点数键被截断为整数**
```php
function storeMetrics($metric_id, $value) {
    static $metrics = [];
    // metric_id 可能来自用户输入或外部 API
    $metrics[$metric_id] = $value;  // 浮点数自动转为整数键
    return $metrics;
}

storeMetrics(1.5, 'admin');    // 键 1.5 被存储为键 1
storeMetrics(1.9, 'user');     // 键 1.9 也被存储为键 1，覆盖前值
// 结果：$metrics[1] = 'user'，admin 数据被覆盖
```

**危险模式2：字符串数字键与整数键碰撞**
```php
function processUserData($user_ids) {
    $users = [];
    // 存储用户数据时，键来自不同来源
    foreach ($user_ids as $uid) {
        $users[$uid] = getUserInfo($uid);  // $uid 可能是字符串或整数
    }
    return $users;
}

// 调用方式1：整数键
$data1 = processUserData([1, 2, 3]);         // 键为 1, 2, 3 (int)
// 调用方式2：字符串键
$data2 = processUserData(['1', '2', '3']);   // 键为 1, 2, 3 (string)
// PHP 认为 (int)1 === (string)'1'，第二次调用覆盖第一次的数据

$combined = [];
$combined[1] = 'first';    // 整数键 1
$combined['1'] = 'second'; // 字符串 '1' 转为整数 1，覆盖 first
// 结果：只有 'second' 存在
```

**危险模式3：大整数溢出导致键转换为浮点**
```php
function parseUserID($id_string) {
    $user_cache = [];
    // 在 64 位系统，PHP_INT_MAX ≈ 9.2e18
    $uid = intval($id_string);  // 超出范围时转为浮点数
    $user_cache[$uid] = fetchUserData($uid);

    // 之后的访问可能找不到该键
    return isset($user_cache[$uid]) ? $user_cache[$uid] : null;
}

// 大于 PHP_INT_MAX 的数字被转为浮点，浮点键存储和访问时精度不同
parseUserID('9223372036854775808');  // 键存储为浮点，访问时可能因精度丢失失败
```

**危险模式4：布尔和 null 键转换导致碰撞**
```php
function configStorage($key, $value) {
    static $config = [];
    $config[$key] = $value;  // 各种类型的键都被转换
    return $config;
}

configStorage(true, 'enabled');    // true → 键 1
configStorage(1, 'one');           // 1 → 键 1，覆盖前值
configStorage(false, 'disabled');  // false → 键 0
configStorage(0, 'zero');          // 0 → 键 0，覆盖前值
configStorage(null, 'empty');      // null → 键 ''（空字符串）

// 问题：true、1 使用相同键，false、0 使用相同键
// 导致配置数据被覆盖或混淆
```

**危险模式5：数组键用于权限决策**
```php
function checkPermission($role, $permission) {
    $permissions = [
        0 => ['read'],        // 角色 0 的权限
        1 => ['read', 'write'], // 角色 1 的权限
        2 => ['read', 'write', 'delete']  // 角色 2 的权限
    ];

    // 角色来自用户输入或数据库，类型不确定
    if (isset($permissions[$role])) {
        return in_array($permission, $permissions[$role]);
    }
    return false;
}

// 攻击：如果 $role = '0admin'（字符串）
// '0admin' → 0（字符串转整数），访问 $permissions[0]
// 可能绕过权限检查或获得意外权限
checkPermission('0admin', 'read');    // '0admin' → 0，获得角色 0 权限

// 攻击：$role = true
// true → 1，直接获得角色 1 权限
checkPermission(true, 'write');       // true → 1，获得写权限
```

**危险模式6：缓存键碰撞导致数据混淆**
```php
function getCachedData($cache_key) {
    static $cache = [];

    if (!isset($cache[$cache_key])) {
        // 从数据库获取数据，消耗资源
        $cache[$cache_key] = fetchExpensiveData($cache_key);
    }
    return $cache[$cache_key];
}

// 攻击场景：
getCachedData(0);        // 缓存键为 0
getCachedData('0');      // 字符串 '0' 转为 0，命中缓存
getCachedData('0admin'); // 字符串 '0admin' 转为 0，仍命中缓存，获得 0 的数据
// 结果：不同的输入因类型转换访问了同一缓存
```

**危险模式7：JSON 反序列化后键类型混乱**
```php
function processJsonData($json_str) {
    $data = json_decode($json_str, true);  // 转为关联数组
    $results = [];

    foreach ($data as $id => $value) {
        // JSON 中所有键都是字符串，但 PHP 会自动转换
        $results[$id] = processValue($value);  // 字符串键可能被转为整数
    }
    return $results;
}

$json = '{"1": "admin", "2": "user"}';
$result = processJsonData($json);
// JSON 键为 "1", "2"，转换后为整数键 1, 2

$json2 = '{"01": "guest", "001": "viewer"}';
$result2 = processJsonData($json2);
// "01" → 1, "001" → 1，键碰撞，后者覆盖前者
```

**危险模式8：数组键与哈希表操作的类型混淆**
```php
function validateSessionToken($token) {
    // 使用数组模拟哈希表存储会话
    static $sessions = [
        '0e123456789abcdef' => ['user' => 'admin'],
        '0e987654321fedcba' => ['user' => 'user']
    ];

    // 如果 token 包含数字前缀
    if (isset($sessions[$token])) {
        return $sessions[$token];
    }
    return null;
}

// Magic Hash 攻击：
// 科学计数法字符串 '0e...' 在宽松比较中等于 0
validateSessionToken('0e123456789abcdef');   // 精确匹配，返回 admin 会话
validateSessionToken('0');                    // 不会匹配任何键
// 但如果使用 in_array() 则会出现 Magic Hash 问题
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]**:
- 数组键赋值来自外部输入：`$arr[$_GET['id']]`, `$arr[$user_input]`
- 函数参数作为数组键：`function store($key, $value) { $arr[$key] = $value; }`
- 数据库查询结果作为数组键：`foreach (db_query() as $row) { $data[$row['id']] = ... }`
- JSON 反序列化后的键使用：`$json_data = json_decode(...); $result[$json_data[$key]]`
- 缓存操作中的键构造：`$cache[$user_id]`, `$cache[$role.$permission]`
- `isset()`, `array_key_exists()`, `in_array()` 操作中涉及类型混乱的键
- 布尔值或特殊类型用作数组键：`$arr[true]`, `$arr[false]`, `$arr[null]`
- 浮点数运算用于数组索引：`$arr[(int)$float_value]`, `$arr[floor($value)]`

**快速定位保护机制 [L2-L3]**:
- 是否在键使用前进行严格类型检查：`if (!is_string($key) && !is_int($key)) {}`
- 是否对键进行白名单验证：`if (!in_array($key, $ALLOWED_KEYS, true))`
- 是否使用 `array_key_exists()` 替代 `isset()`（null 值处理）
- 是否对键进行数值范围验证：`if ($key >= MIN_KEY && $key <= MAX_KEY)`
- 是否使用哈希函数生成稳定的字符串键：`$hash_key = hash('sha256', $user_input)`
- 是否启用严格的 PHP 配置或类型声明（PHP 7+）
- 是否有单元测试覆盖边界类型（浮点、大整数、布尔、null）

---

## Classify

**研判为真漏洞的特征：**

1. **直接键碰撞导致数据混淆**：多个不同来源的值因类型转换被分配到同一键，导致数据覆盖或访问错误数据

2. **权限绕过**：利用类型转换（如 '0admin' → 0）访问权限数组，绕过角色检查

3. **缓存中毒**：不同的输入因类型转换访问同一缓存项，导致缓存数据与预期不符

4. **大整数溢出**：超过 PHP_INT_MAX 的数值转为浮点数作为键，导致存储和查询时精度不一致

5. **JSON 反序列化碰撞**：JSON 字符串键（如 "01"）被自动转为整数 1，与其他键碰撞

6. **用户输入直接用作数组键，无类型验证**：如 `$_GET['role']` 直接用于访问权限或配置数组

**误报/代码异味的特征：**

- 键来自内部循环或常量，不涉及用户输入或外部数据
- 键使用前有严格的类型检查和范围验证：`if (is_int($key) && $key >= 0 && $key < 100)`
- 仅在同一类型的数据之间进行数组操作（全为字符串或全为整数）
- 使用 `array_key_exists()` 而非 `isset()`，显示对 null 值的理解
- 键由哈希函数或 ID 生成，确保稳定性
- 代码使用类型提示强制键类型：`function store(int $key, $value)`

---

## Low risk

**以下场景可评为低风险：**

1. **严格的键类型检查**
   - 键使用前检查类型：`if (!is_int($key)) { throw new Exception('Invalid key'); }`
   - 使用联合类型声明：`function store(int|string $key)` 并在函数内部进行验证
   - 使用 `array_filter()` 或 `array_map()` 等函数确保键的一致性

2. **内部受控的键**
   - 键来自预定义的常量集合：`$arr[self::ROLE_ADMIN]`, `$arr[self::CACHE_KEY_PREFIX]`
   - 键由循环计数器生成：`for ($i = 0; $i < count($data); $i++) { $arr[$i] = ... }`
   - 键来自数据库主键或 UUID，经过 ORM 框架验证

3. **安全的键操作方法**
   - 使用 `SplFixedArray` 或其他 SPL 集合强制类型
   - 使用专用的缓存库（如 Redis、Memcached），不依赖 PHP 数组
   - 使用 ORM 框架（如 Doctrine、Eloquent）处理数据映射

4. **键的用途不涉及安全决策**
   - 键仅用于数据分组或统计，不影响访问控制或权限
   - 键被覆盖或碰撞时，系统无副作用（如仅用于显示）
   - 键的混乱不导致敏感信息泄露

5. **PHP 7+ 类型声明和严格模式**
   - 使用明确的类型提示：`function store(int $key, mixed $value): void`
   - 启用 `declare(strict_types=1);` 在文件顶部
   - 使用 PHPStan 或 Psalm 进行静态类型检查，验证无键碰撞风险

6. **使用 isset() 和 array_key_exists() 的安全模式**
   - 区分 `isset()` 和 `array_key_exists()`：前者不适用 null 值，后者适用
   - 显示检查键是否存在再访问：`if (array_key_exists($key, $arr)) { access... }`
   - 提供默认值或回退机制：`$value = $arr[$key] ?? $default;`

