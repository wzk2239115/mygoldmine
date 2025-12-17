# Rust_MFA_Verification_Bypass

**漏洞类型**: Rust 多因素认证实现中，MFA 令牌验证逻辑可被绕过，导致 MFA 验证可被跳过

---

## Details

### 代码示例

```rust
fn verify_mfa(code: &str, secret: &str) -> bool {
    // 缺少时间窗口检查
    let computed = compute_totp(secret);
    code == computed  // 逻辑过于简单
}

// 应该包含时间窗口: 当前 ± 30 秒
fn verify_with_window(code: &str, secret: &str) -> bool {
    for i in [-1, 0, 1] {
        let time_window = (SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs() / 30) + i;
        // 计算该时间窗口的 TOTP
    }
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `verify_mfa()`, `check_totp()`, `validate_code()`
- TOTP 库: `totp_rs`, `oath`
- 时间检查: 缺失时间窗口验证

**L2 跳读定位**:
- MFA 验证函数
- 令牌生成和验证流程

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 时间窗口检查
- 使用成熟的 TOTP 库

**L3 逐行分析**:
- 验证时考虑时间窗口 (± 1)
- 检查码长度和格式
- 限制验证尝试次数

---

## Classify

确认为漏洞: 无时间窗口检查或逻辑缺陷
误报判定: 使用成熟库，时间窗口正确
代码异味: 自定义 TOTP 实现

---

## Low risk

- 虽可绕过但有其他认证层
- 实时监控异常 MFA 使用
