# PHP_Extension_Type_Conversion

**漏洞类型**: 扩展模块类型转换，PHP 扩展中的类型转换问题

**PHP**

PHP 扩展（如 GMP、BCMath、ImageMagick、PECL 等）与 PHP 核心在类型转换时的不匹配，导致精度丢失、缓冲区溢出或逻辑错误。C/C++ 编写的扩展与 PHP 弱类型系统的交互中，类型转换规则差异可能导致安全漏洞。

---

## Details

### 代码示例与核心操作定位

**危险模式1：GMP 整数转 PHP 整型溢出**
```php
extension_loaded('gmp') or die('GMP extension required');

function calculatePermissions($user_id) {
    // user_id 可能超过 PHP_INT_MAX
    $gmp_id = gmp_init($user_id);
    $permission_level = gmp_intval($gmp_id);  // 溢出或精度丢失

    if ($permission_level > 1000) {
        // 权限检查依赖于转换结果
        grantAdminAccess();
    }
}

// 攻击：传入超过 64 位的大数
calculatePermissions('99999999999999999999999999');
// gmp_intval() 返回值不可预测，绕过权限检查
```

**危险模式2：BCMath 字符串转整数的精度丢失**
```php
extension_loaded('bcmath') or die('BCMath extension required');

function validateTransactionAmount($amount_str) {
    $bc_result = bcmul($amount_str, 1);  // 返回字符串
    $int_amount = (int)$bc_result;       // 转整数时精度丢失

    if ($int_amount > 10000) {
        processHighValue();
    }

    return $int_amount;
}

// 高精度金额被截断
validateTransactionAmount('10000.99999999999');
// (int) 转换导致精度丢失
```

**危险模式3：ImageMagick 扩展的宽度/高度整型转换**
```php
extension_loaded('imagick') or die('Imagick extension required');

function resizeImage($image_path, $width, $height) {
    $img = new Imagick($image_path);

    // width/height 来自用户输入或外部 API
    // 可能是浮点、大整数或负数
    $img->resizeImage((int)$width, (int)$height, Imagick::FILTER_LANCZOS, 1);

    // 缓冲区溢出风险：负数转为无符号整数
    return $img->getImage();
}

// 攻击：传入负数或超大整数
resizeImage('photo.jpg', -100, 2147483648);
// 转为无符号数，导致缓冲区问题
```

**危险模式4：PDO/MySQLi 扩展的大整数返回值处理**
```php
$pdo = new PDO('mysql:host=localhost;dbname=test');

function getUserBalance($user_id) {
    // 数据库返回的大整数可能是字符串或浮点
    $stmt = $pdo->prepare('SELECT balance FROM users WHERE id = ?');
    $stmt->execute([$user_id]);
    $result = $stmt->fetch(PDO::FETCH_ASSOC);

    $balance = (int)$result['balance'];  // 扩展返回值的类型不确定

    if ($balance > 1000000) {
        processLargeBalance();  // 精度丢失导致阈值判断错误
    }

    return $balance;
}

// PDO 可能将大整数返回为浮点或字符串
```

**危险模式5：OpenSSL 扩展的密钥长度转换**
```php
extension_loaded('openssl') or die('OpenSSL extension required');

function generateKey($key_length) {
    // key_length 来自配置或用户输入
    // 浮点转整数导致密钥强度不足
    $bits = (int)$key_length;

    $private_key = openssl_pkey_new([
        'private_key_bits' => $bits,
        'private_key_type' => OPENSSL_KEYTYPE_RSA
    ]);

    return $private_key;
}

// 攻击：传入 1024.5，转为 1024 位（本应 2048）
generateKey(2048.5);  // 浮点截断削弱密钥强度
```

**危险模式6：JSON 扩展与 GMP 的交互**
```php
extension_loaded('gmp') or die('GMP extension required');

function processPayment($gmp_json) {
    // JSON 中的大整数被解析为浮点
    $data = json_decode($gmp_json, true);
    $amount = $data['transaction_id'];  // 字符串或浮点

    $gmp_amount = gmp_init($amount);
    $verified = gmp_cmp($gmp_amount, gmp_init('99999999999999999'));

    // 类型混淆导致比较结果不可靠
    if ($verified > 0) {
        rejectTransaction();
    }
}

$json = '{"transaction_id": 99999999999999999999}';
processPayment($json);  // JSON 解析导致精度丢失
```

**危险模式7：Memcached/Redis 扩展的整型键转换**
```php
extension_loaded('memcached') or die('Memcached extension required');

function cacheLookup($user_id, $cache_key_prefix) {
    $memcached = new Memcached();
    $memcached->addServer('localhost', 11211);

    // user_id 是浮点或大整数
    $cache_key = $cache_key_prefix . (int)$user_id;  // 精度丢失

    $cached = $memcached->get($cache_key);
    if ($cached === false) {
        // 缓存未命中，重新计算
        $cached = computeExpensiveData($user_id);
        $memcached->set($cache_key, $cached);
    }

    return $cached;
}

// 浮点 user_id 被截断导致缓存密钥混乱
cacheLookup(12345.789, 'user_');
```

**危险模式8：FFI 扩展的 C 类型转换**
```php
extension_loaded('ffi') or die('FFI extension required');

function callCFunction($number) {
    $ffi = FFI::cdef('
        int process_number(long long num);
    ', 'mylib.so');

    // PHP 整数到 C long long 的转换可能溢出
    $result = $ffi->process_number((int)$number);  // 不安全转换

    return $result;
}

// PHP_INT_MAX 超出 C 类型范围导致溢出
callCFunction(9999999999999999);
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]**:
- `gmp_init()`, `gmp_intval()`, `gmp_strval()` - GMP 转换
- `bcadd()`, `bcmul()`, `bcdiv()`, `bcmod()` - BCMath 返回值处理
- `new Imagick()`, `resizeImage()`, `cropImage()` - 图片尺寸参数
- `openssl_pkey_new()`, `openssl_sign()` - 密钥长度、摘要长度
- `PDO::fetch()`, `mysqli_fetch_assoc()` - 数据库返回值
- `json_decode()` - 大整数解析
- `new Memcached()`, `new Redis()` - 缓存键操作
- `FFI::cdef()`, 结构体字段赋值 - C 类型转换

**快速定位保护机制 [L2-L3]**:
- 是否在转换前验证范围：`if (gmp_cmp($val, gmp_init(PHP_INT_MAX)) > 0)`
- 是否保持原始类型：GMP 对象始终为对象，不转整数
- 是否用 bccomp 比较：`bccomp($a, $b)` 而非整数比较
- 是否检查扩展返回类型：`gettype()`, `is_numeric()` 验证
- 是否在扩展操作后验证结果：`var_dump()`, 断言检查
- JSON 大整数处理：`JSON_BIGINT_AS_STRING` 选项是否使用
- 是否对外部数据进行类型声明：函数参数类型提示
- 数据库查询是否指定返回类型：`PDO::ATTR_EMULATE_PREPARES`

---

## Classify

**研判为真漏洞的特征：**

1. **无验证的跨扩展类型转换**：从 GMP 对象、BCMath 字符串、或数据库返回值直接转为 PHP 整数，未验证范围

2. **精度丢失导致安全决策**：浮点或大整数转整数后用于权限、金额、密钥长度等安全相关判断

3. **扩展返回值类型不确定**：直接使用 PDO/MySQLi 返回的数据库值作为类型敏感操作，不检查实际类型

4. **缓冲区溢出风险**：负数或超大整数转为无符号数用于 ImageMagick、FFI 等 C 函数的大小参数

5. **密钥/哈希参数的精度丢失**：浮点数用于 OpenSSL 密钥长度、摘要长度等参数

6. **跨模块类型混淆**：JSON 解析后的值直接传给 GMP/BCMath，或 GMP 结果直接用于数据库查询

**误报/代码异味的特征：**

- 类型转换前有完整验证：`if (is_int($val) && $val > 0 && $val < PHP_INT_MAX)`
- GMP/BCMath 值始终保持原始类型，不转换为 PHP 整数
- 转换结果用于展示/日志，未用于逻辑判断或安全决策
- 扩展操作有明确的返回类型检查：`if (is_int($result))`
- 使用 ORM 框架或类型提示声明参数类型
- 缓存键使用哈希函数而非直接类型转换

---

## Low risk

**以下场景可评为低风险：**

1. **完整的范围验证**
   - GMP 值与 PHP_INT_MAX 比较：`if (gmp_cmp($gmp_val, gmp_init(PHP_INT_MAX)) < 0) { $int_val = gmp_intval($gmp_val); }`
   - BCMath 值在转换前验证：`if (bccomp($bc_val, PHP_INT_MAX) < 0 && bccomp($bc_val, PHP_INT_MIN) > 0)`
   - 数据库返回值检查类型：`if (is_int($db_result) || is_numeric($db_result))`
   - 外部参数验证范围：`if ($value >= 0 && $value <= 4096)`

2. **安全的扩展使用模式**
   - 保持 GMP 对象类型：`$gmp_id = gmp_init($input)` 后始终用 GMP 函数，不转整数
   - BCMath 结果用字符串处理：`$sum = bcadd($a, $b)` 后保持为字符串
   - JSON 大整数作为字符串：`json_decode($json, true, 512, JSON_BIGINT_AS_STRING)`
   - 数据库查询参数化且结果类型检查

3. **类型声明和验证**
   - 函数参数有类型提示：`function process(int $width, int $height): void`
   - 启用严格类型：`declare(strict_types=1);`
   - 返回值验证：函数返回前 `assert(is_int($result))`

4. **扩展特定的安全实践**
   - ImageMagick 尺寸参数范围限制：`if ($width > 0 && $width <= 10000 && $height > 0 && $height <= 10000)`
   - OpenSSL 密钥长度为预定义值：`const RSA_KEY_LENGTH = 2048;`
   - Memcached/Redis 键使用哈希：`$key = hash('sha256', $user_id)`
   - FFI 结构体字段赋值前验证范围

5. **扩展操作的异常处理**
   - GMP 操作异常捕获：`try { $gmp_intval = gmp_intval($gmp); } catch (Exception $e) {}`
   - BCMath 错误检查：检查返回值是否为 false
   - JSON 解析验证：`if ($decoded === null && json_last_error() !== JSON_ERROR_NONE)`
   - 数据库查询异常处理：捕获 PDO 异常

6. **内部受控的扩展使用**
   - 扩展参数来自应用常量：`const MAX_IMAGE_WIDTH = 1920;`
   - GMP 值来自受信配置文件
   - 数据库查询结果由 ORM 框架验证
   - 缓存操作使用专用库而非原始扩展 API

