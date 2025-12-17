# C/C++ CSRF Token 跨会话复用漏洞

## Details

### 漏洞成因
在某些 C/C++ Web 框架或自研实现中，CSRF Token 生成后存储在全局变量、共享内存或静态数组中，未与用户会话 ID 绑定。所有用户共享同一个 Token，或 Token 在会话间可复用，攻击者可通过窃取或猜测 Token 直接伪造请求。问题常见于手动实现 CSRF 防护但缺乏会话管理机制。

### 代码示例

**易受攻击的代码：**
```cpp
std::string globalCsrfToken;

void initToken() {
    if (globalCsrfToken.empty()) {
        globalCsrfToken = generateRandomToken(); // 仅一次
    }
}

bool validateToken(const std::string& token) {
    return token == globalCsrfToken; // 所有用户共享
}
```

**另一个不安全示例（共享内存）：**
```cpp
SharedMemory<std::string> csrfTokenStorage("csrf_token");

void storeToken(const std::string& token) {
    csrfTokenStorage.set(token); // 未区分 session
}

bool checkToken(const std::string& token) {
    return csrfTokenStorage.get() == token;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 全局变量：`static std::string csrfToken`, `global`, `Singleton`
- 共享存储：`SharedMemory`, `shm`, `memcached`, `redis.set("csrf"`
- 会话操作：`session.get`, `request.cookie("session")`

**定位步骤：**
1. 搜索 Token 存储是否与 session 相关。
2. 检查验证函数是否比较当前用户的 Token。
3. 跳读（L2）确认 Token 是否在登录/注销时刷新。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **会话绑定**：Token 与 session ID、user ID 组合存储。
- **一次性**：成功使用后删除或更新。
- **并发安全**：多线程环境中 Token 存储隔离。
- **过期策略**：定期刷新 Token。

**定位技巧：**
- 注意 Token 是否保存在 cookie 中且未验证 Cookie 与 Token 一致。
- 检查多服务器部署，是否使用共享存储导致覆盖。
- 评估 Token 是否通过 URL 或日志泄露给其他用户。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Token 与会话强绑定 | **L0（快速跳过）** | 风险低 |
| Token 全局复用 | **L3（逐行读）** | 高风险 |
| Token 可跨用户重复使用 | **L4（跨模块追踪）** | 极高风险 |
| Token 刷新不及时 | **L2（跳读）** | 需优化 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. Token 对所有用户或多个用户共享。
2. 验证未结合当前会话/用户信息。
3. 攻击者可利用他人 Token 发起 CSRF。

#### 误报
以下情况非漏洞：
1. Token 使用双重提交 Cookie 并检查一致性。
2. 应用为无状态 API，不依赖 Cookie。
3. Token 仅用于内部 API 调用并通过签名授权。

#### 代码异味
需记录：
1. Token 保存在静态变量，服务重启后才刷新。
2. Token 与 session 绑定但 session ID 可被固定或预测。
3. Token 通过 `?token=` 形式在 URL 中传递。
4. Token 使用弱随机源，易被暴力猜测。

## Low risk

### 低风险评级场景

#### 1. 内部系统 + 访问控制
- **场景：** 仅受控网络访问。
- **风险评估：** 攻击面有限，但建议修复。

#### 2. 二次验证
- **场景：** 敏感操作需额外确认。
- **风险评估：** 提高攻击成本，仍需绑定会话。

#### 3. SameSite=Strict Cookie
- **场景：** 设置 Strict 减少跨站请求。
- **风险评估：** 部分缓解，但不替代修复。

#### 4. Token 短期有效
- **场景：** Token 定期刷新并记录使用。
- **风险评估：** 可降低窗口，但需根本解决。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 | 攻击面有限 | 中 |
| 二次验证 | 提高攻击成本 | 中 |
| SameSite=Strict | 浏览器缓解 | 低 |
| Token 快速刷新 | 缩短窗口期 | 中 |

