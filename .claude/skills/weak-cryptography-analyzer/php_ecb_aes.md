# PHP ECB 模式 AES 加密审计

## Details

### 典型代码特征
```php
// openssl_encrypt 显式使用 ECB 模式
$encrypted = openssl_encrypt($data, 'AES-128-ECB', $key);
$encrypted = openssl_encrypt($data, 'AES-192-ECB', $key);
$encrypted = openssl_encrypt($data, 'AES-256-ECB', $key);

// mcrypt 库使用 ECB（已废弃但遗留代码常见）
$encrypted = mcrypt_encrypt(MCRYPT_RIJNDAEL_128, $key, $data, MCRYPT_MODE_ECB);
$encrypted = mcrypt_encrypt(MCRYPT_RIJNDAEL_256, $key, $data, 'ecb');

// 通过变量传入 ECB 模式
$cipher = 'AES-256-ECB';
$encrypted = openssl_encrypt($plaintext, $cipher, $key);

// 配置文件中指定 ECB
$config['encryption']['method'] = 'AES-128-ECB';
$result = openssl_encrypt($data, $config['encryption']['method'], $key);

// 加密工具类封装 ECB
class Crypto {
    private $method = 'aes-256-ecb';
    public function encrypt($data) {
        return openssl_encrypt($data, $this->method, $this->key);
    }
}

// 条件使用 ECB（兼容模式）
if ($legacy_mode) {
    $cipher = 'AES-256-ECB';
} else {
    $cipher = 'AES-256-CBC';
}

// Laravel 加密器配置 ECB
'cipher' => 'AES-256-ECB',  // config/app.php

// 数据库字段加密使用 ECB
function encryptField($value) {
    return base64_encode(openssl_encrypt($value, 'aes-128-ecb', DB_KEY));
}

// Cookie/Session 加密
$_COOKIE['token'] = openssl_encrypt($user_id, 'AES-256-ECB', SECRET_KEY);
$_SESSION['data'] = mcrypt_encrypt(MCRYPT_RIJNDAEL_128, $key, $data, MCRYPT_MODE_ECB);

// API 参数加密
$params['encrypted'] = openssl_encrypt(json_encode($data), 'aes-256-ecb', API_KEY);

// 文件加密存储
$encrypted_content = openssl_encrypt(file_get_contents($file), 'AES-128-ECB', $key);
file_put_contents($file . '.enc', $encrypted_content);
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "openssl_encrypt.*ECB" --include="*.php"
grep -rn "mcrypt_encrypt.*ECB\|MCRYPT_MODE_ECB" --include="*.php"
grep -rn "'aes-.*-ecb'\|\"aes-.*-ecb\"" --include="*.php" -i
grep -rn "AES-128-ECB\|AES-192-ECB\|AES-256-ECB" --include="*.php"
grep -rn "MCRYPT_RIJNDAEL.*ECB" --include="*.php"
grep -rn "\$cipher.*=.*ecb\|\$method.*=.*ecb" --include="*.php" -i
```

**高危 API 模式（L2 跳读）：**
- `openssl_encrypt($data, 'AES-*-ECB', $key)` 任意密钥长度
- `openssl_encrypt($data, $method, $key)` 检查 `$method` 变量来源
- `mcrypt_encrypt(MCRYPT_RIJNDAEL_*, $key, $data, MCRYPT_MODE_ECB)`
- `mcrypt_encrypt(MCRYPT_*, $key, $data, 'ecb')`
- 配置数组 `$config['cipher']` / `$config['method']` 包含 "ecb"
- 常量定义：`define('CIPHER_METHOD', 'AES-256-ECB')`
- 类属性：`private $cipher = 'aes-128-ecb';`
- Laravel: `config('app.cipher')` 或 `.env` 中 `CIPHER_METHOD`
- WordPress: `$wpdb->encryption_method` 自定义字段
- 无 IV 参数传递（ECB 不需要 IV，缺失 IV 是特征）
- `openssl_encrypt()` 第四参数为 `0` 或省略（非 OPENSSL_RAW_DATA）

**函数调用链追踪（L3 逐行）：**
- 加密入口：`$_POST` / `$_GET` / `$_COOKIE` 参数加密处理
- 用户数据：注册/登录逻辑中密码或令牌加密
- API 控制器：`encrypt_request()` / `secure_api_call()` 函数实现
- 中间件：Laravel/Symfony 中间件加密请求/响应
- ORM 模型：Eloquent Accessor/Mutator 或 Doctrine 字段转换
- Session 处理器：自定义 `SessionHandler` 的 `write()` 方法
- 缓存层：Redis/Memcached 存储前加密（`set($key, encrypt($data))`）
- 日志脱敏：`log_secure($message)` 内部使用 ECB 加密
- 配置加载：`config.php` / `settings.php` / `.env` 解析
- 框架集成：ThinkPHP `think\facade\Crypt` / Yii2 `Security` 组件配置

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 硬编码 `'AES-256-ECB'` 字符串常量
- 配置文件默认值设为 ECB
- 无算法白名单验证（直接传入 `openssl_encrypt`）
- 无模式检查逻辑：`if (strpos($cipher, 'ECB') !== false) { throw ... }`
- `mcrypt_*` 函数仍在使用（PHP 7.1+ 已废弃）
- 加密类无构造函数验证或模式强制

**伪保护识别（L3 逐行）：**
```php
// 配置可选但默认 ECB
$cipher = $_ENV['CIPHER'] ?? 'AES-256-ECB';  // 危险的默认值

// 误认为 AES-256 足够安全
if ($security_level == 'high') {
    $cipher = 'AES-256-ECB';  // 密钥长度不解决模式问题
}

// 条件性 ECB（开发环境）
if (ENV == 'development') {
    return openssl_encrypt($data, 'AES-128-ECB', KEY);  // 配置泄露风险
}

// 封装类名具误导性
class SecureCrypto {
    const METHOD = 'aes-256-ecb';  // 名不副实
}

// 降级逻辑
try {
    $result = openssl_encrypt($data, 'AES-256-GCM', $key, 0, $iv, $tag);
} catch (Exception $e) {
    $result = openssl_encrypt($data, 'AES-256-ECB', $key);  // 危险降级
}

// 注释标注但未执行
// TODO: 迁移到 CBC 模式
return openssl_encrypt($data, 'AES-256-ECB', $key);

// 多层函数调用隐藏 ECB
function secure_encrypt($data) {
    return base64_encode(crypto_helper($data));
}
function crypto_helper($data) {
    return openssl_encrypt($data, get_cipher(), KEY);  // 需追踪 get_cipher()
}
function get_cipher() {
    return 'AES-128-ECB';  // 深层调用中暴露
}

// 框架配置间接使用
// Laravel Encrypter 构造函数接收 cipher
new Encrypter($key, 'AES-256-ECB');  // 非标准配置
```

**跨模块保护追踪（L4）：**
- Laravel: `config/app.php` → `'cipher'` 配置项检查
- Symfony: `config/packages/framework.yaml` → `secret` 加密配置
- ThinkPHP: `config/app.php` → `data_crypt_type` 设置
- Yii2: `components['security']` → `$cipher` 属性
- WordPress: `wp-config.php` 自定义常量或插件设置
- `.env` 文件：`ENCRYPTION_METHOD` / `CIPHER_ALGO` 环境变量
- Composer 依赖：`paragonie/halite` / `defuse/php-encryption` 配置审查
- Docker 环境变量：`docker-compose.yml` 中 `CIPHER_METHOD`
- Nginx/Apache 配置：`SetEnv CRYPTO_METHOD` 传递方式
- 数据库配置表：`settings` 表中 `encryption_method` 字段
- Redis 配置：分布式系统中配置中心存储的加密算法
- Ansible/Terraform：基础设施即代码中的加密配置变量
- CI/CD 流水线：GitLab CI / Jenkins 环境变量注入
- 日志系统：ELK/Splunk 中加密函数调用记录
- APM 监控：New Relic / Datadog 追踪 `openssl_encrypt` 参数

## Classify

**确认漏洞：**
- 用户密码/令牌/会话 ID 使用 ECB 加密存储或传输
- Cookie/JWT Payload 内容加密采用 ECB 模式
- API 请求签名参数或敏感字段 ECB 加密
- 数据库敏感列（身份证/银行卡/手机号）ECB 加密
- 文件上传加密存储（用户隐私文档/图片）
- 支付回调通知数据 ECB 加密验证
- OAuth2/SAML 断言或票据使用 ECB
- 相同明文产生相同密文（可通过日志/抓包验证）
- 加密数据存在模式特征（如相同字段值重复出现）
- 公开接口返回 ECB 加密数据（Base64 解码后无 IV）

**研判误报：**
- 单元测试代码（`tests/` 目录且不影响生产）
- 示例文档/教程代码（`examples/` / `docs/` 路径）
- 已废弃文件明确标注（文件头注释 `@deprecated`）
- 仅解密历史数据（只读兼容，新数据用 CBC/GCM）
- 开发环境配置（`.env.example` 且生产强制覆盖）
- Mock 实现或测试桩（`MockCrypto` 类非实际调用）
- 死代码：Git blame 显示未被调用且有删除计划
- 配置系统强制：运行时检查禁止 ECB（启动时抛异常）

**代码异味：**
- 可配置算法但默认 ECB（应默认 CBC-HMAC 或 GCM）
- 注释 "临时使用 ECB" 但无明确迁移时间表
- 分环境配置：开发 ECB，生产"应该"用 CBC
- 日志记录 "使用 ECB 以提升性能"（错误的优化理由）
- 加密工具类提供 ECB 选项（接口设计缺陷）
- 文档建议使用 ECB 简化开发（安全意识不足）
- 配置白名单包含 ECB（`allowed_ciphers = ['aes-256-cbc', 'aes-256-ecb']`）
- 框架扩展/插件使用 ECB 作为默认实现
- 兼容性说明引用 "与旧版本保持一致"

**关键判断点：**
1. **数据敏感性**：PII/金融/认证信息 vs 公开/缓存数据
2. **模式可观察性**：相同输入是否产生相同输出（幂等性测试）
3. **调用路径**：生产代码主流程 vs 边缘兼容逻辑
4. **替代方案**：系统是否已有 CBC/GCM 实现可切换
5. **攻击面**：外部 API vs 内部工具（网络暴露程度）
6. **数据结构**：重复字段多（如列表/表格）ECB 模式泄露严重

## Low risk

**可接受的低风险场景：**
- 加密非敏感配置项（UI 主题/语言偏好）
- 缓存键名混淆（非内容加密，仅防猜测）
- 一次性随机数据加密（无重复模式，单次使用）
- 完全内网系统且网络物理隔离（无公网暴露）
- 历史数据解密（只读迁移任务，非常驻服务）
- 已有外层 TLS 1.3 + 应用层签名验证（多重保护）

**降级条件：**
- 数据粒度极小且无重复（单个 UUID 加密，每次唯一）
- 短期临时方案有明确替换时间（项目看板可追踪）
- 访问受严格认证 + IP 白名单 + 速率限制
- 加密前添加随机盐（每条记录不同，但不等同于 IV）
- 仅内部管理后台使用且操作审计完整
- 数据已公开或脱敏处理后加密（如城市代码非详细地址）
- 攻击成本极高（需要数十万条数据样本才能识别模式）

**注意：** ECB 模式核心问题是相同明文块产生相同密文块，导致数据模式泄露（如企鹅图片加密后仍可见轮廓）。任何结构化数据（JSON/XML/表单）、重复字段（列表/数组）、可预测内容（状态码/布尔值）使用 ECB 都存在高风险。`openssl_encrypt()` 应强制使用 `AES-256-CBC` + HMAC 或 `AES-256-GCM`（认证加密）。`mcrypt` 扩展已在 PHP 7.1 废弃、7.2 移除，遗留代码应立即迁移。Laravel 等框架默认使用 CBC-HMAC 组合，手动配置 ECB 属于严重配置错误。低风险评级仅适用于极端特殊场景（内网隔离 + 非敏感 + 无重复模式 + 有迁移计划），生产环境强烈建议统一使用 GCM/CCM 认证加密模式消除 ECB 模式泄露风险。