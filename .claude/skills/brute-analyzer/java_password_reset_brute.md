# Java 密码重置功能暴力破解漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 25-35分钟
- **影响范围：** 账户完全接管、隐私数据泄露、金融欺诈
- **CVSS:** 7.5-9.0（取决于组件重要性）

## 快速检查清单
- [ ] 令牌生成：`SecureRandom` + ≥32字节？
- [ ] 有效期：≤30分钟？
- [ ] 一次性使用：验证后删除或标记？
- [ ] 速率限制：IP限制(3/h) + 用户限制(5/day)?
- [ ] 用户枚举防护：响应、延迟、日志相同？
- [ ] 验证码：≥6位字母数字 + 尝试限制3次?
- [ ] 存储：SHA-256哈希 + salt？
- [ ] 审计日志：完整记录IP、时间、结果？
- [ ] 并发控制：令牌生成/验证线程安全？
- [ ] 邮件链接：token + email校验？

## 漏洞成因与核心问题
密码重置是高风险功能，攻击面广。常见漏洞：
1. **令牌可预测**：`Random`、`UUID`(128位)、时间戳种子
2. **有效期长**：无期限、>24小时、未检查时区
3. **重复使用**：未删除、未标记已使用、并发漏洞
4. **验证码弱**：6位纯数字(100万)、无尝试限制、无延迟
5. **用户枚举**：不同响应、响应时间差异、错误信息泄露
6. **无限请求**：缺速率限制、IP黑名单过期不清理
7. **明文存储**：数据库泄露直接获得令牌、缺少salt
8. **并发缺陷**：令牌生成/删除竞态、Double-submit漏洞

## 代码示例

### 漏洞1：令牌生成不安全
```java
// ✗ 漏洞：Random可预测，长度不足
private Random random = new Random();
public String generateToken(String email) {
    random.setSeed(System.currentTimeMillis());  // ✗ 可预测种子
    int token = random.nextInt(100000000);       // ✗ 仅8位数字，100万种
    return String.format("%08d", token);
}

// ✗ 漏洞：UUID不适合作令牌（只有128位熵，< 256位建议）
String token = UUID.randomUUID().toString();  // ✗ 安全性不足
```

### 漏洞2：有效期与一次性机制缺陷
```java
// ✗ 漏洞：无有效期检查，令牌不删除
public boolean validateToken(String token) {
    PasswordResetToken resetToken = tokenRepository.findByToken(token);
    return resetToken != null;  // ✗ 无过期检查，重复使用
}

// ✗ 漏洞：有效期过长(7天)
private LocalDateTime expiresAt = LocalDateTime.now().plusDays(7);  // ✗ > 30分钟

// ✗ 漏洞：时区问题
if (token.expiresAt.isBefore(LocalDateTime.now())) {  // ✗ 未考虑时区，跨域时出错
```

### 漏洞3：用户枚举 + 速率限制缺失
```java
// ✗ 漏洞：存在性判断返回不同响应
@PostMapping("/forgot-password")
public ResponseEntity<?> forgotPassword(@RequestParam String email) {
    User user = userRepository.findByEmail(email);
    if (user == null) {
        return ResponseEntity.status(404).body("User not found");  // ✗ 泄露存在性
    }
    // ✗ 无IP/邮箱速率限制，可轰炸
    sendResetEmail(user);
    return ResponseEntity.ok("Reset email sent");
}

// ✗ 漏洞：响应时间差异（时序攻击）
User user = userRepository.findByEmail(email);  // 数据库查询快速
if (user == null) {
    return "Not found";  // ✗ 不存在用户立即返回，存在用户发邮件耗时
}
```

### 漏洞4：验证码与尝试限制
```java
// ✗ 漏洞：6位纯数字，100万种可能，无尝试限制
public String generateVerificationCode() {
    return String.format("%06d", random.nextInt(1000000));
    // ✗ 攻击者可快速暴力：000000-999999，需100万次请求
}

// ✗ 漏洞：无尝试次数限制、无延迟
public boolean verifyCode(String code) {
    VerificationCode vc = vcRepository.findByCode(code);
    return vc != null && !vc.isExpired();  // ✗ 无尝试计数、无延迟
}
```

### 漏洞5：明文存储与并发缺陷
```java
// ✗ 漏洞：明文存储，数据库泄露直接���到令牌
@Column(nullable = false)
private String token;  // ✗ 明文，应SHA-256(token+salt)

// ✗ 漏洞：并发冲突，两个请求同时验证同一令牌
public void resetPassword(String token, String newPassword) {
    PasswordResetToken rt = tokenRepository.findByToken(token);  // ✗ Check-Then-Act
    if (rt.isUsed()) return;  // ✗ 第一个线程刚读取，第二个线程未被检测
    rt.setUsed(true);
    // ✗ 第二个线程也能修改密码
    userRepository.updatePassword(rt.getUserId(), newPassword);
}
```

## 快速扫描（审计技巧）

### 关键词搜索
```
password-reset, forgot-password, resetPassword, generateToken, expiresAt,
PasswordResetToken, verifyCode, validateToken, Bucket4j, RateLimiter
```

### 代码特征识别
| 特征 | 含义 | 风险 |
|------|------|------|
| `new Random()` | 非密码学RNG | P0 - 直接可预测 |
| `random.setSeed()` | 固定种子 | P0 - 重放风险 |
| `%06d` / `%08d` | 纯数字码 | P1 - 搜索空间小 |
| 无 `LocalDateTime.now().isAfter()` | 无过期检查 | P0 - 无限有效 |
| 无 `delete()` / `remove()` | 令牌不删除 | P0 - 重复使用 |
| `if (user == null) return 404` | 用户枚举 | P1 - 账户探测 |
| 无 Redis / Bucket4j | 无速率限制 | P1 - 轰炸风险 |
| 明文token存储 | 数据库即密钥 | P0 - 完全破坏 |
| 无 `@Transactional` | 并发不安全 | P0 - Double-submit |
| `UUID.randomUUID()` | 熵不足 | P1 - 低于256位 |

### 危险代码模式（Grep搜索）
```bash
# P0级别查找
grep -r "Random\|setSeed" src/  # 非密码学RNG
grep -r "findByToken\|verifyCode" src/ | grep -v "delete\|expire\|used"  # 未删除
grep -r "password.*reset" src/ | grep -v "Redis\|Bucket4j\|RateLimiter"  # 无限流

# 并发检查
grep -r "@Transactional" src/ | grep -i reset  # 是否原子操作
grep -A5 "findByToken" src/ | grep -c "setUsed\|delete"  # 是否标记使用

# 响应检查
grep -B2 "user == null\|user not found" src/ | grep "return\|throw"  # 响应是否统一
```

### 动态审计技巧
1. **构造攻击请求**：
   - 发送100个重置请求（无速率限制？）
   - 多用户邮箱尝试观察响应时间（时序攻击？）
   - 使用Intruder暴力6位数字码（验证码弱？）

2. **数据库检查**：
   ```sql
   SELECT token FROM password_reset_tokens LIMIT 5;  -- 明文存储？
   SELECT * FROM password_reset_tokens WHERE user_id=123;  -- 有效期？已使用标记？
   SELECT * FROM password_reset_tokens WHERE created_at < NOW() - INTERVAL 24 HOUR;  -- 不清理？
   ```

3. **日志分析**：
   - 同一IP/邮箱多次请求是否记录？
   - 失败/成功是否分别记录？
   - token值是否出现在日志？（安全风险）

4. **并发测试**：
   - JMeter同时提交同一令牌的两个重置请求
   - 观察两个都成功或只有一个成功

## 防护机制检查表
| 防护项 | 要求 | 标志 | 备注 |
|-------|------|------|------|
| 令牌生成 | `SecureRandom` + ≥32字节 | ✓关键 | 256位熵以上，Base64编码 |
| 有效期 | ≤30分钟(建议15分钟) | ✓关键 | ZoneId.systemDefault()避免时区坑 |
| 一次性 | 验证后delete或标记used | ✓关键 | 结合@Transactional避免并发 |
| 存储 | SHA-256(token+salt)哈希 | ✓重要 | salt=userId+timestamp |
| IP限制 | 3/h且支持黑名单 | ✓重要 | X-Forwarded-For信任策略 |
| 用户限制 | 5/day，超限临时封禁 | ✓重要 | 30分钟后自动解封 |
| 响应统一 | 不管用户存不存在 | ✓重要 | 延迟模拟：随机50-200ms |
| 验证码 | 8位字母数字 + 尝试≤3次 | ✓重要 | 每次失败延迟1s，计数存Redis |
| 邮件验证 | token + email双重校验 | ✓重要 | 防token盗用跨用户重置 |
| 删除旧令牌 | 新请求前删除该用户旧令牌 | ✓重要 | 防泄露后重用 |
| 审计日志 | IP、邮箱、时间、结果 | 中等 | 不记录token值 |
| 定时清理 | 每小时清理过期令牌 | 中等 | 防表膨胀 |

## 审计等级
| 等级 | 检查项数 | 漏洞数 | 评级建议 | 示例 |
|------|--------|--------|---------|------|
| L0 | <5 | ≥3 | 高危 | 无限流+明文令牌 |
| L1 | 6-8 | 2-3 | 中危 | 有基础防护缺尝试限制 |
| L2 | 9-11 | 1 | 低危 | 完整防护但实现细节不完美 |
| L3 | 12 | 0 | 信息 | 完全符合最佳实践 |
| L4 | 13+ | 0 | 通过 | L3+MFA/异常检测/审计 |

### 快速评级方法
```
缺陷数 = 缺少的防护机制数量
高危 = 缺陷数≥3 或存在"Random"/"明文token"/"无有效期"
中危 = 缺陷数=2 或响应差异
低危 = 缺陷数=1 或实现细节问题
```

## 漏洞确认与排除

### 必现漏洞（命中即报告）
1. 使用 `java.util.Random` 或 `Math.random()`（可直接预测）
2. 明文存储令牌在数据库
3. 无有效期或有效期>2小时
4. 验证后未删除且无"已使用"标记
5. 6位纯数字验证码+无尝试限制(能暴力100万种)
6. 响应差异：`user not found`(404) vs `reset sent`(200)
7. 无任何速率限制(IP/邮箱)
8. token≤16字节或纯数字

### 可能漏洞（需验证代码逻辑）
- `SecureRandom`但长度16-24字节(需256+位)
- 有效期1-2小时(建议≤30分钟)
- UUID作令牌(128位，低于256位建议)
- 仅IP限制无用户限制，易被绕过(共享IP)
- 延迟模拟缺失，存在时序攻击
- 验证码含历史旧值(重放使用)
- 令牌生成/删除无@Transactional(并发漏洞)

### 完全安全指标（全部满足=低风险）
- ✓ `SecureRandom` + ≥32字节Base64编码令牌
- ✓ 有效期≤30分钟 + 验证后立即delete
- ✓ IP限制3/h + 用户限制5/day + 超限黑名单
- ✓ 响应/延迟统一(无论用户存不存在)
- ✓ 验证码8位字母数字 + 尝试≤3次 + 1s延迟
- ✓ SHA-256(token+salt)哈希存储
- ✓ @Transactional保证原子性
- ✓ 邮件&token双校验(防跨账户)
- ✓ 删除旧令牌+定时清理过期数据
- ✓ 审计日志(IP/邮箱/时间/结果，不记录token)

---

## 快速修复与评级指南

### 高危漏洞修复清单（必须修复）
| 漏洞 | 修复 | 时间 | 代码位置 |
|------|------|------|--------|
| Random或明文令牌 | `SecureRandom` + 32字节Base64 | 当天 | generateToken() |
| 无有效期或过长 | expiresAt = now().plusMinutes(15) | 当天 | PasswordResetToken实体 |
| 验证后不删除 | resetToken.delete() in @Transactional | 3天 | resetPassword() |
| 无速率限制 | Redis or Bucket4j + IP+邮箱key | 3天 | Controller前置 |
| 用户枚举 | 统一返回"如果账户存在..." + Thread.sleep(random) | 1周 | forgotPassword() |

### 中危漏洞修复清单
| 漏洞 | 修复 | 优先级 |
|------|------|--------|
| 弱哈希(MD5/SHA1) | SHA-256 + salt | P1 |
| 验证码6位纯数字 | 8位字母数字 + 3次失败延迟 | P1 |
| 无邮箱校验 | ?token=xxx&email=yyy验证两者 | P2 |
| 不清理旧令牌 | delete where user_id=? before new | P2 |
| 无审计日志 | log request/response(不记token) | P2 |

### 评级建议（快速判断）
```
检查清单中的Yes数量：
≥8个 = 安全(低风险)   可接受，定期审查
6-7个 = 较安全(低危)   需小幅修复，无紧急压力
4-5个 = 一般(中危)     需修复P0/P1，2周内解决
2-3个 = 危险(中高危)   需立即修复，1周内解决
0-1个 = 极危(高危)     需紧急修复，当天内解决
```
