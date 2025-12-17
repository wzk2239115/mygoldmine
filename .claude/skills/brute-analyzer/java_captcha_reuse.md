# Java CAPTCHA验证码重用漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-30分钟
- **关键威胁：** 暴力破解、账户接管、绕过登录保护

## 🚀 30秒快速清单
- [ ] CAPTCHA验证后是否立即从Session删除？
- [ ] CAPTCHA生成是否使用 `SecureRandom` 而非 `Random`？
- [ ] CAPTCHA是否有有效期限制（≤5分钟）？
- [ ] 是否限制同一CAPTCHA的验证次数（≤3次）？
- [ ] 分布式环境下CAPTCHA状态是否同步（Redis）？
- [ ] 验证逻辑是否防止空值绕过？

## Details

### 漏洞成因
验证码重用是指验证码验证后未被删除或标记为已使用，攻击者可持续复用该验证码进行多次尝试。关键缺陷：
1. **一次性机制缺失**：验证后未删除Session中的验证码
2. **弱随机源**：使用 `Random` 而非 `SecureRandom` 生成
3. **无时间约束**：无有效期或有效期过长（>5分钟）
4. **缺乏尝试限制**：同一验证码可无限重试
5. **分布式不同步**：集群环境Session未共享
6. **逻辑漏洞**：空值绕过、大小写不敏感、并发竞态

### 常见漏洞代码模式

| 漏洞 | 问题代码 | 风险 | 审计技巧 |
|------|--------|------|--------|
| 验证后未删除 | 无 `removeAttribute("captcha")` | 验证码可重复使用 | 搜索验证逻辑后是否立即清理 |
| 弱随机源 | `new Random()` 或 `setSeed()` | 4位码可预测 | 跟踪随机数生成，检查熵源 |
| 无有效期 | 存储验证码无时间戳 | 长期有效，慢速破解 | 搜索 `captchaTime`, `timestamp`, `expiry` |
| 无尝试限制 | 验证失败无计数 | 4位码=10000次尝试 | 检查 `attempt`, `count`, `retry` 字段 |
| 空值绕过 | `equals()` 未先检查null | 无验证码即可通过 | 输入null/空字符串测试 |
| 大小写不敏感 | `equalsIgnoreCase()` | 搜索空间减半 | 观察HTTP请求区分大小写 |
| 并发不安全 | `HashMap` 存储 | 竞态条件、内存泄漏 | 寻找 `synchronized` 或 `ConcurrentHashMap` |
| 分布式不同步 | 内存Session+多服务器 | 不同服务器验证失败 | 检查 `spring-session` 依赖配置

### 代码审计核心关键词
**一句话速查**：搜索 `captcha|verifyCode|validateCode` → 找验证逻辑 → 检查 `removeAttribute` → 检查时间戳 → 检查尝试限制

| 操作类型 | 关键词 | 用途 |
|---------|------|------|
| 生成验证码 | `new Random`, `SecureRandom`, `randomAlphanumeric` | 确认随机源强度 |
| 存储验证码 | `session.setAttribute`, `put()`, `redis.set` | 确认存储位置和有效期 |
| 验证验证码 | `equals`, `equalsIgnoreCase`, `Objects.equals` | 检查空值防护和时间复杂度 |
| 清理验证码 | `removeAttribute`, `delete`, `expire` | 确认一次性机制 |
| 尝试计数 | `attempt`, `count`, `retry`, `failed` | 确认重试次数限制 |
| 并发安全 | `synchronized`, `ConcurrentHashMap`, `ReentrantLock` | 确认线程安全 |
| 分布式 | `@EnableRedisHttpSession`, `spring.session.store-type: redis` | 确认分布式Session |

---

## Classify

### 快速确认漏洞（任一条件满足即为漏洞）
1. **验证后未删除**：验证成功或失败后仍保留在Session/缓存中 → grep验证方法找不到 `removeAttribute`
2. **弱随机源**：使用 `java.util.Random` → 提取生成代码，种子为 `System.currentTimeMillis()` 则可预测
3. **无有效期限制**：无时间戳检查或有效期>5分钟 → 搜索验证码存储未见 `captchaTime` 字段
4. **无尝试限制**：同一验证码可无限验证 → 验证逻辑后无 `attemptCount>3` 检查
5. **验证逻辑漏洞**：空值绕过（两个null都通过）或大小写不敏感（搜索 `equalsIgnoreCase`）
6. **分布式不同步**：集群环境使用内存Session → pom.xml未见 `spring-session-data-redis`

**实战速记**：无 `remove` + 无时间戳 + 无尝试限制 = 高危验证码重用漏洞

### 误报排除
- ✗ 使用 `SecureRandom` 或 `ThreadLocalRandom` 生成
- ✗ 验证后立即 `removeAttribute("captcha")`，且无其他引用
- ✗ 时间戳检查有效期≤5分钟
- ✗ 尝试次数限制≤3次且后续锁定账户
- ✗ 使用 `MessageDigest.isEqual()` 常量时间比较
- ✗ 集成Kaptcha/reCAPTCHA等成熟方案
- ✗ Redis自动过期TTL设置正确

### 代码异味（灰色地带）
- △ `SecureRandom` 生成但验证码<6位（无效期虽短但搜索空间小）
- △ 有效期5-10分钟（比最佳实践稍长）
- △ `ConcurrentHashMap` 无定期清理过期条目
- △ Session超时10-30分钟（应≤10分钟）
- △ 验证码为4位纯数字，虽限制重试但搜索空间仅10000

---

## Low Risk

### 低风险评级条件

**低风险场景**：
1. 使用第三方成熟服务（Google reCAPTCHA v3、腾讯云验证码、阿里云）
2. 成熟Java库（Kaptcha v2.3.2+、EasyCaptcha）且参数合理
3. 完善自实现：`SecureRandom` + 6位+ + ≤5分钟有效期 + 验证后删除 + ≤3次尝试
4. 多层防御：CAPTCHA + 速率限制 + 账户锁定（5次失败锁定15分钟）
5. 分布式正确配置：`spring-session-data-redis` + 同步延迟<100ms
6. 非关键业务（评论、订阅）或已有MFA保护

**评级建议**：登录/注册/支付等关键操作即使为低风险也应说明风险，建议实施一次性验证。

---

## 安全实现要点

### 核心修复检查表
| 修复项 | 验证方法 | 优先级 |
|-------|--------|-------|
| 验证后删除 | grep验证逻辑找 `removeAttribute("captcha")` | P0 |
| 安全随机 | grep `SecureRandom` 而非 `new Random()` | P0 |
| 有效期限制 | 验证码时间戳存在且检查≤5分钟 | P0 |
| 尝试限制 | 验证逻辑包含 `attemptCount>3` 检查 | P0 |
| 时序防护 | 使用 `MessageDigest.isEqual()` 或 `ConstantTimeComparison` | P1 |
| 分布式同步 | 生产多服务器环境使用 `spring-session-data-redis` | P1 |

### 实战修复代码片段
```java
// ✓ 正确实现（审计通过）
private boolean verifyCaptcha(String userInput, HttpSession session) {
    long startTime = System.currentTimeMillis();

    String storedCaptcha = (String) session.getAttribute("captcha");
    Long captchaTime = (Long) session.getAttribute("captchaTime");
    Integer attempts = (Integer) session.getAttribute("captchaAttempts");

    // P0: 边界检查
    if (storedCaptcha == null || captchaTime == null || attempts == null)
        return false;

    // P0: 有效期检查（5分钟）
    if (System.currentTimeMillis() - captchaTime > 300000) {
        session.removeAttribute("captcha");
        return false;
    }

    // P0: 尝试次数检查
    if (attempts >= 3) return false;

    // P0: 常量时间比较
    boolean valid = MessageDigest.isEqual(
        userInput.getBytes(), storedCaptcha.getBytes()
    );

    // P0: 验证后删除（一次性使用）
    if (valid) {
        session.removeAttribute("captcha");
        session.removeAttribute("captchaTime");
        session.removeAttribute("captchaAttempts");
    } else {
        session.setAttribute("captchaAttempts", attempts + 1);
    }

    return valid;
}
```

### 修复优先级
1. **P0（当天）**：添加 `removeAttribute()`、更换随机源、添加时间戳检查、添加尝试次数限制
2. **P1（3天）**：实现常量时间比较、分布式环境集成Redis
3. **P2（1周）**：考虑第三方库或服务、实施监控告警
