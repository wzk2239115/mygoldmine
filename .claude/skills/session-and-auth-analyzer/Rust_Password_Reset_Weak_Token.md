# Rust_Password_Reset_Weak_Token

**漏洞类型**: Rust 密码重置功能中，重置令牌使用不安全的生成算法或熵值不足，导致令牌可被预测或枚举

---

## Details

### 代码示例

**易受攻击的代码模式**:
```rust
// 示例1: 使用 rand crate 的非密码学 RNG
use rand::Rng;
fn generate_reset_token() -> String {
    let mut rng = rand::thread_rng();
    format!("{}", rng.gen_range(0..1_000_000))
    // 仅 100 万种可能，可被枚举
}

// 示例2: 使用系统时间作为种子
use std::time::{SystemTime, UNIX_EPOCH};
fn weak_token_generation() -> String {
    let seed = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    format!("{:x}", seed)
}

// 示例3: UUID 但可预测
use uuid::Uuid;
fn generate_token() -> String {
    Uuid::new_v4().to_string()
    // 默认可能不使用密码学 RNG
}

// 示例4: 使用非密码学哈希
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
fn hash_based_token(input: &str) -> String {
    let mut hasher = DefaultHasher::new();
    input.hash(&mut hasher);
    format!("{:x}", hasher.finish())
}

// 示例5: 令牌长度过短
fn short_token_generation() -> String {
    let bytes: Vec<u8> = vec![0; 4]; // 仅 4 字节，32 位
    hex::encode(bytes)
}

// 示例6: rand 的 gen_range 可预测性
fn predictable_range() -> String {
    let mut rng = rand::thread_rng();
    let token = rng.gen_range(10000..99999);
    format!("{}", token)
}

// 示例7: 缺少加密 RNG 导入
// 未使用 rand::rngs::OsRng 或 rand_chacha
fn generate_insecure() -> String {
    let random = rand::random::<u32>();
    format!("{}", random)
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 弱 RNG: `rand::thread_rng()`, `rand::random()`, `gen_range()`, `DefaultHasher`
- 密码学 RNG: `rand::rngs::OsRng`, `rand_chacha`, `StdRng`
- 令牌生成: `generate_reset_token()`, `create_token()`, `gen_token()`
- 时间相关: `SystemTime`, `UNIX_EPOCH`, `as_secs()` 用于令牌
- UUID: `uuid::Uuid::new_v4()`, 检查是否使用了安全 RNG

**L2 跳读定位**:
- 令牌生成函数: 搜索重置令牌相关的函数
- RNG 导入: 检查使用的随机数生成库
- 令牌长度: 生成的令牌是否足够长
- 使用位置: 令牌如何被发送和验证

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- OsRng 使用: `use rand::rngs::OsRng`, `OsRng.fill_bytes()`
- 密码学库: `ring`, `sodiumoxide`, `sha2`
- 令牌长度: >= 16 字节 (128 bits)

**L3 逐行分析**:
- RNG 源:
  - 是否使用 `rand::rngs::OsRng` 或系统 RNG
  - 是否使用了 `StdRng` 而非 `thread_rng`
  - 是否使用 `crypto` 相关的库
  - 种子是否来自安全源
- 令牌大小:
  - 生成字节数是否 >= 16 (128 bits)
  - 编码格式是否保留完整熵值 (hex, base64)
- 哈希使用:
  - 是否用了非密码学哈希 (DefaultHasher 不安全)
  - 是否应该使用 SHA-256 等安全哈希
  - 哈希输入是否包含随机成分
- UUID 实现:
  - Uuid::new_v4() 是否使用了安全 RNG
  - 是否指定了 RNG 类型

**L4 跨模块追踪**:
- 检查所有 rand 库的版本和使用方式
- 验证是否有专门的 token 生成库 (lettre, JWT 库等)
- 检查是否有统一的令牌生成函数
- 审查 Cargo.toml 中的依赖版本

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 使用 `rand::thread_rng()` 或 `random()` 生成令牌
- 令牌由时间戳或可预测源生成
- 令牌长度 < 16 字节
- 使用 DefaultHasher 等非密码学哈希生成令牌
- 令牌范围小于 2^128

**误报判定**:
- 使用 `OsRng` 生成足够长的随机令牌 (>= 128 bits)
- 使用密码学安全的库 (ring, sodiumoxide)
- 令牌编码完整保留熵值
- 应用有额外的令牌验证机制

**代码异味**:
- 导入了 OsRng 但实际使用了 thread_rng
- 令牌长度在 8-15 字节之间
- 使用哈希但其输入包含可预测元素
- 有注释提到"应该使用安全 RNG"但未实现

---

## Low risk

### 低风险场景

**令牌验证**:
- 令牌验证时需要数据库查询和签名验证
- 即使令牌被预测，验证会失败

**访问限制**:
- 令牌仅在邮箱中传输，用户才能获得
- 有速率限制防止暴力枚举

**时间限制**:
- 令牌过期时间极短 (如 15 分钟)
- 重置后自动登出所有会话
