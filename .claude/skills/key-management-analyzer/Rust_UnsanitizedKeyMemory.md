# Rust_UnsanitizedKeyMemory

**漏洞类型**：密钥内存未清理  
**适用场景**：Solana 程序、链下签名服务、密钥派生/轮换模块  
**风险等级**：High  

## Details

### 典型代码模式

```rust
// 漏洞示例1：私钥在Vec/String中直接使用后未清理
fn sign_transaction(private_key: &str) -> Signature {
    let key_bytes = hex::decode(private_key).unwrap();
    let keypair = Keypair::from_bytes(&key_bytes).unwrap();
    // 签名操作...
    signature
    // key_bytes在此作用域结束后不保证被清零
}

// 漏洞示例2：临时密钥缓冲区在栈上未显式清零
fn derive_key(seed: &[u8]) -> [u8; 32] {
    let mut temp_key = [0u8; 64];
    hkdf::extract(seed, &mut temp_key);
    // 处理密钥...
    temp_key[..32].try_into().unwrap()
    // temp_key残留在栈上直到被覆盖
}

// 漏洞示例3：密钥在结构体字段中未实现Drop清理
struct KeyManager {
    master_key: Vec<u8>,
    derived_keys: HashMap<String, Vec<u8>>,
}
```

### 快速定位核心操作（审计等级：L2-L3）

**关键函数扫描**（L2）：
- 密钥派生：`derive_*`, `hkdf::`, `pbkdf2::`, `Keypair::from_*`
- 签名操作：`sign`, `Keypair::sign`, `Signer::sign`
- 密钥导入/解析：`from_bytes`, `from_seed`, `SecretKey::from_*`

**内存容器识别**（L3）：
- 危险容器：`Vec<u8>`, `String`, `Box<[u8]>`, `[u8; N]` 存储密钥材料
- 临时变量：`let mut key_buffer`, `let private_key`, `temp_*`
- 结构体字段：包含 `key`, `secret`, `seed`, `master` 命名的字段

**作用域追踪**（L3）：
- 检查密钥变量的生命周期结束前是否调用清零函数
- 关注提前 `return` 或 `?` 错误传播路径上的清理逻辑
- 注意密钥 clone 或传递到其他函数后的原始副本处理

### 快速定位保护机制（审计等级：L1-L4）

**安全库关键词**（L1）：
- `zeroize::Zeroize`, `zeroize::Zeroizing`
- `secrecy::Secret`, `secrecy::SecretVec`
- `memsec::memzero`, `sodiumoxide::utils::memzero`

**Drop实现检查**（L3）：
```rust
// 寻找自定义Drop trait实现
impl Drop for KeyManager {
    fn drop(&mut self) {
        self.master_key.zeroize(); // 检查是否存在
    }
}
```

**跨模块密钥传播**（L4）：
- 追踪密钥返回给调用方后的处理：函数返回 `Vec<u8>` 或 `[u8; N]`
- 检查序列化场景：密钥是否被 `serde::Serialize` 到临时缓冲区
- 异步上下文：密钥在 `tokio::spawn` 或跨 `await` 点的生命周期管理

**编译器标记**（L2）：
- 查找 `#[must_use]` 或 `#[inline(never)]` 防止优化清零代码
- 检查是否禁用编译器优化：`core::sync::atomic::compiler_fence`

## Classify

### 确认为漏洞

1. **密钥容器无清理机制**：使用 `Vec`/`String`/数组存储私钥且无 `zeroize()` 或等效清零操作
2. **结构体缺失Drop**：密钥作为结构体字段但未实现 `Drop` trait 进行主动清理
3. **错误路径遗漏清理**：正常流程有清理但 `panic!` 或 `Result::Err` 分支缺失（除非使用 `Zeroizing` 包装器）
4. **密钥跨异步边界**：密钥在 `async` 函数中使用且可能在 `await` 时长期驻留内存

### 误报情况

1. **已使用安全库**：代码通过 `secrecy::Secret<T>` 或 `Zeroizing<T>` 包装密钥，自动保证析构时清零
2. **硬件密钥隔离**：密钥从未进入应用内存，全程使用 HSM/SGX/Secure Enclave API 操作
3. **编译期密钥**：仅在编译时生成公钥地址（如 `const` 或 `static` 公钥），私钥不在运行时存在

### 代码异味

1. **过度依赖编译器行为**：手动 memset 但未添加 `compiler_fence`，可能被优化消除
2. **部分清理**：仅清理主密钥但忽略派生密钥或中间状态
3. **清理时机延迟**：密钥在缓存或全局状态中保留超过必要时长（虽有清理但窗口期过长）

## Low risk

1. **瞬态测试密钥**：单元测试或开发环境的硬编码测试密钥，明确标注为非生产用途
2. **公钥材料**：仅存储公钥、地址或哈希而非私钥材料
3. **只读代理**：密钥存储在外部安全模块，应用仅持有句柄或引用ID而非实际密钥字节
4. **加密后的密钥**：内存中仅存储经过 KEK（Key Encryption Key）加密的密钥 blob，且 KEK 本身有清理机制
5. **短生命周期局部变量**：密钥仅在栈上存在微秒级（如立即用于单次签名后函数返回），且进程运行在内存隔离环境（如 SGX enclave）
