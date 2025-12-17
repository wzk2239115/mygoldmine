# PHP | 两步验证（2FA）码暴力破解漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 25-35分钟
- **风险等级：** 高危 (账户接管)

## 🚀 30秒快速清单
- [ ] 2FA验证码是否可无限次尝试？
- [ ] 验证码长度是否≥6位（推荐8位）？
- [ ] 验证码是否有过期时间（建议≤10分钟）？
- [ ] 是否实施了速率限制或失败锁定？
- [ ] 是否使用了安全的随机生成器（`random_bytes()`）？

---

## Details

### 漏洞成因
PHP 2FA实现中，验证码验证往往缺乏防护机制，允许攻击者无限制尝试，导致短验证码可被快速穷举。常见缺陷包括：验证次数无限制、缺少过期机制、使用弱随机源、无速率限制、多个验证步骤之间缺乏完整性验证。

### 代码示例

```php
// ❌ 漏洞1：验证码无尝试限制，可无限尝试
<?php
class TwoFactorService {
    public function verify2FA($userId, $code) {
        // 直接从session或数据库获取验证码
        $stored_code = $_SESSION['2fa_code_' . $userId] ?? null;

        // 问题：无尝试次数限制、无过期检查
        if ($stored_code === $code) {
            unset($_SESSION['2fa_code_' . $userId]);
            return true;
        }
        return false;
    }
}
?>
```

```php
// ❌ 漏洞2：验证码过短，使用不安全随机生成
<?php
class AuthController {
    public function send2FACode($userId) {
        // 问题1：仅4位数字，10000种可能
        // 问题2：使用rand()，不安全
        $code = str_pad(rand(0, 9999), 4, '0', STR_PAD_LEFT);

        $_SESSION['2fa_code_' . $userId] = $code;
        $_SESSION['2fa_time_' . $userId] = time();

        // 发送给用户
        mail(getUserEmail($userId), "2FA Code: $code");
        return ['status' => 'sent'];
    }
}
?>
```

```php
// ❌ 漏洞3：验证逻辑脆弱，多个验证步骤间缺乏完整性
<?php
// Step 1: 发送验证码
$_SESSION['2fa_code'] = generate_code();
$_SESSION['2fa_verified'] = false;  // 初始状态

// Step 2: 验证验证码 (无尝试限制)
if ($_POST['code'] === $_SESSION['2fa_code']) {
    $_SESSION['2fa_verified'] = true;  // 问题：无时间戳验证，可重放
}

// Step 3: 完成登录 (检查不完整)
if ($_SESSION['2fa_verified']) {  // 仅检查布尔值，无时间有效期
    // 允许登录
    login($user);
}
?>
```

### 快速定位核心操作 **(L1:关键词扫描)**
- **生成**：`rand()`, `mt_rand()`, `unpack('C*', ...)`, 不使用`random_bytes()`
- **发送**：`$_SESSION['2fa_code']`, `cache->set()`, 无过期时间参数
- **验证**：`if ($_POST['code'] === $stored)`, 无计数器检查，无`time()`对比
- **缺陷关键词**：无`++$attempts`, 无`max_attempts`, 无`exp_time`

### 保护机制检查 **(L2-L3:跳读+逐行读)**
逐行检查以下保护是否存在：
1. **生成阶段** (L2):
   - ✓ 使用`random_bytes(16)`或`openssl_random_pseudo_bytes()`生成
   - ✓ 至少8位字母数字或6位数字
   - ✓ 存储时添加生成时间戳：`['code' => $code, 'time' => time()]`

2. **验证阶段** (L3):
   - ✓ 验证前检查过期：`time() - $created_time > 600` (10分钟)
   - ✓ 检查尝试计数：`$attempts > 3` 则拒绝
   - ✓ 每次验证失败递增计数：`$attempts++`
   - ✓ 验证成功后立即删除：`unset($_SESSION['2fa_code'])`

3. **跨请求保护** (L4:跨模块追踪):
   - ✓ 尝试计数持久化（数据库、Redis）
   - ✓ 速率限制：检查`$_SERVER['REQUEST_TIME'] - $last_attempt_time < 1`
   - ✓ IP绑定：验证IP与发送时IP一致

---

## Classify

### 确认漏洞特征
仅需满足以下任一条即为漏洞：

1. **无尝试限制**
   - 验证代码无失败计数器，或无上限检查
   - 理论可枚举：4位数字(10,000次) ≈ 2-10秒, 6位数字(1,000,000次) ≈ 20-100秒

2. **验证码过短**
   - 纯数字 < 6位，或字母数字 < 4位
   - 重用旧验证码（未删除）

3. **无过期机制**
   - 验证码永久有效或过期时间 > 30分钟
   - 验证码生成后无时间戳记录

4. **使用弱随机源**
   - `rand()`, `mt_rand()`, `uniqid()`, `microtime()`
   - 验证码中使用可预测值

5. **无速率限制**
   - 无IP/用户级别限流
   - 允许高频请求

### 误报排除（确保为安全实现）
- ✓ 8位字母数字验证码 + `random_bytes()`
- ✓ 尝试限制≤3次，超限后锁定或延迟
- ✓ 过期时间≤10分钟，时间戳严格检查
- ✓ 验证成功/超限后立即删除验证码
- ✓ 速率限制≤5次/分钟 (用户级别)
- ✓ 多个验证步骤间有完整性校验（时间戳、会话ID绑定）

---

## Low Risk

以下实现方式可评为低风险：

1. **强验证码生成**
   - 使用`random_bytes()` + base62编码生成8位+验证码
   - 验证码包含生成时间戳和用户标识

2. **完整的尝试限制**
   - 3次失败后强制延迟或锁定
   - 锁定时间≥15分钟，或需邮件验证解锁

3. **严格的过期机制**
   - ≤10分钟自动过期
   - 必须逐行检查：`if (time() - $created_time > EXPIRY)`

4. **多层防护**
   - IP限流 + 用户账户限流 + 验证码复杂度
   - 过期验证码不触发任何操作
   - 验证失败返回统一错误消息，无信息泄露

5. **持久化保护**
   - 尝试计数/过期时间存储在数据库/Redis（分布式安全）
   - 跨会话、跨IP保持有效
