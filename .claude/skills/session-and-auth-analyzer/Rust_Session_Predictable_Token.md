# Rust_Session_Predictable_Token

**漏洞类型**: Rust Actix Session 中会话令牌生成使用可预测的随机数，导致令牌可被预测

---

## Details

### 代码示例

```rust
use rand::Rng;
fn generate_session_token() -> String {
    let mut rng = rand::thread_rng();
    format!("{}", rng.gen_range(0..1_000_000))  // 仅 100 万种
}

// 修复
fn generate_session_token() -> String {
    use rand::rngs::OsRng;
    let bytes: [u8; 32] = OsRng.gen();
    hex::encode(bytes)
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- `rand::thread_rng()`, `gen_range()`
- `OsRng`, `StdRng`
- 令牌生成函数

**L2 跳读定位**:
- RNG 使用位置

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- `OsRng` 使用

**L3 逐行分析**:
- >= 32 字节随机数
- 使用密码学 RNG

---

## Classify

确认为漏洞: 使用 `thread_rng()` 生成短令牌
误报判定: 使用 `OsRng` 生成长令牌

---

## Low risk

- 虽可预测但有验证机制
