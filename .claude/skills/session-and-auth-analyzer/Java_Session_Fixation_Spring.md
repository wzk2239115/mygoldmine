# Java_Session_Fixation_Spring

**漏洞类型**: Spring Security 中会话ID在用户登录前后保持不变，存在会话固定风险

---

## Details

### 代码示例

```java
// 不安全: 登录前后 ID 不变
@PostMapping("/login")
public String login(Authentication auth) {
    // SecurityContextHolder 已设置，但 session ID 未更新
    return "redirect:/dashboard";
}

// 修复: 明确更新 session ID
@PostMapping("/login")
public String login(HttpServletRequest request) {
    request.changeSessionId();  // 更新 session ID
    // 或在配置中启用
    return "redirect:/dashboard";
}

// 配置方式
@Bean
public SecurityFilterChain filterChain(HttpSecurity http) {
    http.sessionManagement()
        .sessionFixationProtection(SessionFixationProtection.MIGRATE_SESSION);
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `changeSessionId()`, `MIGRATE_SESSION`
- 登录处理代码
- SessionManagement 配置

**L2 跳读定位**:
- 登录流程
- Spring Security 配置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- `changeSessionId()` 调用
- `sessionFixationProtection` 配置

**L3 逐行分析**:
- 登录后调用 `changeSessionId()`
- 配置正确的防护策略

---

## Classify

确认为漏洞: 登录后 ID 不变
误报判定: ID 已更新或自动保护

---

## Low risk

- 虽可固定但需要攻击者先访问
- 有其他防护
