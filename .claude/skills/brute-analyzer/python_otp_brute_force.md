# Python | OTP/2FA暴力破解防护缺失

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-30分钟
- **出现频率：** 72% (互联网OTP流程普遍缺失)

## 🚀 30秒快速清单
- [ ] OTP验证端点是否有速率限制？检查`@limiter.limit()`或`django-ratelimit`装饰器
- [ ] 验证失败次数是否持久化到Redis/DB？检查是否用了内存存储（dict/memory-cache）
- [ ] OTP失败3次后是否强制锁定（需重新获取OTP）？检查`attempts_exceeded`或类似标志
- [ ] OTP过期时间是否≤15分钟？检查配置中的`OTP_VALIDITY`或`TOKEN_EXPIRY`
- [ ] 验证成功后OTP是否立即删除/标记已用？防止重复验证
- [ ] 所有OTP端点的验证逻辑是否统一（API/表单/WebAuthn）？

## 漏洞核心特征

### ⚠️ 高频缺陷模式（审计时优先检查）

| 缺陷类型 | 表现形式 | 风险等级 | 快速定位 |
|---------|--------|--------|--------|
| **无失败限制** | OTP验证端点无Intruder防护，6位验证码100万种可能 | 🔴 严重 | 搜索`@app.route('/verify')`无限制逻辑 |
| **内存计数** | 失败次数存`dict`/`{}` 或`cache.get()`内存，重启丢失 | 🔴 严重 | Grep`attempts = {}`或`get_cache()` |
| **过期时间过长** | `OTP_VALIDITY = 3600`（1小时）或24小时，被捕获可长期重用 | 🟠 高 | 搜索`VALIDITY`、`EXPIRY`、`TTL` |
| **验证码可重复用** | 验证成功后未删除，同一OTP可多次通过验证 | 🟠 高 | 检查验证逻辑是否`delete_otp()`或`mark_used()` |
| **用户枚举** | 返回`"OTP已发送"`vs`"用户不存在"`，泄露用户 | 🟠 高 | 检查验证码获取和验证的错误消息 |
| **无重新获取冷却** | 用户可无限快速重新获取OTP，穷举所有发送出的OTP | 🟡 中 | 搜索获取OTP端点是否限流 |
| **时间窗口TOTP弱化** | 允许前后多个时间步长验证，大幅增加有效窗口 | 🟡 中 | TOTP验证是否允许`±1`或`±2`步长 |

## Details

### 漏洞成因

Python框架（Flask、Django、FastAPI）默认无OTP防护机制，关键缺失：

1️⃣ **无失败追踪**：验证端点无失败计数，可无限尝试
2️⃣ **内存易失**：锁定状态存内存，重启/扩展后丢失
3️⃣ **过期时间长**：OTP有效期过长，被劫持可长期利用
4️⃣ **验证码重用**：验证后未删除，可多次使用同一码
5️⃣ **端点防护不一致**：获取和验证端点限流规则不同
6️⃣ **TOTP窗口宽松**：允许多个时间步长，增加破解几率

### 核心漏洞代码示例

#### 漏洞1：无失败限制 + 无速率限制
```python
# ❌ 危险：验证端点无任何防护
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    user_id = request.form['user_id']
    otp_input = request.form['otp']

    # 直接验证，无失败计数，可无限尝试
    stored_otp = redis.get(f"otp:{user_id}")
    if otp_input == stored_otp:
        # 验证通过
        pass

    return "验证失败"
# 攻击者可在秒级内尝试所有6位数字（0-9）组合
```

**审计技巧**：搜索`@app.route('/verify')`、`/otp/check`、`/2fa/validate`等验证端点，检查是否无`@limiter.limit()`装饰器；尝试用Burp Intruder发送20-30个错误OTP，观察是否被拒

#### 漏洞2：失败计数存内存（重启失效）
```python
# ❌ 严重：dict存储，重启丢失，分布式不同步
failed_attempts = {}  # ❌ 全局内存

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    user_id = request.form['user_id']

    # 计数器在内存，重启/扩展丢失
    if user_id not in failed_attempts:
        failed_attempts[user_id] = 0

    failed_attempts[user_id] += 1

    if failed_attempts[user_id] >= 5:
        return "验证失败过多，请重试", 429
# 问题：应用重启后dict清空，计数重置；多进程/容器环境各实例计数不同步
```

**审计技巧**：Grep搜索`failed_attempts = {}`、`attempts[user] = `或`cache_dict = {}`等内存存储

#### 漏洞3：OTP过期时间过长
```python
# ❌ OTP有效期过长，被劫持长期可用
def generate_otp(user_id):
    otp = random.randint(100000, 999999)
    # ❌ 1小时过期太长！
    redis.setex(f"otp:{user_id}", 3600, otp)  # 应为600-900秒
    send_sms_or_email(otp, user_id)
```

**审计技巧**：搜索`setex`、`expire`、`timeout`等过期设置，检查秒数是否≤15分钟（900秒）

#### 漏洞4：验证成功后未删除OTP
```python
# ❌ 验证成功后未删除，可重复使用
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    user_id = request.form['user_id']
    otp_input = request.form['otp']

    stored_otp = redis.get(f"otp:{user_id}")
    if otp_input == stored_otp:
        # ❌ 未删除OTP，可无限重复验证！
        # ❌ 应该：redis.delete(f"otp:{user_id}")
        create_session(user_id)
        return "验证成功"
```

**审计技巧**：验证成功后，立即用同一OTP再次验证，观察是否再次通过

#### 漏洞5：用户枚举（信息泄露）
```python
# ❌ 不同错误消息泄露用户存在性
@app.route('/send-otp', methods=['POST'])
def send_otp():
    user_id = request.form['user_id']
    user = User.query.filter_by(id=user_id).first()

    if not user:
        return "该用户不存在", 404  # ❌ 泄露用户不存在

    # 生成并发送OTP
    return "OTP已发送"  # 真实用户返回此消息
```

**审计技巧**：尝试已知用户和不存在用户的OTP获取，观察是否返回不同消息或状态码

#### 漏洞6：TOTP验证窗口过宽
```python
# ❌ 允许多个时间步长，增加破解几率
import pyotp

def verify_totp(secret, token):
    totp = pyotp.TOTP(secret)
    # ❌ 允许前后2个步长（30秒），有效窗口=30秒*5=150秒！
    return totp.verify(token, valid_window=2)  # 应为0或1
```

**审计技巧**：搜索`pyotp.verify()`、`valid_window`、`time_step`，确认窗口≤1

---

## 快速审计清单

### 📋 审计步骤（按优先级）

1. **定位所有OTP端点**：搜索`/verify`、`/check-otp`、`/2fa`、`/validate-token`、`/otp`
2. **检查获取端点**：`/send-otp`、`/request-otp`是否有速率限制（应≤1分钟）
3. **检查验证端点**：是否有`@limiter.limit()`或`ratelimit`装饰器
4. **检查失败存储**：搜索是否用`dict`、`session`等内存存储；应用Redis/DB
5. **检查过期时间**：OTP TTL是否≤15分钟（600-900秒）
6. **检查删除逻辑**：验证成功后是否`redis.delete()`或标记已用
7. **检查错误消息**：获取和验证的错误是否统一，不泄露用户信息
8. **检查并发会话**：同用户是否可多个OTP同时有效

### 🔴 一句话判断漏洞
```
无失败限制 || 内存存储计数 || OTP过期>15分钟 || 验证后未删除 || 错误消息泄露 → 漏洞确认
```

### ✅ 正确防护的标志
```python
# 四个关键信号都需要有：
1. 验证端点@limiter.limit("3 per minute per user")限制
2. 失败次数存Redis/DB（self.redis.incr()，非内存dict）
3. OTP TTL ≤ 15分钟（setex(..., 900)）
4. 验证成功后redis.delete()立即删除OTP
5. 统一错误消息"Invalid OTP" + HTTP 401
6. TOTP验证valid_window ≤ 1
```

---

## Classify

### ✅ 确认漏洞（满足任意一条）
| # | 漏洞特征 | 确认方法 |
|---|--------|--------|
| 1 | 验证端点无限制，可连续尝试 | Burp Intruder发送30个错误OTP，全部通过 |
| 2 | 失败次数存内存（dict、session、memory-cache） | Grep找到`failed_attempts = {}`或`cache_dict` |
| 3 | OTP有效期>15分钟（如3600秒、1小时） | 搜索`setex`或`expire`，秒数>900 |
| 4 | 验证成功后OTP未删除，可重复使用 | 验证通过后用同OTP再验一次，仍通过 |
| 5 | 错误消息泄露用户存在性 | 已知用户和虚构用户返回不同消息/状态码 |
| 6 | 无重新获取冷却，可无限快速获取OTP | `/send-otp`无限制，可秒级获取100个 |
| 7 | TOTP验证允许多个时间步长 | `valid_window=2`或更大 |

### ❌ 误报排除（全部满足才为低风险）
- ✓ 验证端点有`@limiter.limit("3 per minute per user")`或类似限制
- ✓ 失败次数存Redis/DB，使用`redis.incr()` + `redis.expire()`持久化
- ✓ OTP TTL ≤ 15分钟（setex秒数≤900）
- ✓ 验证成功后`redis.delete(f"otp:{user_id}")`立即删除
- ✓ 获取OTP端点也有限流（如1分钟1次，存Redis中）
- ✓ 3次验证失败后强制`redis.set("otp_locked:user", True, ex=900)`锁定15分钟
- ✓ 所有错误消息统一为"Invalid OTP"，不区分用户/OTP/错误

### 🟡 代码异味（需进一步验证）
- △ 验证失败仅记日志，未限制后续尝试
- △ 失败计数存`ConcurrentHashMap`或内存缓存（应改为Redis）
- △ OTP有效期5-10分钟（建议≤5分钟，最多15分钟）
- △ 删除OTP的逻辑仅在某些分支执行（异常处理可能跳过）
- △ 无审计日志（未记录所有验证尝试）
- △ 分布式环境无Redis同步，各实例各自维护失败计数

