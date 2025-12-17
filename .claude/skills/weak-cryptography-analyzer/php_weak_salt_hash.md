# PHP 弱盐值/固定盐值密码哈希审计

## Details

### 典型代码特征
```php
// 场景1: 固定盐值密码哈希
define('PASSWORD_SALT', 'mysecretkey123');
$hashedPassword = md5($password . PASSWORD_SALT);
$user->password = $hashedPassword;

// 场景2: 空盐值或简单盐值
$salt = "salt";
$hashedPassword = hash('sha256', $password . $salt);

// 场景3: 用户名作为盐值（可枚举）
$hashedPassword = md5($username . $password);
if ($hashedPassword === $storedHash) { /* 认证 */ }

// 场景4: 时间戳盐值（可预测）
$salt = date('Y-m-d');
$hashedPassword = hash('sha1', $salt . $password);

// 场景5: 全局配置盐值
// config.php: $config['salt'] = 'app_secret_2023';
$hashedPassword = sha1($config['salt'] . $password);

// 场景6: 数据库ID作为盐值（顺序可测）
$salt = $user->id;
$hashedPassword = hash('sha256', $password . $salt);

// 场景7: 短盐值（熵不足）
$salt = substr(uniqid(), 0, 4);  // 仅4字符
$hashedPassword = hash('sha512', $password . $salt);

// 场景8: crypt() 固定盐值
$hashedPassword = crypt($password, '$6$fixedsalt$');

// 场景9: hash_hmac 弱密钥
$key = 'hardcoded_key';
$hash = hash_hmac('sha256', $password, $key);

// 场景10: 盐值复用
$globalSalt = getenv('APP_SALT') ?: 'default_salt';
foreach ($users as $user) {
    $user->password = hash('sha256', $user->password . $globalSalt);
}

// 场景11: Base64编码后作为盐值
$salt = base64_encode('fixed_string');
$hashedPassword = hash('sha256', $password . $salt);

// 场景12: 用户可控数据作为盐值
$salt = $_GET['email'];  // 攻击者可控
$hashedPassword = md5($password . $salt);
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "md5.*PASSWORD\|sha1.*PASSWORD" --include="*.php"
grep -rn "hash.*password.*['\"]" --include="*.php"
grep -rn "define.*SALT\|\\$salt\s*=" --include="*.php"
grep -rn "crypt(.*,\s*['\"]" --include="*.php"
grep -rn "hash_hmac.*['\"][^'\"]*['\"]" --include="*.php"
grep -rn "PASSWORD_SALT\|GLOBAL_SALT" --include="*.php"
```

**高危API模式（L2 跳读）：**
- `md5($password . CONSTANT)` / `sha1($password . $config['salt'])`
- `hash('sha256', $password . $username)` 用户名/ID作为盐值
- `crypt($password, '$2a$04$固定字符串$')` 固定盐值
- `hash_hmac('sha256', $data, '硬编码密钥')`
- `define('SALT', '...')` 配置文件中盐值常量
- `$salt = 'salt'` / `$salt = 'abc123'` 简单字符串字面量
- 盐值长度 < 16字节：`substr(uniqid(), 0, 8)`
- 盐值来源：`$_GET` / `$_POST` / `$_COOKIE` 用户可控
- 时间函数作为盐：`date()` / `time()` / `strtotime()`
- 全局变量盐值：`$GLOBALS['app_salt']` / `getenv('SALT')`
- 数据库字段盐值：`user_id` / `created_at` 可预测字段

**函数调用链追踪（L3 逐行）：**
- 注册逻辑：`registerUser()` → 密码哈希处理 → 盐值来源检查
- 配置文件：`config.php` / `.env` / `constants.php` 中 `SALT` / `SECRET` 定义
- 盐值生成函数：`generateSalt()` / `getSalt()` 实现是否随机
- 数据库Schema：`password VARCHAR(32)` MD5长度 / `salt VARCHAR(8)` 过短
- ORM模型：Laravel Model `$hidden` / `setPasswordAttribute()` 哈希逻辑
- 认证逻辑：`authenticate()` 中 `hash($input . SALT) === $stored`
- 迁移脚本：`migrations/` 中盐值字段定义和默认值
- 工具类：`HashUtil::hash()` / `SecurityHelper::encrypt()` 实现
- 框架配置：Laravel `config/hashing.php` / Symfony `security.yaml`
- 历史代码：Git blame 检查盐值定义时间和修改记录

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 盐值为字符串字面量：`'salt'` / `'mysecret'`
- `define()` / `const` 定义的全局盐值常量
- 空盐值：`hash('sha256', $password . '')`
- 单一盐值用于所有用户：无 `users.salt` 字段
- 盐值长度 < 128位（16字节）
- 未使用 `password_hash()` / `password_verify()`
- 配置文件注释 "TODO: change salt in production"

**伪保护识别（L3 逐行）：**
```php
// 盐值虽随机但过短
$salt = bin2hex(random_bytes(4));  // 仅8字符hex（4字节熵）
$hash = hash('sha256', $password . $salt);

// 盐值基于可预测数据
$salt = md5($username . 'fixed_suffix');  // 用户名可枚举
$hash = hash('sha512', $password . $salt);

// 每个用户独立盐值但来源弱
$salt = substr($user->email, 0, 10);  // 邮箱前缀易猜测
$hash = hash('sha256', $salt . $password);

// 盐值存储但生成逻辑弱
$user->salt = uniqid();  // uniqid() 基于时间可预测
$user->password = md5($password . $user->salt);

// 加盐但哈希算法弱
$salt = bin2hex(random_bytes(16));  // 盐值安全
$hash = md5($password . $salt);  // MD5仍易暴力破解

// 时间相关盐值
$salt = date('Ymd') . $user->id;  // 日期+ID组合可枚举
$hash = hash('sha256', $password . $salt);

// 环境变量盐值（所有用户共享）
$salt = getenv('APP_SECRET');  // 单一全局盐值
$hash = hash('sha256', $password . $salt);

// 配置降级逻辑
if (function_exists('random_bytes')) {
    $salt = bin2hex(random_bytes(16));
} else {
    $salt = 'fallback_salt';  // 危险降级
}

// 盐值拼接位置固定
$hash = hash('sha256', $password . $salt);  // 攻击者可预构建彩虹表

// 数据库默认值
// CREATE TABLE users (salt VARCHAR(32) DEFAULT 'default_salt')
INSERT INTO users (username, password, salt) VALUES (?, ?, DEFAULT);
```

**跨模块保护追踪（L4）：**
- Laravel：`config/hashing.php` 驱动配置是否 `bcrypt` / `argon2`
- Symfony：`security.yaml` 中 `encoders` 算法和盐值策略
- WordPress：`wp-config.php` 中 `AUTH_KEY` / `SECURE_AUTH_SALT` 配置
- Drupal：`settings.php` 中 `$settings['hash_salt']` 检查
- 数据库审计：`users` 表 `salt` 字段 NULL/重复值统计
- ORM拦截器：Eloquent `saving` 事件 / Doctrine `prePersist` 监听器
- 中间件：认证中间件 `AuthMiddleware` 密码验证逻辑
- Composer依赖：`composer.json` 是否引入 `paragonie/password_lock`
- 环境配置：`.env` / `.env.example` 中盐值注释和示例值
- Docker镜像：`Dockerfile` ENV 硬编码盐值检查
- CI/CD配置：Jenkins/GitLab CI 环境变量盐值轮转策略
- 日志审计：应用日志中 "using salt" / "default salt" 警告信息
- 代码扫描：RIPS / Psalm / PHPStan 静态分析规则

## Classify

**确认漏洞：**
- 用户密码存储使用固定盐值（所有用户共享）
- 盐值为硬编码字符串常量：`define('SALT', 'xxx')`
- 盐值来源可预测：用户名/ID/时间戳/邮箱
- 盐值长度不足（< 16字节）或熵过低
- 用户可控数据作为盐值：`$_GET` / `$_POST` 参数
- API签名验证使用弱盐值 HMAC
- 会话令牌/CSRF Token 盐值固定
- 密码重置令牌基于可预测盐值
- 配置文件示例盐值未在生产环境修改
- 数据库 `salt` 字段存在重复值或 NULL
- 多租户系统租户间共享盐值

**研判误报：**
- 测试代码：`tests/` 目录中Mock哈希逻辑
- 示例文档：README / 教程中演示代码
- 已废弃功能：代码注释标注 `@deprecated` 且路由已移除
- 历史数据兼容：仅读取旧哈希，新注册用 `password_hash()`
- 非密码场景：缓存键生成 / API幂等性校验（短期Token）
- 开发环境：`APP_ENV=local` 配置明确标注非生产
- 注释代码：`//` 或 `/* */` 包裹的未执行逻辑
- 第三方库内部：Vendor目录代码非项目控制

**代码异味：**
- 注释 "TODO: use password_hash()" 但仍生产运行
- 配置可选但默认弱盐值：`$salt = $config['salt'] ?? 'default'`
- 新旧用户分别处理：老用户弱盐值无统一升级计划
- 环境变量 fallback：`SALT=getenv('SALT') ?: 'fallback'`
- 文档声称"加盐哈希"实际盐值固定
- 盐值生成函数返回常量：`function getSalt() { return 'salt'; }`
- 混合策略：管理员 bcrypt，普通用户 md5+固定盐
- 性能理由：注释 "password_hash too slow"
- 前端传递盐值：AJAX请求中 `{password, salt}` 参数

**关键判断点：**
1. 盐值唯一性：每个用户独立 vs 全局共享
2. 盐值熵源：`random_bytes()` vs 固定字符串/时间/用户属性
3. 盐值长度：>= 16字节 vs < 16字节
4. 盐值存储：数据库独立字段 vs 配置文件常量
5. 哈希算法：`password_hash()` vs `md5()` / `sha1()` / `hash()`
6. 可预测性：攻击者是否可枚举/猜测盐值
7. 用户可控：盐值来源是否涉及 `$_GET` / `$_POST` / `$_COOKIE`

## Low risk

**可接受的低风险场景：**
- 开发环境快速原型（`APP_ENV=development`）
- 单元测试固定盐值（便于断言结果一致性）
- 历史数据只读迁移脚本（一次性转换旧哈希）
- 内部工具账户（无外网暴露 + IP白名单）
- 短期临时令牌（< 5分钟 + 单次使用 + 强随机前缀）
- 缓存键哈希（非认证凭证，碰撞仅影响性能）

**降级条件：**
- 数据已公开或低敏感度（非PII/PCI DSS数据）
- 明确迁移时间表（看板记录 + Sprint规划）
- 外层多因素认证（短信验证码 + 硬件Token）
- 网络严格隔离（内网专线 + VPN + 证书认证）
- 攻击窗口极短（临时令牌 < 30秒 + 速率限制 100ms延迟）
- 仅向后兼容读取，新写入用 `password_hash(PASSWORD_ARGON2ID)`
- 已有监控告警（异常登录尝试 + WAF规则）
- 用户基数极小（< 100内部员工 + 定期密码轮转）

**注意：** 固定盐值本质上等同于无盐值，攻击者可针对该盐值预构建彩虹表批量破解。弱盐值（如用户名/ID）可通过用户枚举逐个生成字典。PHP 5.5+ 提供 `password_hash()` 默认使用 BCrypt + 自动随机盐值（每用户独立），应优先使用。盐值长度应 >= 128位，使用 `random_bytes(16)` 生成。OWASP 推荐密码哈希迭代次数：PBKDF2-SHA256 >= 600,000 次，BCrypt cost >= 12，Argon2id 按OWASP配置。固定盐值违反 PCI DSS 8.2.1、GDPR 安全原则、等保2.0 三级要求。低风险评级不代表长期可接受，需明确技术债务清理计划。
