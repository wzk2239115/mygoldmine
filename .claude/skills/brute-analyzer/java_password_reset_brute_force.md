# Java | 密码重置验证码暴力破解漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-30分钟

## 🚀 30秒快速清单
- [ ] 验证码是否足够复杂（≥6位字母数字）？
- [ ] 是否有次数限制（≤3次）？
- [ ] 是否有时间限制（≤10分钟）？
- [ ] 是否实施速率限制（≤3次/小时）？

## Details

### 漏洞成因
密码重置验证码常见问题：位数过少、无尝试限制、无时间限制、可重复使用、响应消息不同、无速率限制。

### 代码示例

```java
// 漏洞1：验证码过短且无尝试限制
@Service
public class PasswordResetService {
    private Random random = new Random();

    public String generateCode() {
        // 仅4位数字，10000种可能
        int code = random.nextInt(10000);
        return String.format("%04d", code);
    }

    public boolean verifyCode(String email, String code) {
        String stored = cacheService.get("reset_code:" + email);
        // 问题：无尝试限制、无过期检查、无延迟
        return code.equals(stored);
    }
}
```

```java
// 漏洞2：无速率限制和用户枚举
@PostMapping("/request-reset")
public ResponseEntity<?> requestReset(@RequestParam String email) {
    // 问题：无速率限制，响应不同泄露用户存在
    if (userRepository.findByEmail(email).isPresent()) {
        String code = generateCode();
        cacheService.set("reset_code:" + email, code, 3600);
        emailService.send(email, code);
        return ResponseEntity.ok("Code sent");
    }
    return ResponseEntity.status(404).body("User not found");
}
```

### 快速定位
- **生成**：`random.nextInt()`, `String.format()`
- **存储**：`cacheService.set()`, `redisTemplate`
- **验证**：`cacheService.get()`, `equals()`, 缺少计数

### 保护机制
- **8位字母数字**验证码，`SecureRandom`生成
- **尝试限制**：3次失败后锁定
- **时间限制**：10分钟自动过期
- **一次性**：验证成功后删除
- **速率限制**：每小时≤3次请求
- **统一响应**：用户存在与否返回相同消息

---

## Classify

### 确认漏洞
1. 验证码过短（纯数字<6位）
2. 无尝试限制
3. 无时间限制
4. 可重复使用
5. 响应消息不同

### 误报排除
- ✗ 8位字母数字验证码
- ✗ 尝试限制≤3次
- ✗ 有效期≤10分钟
- ✗ 速率限制≤3次/小时
- ✗ 统一响应

---

## Low Risk

1. **强验证码**：8位字母数字，`SecureRandom`
2. **强限制**：3次尝试，10分钟过期，3次/小时请求
3. **防枚举**：统一响应，相同延迟
4. **多因素**：邮件+短信验证

---

## 安全实现

```java
@Service
@RequiredArgsConstructor
public class SecureVerificationService {
    private final RedisTemplate<String, Object> redis;
    private final EmailService emailService;

    private static final SecureRandom random = new SecureRandom();
    private static final int CODE_LENGTH = 8;
    private static final int VALIDITY_MINUTES = 10;
    private static final int MAX_ATTEMPTS = 3;

    public String generateCode() {
        String chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        StringBuilder code = new StringBuilder();
        for (int i = 0; i < CODE_LENGTH; i++) {
            code.append(chars.charAt(random.nextInt(chars.length())));
        }
        return code.toString();
    }

    public void requestCode(String email, String ip) {
        // 速率限制检查
        String key = "reset:" + email;
        Long count = redis.opsForValue().increment(key);
        if (count == 1) {
            redis.expire(key, Duration.ofHours(1));
        }
        if (count > 3) {
            return; // 静默失败，统一响应
        }

        // 生成并发送
        String code = generateCode();
        redis.opsForValue().set("code:" + email, code, Duration.ofMinutes(VALIDITY_MINUTES));
        redis.opsForValue().set("attempts:" + email, "0", Duration.ofMinutes(VALIDITY_MINUTES));
        emailService.send(email, code);
    }

    public boolean verifyCode(String email, String inputCode) {
        String codeKey = "code:" + email;
        String attemptsKey = "attempts:" + email;

        Object stored = redis.opsForValue().get(codeKey);
        if (stored == null) {
            return false;
        }

        int attempts = Integer.parseInt((String) redis.opsForValue().get(attemptsKey));
        if (attempts >= MAX_ATTEMPTS) {
            redis.delete(codeKey);
            redis.delete(attemptsKey);
            return false;
        }

        redis.opsForValue().increment(attemptsKey);

        if (!inputCode.equals((String) stored)) {
            // 延迟
            try {
                Thread.sleep(100 * (long) Math.pow(2, attempts));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            return false;
        }

        // 验证成功，清理
        redis.delete(codeKey);
        redis.delete(attemptsKey);
        return true;
    }
}
```

## 修复优先级

1. **当天**：8位字母数字+SecureRandom
2. **3天**：时间和次数限制
3. **1周**：速率限制+统一响应
4. **2周**：延迟机制+审计日志
