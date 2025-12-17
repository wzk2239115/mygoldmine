# PHP｜密码存储安全策略

## Details

### 漏洞成因
Web应用中用户密码的存储是认证系统的核心安全环节。PHP应用中，当使用弱哈希算法（MD5/SHA1）、不适当的哈希函数、缺少盐值（salt）、盐值重复或硬编码、迭代次数不足等错误策略时，密码数据库一旦泄露将面临大规模破解风险。现代密码存储应使用专门设计的慢哈希算法（如bcrypt、Argon2、PBKDF2）并配合适当的盐值策略。

### 代码示例

**易受攻击的代码 - 弱哈希算法：**
```php
// 极其危险的密码存储 - 无盐值MD5
$password = $_POST['password'];
$hash = md5($password); // 容易被彩虹表破解
$sql = "INSERT INTO users (username, password) VALUES ('$username', '$hash')";
```

**易受攻击的代码 - 通用但不安全的方法：**
```php
// 使用SHA256但缺少盐值和迭代
$password = $_POST['password'];
$hash = hash('sha256', $password); // 仍然容易被暴力破解

// 或者使用重复的全局盐值
$global_salt = 'hardcoded_salt_123'; // 硬编码盐值
$hash = hash('sha256', $global_salt . $password); // 盐值重复降低安全性
```

**易受攻击的代码 - 迭代次数不足：**
```php
// PBKDF2但迭代次数过少
$password = $_POST['password'];
$hash = hash_pbkdf2('sha256', $password, $salt, 1000, 64); // 1000次迭代过低
```

**安全示例 - 使用password_hash()：**
```php
// 推荐的密码哈希方法
$password = $_POST['password'];

// 使用bcrypt（默认算法）
$hash = password_hash($password, PASSWORD_DEFAULT);
// 结果示例：$2y$10$SomeSaltSomeHash...

// 存储到数据库
$sql = "INSERT INTO users (username, password_hash) VALUES (?, ?)";
$stmt = $pdo->prepare($sql);
$stmt->execute([$username, $hash]);

// 验证密码
if (password_verify($password, $stored_hash)) {
    // 密码正确
    if (password_needs_rehash($stored_hash, PASSWORD_DEFAULT)) {
        // 重新哈希以使用更新的算法/参数
        $new_hash = password_hash($password, PASSWORD_DEFAULT);
        // 更新数据库中的哈希值
        updateUserPasswordHash($user_id, $new_hash);
    }
}
```

**安全示例 - 自定义bcrypt参数：**
```php
// 自定义bcrypt参数（更严格的安全要求）
$password = $_POST['password'];

$options = [
    'cost' => 12, // 增加计算成本（默认10）
];

$hash = password_hash($password, PASSWORD_BCRYPT, $options);

// 验证时自动处理参数
if (password_verify($password, $stored_hash)) {
    // 验证成功
}
```

**安全示例 - 使用Argon2id（PHP 7.2+）：**
```php
// 使用Argon2id（现代推荐算法）
$password = $_POST['password'];

$options = [
    'memory_cost' => 1<<17,    // 128 MB
    'time_cost'   => 4,        // 迭代次数
    'threads'     => 4,        // 线程数
];

$hash = password_hash($password, PASSWORD_ARGON2ID, $options);

// 验证和重新哈希检查
if (password_verify($password, $stored_hash)) {
    if (password_needs_rehash($stored_hash, PASSWORD_ARGON2ID, $options)) {
        $new_hash = password_hash($password, PASSWORD_ARGON2ID, $options);
        // 更新数据库
    }
}
```

**安全示例 - 使用PBKDF2（兼容性要求）：**
```php
// PBKDF2实现（需要兼容性时）
$password = $_POST['password'];
$salt = random_bytes(32); // 每个用户独立的随机盐值
$iterations = 100000; // 足够高的迭代次数
$length = 64; // 输出长度

$hash = hash_pbkdf2('sha256', $password, $salt, $iterations, $length);

// 存储格式：algorithm:iterations:salt:hash
$stored_format = "pbkdf2_sha256:$iterations:" . bin2hex($salt) . ":$hash";

// 验证函数
function verifyPassword($password, $stored_format) {
    list($algo, $iterations, $salt, $hash) = explode(':', $stored_format);
    $calculated_hash = hash_pbkdf2('sha256', $password, hex2bin($salt), (int)$iterations, 64);
    return hash_equals($hash, $calculated_hash);
}
```

**安全示例 - Laravel框架集成：**
```php
// Laravel中的密码哈希（自动使用最佳算法）
use Illuminate\Support\Facades\Hash;

// 创建用户时哈希密码
$user = new User();
$user->password = Hash::make($request->password);
$user->save();

// 验证密码
if (Hash::check($request->password, $user->password)) {
    // 密码正确
    
    if (Hash::needsRehash($user->password)) {
        // 重新哈希以使用更新的算法
        $user->password = Hash::make($request->password);
        $user->save();
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 密码哈希：`password_hash`, `md5`, `sha1`, `hash`, `crypt`
- 验证函数：`password_verify`, `hash_equals`, `md5()`
- 哈希算法：`PASSWORD_DEFAULT`, `PASSWORD_BCRYPT`, `PASSWORD_ARGON2ID`

**定位步骤：**
1. 搜索项目中所有密码处理逻辑
2. 检查使用的哈希算法和函数
3. 验证盐值生成策略
4. 检查迭代次数配置

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **现代算法：** `password_hash()` 或 Argon2/bcrypt
- **适当成本：** 算法参数配置（cost/iterations）
- **重新哈希：** `password_needs_rehash()` 检查
- **安全比较：** `hash_equals()` 或 `password_verify()`

**定位技巧：**
- 检查是否使用`password_hash()`而非通用哈希函数
- 验证算法参数是否适当（bcrypt cost >= 10）
- 确认是否存在重新哈希机制
- 检查是否使用常量时间比较

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| password_hash()+Argon2/bcrypt | **L0（快速跳过）** | 现代安全实现 |
| password_hash()+适当参数 | **L2（跳读）** | 基本安全，需验证参数 |
| 使用过时算法但正确实现 | **L3（逐行读）** | 需要升级算法 |
| 使用MD5/SHA1或缺少盐值 | **L4（跨模块追踪）** | 严重安全缺陷 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 使用MD5、SHA1或其他快速哈希算法
2. 缺少盐值或使用重复的全局盐值
3. 迭代次数过低（bcrypt cost < 10, PBKDF2 < 10000）
4. 使用不适当的哈希算法（如通用SHA256而非专用密码哈希）

#### 误报
以下情景可判定为误报：
1. 使用`password_hash()`配合PASSWORD_DEFAULT/ARGON2ID/BCRYPT
2. 适当的算法参数（bcrypt cost >= 10, Argon2现代参数）
3. 实现重新哈希检查机制
4. 使用专用密码哈希库

#### 代码异味
需记录的风险：
1. 硬编码的盐值或全局盐值
2. 不一致的哈希策略（不同部分使用不同算法）
3. 缺少重新哈希机制
4. 自定义加密实现

## Low risk

### 低风险评级场景

#### 1. 遗留系统兼容性
- **场景：** 为兼容旧系统暂时保留传统哈希
- **风险评估：** 需要迁移计划，风险可控

#### 2. 分阶段算法升级
- **场景：** 逐步升级到现代算法
- **风险评估：** 合理的实施策略，需跟踪进度

#### 3. 专用硬件支持
- **场景：** 使用硬件安全模块(HSM)或专用芯片
- **风险评估：** 专业实现通常安全可靠

### 密码存储安全检查表

| 检查项 | 安全要求 | 风险等级 | 检测方法 |
|--------|----------|----------|----------|
| 哈希算法 | password_hash() | 高 | 算法识别 |
| 算法参数 | 适当成本参数 | 中 | 参数检查 |
| 盐值策略 | 每个密码独立随机 | 高 | 盐值分析 |
| 重新哈希 | needs_rehash检查 | 中 | 代码逻辑检查 |

### 常见哈希算法对比

| 算法 | 安全性 | 适用场景 | 检测要点 |
|------|--------|----------|----------|
| Argon2id | ⭐⭐⭐⭐⭐ | 现代应用 | PHP 7.2+ |
| bcrypt | ⭐⭐⭐⭐ | 通用场景 | 成本参数>=10 |
| PBKDF2 | ⭐⭐⭐ | 兼容性需求 | 迭代>=10000 |
| SHA-256 | ⭐ | 仅数据完整性 | 不适合密码 |
| MD5/SHA1 | ⭐ | 已淘汰 | 立即升级 |

### 算法参数建议

| 算法 | 参数 | 建议值 | 说明 |
|------|------|--------|------|
| bcrypt | cost | 10-12 | 平衡安全性和性能 |
| Argon2id | memory_cost | 1<<17 (128MB) | 内存硬度 |
| Argon2id | time_cost | 4 | 时间成本 |
| Argon2id | threads | 4 | 并行度 |
| PBKDF2 | iterations | 10000+ | 迭代次数 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| password_hash()使用 | 现代安全API | 高 |
| Argon2id算法 | 最先进算法 | 高 |
| 适当成本参数 | 平衡安全性能 | 高 |
| 重新哈希机制 | 前向兼容性 | 中 |