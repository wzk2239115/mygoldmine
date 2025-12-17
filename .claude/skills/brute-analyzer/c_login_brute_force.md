# C/C++ 登录接口未实现速率限制

## 基本信息
- **难度等级：** ★★☆☆☆ | **审计时间：** 15-25分钟
- **关键词搜索：** `login`, `auth`, `password`, `authenticate`, `rate`, `limit`, `attempt`, `/api/login`
- **快速检查：** 是否有频率检查、失败计数、账户锁定、验证码防护

## 漏洞成因
速率限制是防御暴力破解的第一道防线。C/C++网络服务若未对请求频率、来源IP、失败次数限制，攻击者可利用自动化工具（hydra/hashcat）高速枚举密码。核心问题：完全缺失频率检查、仅客户端限制、计数器竞态条件、分布式不同步、IP伪造绕过。

### 常见漏洞模式

**无防护登录**：直接验证密码无任何速率限制
```c
int handle_login(const char* username, const char* password) {
    User* user = db_find_user(username);  // 无速率限制
    if (!user) return ERR_USER_NOT_FOUND;
    if (strcmp(user->password_hash, hash_password(password)) == 0) {
        create_session(user);
        return SUCCESS;
    }
    return ERR_INVALID_PASSWORD;  // 立即返回，无延迟记录
}
```

**客户端限制**：仅前端有限制，服务端不验证
```c
void http_post_login(int client_socket, const char* body) {
    json_t* data = parse_json(body);  // 前端限制了,但服务端完全信任
    if (authenticate(json_get_string(data, "username"),
                    json_get_string(data, "password"))) {
        send_response(client_socket, "200 OK", "Login successful");
    }  // 攻击者: curl绕过浏览器直接发送请求
}
```

**IP伪造绕过**：从可伪造HTTP头获取IP
```c
const char* get_client_ip(const char* http_header) {
    const char* forwarded = get_header(http_header, "X-Forwarded-For");
    return forwarded ? forwarded : "0.0.0.0";  // 可被伪造,每次改造头值即绕过限制
}
```

**多端点不一致**：部分端点有限制，部分无
```c
// /api/v1/login - 有限制  |  /legacy/auth - 无限制 → 切换端点绕过
// /login, /oauth/password, /sso/auth 需全覆盖
```

**竞态条件**：非原子计数器更新
```c
if (counters[idx].request_count >= 10) return false;
counters[idx].request_count++;  // RACE: 多线程可同时通过检查后都++,绕过限制
```

**分布式不同步**：本地内存存储，多服务器各自计数
```c
// LB轮询: 服务器A允许10次,B也允许10次 → 攻击者轮流请求,共20次通过
```

### 审计检查清单（按优先级）

| 优先级 | 检查项 | 审计方法 |
|--------|--------|---------|
| **P0** | **无速率限制** | grep `handle_login\|do_auth` 检查内部是否有 `count\|time\|limit` 相关逻辑；空白函数直接return即漏洞 |
| **P0** | **IP获取方式** | 搜索 `X-Forwarded-For\|X-Real-IP\|getpeername` ；调用可伪造头即漏洞 |
| **P1** | **多端点遗漏** | 搜索所有认证相关函数 `/login\|/auth\|/oauth\|/sso\|password_reset` ；即使一个端点无限制也是漏洞 |
| **P1** | **竞态条件** | 搜索 `count++\|attempt++` ，检查是否被 `mutex\|_Atomic` 保护；未保护即为漏洞 |
| **P1** | **分布式同步** | 搜索 `local_counter\|static.*count` ；多服务器仅本地存储即漏洞 |
| **P2** | **延迟防护** | 搜索 `usleep\|sleep\|delay` ；无延迟或延迟<100ms为不足 |
| **P2** | **锁定机制** | 搜索 `locked_until\|account_lock\|lockout` ；无锁定或<15分钟为不足 |
| **P3** | **CAPTCHA防护** | 搜索 `captcha\|verify_code` ；失败3次后无强制验证为可选加强 |

### 审计等级判定

| 等级 | 特征 | 审计重点 |
|------|------|---------|
| **L0** | 本地CLI、无网络接口、内部工具 | **跳过**速率限制检查 |
| **L1** | 有简单计数器但无防护机制 | 验证阈值≥10次/分钟；检查是否被绕过 |
| **L2** | 单服务器+基础限制，多端点 | **关键**: 端点间限制一致性；遍历所有路由 |
| **L3** | 多线程/高并发，有锁保护 | 编译代码，检查原子操作正确性；并发压测 |
| **L4** | 分布式/LB+缓存，有Redis同步 | 跨节点限制验证；测试LB轮询绕过；Redis过期时间 |

---

## 漏洞判定

### 确认漏洞（三个条件全部满足）
1. 存在网络可访问的认证端点（HTTP GET/POST）
2. 无速率限制、失败计数、IP限制、账户锁定
3. 支持自动化暴力破解（无验证码、无延迟或延迟<50ms）

### 典型漏洞特征（满足任一项即确认）
- ✗ 无 `time()` 或计数器相关检查
- ✗ IP从 `X-Forwarded-For` 等可伪造头获取（不使用 `getpeername()`）
- ✗ 计数器非原子（`counter++` 未被 `mutex/_Atomic` 保护）
- ✗ 多端点防护不一致（部分无限制）
- ✗ 分布式仅本地内存存储（未同步Redis）
- ✗ 客户端限制，服务端不验证

### 安全排除（任一项充分）
- ✓ IP限制：10-20次/分钟 + 源IP有效认证（非可伪造头）
- ✓ 账户锁定：≥3次失败后锁定≥15分钟
- ✓ 强制验证码：3次失败后必须验证码
- ✓ MFA/2FA启用：不可绕过的第二因素
- ✓ WAF防护：ModSecurity/fail2ban全局限流且生效
- ✓ 非密码认证：仅支持证书/OIDC等，无密码认证
- ✓ 内部网络+白名单：网络隔离+IP白名单+mTLS

### 灰色判定（风险较低但需注意）
- ⚠ 限制过高（>50次/分钟）或延迟过短（<100ms）
- ⚠ 仅基于IP或仅基于账户（应同时限制）
- ⚠ Redis无过期时间配置（内存泄漏）
- ⚠ 多线程竞态但未完全验证原子性

---

## 安全实现（快速参考）

### 核心方案：IP+账户双重限制+原子操作+锁定

```c
// 关键配置
#define IP_LIMIT 10       // IP: 10次/分钟
#define ACCT_LIMIT 5      // 账户: 5次/分钟
#define LOCKOUT_SEC 900   // 锁定: 15分钟

// 关键函数（仅框架，非完整代码）
const char* get_real_ip(int socket_fd) {
    struct sockaddr_in addr;
    socklen_t len = sizeof(addr);
    // ✓ 使用getpeername()而非X-Forwarded-For
    getpeername(socket_fd, (struct sockaddr*)&addr, &len);
    return inet_ntoa(addr.sin_addr);
}

bool check_rate_limit(const char* key, int max_requests) {
    // ✓ 使用Redis/Memcached进行分布式存储
    // ✓ 时间窗口: 滑动窗口或固定窗口(≥60秒)
    // ✓ 原子操作: 使用_Atomic或mutex保护
    // ✓ 失败3次自动延迟200ms,5次锁定15分钟
    RateLimitEntry* entry = redis_get(key);
    if (entry->locked_until > time(NULL)) return false;
    if (entry->count >= max_requests) {
        redis_set(key, {locked: now+900});
        return false;
    }
    // ✓ 原子增加计数
    atomic_fetch_add(&entry->count, 1);
    return true;
}

int secure_login(int sock, const char* user, const char* pass) {
    const char* ip = get_real_ip(sock);

    // ✓ IP限制
    if (!check_rate_limit(ip, IP_LIMIT)) return ERR_RATE_LIMIT;

    // ✓ 账户限制
    if (!check_rate_limit(user, ACCT_LIMIT)) return ERR_LOCKED;

    // ✓ 密码验证(bcrypt延迟>100ms天然防护)
    User* u = db_find_user(user);
    if (!u || !bcrypt_verify(pass, u->hash)) {
        usleep(150000);  // 延迟,同时不拒绝请求
        return ERR_INVALID;
    }

    return SUCCESS;  // 成功后在check_rate_limit重置计数
}
```

### 实现检查清单
- [ ] 使用 `getpeername()` 获取真实IP，不信任 `X-Forwarded-For`
- [ ] 双重限制：IP + 账户名（同时生效）
- [ ] 原子操作或互斥锁保护计数器
- [ ] 时间窗口≥60秒（滑动或固定）
- [ ] 失败3次自动延迟≥200ms，5次锁定≥900秒
- [ ] 分布式使用Redis存储（设置过期时间），不用本地内存
- [ ] 所有认证端点均应用限制（/login, /api/auth, /oauth, 等）
- [ ] 审计日志记录所有失败/锁定事件（IP+账户+时间）

---

## 修复优先级

1. **立即修复**：添加IP+账户双重速率限制，禁止密码暴力破解
2. **本周修复**：使用原子操作/互斥锁+Redis同步，防竞态和分布式绕过
3. **可选加强**：CAPTCHA验证(3次失败)+审计日志+告警
4. **长期优化**：MFA/2FA二次认证，替代密码认证
