# Java_MFA_Bypass_Logic

**漏洞类型**: Java Spring Security 或自定义认证中，MFA 验证逻辑有缺陷，可被绕过

---

## Details

### 代码示例

```java
public boolean validateMFA(String mfaCode) {
    if (mfaCode == null || mfaCode.isEmpty()) {
        return true;  // 允许空 code
    }
    return verifyTOTP(mfaCode);
}

// 应该: 如果用户启用了 MFA，强制验证
public boolean validateMFA(String mfaCode, User user) {
    if (user.isMFAEnabled()) {
        if (mfaCode == null || mfaCode.isEmpty()) {
            throw new InvalidMFAException();
        }
        return verifyTOTP(mfaCode);
    }
    return true;
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `validateMFA()`, `verifyMFA()`, `checkMFA()`
- `mfaCode == null`, 空值检查
- `isMFAEnabled()`, `mfa_required`

**L2 跳读定位**:
- MFA 验证路由
- 逻辑流程和分支

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 空值验证
- MFA 启用检查

**L3 逐行分析**:
- 验证入参有效性
- 检查用户 MFA 状态
- 验证失败处理

---

## Classify

确认为漏洞: 空值被接受，逻辑缺陷
误报判定: 完整的逻辑验证
代码异味: 多个验证入口

---

## Low risk

- 虽可绕过但有其他层验证
- 定期强制 MFA 重新验证
