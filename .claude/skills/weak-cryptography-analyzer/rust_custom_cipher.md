# Rust 自定义加密算法审计

## Details

### 典型代码特征
```rust
// 场景1: 手动 XOR 流密码实现
struct CustomCipher {
    key: Vec<u8>,
}

impl CustomCipher {
    fn encrypt(&self, data: &[u8]) -> Vec<u8> {
        data.iter()
            .enumerate()
            .map(|(i, &b)| b ^ self.key[i % self.key.len()])
            .collect()
    }
}

let cipher = CustomCipher { key: b"secret".to_vec() };
let encrypted = cipher.encrypt(password.as_bytes());

// 场景2: 区块链钱包自定义密钥派生
fn derive_key(seed: &[u8], index: u32) -> [u8; 32] {
    let mut key = [0u8; 32];
    for i in 0..32 {
        key[i] = seed[i % seed.len()] ^ (index as u8).wrapping_add(i as u8);
    }
    key
}

let wallet_key = derive_key(&mnemonic_bytes, account_index);

// 场景3: 自定义置换密码（Substitution Cipher）
const SBOX: [u8; 256] = [/* 手动构造的替换表 */];

fn custom_block_cipher(block: &mut [u8; 16], key: &[u8; 16]) {
    for round in 0..10 {
        for i in 0..16 {
            block[i] = SBOX[block[i] as usize] ^ key[i];
        }
        // 简单移位混淆
        block.rotate_left(1);
    }
}

// 场景4: 智能合约数据密封
pub fn seal_contract_data(data: &[u8], nonce: u64) -> Vec<u8> {
    let mut sealed = Vec::new();
    let key_stream = generate_keystream(nonce);
    for (i, &byte) in data.iter().enumerate() {
        sealed.push(byte.wrapping_add(key_stream[i % 32]));
    }
    sealed
}

fn generate_keystream(seed: u64) -> [u8; 32] {
    let mut stream = [0u8; 32];
    let mut state = seed;
    for i in 0..32 {
        state = state.wrapping_mul(1103515245).wrapping_add(12345); // LCG
        stream[i] = (state >> 16) as u8;
    }
    stream
}

// 场景5: unsafe 内存操作的"优化"加密
unsafe fn fast_encrypt(data: *mut u8, len: usize, key: u8) {
    for i in 0..len {
        *data.add(i) ^= key.wrapping_add(i as u8);
    }
}

let mut buffer = password.into_bytes();
unsafe { fast_encrypt(buffer.as_mut_ptr(), buffer.len(), 0x42) };

// 场景6: 自定义 Feistel 网络实现
fn feistel_round(left: u32, right: u32, round_key: u32) -> (u32, u32) {
    let f_output = (right ^ round_key).wrapping_mul(0x9E3779B9); // 简单 F 函数
    (right, left ^ f_output)
}

fn custom_feistel_encrypt(block: u64, key: u64) -> u64 {
    let mut left = (block >> 32) as u32;
    let mut right = block as u32;
    for round in 0..8 {
        let round_key = (key.wrapping_shr(round * 8)) as u32;
        (left, right) = feistel_round(left, right, round_key);
    }
    ((left as u64) << 32) | (right as u64)
}

// 场景7: WASM 模块中的自定义加密
#[no_mangle]
pub extern "C" fn wasm_encrypt(ptr: *mut u8, len: usize, key: u32) {
    unsafe {
        let data = std::slice::from_raw_parts_mut(ptr, len);
        for (i, byte) in data.iter_mut().enumerate() {
            *byte ^= ((key >> (i % 4) * 8) & 0xFF) as u8;
        }
    }
}

// 场景8: 嵌入式设备自定义轻量级密码
#[cfg(target_arch = "arm")]
fn embedded_cipher(data: &mut [u8], key: u16) {
    let mut lfsr = key; // Linear Feedback Shift Register
    for byte in data.iter_mut() {
        let bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) & 1;
        lfsr = (lfsr >> 1) | (bit << 15);
        *byte ^= (lfsr & 0xFF) as u8;
    }
}

// 场景9: Trait 实现自定义加密算法
trait Cipher {
    fn encrypt(&self, plaintext: &[u8]) -> Vec<u8>;
    fn decrypt(&self, ciphertext: &[u8]) -> Vec<u8>;
}

struct HomemadeCipher {
    secret: [u8; 32],
}

impl Cipher for HomemadeCipher {
    fn encrypt(&self, plaintext: &[u8]) -> Vec<u8> {
        plaintext.iter()
            .zip(self.secret.iter().cycle())
            .map(|(&p, &k)| p.wrapping_add(k).rotate_left(3) ^ k)
            .collect()
    }
    
    fn decrypt(&self, ciphertext: &[u8]) -> Vec<u8> {
        ciphertext.iter()
            .zip(self.secret.iter().cycle())
            .map(|(&c, &k)| (c ^ k).rotate_right(3).wrapping_sub(k))
            .collect()
    }
}

// 场景10: 区块链交易签名自定义哈希
fn custom_transaction_hash(tx_data: &[u8]) -> [u8; 32] {
    let mut hash = [0u8; 32];
    let mut state: u64 = 0x0123456789ABCDEF;
    
    for &byte in tx_data {
        state = state.rotate_left(5) ^ (byte as u64);
        state = state.wrapping_mul(0x517CC1B727220A95);
    }
    
    for i in 0..32 {
        hash[i] = ((state >> (i * 8)) & 0xFF) as u8;
    }
    hash
}

// 场景11: 常量时间比较未实现
fn compare_hmac(computed: &[u8], expected: &[u8]) -> bool {
    computed == expected // 非常量时间比较，易受时序攻击
}

// 场景12: 自定义流密码生成器
struct CustomStreamCipher {
    state: [u32; 4],
}

impl CustomStreamCipher {
    fn next_byte(&mut self) -> u8 {
        self.state[0] = self.state[0].wrapping_add(self.state[1]);
        self.state[1] ^= self.state[2];
        self.state[2] = self.state[2].rotate_left(7);
        (self.state[0] >> 24) as u8
    }
    
    fn encrypt(&mut self, data: &mut [u8]) {
        for byte in data {
            *byte ^= self.next_byte();
        }
    }
}

// 场景13: 零知识证明中自定义承诺方案
fn custom_commitment(value: u64, blinding: u64) -> [u8; 32] {
    let mut result = [0u8; 32];
    let combined = value ^ blinding.rotate_left(13);
    for i in 0..32 {
        result[i] = ((combined >> (i * 2)) & 0xFF) as u8;
    }
    result
}

// 场景14: P2P 网络握手自定义密钥交换
fn custom_key_exchange(my_secret: u64, peer_public: u64) -> u64 {
    // 伪 DH 实现：简单乘法而非模幂运算
    my_secret.wrapping_mul(peer_public).wrapping_add(0xDEADBEEF)
}

// 场景15: 配置文件加密（开发者自创）
fn obfuscate_config(value: &str, salt: &[u8]) -> String {
    let bytes: Vec<u8> = value.bytes()
        .enumerate()
        .map(|(i, b)| b ^ salt[i % salt.len()].wrapping_add(i as u8))
        .collect();
    base64::encode(&bytes)
}

let encrypted_db_pwd = obfuscate_config(&db_password, b"salt");
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
# XOR 操作模式
rg "\.map\(.*\^" --type rust
rg "byte \^ |data\[i\] \^" --type rust
rg "wrapping_(add|sub|mul).*\^" --type rust

# 自定义密码学关键字
rg "fn.*encrypt|fn.*cipher|fn.*seal" --type rust
rg "struct.*Cipher|trait.*Crypto" --type rust
rg "impl.*encrypt|impl.*decrypt" --type rust

# 手动实现模式
rg "rotate_left|rotate_right" --type rust | rg "encrypt|cipher"
rg "SBOX|S_BOX|substitution" --type rust
rg "round_key|feistel|permutation" --type rust

# 不安全操作
rg "unsafe.*encrypt|unsafe.*cipher" --type rust
rg "std::slice::from_raw_parts.*crypt" --type rust

# 区块链特征
rg "derive_key|wallet.*encrypt|mnemonic.*seal" --type rust
rg "transaction.*hash|block.*cipher" --type rust

# 配置/硬编码密钥
rg "const.*KEY.*=.*\[|static.*SECRET.*=" --type rust
rg "b\".*\".*encrypt|\".*\".as_bytes\(\).*\^" --type rust
```

**高危 API 模式（L2 跳读）：**
- `byte ^ key[i % key.len()]` 循环密钥 XOR
- `wrapping_add() / wrapping_mul()` 算术运算作为加密原语
- `rotate_left() / rotate_right()` 位旋转作为混淆
- `for round in 0..N { ... }` 多轮自定义变换
- `unsafe { ... }` 块内存在加密逻辑
- `impl Cipher for CustomStruct` 自定义 Trait 实现
- 手动构造 `SBOX / PBOX` 置换表
- `#[no_mangle] pub extern "C"` WASM/FFI 加密导出
- `seed.wrapping_mul(...).wrapping_add(...)` LCG/PRNG 作为密钥流
- `state.rotate_left() ^ input` 简单状态机密码
- `plaintext == ciphertext` 非常量时间比较
- `base64::encode(xored)` Base64 包装自定义加密
- `tx_data.iter().fold()` 迭代器构造哈希/签名
- 函数名含 `obfuscate / seal / protect` 但无标准库调用
- `#[cfg(target_arch)]` 嵌入式条件编译特殊实现

**函数调用链追踪（L3 逐行）：**
- 入口定位：`pub fn encrypt() / pub fn seal()` 公开接口
- 密钥来源：追踪 `key: &[u8]` 参数从何处传入
- 配置读取：`Config::load() / env::var()` 算法选择逻辑
- Trait 边界：`where T: Cipher` 泛型约束实现位置
- 宏展开：`macro_rules! define_cipher` 生成的代码
- 区块链集成：`impl Transaction::sign()` 签名算法实现
- WASM 导出：`#[wasm_bindgen]` 标注的加密函数
- FFI 边界：`extern "C" fn` 与 C/Python 交互的加密接口
- 数据库存储：`sqlx::query!()` 插入加密数据的路径
- 序列化钩子：`impl Serialize for EncryptedData` 自定义序列化
- 构造函数：`new() / from_seed()` 初始化密钥材料
- 智能合约：`#[near_bindgen] / #[ink::contract]` 链上加密逻辑
- 常量定义：`const ROUNDS: usize` / `const KEY_SIZE: usize` 算法参数
- 测试用例：`#[test]` 验证加密正确性的逻辑（可能暴露算法细节）
- 依赖检查：`Cargo.toml` 是否引入 `ring / rust-crypto / sodiumoxide`

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 硬编码密钥：`const KEY: [u8; 16] = [0x01, 0x02, ...]`
- 注释显示：`// Simple XOR cipher` / `// Toy implementation`
- 单层 XOR：无多轮变换、扩散、混淆机制
- 固定 S-Box：手动定义替换表无密码学理论支撑
- 简单 LCG：`state = a * state + c` 作为密钥流生成器
- 非常量时间：`if computed == expected` 直接比较
- Unsafe 混淆：使用 `unsafe` 仅为性能无安全增强
- 算术运算：仅 `+、-、*、^` 无非线性变换
- 静态轮数：`for _ in 0..4` 固定少量轮次

**伪保护识别（L3 逐行）：**
```rust
// 多轮 XOR 仍可逆
fn multi_round_xor(data: &[u8], key: &[u8]) -> Vec<u8> {
    let mut result = data.to_vec();
    for round in 0..100 {
        for i in 0..result.len() {
            result[i] ^= key[i % key.len()];
        }
    }
    result // 偶数轮抵消
}

// 复杂位运算无安全性
fn complex_obfuscate(byte: u8, key: u8) -> u8 {
    byte.rotate_left(3)
        .wrapping_add(key)
        .rotate_right(5)
        .wrapping_mul(0xB) // 复杂但可逆
}

// 伪随机数生成器作为密钥流
use rand::Rng;
fn generate_keystream(seed: u64) -> Vec<u8> {
    let mut rng = rand::rngs::StdRng::seed_from_u64(seed); // 可预测
    (0..256).map(|_| rng.gen()).collect()
}

// 类 AES 结构但 S-Box 自创
const CUSTOM_SBOX: [u8; 256] = [/* 无密码学依据的排列 */];
fn aes_like_round(state: &mut [u8; 16], round_key: &[u8; 16]) {
    for i in 0..16 {
        state[i] = CUSTOM_SBOX[state[i] as usize]; // 伪 SubBytes
    }
    state.rotate_left(4); // 伪 ShiftRows
    for i in 0..16 {
        state[i] ^= round_key[i]; // 伪 AddRoundKey
    }
    // 缺少真正的 MixColumns
}

// 动态密钥但派生算法弱
fn derive_key_weak(password: &str, salt: &[u8]) -> [u8; 32] {
    let mut key = [0u8; 32];
    let pwd_bytes = password.as_bytes();
    for i in 0..32 {
        key[i] = pwd_bytes[i % pwd_bytes.len()] ^ salt[i % salt.len()];
    }
    key // 无拉伸、迭代次数
}

// 常量时间声称但实现有误
fn constant_time_compare(a: &[u8], b: &[u8]) -> bool {
    let mut result = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        result |= x ^ y;
    }
    result == 0 // 短路问题：长度检查仍泄露
}

// 配置可选但默认弱算法
enum CipherType {
    Custom,  // 默认
    AES256,
}

fn encrypt_data(data: &[u8], cipher: CipherType) -> Vec<u8> {
    match cipher {
        CipherType::Custom => custom_xor_encrypt(data),
        CipherType::AES256 => aes_gcm_encrypt(data),
    }
}

let config_cipher = CipherType::Custom; // 配置未强制 AES

// 区块链项目中的"临时"方案
// TODO: Replace with RustCrypto aes-gcm after testnet
fn seal_state(data: &[u8]) -> Vec<u8> {
    custom_cipher(data, &CHAIN_SECRET)
}
```

**跨模块保护追踪（L4）：**
- `Cargo.toml` 依赖审计：
  - 缺少 `ring / aes-gcm / chacha20poly1305 / sodiumoxide`
  - 存在 `rust-crypto`（已废弃）或自维护 fork
  - `[dependencies]` 中无密码学库但有加密需求
- 配置文件检查：
  - `.env / config.toml` 中 `CIPHER_TYPE=custom`
  - `encryption.algorithm = "homemade"`
  - Feature flags：`cargo build --features=unsafe_crypto`
- 条件编译审计：
  - `#[cfg(not(feature = "std"))]` no_std 环境自定义实现
  - `#[cfg(target_arch = "wasm32")]` WASM 特殊加密路径
  - `#[cfg(test)]` 测试模式使用弱算法
- 智能合约平台：
  - NEAR Protocol：`#[near_bindgen]` 合约存储加密
  - Substrate：`decl_storage!` 宏定义加密字段
  - Solana：`#[account]` 账户数据序列化前加密
- 区块链钱包：
  - BIP39 助记词到私钥派生算法
  - Keystore 文件加密算法（JSON 格式检查）
  - HD 钱包密钥派生：非标准 `m/44'/60'/0'/0` 路径实现
- 网络协议层：
  - libp2p 自定义传输层加密（非 TLS/Noise）
  - WebSocket 握手自定义密钥交换
  - gRPC metadata 中的签名算法
- 数据库集成：
  - Diesel/SQLx ORM 加密字段实现
  - Redis 缓存值序列化前加密钩子
  - RocksDB 自定义 Comparator 加密索引
- 构建系统：
  - `build.rs` 编译期生成密钥/S-Box
  - `include_bytes!()` 嵌入加密表
  - proc-macro 生成加密代码
- 日志审计：
  - `tracing / log` 输出 "using custom cipher"
  - `debug!()` 打印密钥材料
- 文档注释：
  - `/// Security: not audited` 警告标识
  - `// HACK: temporary solution` 技术债标记

## Classify

**确认漏洞：**
- 用户密码/私钥存储使用自定义加密（任何形式）
- 区块链钱包助记词/种子密封非标准算法
- 智能合约状态加密使用自创密码
- JWT/Session Token 签名基于自定义哈希
- API 密钥/OAuth Token 自定义混淆存储
- 支付/交易签名验证使用自研算法
- P2P 网络握手密钥交换非标准协议（非 Noise/TLS）
- 零知识证明承诺方案自定义构造
- WASM 模块导出的加密函数无标准库支撑
- 嵌入式设备密码学原语自行实现
- 跨 FFI 边界的加密接口使用自定义算法
- 配置文件敏感数据（DB/API 密钥）自定义保护

**研判误报：**
- 单元测试 Mock 实现（`#[cfg(test)]` 隔离）
- 示例代码/文档测试（`examples/` 目录）
- Benchmark 对比基准（`benches/` 目录）
- 已废弃代码明确标注 `#[deprecated]` 且无调用
- 教学材料（`tutorial-*` crate）
- 第三方 crate 内部实现（非直接依赖）
- 编译条件排除的死代码（`#[cfg(not(production))]`）
- Fuzzing 测试目标简化实现（`fuzz/` 目录）

**代码异味：**
- 注释标注 "TODO: use ring crate" 无时间表
- 函数名 `secure_encrypt()` 但实现简单 XOR
- Feature flag 可选标准算法但默认自定义
- 性能理由选择自定义（"AES-NI too slow"）
- 认为"简单场景无需标准加密"
- 新旧版本不同算法无统一迁移计划
- 多层包装掩盖底层弱算法
- 区块链项目"快速上线"临时方案
- 声称"算法已内部审计"但无公开证据
- 常量时间声称但实现有缺陷

**关键判断点：**
1. **加密目标**：测试数据/日志 vs 私钥/用户凭证/金融数据
2. **密码学依据**：有无引用学术论文/标准（NIST/RFC）
3. **审计状态**：第三方密码学审计报告是否存在
4. **替代方案**：项目中是否已使用 `ring / RustCrypto / sodiumoxide`
5. **安全边界**：内网工具 vs 公链/DApp 公开部署
6. **合规需求**：金融级应用/等保认证/SOC2 是否要求
7. **攻击模型**：是否需抗量子/侧信道/时序攻击
8. **维护状态**：最后更新时间、Issue 中安全讨论
9. **社区反馈**：Crates.io 评论/GitHub Security Advisory
10. **算法复杂度**：简单 XOR vs 复杂但未证明的多轮结构

## Low risk

**可接受的低风险场景：**
- 非敏感日志脱敏（用户 ID 混淆仅内部可逆）
- 进程内临时缓存键扰动（不持久化）
- 开发环境原型（`#[cfg(debug_assertions)]` 隔离）
- 单机工具离线数据保护（明确告知用户非军事级）
- 性能测试负载生成（无真实敏感数据）
- 代码混淆/反篡改（非加密用途）
- 已公开数据的格式变换（无保密需求）

**降级条件：**
- 数据已公开或极低敏感度（公开区块链数据压缩）
- 明确过渡方案有时间表（Milestone 可查）
- 访问严格隔离（私有链 + 节点认证）
- 仅向后兼容读取，新数据用 `aes-gcm`
- 攻击窗口极短（一次性 nonce < 1min + replay 防护）
- 外层 TLS 1.3 保护（内部二次混淆）
- 攻击成本远超资产价值（量化风险评估）
- 明确非安全用途标注（README + 代码注释）
- 依赖环境约束（HSM/TEE 硬件保护）
- 多重签名/多因素认证补偿控制

**注意：** Rust 内存安全不等于密码学安全，自定义算法即使通过编译也可能存在数学漏洞（线性/差分密码分析）。`unsafe` 块可能引入侧信道泄露（缓存时序攻击）。区块链项目尤其高危：私钥泄露不可逆、智能合约漏洞无法修补。应优先使用经过审计的 crate：`ring`（BoringSSL 移植）、`RustCrypto`（纯 Rust 实现）、`sodiumoxide`（libsodium 绑定）、`chacha20poly1305`（AEAD）。嵌入式设备考虑 `crypto-bigint` + `elliptic-curve`。常量时间必须用 `subtle` crate 的 `ConstantTimeEq`。任何涉及金融、区块链、医疗、国防的系统必须经过第三方密码学审计（Trail of Bits / NCC Group / Kudelski）。低风险评级不代表长期接受，需明确责任人和迁移路线图。