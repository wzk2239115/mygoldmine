# PHP MD5 密码哈希审计

## Details

### 典型代码特征
```php
// 直接使用 md5() 函数哈希密码
$hashedPassword = md5($password);
$sql = "INSERT INTO users (password) VALUES ('$hashedPassword')";

// 密码验证
if (md5($inputPassword) === $storedHash) {
    // 登录成功
}

// 加盐但仍用 MD5
$salt = "static_salt_123";
$hash = md5($password . $salt);
$hash = md5($salt . $password . $salt);  // 多重拼接仍无效

// 动态盐仍用 MD5
$salt = uniqid();
$hash = md5($password . $salt);
mysqli_query($conn, "INSERT INTO users (password, salt) VALUES ('$hash', '$salt')");

// 多轮迭代 MD5
$hash = $password;
for ($i = 0; $i < 1000; $i++) {
    $hash = md5($hash);  // 迭代不能弥补算法弱点
}

// Laravel 旧版 Hash Facade 配置 MD5
'driver' => 'md5',  // config/hashing.php
Hash::make($password);  // 底层调用 md5()

// CodeIgniter 旧版密码库
$this->encryption->hash($password, 'md5');

// WordPress 旧版密码（wp_hash_password）
$hash = md5($password);  // 旧插件实现

// 自定义加密类
class Security {
    public static function hashPassword($pwd) {
        return md5($pwd . SALT_CONSTANT);  // 包装 MD5
    }
    
    public static function encrypt($data) {
        return md5($data);  // 误称为加密
    }
}

// Cookie/Session 加密
$sessionId = md5(uniqid() . $_SERVER['REMOTE_ADDR']);
setcookie('token', md5($userId . SECRET_KEY), time() + 3600);

// API 签名验证
$signature = md5($params . $timestamp . $apiSecret);
if ($signature !== $_GET['sign']) {
    die('Invalid signature');
}

// ThinkPHP 旧版
$User->password = md5($_POST['password']);
$User->save();

// Yii 框架手动实现
public function validatePassword($password) {
    return md5($password) === $this->password_hash;
}

// PDO 预处理仍用 MD5
$stmt = $pdo->prepare("SELECT * FROM users WHERE password = :pwd");
$stmt->execute(['pwd' => md5($password)]);

// 数据库触发器/存储过程
-- CREATE TRIGGER before_user_insert
-- BEFORE INSERT ON users FOR EACH ROW
-- SET NEW.password = MD5(NEW.password);

// sha1() 同样不安全
$hash = sha1($password);
$hash = sha1(md5($password));  // 组合仍弱

// crypt() 使用 CRYPT_MD5
$hash = crypt($password, '$1$' . $salt . '$');  // $1$ 表示 MD5

// hash() 函数指定 md5
$hash = hash('md5', $password);
$hash = hash('sha1', $password);

// password_hash() 误配置
define('PASSWORD_DEFAULT', PASSWORD_MD5);  // 不存在此常量，误用
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "md5\s*(" --include="*.php"
grep -rn "sha1\s*(" --include="*.php"
grep -rn "hash\s*(\s*['\"]md5" --include="*.php"
grep -rn "hash\s*(\s*['\"]sha1" --include="*.php"
grep -rn "crypt\s*(\s*.*\s*,\s*['\"]\\$1\\$" --include="*.php"
grep -rn "'driver'\s*=>\s*'md5'" --include="*.php"
grep -rn "PASSWORD_MD5\|PASSWORD_SHA1" --include="*.php"
grep -rn "MD5\(" --include="*.sql"  # 数据库脚本
```

**高危 API 模式（L2 跳读）：**
- `md5($password)` / `md5($_POST['password'])`
- `sha1($password)` / `sha1($input['pwd'])`
- `hash('md5', $data)` / `hash('sha1', $data)`
- `crypt($password, '$1$...')` MD5 基础的 crypt
- `Hash::make()` 配置 `driver=md5` 的 Laravel
- `$this->encryption->hash($pwd, 'md5')` CodeIgniter
- `Yii::$app->security->hashPassword()` 底层检查
- `password_verify()` 对应存储用 MD5（检查数据库字段长度 32）
- `openssl_digest($data, 'md5')` OpenSSL MD5
- 魔数：32 字符十六进制字符串（MD5）/ 40 字符（SHA-1）
- 数据库字段定义：`password VARCHAR(32)` / `CHAR(32)`
- 配置项：`ENCRYPTION_METHOD=md5` / `HASH_ALGO='MD5'`

**函数调用链追踪（L3 逐行）：**
- 定位 `md5()` 参数来源：`$_POST` / `$_GET` / `$_REQUEST` / `$request->input()`
- 配置文件：`.env` 中 `HASH_DRIVER=md5` / `config.php` 设置
- 框架 Model：`User::create(['password' => md5(...)])` 
- ORM 事件：Laravel `creating` / `updating` 事件监听器
- 中间件：认证中间件 `AuthMiddleware::handle()` 密码处理
- Service 层：`AuthService::register()` / `UserService::updatePassword()`
- Helper 函数：`app/Helpers/security.php` 中自定义函数
- 数据库迁移：`Schema::table()` 中字段长度暗示（32=MD5）
- API 控制器：`LoginController::authenticate()` 密码比对
- 第三方包：Composer 依赖中过时认证库
- 全局函数：`functions.php` / `common.php` 中工具函数
- 会话管理：`SessionHandler::write()` 会话 ID 生成
- 缓存键生成：`Cache::put(md5($key), ...)` 是否用于安全目的
- 遗留数据库：`legacy_users` 表结构分析

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 密码直接哈希：`md5($password)` 无 salt 参数
- 单次哈希无迭代：无 `password_hash()` / `bcrypt` / `argon2`
- 硬编码算法：代码中固定 `md5()` 调用
- 静态盐：`define('SALT', 'fixed_salt')` 全站共用
- 时序攻击：`$hash1 == $hash2` 或 `===` 直接比较（应用 `hash_equals()`）
- 配置默认 MD5：框架配置文件无安全算法
- 数据库字段长度 32：暗示 MD5 存储格式

**伪保护识别（L3 逐行）：**
```php
// 加盐但仍用 MD5（GPU 暴力破解仍有效）
$salt = bin2hex(random_bytes(16));
$hash = md5($password . $salt);  // 彩虹表可预计算

// 多轮迭代不足（应 >= 10000 轮且用 bcrypt）
$hash = $password;
for ($i = 0; $i < 100; $i++) {
    $hash = md5($hash);  // 迭代不改变算法弱点
}

// HMAC-MD5 仍是弱算法
$hmac = hash_hmac('md5', $password, $key);  // HMAC 无法修复 MD5 碰撞

// SHA-1 作为"升级"（已实现碰撞攻击）
$hash = sha1($password);  // 2017 年 SHAttered 攻击

// 误认为 Base64 增强安全
$hash = base64_encode(md5($password, true));  // 编码≠加密

// MD5 组合仍弱
$hash = md5(sha1($password));  // 组合不能弥补单个算法弱点
$hash = sha1(md5($password));

// 配置降级逻辑
if (function_exists('password_hash')) {
    $hash = password_hash($password, PASSWORD_BCRYPT);
} else {
    $hash = md5($password);  // 危险降级
}

// 多层包装但底层 MD5
class SecureHash {
    public static function hash($input) {
        return self::internalHash($input);
    }
    
    private static function internalHash($data) {
        return md5($data);  // 名不副实
    }
}

// 加密混淆但仍用 MD5
$hash = md5(strrev($password) . SALT);  // 反转不增加安全性
$hash = md5(base64_decode($password));  // 无意义变换

// 条件分支仍有 MD5 路径
$hash = ($newUser) ? password_hash($password, PASSWORD_BCRYPT) 
                    : md5($password);  // 旧用户仍用 MD5
```

**跨模块保护追踪（L4）：**
- Laravel：`config/hashing.php` 驱动配置 / `HashServiceProvider`
- Symfony：`security.yaml` 编码器配置 / `PasswordEncoderInterface`
- WordPress：`wp-includes/pluggable.php` 中 `wp_hash_password()` 实现
- Drupal：`user.module` / `PasswordInterface` 实现类
- Magento：`Mage::helper('core')->getHash()` 底层检查
- Composer 依赖：`composer.lock` 中过时认证包版本
- 数据库审计：存储过程 / 触发器 / 函数中 `MD5()` 调用
- Nginx/Apache 配置：`auth_basic` 文件生成方式
- Docker 镜像：`php:7.2` 等旧版本默认配置
- CI/CD：Jenkins/GitLab CI 环境变量 `HASH_METHOD`
- 静态分析：PHPStan / Psalm 规则启用状态
- 微服务通信：gRPC / REST API 签名算法
- 消息队列：RabbitMQ / Kafka 消息签名验证
- 缓存层：Redis Session Handler 令牌生成
- CDN 配置：CloudFlare / Akamai 边缘认证
- 日志系统：ELK 中 `password` 字段模式（32 位十六进制）

## Classify

**确认漏洞：**
- 用户密码存储使用 MD5/SHA-1（无论是否加盐）
- 管理员/特权账户密码用 MD5 哈希
- API 令牌/访问密钥生成使用 MD5
- JWT/JWS 签名使用 MD5 / HMAC-MD5
- 会话令牌/CSRF Token 用 MD5 生成
- OAuth 授权码/刷新令牌使用 MD5
- 支付签名验证（支付宝/微信支付接口）使用 MD5
- 数据库敏感字段哈希（身份证/银行卡索引）
- 找回密码令牌/邮箱验证码用 MD5
- 双因素认证 TOTP 密钥派生用 MD5
- 文件上传校验用于防篡改场景
- 签名证书指纹计算（SSL 证书验证）
- 生产环境强制 MD5 无替代方案

**研判误报：**
- 单元测试文件（`tests/` / `test_*.php` / `*Test.php`）
- PHPUnit Mock 对象 / 测试夹具
- 注释代码 / 示例代码 / 文档说明
- 已废弃函数明确标注 `@deprecated` 且默认禁用
- 历史数据读取脚本（一次性迁移，仅查询旧表）
- 性能对比基准测试（Benchmark 对照组）
- 第三方库内部实现（vendor/ 目录且非项目调用）
- 条件永不满足：`if (false)` / `if (PHP_VERSION < '5.0')`
- IDE 自动生成的样板代码未实际使用

**代码异味：**
- 配置可选 `bcrypt` 但默认 `md5`
- 注释 "临时方案" / "TODO: 升级 bcrypt" 无时间表
- 日志输出 "Using MD5 for legacy compatibility" 无迁移计划
- SHA-1 作为 MD5 的"安全升级"方案
- 算法选择优先级：`md5 > sha1 > sha256`
- 性能理由选择 MD5（"MD5 更快，够用了"）
- 算法白名单包含 `['md5', 'sha1', 'sha256']`
- 新老用户不同算法但未统一升级
- 文档声称"密码加密存储"实际用 MD5 哈希
- 代码审查遗留 TODO 标签无人跟进
- 功能开关 `USE_SECURE_HASH=false` 默认关闭

**关键判断点：**
1. 哈希目标：测试数据 vs 真实用户密码/令牌
2. 安全边界：内部管理系统 vs 公网暴露接口
3. 数据敏感度：演示数据 vs PII/支付信息/健康数据
4. 对抗模型：是否需防御彩虹表/GPU 暴力破解
5. 生命周期：临时会话（5 分钟）vs 长期存储（数年）
6. 替代方案：系统是否有 `password_hash()` / `bcrypt` 实现
7. 调用频率：历史数据读取 vs 高频注册登录
8. 合规要求：是否涉及 GDPR / PCI DSS / 等保 2.0
9. 攻击面：登录失败锁定 / 验证码 / 速率限制是否存在
10. 数据泄露历史：数据库是否曾被脱库

## Low risk

**可接受的低风险场景：**
- 非安全用途的缓存键生成（Memcached Key / ETag）
- 日志追踪 ID 生成（Request ID / Trace ID）
- 文件去重标识（内部备份系统，无对抗需求）
- 分布式锁键生成（Redis 锁标识）
- 消息幂等性校验（临时去重窗口 < 5 分钟）
- 开发环境/Vagrant 快速原型搭建
- 读取 10 年前历史归档数据（一次性迁移）
- 与遗留第三方系统互操作（对方只支持 MD5 且内网专线）
- 性能测试环境模拟数据生成

**降级条件：**
- 数据已公开或低敏感度（公开文章 ID / 匿名统计）
- 短期过渡方案有明确迁移里程碑（Jira 可查）
- 访问受严格网络隔离（VPC 专网 + IP 白名单 + VPN）
- 仅向后兼容读取，所有新注册用 `password_hash()`
- 攻击窗口极短（一次性令牌 < 5 分钟 + 使用后失效 + HTTPS）
- 已有外层强保护（TLS 1.3 + mTLS 双向认证）
- 数据量极小且无重复模式（UUID / CSPRNG 生成）
- 攻击成本远高于资产价值（内部低价值测试系统）
- 登录保护完善（Captcha + 速率限制 + 账户锁定 + 2FA）
- 监控告警覆盖（暴力破解检测 + SOC 24/7 响应）

**注意：** MD5 已被实用碰撞攻击证明不安全（2008 年伪造 CA 证书、2012 年 Flame 恶意软件）。商用彩虹表覆盖常见密码，GPU 集群暴力破解简单密码 MD5 仅需秒级（8 位纯小写字母 < 1 小时）。PHP 5.5+ 提供 `password_hash()` / `password_verify()` 内置 bcrypt，无理由继续使用 MD5。任何涉及身份认证、支付签名、PCI DSS / GDPR / 等保 2.0 / 医疗 HIPAA 合规的系统应立即迁移至 bcrypt（密码）/ Argon2id（高安全）/ SHA-256（通用哈希）/ HMAC-SHA256（签名）。低风险评级不代表接受长期使用，仅适用于有明确迁移计划的过渡期或非安全关键场景。WordPress / Laravel / Symfony 现代版本均已默认使用安全算法，旧项目需审查框架版本与自定义实现。
