# C/C++ 账户锁定机制绕过漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)  
- **审计时间：** 20-30分钟

## 🚀 30秒快速清单
- [ ] 账户锁定时间是否足够长（≥15分钟）？
- [ ] 是否仅按账户计数，未考虑IP？
- [ ] 用户能否手动解锁账户？
- [ ] 多个登录端点是否有一致的锁定机制？

## Details

### 漏洞成因
账户锁定机制旨在防御暴力破解攻击，但实现不当时可被绕过。核心问题包括：锁定时间过短无法有效延缓攻击、仅追踪账户而忽略来源IP导致攻击者可分散目标、锁定状态检查不一致使攻击者利用不同入口点、以及锁定解除机制缺乏额外验证。

### 代码示例

```c
// 典型缺陷：锁定时间过短（30秒）
typedef struct {
    char username[64];
    int failed_attempts;
    time_t locked_until;
} UserAccount;

bool check_login(const char* username, const char* password) {
    UserAccount* user = get_user(username);
    
    // 检查锁定状态
    if (user->locked_until > time(NULL)) {
        return false;  // 账户已锁定
    }
    
    if (verify_password(user, password)) {
        user->failed_attempts = 0;  // 重置计数
        return true;
    }
    
    // 失败计数递增
    user->failed_attempts++;
    if (user->failed_attempts >= 5) {
        user->locked_until = time(NULL) + 30;  // 仅锁定30秒！
    }
    
    return false;
}
```

```c
// 绕过方式1：仅按账户计数，未关联IP
// 攻击者可以分布式扫描不同账户
bool authenticate(const char* username, const char* password) {
    UserAccount* user = find_user(username);
    
    if (user->is_locked) {
        return false;
    }
    
    if (!verify_credentials(user, password)) {
        user->login_failures++;
        if (user->login_failures >= MAX_ATTEMPTS) {
            user->is_locked = true;  // 未记录攻击来源IP
        }
        return false;
    }
    
    return true;
}
// 攻击场景：攻击者针对1000个账户各尝试4次，总共4000次尝试无锁定
```

```c
// 绕过方式2：用户可通过邮件/短信自助解锁
void handle_unlock_request(const char* username, const char* code) {
    UserAccount* user = get_user(username);
    
    // 仅验证邮件中的6位数字码
    if (strcmp(user->unlock_code, code) == 0) {
        user->is_locked = false;
        user->failed_attempts = 0;  // 攻击者可通过邮箱劫持无限重试
    }
}
```

```cpp
// 绕过方式3：多登录端点计数不一致
// API端点 /api/login
bool api_login(const string& username, const string& password) {
    if (check_account_locked(username)) {
        return false;
    }
    
    if (verify_password(username, password)) {
        return true;
    }
    
    increment_failure_count(username);  // 更新数据库
    return false;
}

// Web端点 /web/signin（独立实现）
bool web_signin(const string& username, const string& password) {
    User user = load_user_from_cache(username);  // 从缓存读取
    
    // 问题：未检查全局锁定状态！
    if (hash(password) == user.password_hash) {
        return true;
    }
    
    return false;  // 未更新失败计数
}
// 攻击场景：在API端点被锁定后切换到Web端点继续攻击
```

```c
// 绕过方式4：锁定状态竞态条件
bool concurrent_login_check(const char* username, const char* password) {
    int failures = get_failure_count(username);
    
    if (failures >= MAX_ATTEMPTS) {
        return false;  // 检查时刻未达到阈值
    }
    
    // 时间窗口：多个线程可能同时执行到此
    if (!verify_password(username, password)) {
        failures = increment_failure_count(username);  // 非原子操作
        // 可能导致实际尝试次数远超阈值才触发锁定
        return false;
    }
    
    return true;
}
```

```c
// 绕过方式5：锁定状态存储不持久
static struct {
    char username[64];
    int failures;
    time_t lock_time;
} login_cache[1024];  // 仅内存存储

// 重启服务后所有锁定状态丢失
bool login_with_cache(const char* username, const char* password) {
    int idx = hash(username) % 1024;
    
    if (login_cache[idx].lock_time > time(NULL)) {
        return false;
    }
    
    // ... 验证逻辑
}
// 攻击场景：触发服务重启（如通过其他漏洞）清空锁定状态
```

### 快速定位核心操作
- **关键词扫描**：`lock`, `locked`, `fail`, `attempt`, `retry`, `ban`, `block`, `throttle`, `cooldown`
- **计数器追踪**：搜索 `failed_attempts`, `login_count`, `retry_count` 等变量
- **时间检查**：`time()`, `clock_gettime()`, `expired`, `until`, `duration`
- **认证端点**：`login`, `signin`, `auth`, `authenticate`, `verify_password` 函数
- **数据存储**：检查锁定状态存储位置（内存/数据库/Redis）
- **IP关联**：搜索 `getpeername()`, `inet_ntoa()`, `remote_addr`, `client_ip`

### 快速定位保护机制
- **时间验证**：锁定时长计算 `locked_until - current_time >= THRESHOLD`
- **IP绑定**：`struct sockaddr_in`, IP黑名单/白名单机制
- **持久化**：数据库事务、Redis INCR、日志审计
- **分布式同步**：集群间状态共享（memcached, Redis, 数据库）
- **全局限流**：`iptables`, `fail2ban`, WAF规则
- **渐进延迟**：指数退避算法（1s, 2s, 4s, 8s...）
- **额外验证**：CAPTCHA、MFA强制启用、邮件/短信二次确认

### 审计等级判定

| 等级 | 场景 | 审计策略 |
|------|------|----------|
| **L0** | 内部管理系统、单用户环境 | 快速检查是否有基本锁定 |
| **L1** | 有基本锁定（5次/15分钟）且单入口 | 验证时长、阈值配置 |
| **L2** | 多端点登录或API认证 | 跨模块追踪计数一致性 |
| **L3** | 高价值目标（金融/管理后台） | 逐行审查绕过可能性、测试并发场景 |
| **L4** | 分布式架构、微服务认证 | 全链路追踪、压测验证、检查服务间同步机制 |

---

## Classify

### 确认漏洞（需满足以下任一条件）
1. **时间阈值不足**：锁定时长 < 5分钟，无法有效延缓暴力破解
2. **计数维度单一**：仅按账户计数，未结合IP/设备指纹，可横向分散攻击
3. **状态可重置**：用户可无额外验证地解锁账户（如仅通过邮件链接）
4. **实现不一致**：多个认证端点（API/Web/Mobile）锁定逻辑不同步
5. **非原子操作**：并发场景下计数器更新存在竞态，可超阈值尝试

**典型漏洞特征**：
- 锁定时间 < 300秒（5分钟）
- 失败次数阈值 > 10次
- 计数器仅存储在内存中，服务重启后清空
- 锁定检查与计数更新使用不同数据源（缓存vs数据库）
- 解锁接口无需重新认证或仅需弱验证（6位纯数字）
- SQL查询未使用事务或行锁：`UPDATE users SET failures=failures+1 WHERE id=?`
- 不同登录路径使用独立的session/cookie验证
- IP地址从 `X-Forwarded-For` 等可伪造头部获取

### 误报排除
- ✗ 锁定时长 ≥ 15分钟且有IP级限制（符合OWASP建议）
- ✗ 强制启用MFA后的锁定机制（已有额外防护层）
- ✗ 内部管理系统且限制IP白名单访问
- ✗ 使用硬件密钥/证书认证的场景（不依赖密码）
- ✗ 已部署专业防护（fail2ban, WAF规则, 验证码）
- ✗ 测试/演示环境的简化实现（明确标注非生产代码）

### 代码异味（需进一步验证）
- △ 锁定时长在5-15分钟之间（勉强可接受但不理想）
- △ 有IP追踪但未持久化（仅在内存中）
- △ 失败阈值为5-10次（需结合实际场景判断）
- △ 使用Redis但未设置过期时间（可能导致永久锁定）
- △ 解锁需要邮件验证但邮箱未做二次确认（邮箱劫持风险）
- △ 日志记录失败尝试但无告警机制

---

## Low Risk

### 给予低风险评级的场景

1. **已有多层防御**
   - 前置WAF/CDN已实施IP级速率限制
   - 强制启用CAPTCHA（每3次失败后）
   - 所有账户已强制绑定MFA
   - 部署了专业入侵检测系统（如fail2ban）

2. **锁定时间接近安全阈值**
   - 锁定时长为10-15分钟（虽未达最佳实践但有一定防护）
   - 失败阈值为3-5次（相对保守）
   - 有渐进式延迟机制（如3次后1分钟，5次后5分钟，10次后1小时）

3. **攻击成本极高**
   - 账户名为邮箱格式且需邮箱验证激活（攻击者难以批量注册）
   - 密码策略强制16位+特殊字符（暴力破解空间巨大）
   - 登录需要设备指纹+生物识别（移动APP场景）

4. **业务特性限制**
   - B2B系统且客户总数 < 100（攻击面小）
   - 仅内网访问且有VPN二次认证
   - 账户创建需人工审批（无法批量注册攻击）

5. **已有监控补偿**
   - SOC团队7x24实时监控异常登录
   - 每小时生成失败登录报告并自动告警
   - 有人工审查流程处理可疑账户
   - 金融级审计日志且不可篡改

6. **影响范围有限**
   - 受攻击账户为低权限用户（如只读访客）
   - 系统不涉及资金、敏感数据
   - 成功登录后还有二次授权（如操作需审批）

**评级建议**：即使为低风险，也应在报告中明确指出锁定机制的具体缺陷，建议按OWASP标准加固（15分钟锁定 + IP限制 + 日志审计）。对于高价值系统，任何账户锁定绕过都应视为中危及以上。
