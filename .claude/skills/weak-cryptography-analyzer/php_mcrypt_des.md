# PHP mcrypt + DES 弱加密审计

## Details

### 典型代码特征
```php
// mcrypt_encrypt 使用 DES 算法
$key = "secret12";  // DES 密钥 8 字节
$iv = "12345678";
$encrypted = mcrypt_encrypt(MCRYPT_DES, $key, $plaintext, MCRYPT_MODE_ECB);
$decrypted = mcrypt_decrypt(MCRYPT_DES, $key, $encrypted, MCRYPT_MODE_ECB);

// 显式指定 CBC 模式仍用 DES
$cipher = mcrypt_encrypt(MCRYPT_DES, $key, $data, MCRYPT_MODE_CBC, $iv);
$encoded = base64_encode($cipher);

// 3DES 系列（仍基于 DES 原语）
$encrypted = mcrypt_encrypt(MCRYPT_3DES, $key, $plaintext, MCRYPT_MODE_ECB);
$encrypted = mcrypt_encrypt(MCRYPT_TRIPLEDES, $key, $data, MCRYPT_MODE_CBC, $iv);

// mcrypt_generic 接口
$td = mcrypt_module_open(MCRYPT_DES, '', MCRYPT_MODE_ECB, '');
mcrypt_generic_init($td, $key, $iv);
$encrypted = mcrypt_generic($td, $plaintext);
mcrypt_generic_deinit($td);

// 密码存储场景
$hashedPassword = base64_encode(mcrypt_encrypt(MCRYPT_DES, $salt, $password, MCRYPT_MODE_ECB));
if ($hashedPassword === $user['password']) { /* 登录成功 */ }

// Cookie 加密
$userData = serialize(['id' => $userId, 'role' => $role]);
$encryptedCookie = mcrypt_encrypt(MCRYPT_DES, SECRET_KEY, $userData, MCRYPT_MODE_CBC, $iv);
setcookie('auth', base64_encode($encryptedCookie));

// API 签名
$signature = base64_encode(mcrypt_encrypt(MCRYPT_DES, $apiKey, $requestBody, MCRYPT_MODE_ECB));
$headers['X-Signature'] = $signature;

// 自定义加密工具类
class Crypto {
    private $algorithm = MCRYPT_DES;
    public function encrypt($data) {
        return mcrypt_encrypt($this->algorithm, $this->key, $data, MCRYPT_MODE_CBC, $this->iv);
    }
}

// Laravel 3.x/4.x 旧版使用 mcrypt
Config::get('app.cipher') === 'MCRYPT_DES';
$encrypted = Crypt::encrypt($data);  // 底层调用 mcrypt

// 配置驱动算法选择
$config = parse_ini_file('config.ini');
$cipher = mcrypt_encrypt($config['cipher_algorithm'], $key, $data, MCRYPT_MODE_ECB);

// 数据库字段加密
$encrypted = mcrypt_encrypt(MCRYPT_DES, DB_SECRET_KEY, $credit_card, MCRYPT_MODE_ECB);
$sql = "INSERT INTO users (card) VALUES ('$encrypted')";

// 会话数据加密
session_start();
$_SESSION['token'] = base64_encode(mcrypt_encrypt(MCRYPT_DES, session_id(), $token, MCRYPT_MODE_ECB));
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "mcrypt_encrypt\|mcrypt_decrypt" --include="*.php"
grep -rn "MCRYPT_DES\|MCRYPT_3DES\|MCRYPT_TRIPLEDES" --include="*.php"
grep -rn "mcrypt_module_open\|mcrypt_generic" --include="*.php"
grep -rn "extension.*mcrypt\|dl.*mcrypt" --include="*.php" --include="*.ini"
grep -rn "Crypt::encrypt\|Illuminate\\\\Encryption" --include="*.php"  # Laravel 旧版
```

**高危 API 模式（L2 跳读）：**
- `mcrypt_encrypt(MCRYPT_DES, ...)` / `MCRYPT_3DES` / `MCRYPT_TRIPLEDES`
- `mcrypt_module_open(MCRYPT_DES, '', ...)` 初始化 DES 模块
- `mcrypt_generic()` 配合 DES 算法描述符
- `mcrypt_decrypt()` 逆向操作标识存在加密逻辑
- 魔数：密钥长度 8 字节（DES）/ 24 字节（3DES）
- `MCRYPT_MODE_ECB` 无 IV 的不安全模式
- Laravel `config/app.php` 中 `cipher => 'des'` / `'des-ede3'`
- `php.ini` / `phpinfo()` 中 `mcrypt support => enabled`（PHP 7.2 前）
- 配置数组：`$config['encryption'] = 'mcrypt_des'`
- `base64_encode(mcrypt_encrypt(...))` 常见编码包装

**函数调用链追踪（L3 逐行）：**
- 定位 `mcrypt_encrypt()` 第一参数来源：常量/变量/配置读取
- 配置文件：`$cfg = include 'config.php'; $algo = $cfg['cipher'];`
- 条件分支：`if($legacy) { $algo = MCRYPT_DES; } else { $algo = MCRYPT_RIJNDAEL_128; }`
- Laravel 配置：`config('app.cipher')` 或 `env('APP_CIPHER', 'mcrypt_des')`
- 自定义加密类：`CryptoHelper::encrypt()` 内部算法选择
- Cookie 处理：`setcookie()` 之前的加密逻辑
- 会话处理器：`session_set_save_handler()` 自定义加密回调
- 数据库层：PDO 预处理前对敏感字段的加密
- ORM 插件：Doctrine/Eloquent `@Encrypted` 注解实现检查
- 中间件：认证中间件中 Token 解密逻辑
- Composer 依赖：`phpseclib/mcrypt_compat` 兼容层（仍用 DES 则有风险）

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 硬编码 `MCRYPT_DES` 无算法协商或升级路径
- 配置文件默认值 `cipher_algorithm=mcrypt_des`
- `php.ini` 启用 `extension=mcrypt.so`（PHP 7.1 废弃警告）
- 无版本检查：未判断 `PHP_VERSION_ID >= 70200`
- 无降级保护：`@mcrypt_encrypt()` 抑制错误继续执行
- 密钥直接硬编码：`$key = "mysecret";` 明文存储

**伪保护识别（L3 逐行）：**
```php
// 使用 CBC 模式但算法仍是 DES
$iv = mcrypt_create_iv(mcrypt_get_iv_size(MCRYPT_DES, MCRYPT_MODE_CBC), MCRYPT_RAND);
$encrypted = mcrypt_encrypt(MCRYPT_DES, $key, $data, MCRYPT_MODE_CBC, $iv);  // 模式不解决密钥长度问题

// 3DES 作为"安全升级"（仍不足现代标准）
if ($secureMode) {
    $cipher = mcrypt_encrypt(MCRYPT_3DES, $key, $data, MCRYPT_MODE_CBC, $iv);  // 有效密钥 112 位不足 128 位
}

// 多轮加密仍用 DES
$encrypted = $data;
for ($i = 0; $i < 3; $i++) {
    $encrypted = mcrypt_encrypt(MCRYPT_DES, $key, $encrypted, MCRYPT_MODE_ECB);  // 无效增强
}

// 配置降级逻辑
if (function_exists('openssl_encrypt')) {
    return openssl_encrypt($data, 'AES-256-CBC', $key, 0, $iv);
} else {
    return mcrypt_encrypt(MCRYPT_DES, $key, $data, MCRYPT_MODE_CBC, $iv);  // 危险降级
}

// Base64 编码误当加密增强
$encrypted = base64_encode(mcrypt_encrypt(MCRYPT_DES, $key, $data, MCRYPT_MODE_ECB));
$encrypted = base64_encode($encrypted);  // 多重编码无效

// 兼容层包装但底层仍用 mcrypt
class LegacyEncryptor {
    public function secureEncrypt($data) {
        if (PHP_VERSION_ID < 70200) {
            return mcrypt_encrypt(MCRYPT_DES, $this->key, $data, MCRYPT_MODE_ECB);  // 名不副实
        }
        return openssl_encrypt($data, 'AES-128-CBC', $this->key, 0, $this->iv);
    }
}

// Laravel 迁移未完成
// config/app.php: 'cipher' => env('APP_CIPHER', 'DES-EDE3-CBC'),  // .env 未修改
```

**跨模块保护追踪（L4）：**
- PHP 版本审计：`php -v` 或 `phpinfo()` 检查是否 >= 7.2（mcrypt 已移除）
- 扩展检查：`php -m | grep mcrypt` 或 `extension_loaded('mcrypt')`
- Composer 依赖：`composer.json` 中 `phpseclib/mcrypt_compat` 兼容包
- Laravel 版本：5.1+ 默认 AES，4.x 及以前可能用 mcrypt
- 配置中心：`.env` / `config/app.php` / `parameters.yml` 算法配置
- Docker 镜像：`Dockerfile` 基础镜像 `php:7.1` 及以下（支持 mcrypt）
- Web 服务器：Apache/Nginx 配置中环境变量 `SetEnv CIPHER_ALGO DES`
- 数据库审计：存储过程/触发器中调用 PHP UDF 加密函数
- Redis/Memcached：缓存序列化数据加密方式
- 日志记录：运行时日志 `PHP Deprecated: mcrypt is deprecated`
- CI/CD 配置：Jenkins/GitLab CI 环境变量 `ENCRYPTION_METHOD=mcrypt_des`
- 第三方集成：支付网关/OAuth 客户端回调数据解密算法

## Classify

**确认漏洞：**
- 用户密码存储使用 mcrypt + DES 哈希/加密
- Cookie/Session 加密使用 MCRYPT_DES 算法
- JWT/Token 签名或加密使用 DES
- API 请求签名验证基于 mcrypt DES
- 数据库敏感字段加密（身份证/银行卡/手机号）
- 支付/交易签名使用 DES 算法
- OAuth state/nonce 参数加密
- 文件上传内容加密存储（用户隐私文件）
- 跨域请求 CSRF Token 生成
- 无替代算法的生产环境强制 mcrypt + DES

**研判误报：**
- PHP 7.2+ 环境已移除 mcrypt 扩展（代码无法执行）
- 单元测试/集成测试用例（`tests/` 目录）
- 示例代码/文档注释中演示（`@example` / `docs/` 目录）
- 已废弃接口明确标注 `@deprecated` 且路由禁用
- 历史数据解密脚本（一次性迁移任务，仅读取不写入）
- 兼容性检测代码：`if(function_exists('mcrypt_encrypt'))` 但实际分支用 openssl
- Mock 对象/测试桩（PHPUnit DataProvider）
- Composer 开发依赖（`require-dev` 非生产环境）

**代码异味：**
- 配置可选 AES 但默认 DES：`cipher = env('CIPHER', 'mcrypt_des')`
- 注释 "TODO: migrate to openssl" 无时间表
- 版本检查后降级：`PHP_VERSION_ID < 70200 ? mcrypt : openssl`
- 3DES 作为"安全升级"方案（应直接 AES-256）
- 日志 "mcrypt is deprecated but still in use"
- 性能理由选择 mcrypt（"openssl slower"）
- 可配置白名单包含 DES：`allowed_ciphers=des,3des,aes`
- 新旧用户不同算法但未统一升级
- Laravel 5.x 使用 `legacy_cipher` 配置项

**关键判断点：**
1. PHP 版本：7.2+ 已移除 vs 7.1- 可用（仍需审计）
2. 加密目标：测试数据 vs 生产环境密码/Token/支付信息
3. 调用路径：活跃业务逻辑 vs 历史兼容层（Git blame 提交时间）
4. 替代方案：项目是否已使用 `openssl_encrypt()` / `sodium_crypto_*`
5. 敏感度：PII/PCI DSS 合规数据 vs 公开/低敏信息
6. 生命周期：临时会话 vs 长期数据库存储
7. 攻击面：公网 API vs 内网专用（VPC 隔离）

## Low risk

**可接受的低风险场景：**
- PHP 7.2+ 环境代码存在但无法执行（mcrypt 已移除）
- 一次性历史数据迁移脚本（解密旧数据后用 AES 重新加密）
- 与遗留第三方系统对接（对方只支持 DES 且专线隔离）
- 开发环境快速原型（`.env.local` 明确标注非生产）
- 单元测试加密逻辑验证（`tests/Unit/LegacyCryptoTest.php`）
- 内部低敏感度数据（非用户隐私/金融信息）
- 已有外层强保护的二次混淆（TLS 1.3 内部再加密）

**降级条件：**
- 数据已公开或低敏感度（公开文档/非 PII 数据）
- 短期过渡方案有明确迁移计划（Jira 可查时间表）
- 访问受严格网络隔离（内网 + 防火墙白名单）
- 仅向后兼容读取，所有新写入用 `openssl_encrypt('AES-256-GCM', ...)`
- 攻击窗口极短（一次性令牌 < 5 分钟 + Redis 自动过期）
- 用户量极小且非公开服务（内部管理系统 < 10 用户）
- 攻击成本远高于资产价值（内部测试环境）
- PHP 版本升级计划已立项（升级至 7.2+ 自动失效）

**注意：** mcrypt 扩展自 PHP 7.1.0 标记废弃，PHP 7.2.0 完全移除，任何使用均会报致命错误。DES 56 位密钥已被证明可在数小时内暴力破解（1998 年 EFF DES Cracker），现代 GPU 集群可秒级破解。3DES 虽密钥长度增加但基于 DES 原语，NIST SP 800-131A 已弃用。任何涉及 PCI DSS / GDPR / 等保 2.0 合规的系统应立即迁移至 `openssl_encrypt('AES-256-GCM', ...)` 或 Sodium 扩展（`sodium_crypto_secretbox()`）。Laravel 5.1+ 默认使用 OpenSSL AES-256-CBC，4.x 及以前版本需手动升级配置。低风险评级不代表接受长期使用，仅适用于有明确迁移计划的过渡期或 PHP 7.2+ 环境下的遗留代码（已无法执行）。