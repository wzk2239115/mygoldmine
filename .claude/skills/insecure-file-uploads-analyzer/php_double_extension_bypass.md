# PHP｜双写绕过漏洞

## Details

### 漏洞成因
PHP文件上传验证中，当使用`str_replace`或`str_ireplace`等函数进行简单的字符串替换来过滤危险扩展名时，如果未考虑替换后的结果可能重新组合成危险扩展名，就会产生双写绕过漏洞。攻击者可以通过构造特殊的文件名（如`shell.pphphp`），当过滤函数将中间的`php`替换为空字符串后，剩下的部分重新组合成`shell.php`，从而绕过黑名单验证。这种漏洞的根本原因在于字符串替换操作的非原子性和过滤逻辑的不完整性。

### 代码示例

**易受攻击的代码 - 简单str_replace：**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $filename = $_FILES['upload']['name'];
    
    // 危险：简单的字符串替换
    $filename = str_ireplace('.php', '', $filename);
    $filename = str_ireplace('.asp', '', $filename);
    $filename = str_ireplace('.jsp', '', $filename);
    
    // 双写绕过：shell.pphphp -> 经过str_ireplace后变成shell.php
    $target_file = __DIR__ . '/uploads/' . $filename;
    move_uploaded_file($_FILES['upload']['tmp_name'], $target_file);
}
```

**易受攻击的代码 - 多次替换：**
```php
$filename = $_FILES['upload']['name'];

// 多次替换，每次处理不同的扩展名
$dangerous_extensions = ['.php', '.php3', '.php4', '.php5', '.phtml'];
foreach ($dangerous_extensions as $ext) {
    $filename = str_ireplace($ext, '', $filename);
}

// 双写组合：shell.pphpphp4 -> 经过循环替换后可能变成shell.php
$upload_path = 'uploads/' . $filename;
move_uploaded_file($_FILES['upload']['tmp_name'], $upload_path);
```

**易受攻击的代码 - 递归替换问题：**
```php
function sanitize_filename($filename) {
    $dangerous = ['.php', '.asp', '.jsp', '.phtml'];
    
    // 递归替换直到没有匹配
    foreach ($dangerous as $ext) {
        while (stripos($filename, $ext) !== false) {
            $filename = str_ireplace($ext, '', $filename);
        }
    }
    
    return $filename;
}

$filename = sanitize_filename($_FILES['upload']['name']);

// 复杂的双写：shell.pphphpp -> 可能绕过递归检测
move_uploaded_file($_FILES['upload']['tmp_name'], 'uploads/' . $filename);
```

**攻击示例 - 构造双写文件名：**
```php
// 测试双写绕过
$test_cases = [
    'shell.pphphp',      // 基本双写
    'shell.pphpphp',     // 重叠双写
    'shell.phpphp',      // 连续双写
    'shell.pphphpp',     // 扩展双写
    'shell.pphpphp3',    // 组合双写
    'test.pphphppphphp', // 复杂双写
];

foreach ($test_cases as $filename) {
    echo "Original: $filename\n";
    
    // 模拟不安全的过滤
    $filtered = str_ireplace('.php', '', $filename);
    echo "Filtered: $filtered\n";
    
    // 检查结果是否仍然危险
    if (stripos($filtered, '.php') !== false) {
        echo "RESULT: Still contains .php - BYPASS SUCCESS!\n";
    } else {
        echo "RESULT: Clean - No bypass\n";
    }
    echo "---\n";
}
```

**安全示例 - 白名单验证：**
```php
$file = $_FILES['upload'];
$filename = $file['name'];

// 1. 提取扩展名（安全方式）
$ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));

// 2. 白名单验证（推荐）
$allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx'];
if (!in_array($ext, $allowed_extensions)) {
    die('File type not allowed');
}

// 3. 多重验证
$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime_type = finfo_file($finfo, $file['tmp_name']);
finfo_close($finfo);

$allowed_mimes = [
    'jpg' => 'image/jpeg',
    'jpeg' => 'image/jpeg', 
    'png' => 'image/png',
    'gif' => 'image/gif',
    'pdf' => 'application/pdf'
];

if (!isset($allowed_mimes[$ext]) || $allowed_mimes[$ext] !== $mime_type) {
    die('MIME type does not match extension');
}

// 4. 使用随机文件名
$new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $new_filename);
```

**安全示例 - 严格的黑名单验证：**
```php
function validate_extension($filename) {
    // 提取扩展名
    $ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
    
    // 危险扩展名黑名单
    $dangerous_extensions = [
        'php', 'php3', 'php4', 'php5', 'phtml', 'phps',
        'asp', 'aspx', 'jsp', 'jspx', 'sh', 'bash',
        'exe', 'com', 'scr', 'bat', 'cmd'
    ];
    
    // 精确匹配（非字符串替换）
    if (in_array($ext, $dangerous_extensions)) {
        return false;
    }
    
    return true;
}

function sanitize_filename($filename) {
    // 不允许连续的点号
    if (strpos($filename, '..') !== false) {
        return false;
    }
    
    // 不允许空格和特殊字符
    if (preg_match('/[<>:\\|\?\*]/', $filename)) {
        return false;
    }
    
    // 去除首尾的点号和空格
    $filename = trim($filename, " \t\n\r\0\x0B.");
    
    return $filename;
}

$file = $_FILES['upload'];
$filename = $file['name'];

// 验证扩展名
if (!validate_extension($filename)) {
    die('Dangerous file type detected');
}

// 净化文件名
$clean_filename = sanitize_filename($filename);
if ($clean_filename === false) {
    die('Invalid filename');
}

// 使用随机文件名避免其他问题
$ext = pathinfo($clean_filename, PATHINFO_EXTENSION);
$new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $new_filename);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 字符串替换：`str_replace`, `str_ireplace`, `preg_replace`
- 扩展名处理：`pathinfo`, `explode`, `substr`, `strrchr`
- 循环处理：`foreach`, `while`, `for`

**定位步骤：**
1. 搜索上传处理逻辑，检查字符串替换函数的使用
2. 确认是否存在循环替换或多次替换操作
3. 验证是否使用安全的扩展名提取方法

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单机制：** 只允许特定的安全扩展名
- **精确匹配：** 使用`in_array`而非字符串替换
- **pathinfo提取：** 使用安全的扩展名提取方法
- **多重验证：** 结合MIME类型等其他验证手段

**定位技巧：**
- 检查是否使用`pathinfo($file, PATHINFO_EXTENSION)`提取扩展名
- 确认是否使用`in_array`进行白名单或黑名单验证
- 验证是否存在多层验证机制

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单+pathinfo+多重验证 | **L0（快速跳过）** | 风险低 |
| 有黑名单但使用in_array | **L2（跳读）** | 需验证其他防护 |
| 使用str_replace过滤 | **L3（逐行读）** | 高风险 |
| 复杂的字符串处理逻辑 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 使用`str_replace`或`str_ireplace`进行字符串替换过滤
2. 未考虑替换后可能重新组合成危险扩展名
3. 未使用白名单机制或精确匹配验证
4. 过滤后的文件仍可被识别为危险类型

#### 误报
以下情景可判定为误报：
1. 使用白名单机制和`in_array`精确验证
2. 使用`pathinfo`安全提取扩展名
3. 结合MIME类型等多重验证手段
4. 使用随机文件名避免预测

#### 代码异味
需记录的风险：
1. 仅依赖字符串替换进行过滤
2. 存在循环替换或多次替换操作
3. 未使用安全的扩展名提取方法
4. 验证逻辑过于简单，未考虑绕过可能性

## Low risk

### 低风险评级场景

#### 1. 白名单验证
- **场景：** 只允许特定的安全扩展名
- **风险评估：** 可有效防止任何类型的绕过

#### 2. 精确匹配验证
- **场景：** 使用`in_array`进行精确的扩展名匹配
- **风险评估：** 避免字符串替换带来的问题

#### 3. 多重验证机制
- **场景：** 结合扩展名、MIME类型、文件内容等多重验证
- **风险评估：** 提高绕过难度，降低风险

### 双写绕过模式分析

| 绕过模式 | 示例 | 过滤结果 | 绕过结果 |
|----------|------|----------|----------|
| 基本双写 | `shell.pphphp` | `shell.php` | 成功 |
| 重叠双写 | `shell.pphpphp` | `shell.pphp` | 部分 |
| 连续双写 | `shell.phpphp` | `shell.php` | 成功 |
| 扩展双写 | `shell.pphphpp` | `shell.php` | 成功 |
| 组合双写 | `shell.pphpphp3` | `shell.php` | 成功 |

### 常见绕过技术总结

| 绕过技术 | 目标函数 | 检测方法 | 防护建议 |
|----------|----------|----------|----------|
| 双写绕过 | str_replace | 代码审计 | 使用白名单 |
| 重叠绕过 | 多次替换 | 逻辑分析 | 精确匹配 |
| 递归绕过 | while循环 | 时序分析 | 限制循环 |
| 组合绕过 | 多种扩展名 | 模式匹配 | 统一验证 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 白名单机制 | 消除绕过可能性 | 高 |
| 精确匹配验证 | 避免字符串问题 | 高 |
| 多重验证机制 | 提高安全性 | 中 |
| 随机文件命名 | 增加预测难度 | 中 |