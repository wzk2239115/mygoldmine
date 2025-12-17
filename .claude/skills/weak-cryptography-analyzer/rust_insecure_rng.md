# Rust 不安全随机数生成器审计

## Details

### 典型代码特征
```rust
// 场景1: thread_rng 用于密钥生成（伪随机，可预测）
use rand::{thread_rng, Rng};
let mut rng = thread_rng();
let mut key = [0u8; 32];
rng.fill(&mut key);  // 密码学密钥应用 OsRng
wallet.encrypt_seed(&key);

// 场景2: StdRng/SmallRng 生成 nonce（确定性种子）
use rand::rngs::StdRng;
use rand::{SeedableRng, RngCore};
let mut rng = StdRng::seed_from_u64(12345);  // 固定种子
let nonce = rng.next_u64();
cipher.encrypt_with_nonce(data, nonce);

// 场景3: 区块链私钥派生用 ChaCha8Rng（快速但非 CSPRNG）
use rand_chacha::ChaCha8Rng;
let mut rng = ChaCha8Rng::from_entropy();  // from_entropy 底层仍可能用 thread_rng
let private_key: [u8; 32] = rng.gen();
let keypair = Keypair::from_bytes(&private_key);

// 场景4: 误用 fastrand crate（性能优先，非安全）
use fastrand::Rng;
let rng = Rng::new();
let salt: u64 = rng.u64(..);  // 盐值不可预测性不足
let hash = argon2::hash_encoded(password, &salt.to_le_bytes(), &config);

// 场景5: 随机数种子来自时间戳（可预测）
use std::time::{SystemTime, UNIX_EPOCH};
let seed = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
let mut rng = StdRng::seed_from_u64(seed);
let session_token = rng.gen::<u128>();

// 场景6: getrandom crate 误配置或降级
use getrandom::getrandom;
let mut buf = [0u8; 16];
if getrandom(&mut buf).is_err() {
    // 降级到不安全 RNG
    let mut rng = thread_rng();
    rng.fill(&mut buf);
}
let api_key = hex::encode(buf);

// 场景7: 测试 RNG 泄露到生产（SmallRng/测试种子）
#[cfg(not(test))]
use rand::rngs::OsRng;
#[cfg(test)]
use rand::rngs::SmallRng;  // 测试配置泄露
let mut rng = SmallRng::from_entropy();  // 编译配置错误
let encryption_key = rng.gen::<[u8; 32]>();

// 场景8: 自定义 RNG 实现（未经审计）
struct CustomRng {
    state: u64,
}
impl RngCore for CustomRng {
    fn next_u32(&mut self) -> u32 {
        self.state = self.state.wrapping_mul(6364136223846793005);  // LCG 弱算法
        (self.state >> 32) as u32
    }
    fn next_u64(&mut self) -> u64 { self.next_u32() as u64 }
    fn fill_bytes(&mut self, dest: &mut [u8]) { /* ... */ }
    fn try_fill_bytes(&mut self, dest: &mut [u8]) -> Result<(), rand::Error> { Ok(()) }
}

// 场景9: solana/substrate 钱包种子生成
use bip39::{Mnemonic, Language};
let mut entropy = [0u8; 32];
thread_rng().fill(&mut entropy);  // 应用 OsRng
let mnemonic = Mnemonic::from_entropy(&entropy, Language::English);

// 场景10: rand_core::mock 在生产环境
use rand_core::mock::StepRng;
let mut rng = StepRng::new(2, 1);  // 测试 Mock 泄露
let challenge = rng.next_u64();
authentication::verify_challenge(challenge);

// 场景11: 误用 rand::random()（底层 thread_rng）
let encryption_nonce: u128 = rand::random();  // 等价 thread_rng().gen()
aes_gcm.encrypt(Nonce::from(encryption_nonce.to_le_bytes()), plaintext);

// 场景12: ThreadRng 跨线程共享（状态污染）
lazy_static! {
    static ref GLOBAL_RNG: Mutex<ThreadRng> = Mutex::new(thread_rng());
}
let mut rng = GLOBAL_RNG.lock().unwrap();
let key_material = rng.gen::<[u8; 32]>();

// 场景13: 区块链签名 nonce 重用检测不足
let mut rng = thread_rng();
let k = rng.gen_biguint(256);  // ECDSA 签名 nonce
let signature = ecdsa_sign(private_key, message, &k);
// 若 k 重复使用可泄露私钥

// 场景14: wasm 目标误用（getrandom 无 fallback）
#[cfg(target_arch = "wasm32")]
use rand::thread_rng;  // WASM 下 getrandom 可能失败
let random_iv = thread_rng().gen::<[u8; 16]>();

// 场景15: 依赖 rand 0.7 以下旧版本（已知问题）
// Cargo.toml: rand = "0.6"  
// 旧版本 thread_rng 熵源质量问题
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
# 导入审计
grep -rn "use rand::{thread_rng\|Rng}" --include="*.rs"
grep -rn "use rand::rngs::{StdRng\|SmallRng\|ThreadRng}" --include="*.rs"
grep -rn "use rand_chacha::{ChaCha8Rng\|ChaCha12Rng}" --include="*.rs"
grep -rn "use fastrand" --include="*.rs"
grep -rn "use rand_core::mock" --include="*.rs"
grep -rn "rand::random()" --include="*.rs"

# 函数调用模式
grep -rn "thread_rng().gen\|thread_rng().fill" --include="*.rs"
grep -rn "StdRng::seed_from_u64\|SmallRng::seed_from_u64" --include="*.rs"
grep -rn "SeedableRng::from_seed" --include="*.rs"
grep -rn "from_entropy()" --include="*.rs"
grep -rn "\.gen::<\[u8" --include="*.rs" | grep -E "key|nonce|salt|seed|private"

# 密码学上下文关键词
grep -rn "encrypt.*thread_rng\|sign.*thread_rng" --include="*.rs"
grep -rn "private_key.*=.*gen()\|keypair.*=.*gen()" --include="*.rs"
grep -rn "nonce.*rand\|salt.*rand\|iv.*rand" --include="*.rs" -i
```

**高危 API 模式（L2 跳读）：**
- `thread_rng()` 用于生成 `key` / `private_key` / `seed` / `nonce` / `salt` / `iv`
- `StdRng::seed_from_u64()` / `SmallRng::seed_from_u64()` 固定或时间戳种子
- `ChaCha8Rng` / `ChaCha12Rng` 在密钥派生场景（应用 ChaCha20Rng + OsRng 种子）
- `fastrand` / `oorandom` / `nanorand` 非 CSPRNG crates 用于安全场景
- `rand::random()` 裸调用生成密码学材料（语法糖，底层 thread_rng）
- `SeedableRng::from_seed()` 种子来自硬编码数组或时间戳
- `getrandom` 失败后降级到 `thread_rng` 的 `if let Err` 分支
- `rand_core::mock::StepRng` / `TestRng` 出现在非 `#[cfg(test)]` 代码
- `RngCore` trait 自定义实现（LCG/Xorshift/Mersenne Twister）
- `ThreadRng` 存储在静态变量 / `lazy_static` / 跨线程传递
- `bip39` / `bip32` / `secp256k1` 密钥派生链用非安全 RNG
- `Keypair::generate()` 参数 `&mut thread_rng()` 而非 `&mut OsRng`
- Cargo.toml 依赖 `rand = "0.6"` / `0.7` 旧版本
- WASM 目标未适配 `getrandom` 的 `js` feature

**函数调用链追踪（L3 逐行）：**
- 定位加密入口：`encrypt()` / `seal()` / `sign()` 函数 RNG 参数来源
- 追踪 RNG 初始化：`impl Default for Wallet` / `new()` 构造函数中 RNG 创建
- 检查密钥生成：`generate_keypair()` / `derive_key()` / `random_bytes()` 内部实现
- 区块链模块：`wallet.rs` / `keystore.rs` / `mnemonic.rs` 种子生成逻辑
- 会话管理：`session_token()` / `csrf_token()` / `api_key()` 生成函数
- 加密模块：`crypto/mod.rs` / `encryption.rs` RNG 提供者配置
- 配置文件：`config.toml` / `.env` 中 `RNG_TYPE` / `USE_HARDWARE_RNG` 设置
- Feature flags：Cargo.toml `[features]` 是否有 `insecure-rng` 开关
- 条件编译：`#[cfg(test)]` / `#[cfg(feature = "dev")]` 测试 RNG 隔离
- 依赖审计：`Cargo.lock` 中 `rand` / `getrandom` / `rand_chacha` 版本
- Trait bounds：`fn encrypt<R: RngCore>(rng: &mut R)` 调用方传入类型
- 宏展开：`#[derive(RustCrypto)]` 等过程宏生成的 RNG 调用

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 全局搜索无 `use rand::rngs::OsRng` 导入（系统熵源缺失）
- 硬编码种子：`let seed = [42u8; 32];` / `seed_from_u64(0)`
- 时间戳种子：`SystemTime::now()` / `Instant::now()` 作为种子源
- 错误降级：`getrandom()` 失败后 `unwrap_or_else(|| thread_rng())`
- 注释显示临时性：`// TODO: use OsRng in production`
- 测试配置泄露：`#[cfg(test)]` 条件判断错误或缺失
- 依赖旧版本：Cargo.toml `rand = "0.6"` / `rand = "0.7"`

**伪保护识别（L3 逐行）：**
```rust
// from_entropy 仍可能用 thread_rng（取决于平台）
let mut rng = ChaCha8Rng::from_entropy();  // 非确定性但非 CSPRNG
let key = rng.gen::<[u8; 32]>();

// OsRng + 弱 PRNG 混合（种子安全但算法弱）
let seed = OsRng.gen::<[u8; 32]>();
let mut rng = StdRng::from_seed(seed);  // 后续可预测（若种子泄露）
loop {
    let nonce = rng.gen::<u64>();  // 长期使用同一种子状态
}

// 密钥派生用安全 RNG 但存储不安全
let key = OsRng.gen::<[u8; 32]>();
std::fs::write("key.txt", hex::encode(key));  // 明文存储抵消 RNG 安全性

// 条件编译但默认不安全
#[cfg(feature = "secure")]
use rand::rngs::OsRng as DefaultRng;
#[cfg(not(feature = "secure"))]
use rand::rngs::SmallRng as DefaultRng;  // 默认弱 RNG

// getrandom 配置降级
[dependencies]
getrandom = { version = "0.2", features = ["js"] }  # WASM 下降级到不安全源

// 误认为多次调用增强随机性
let key1 = thread_rng().gen::<[u8; 16]>();
let key2 = thread_rng().gen::<[u8; 16]>();
let final_key = xor_bytes(&key1, &key2);  // 仍基于伪随机

// 自定义 RNG wrapper 仍用 thread_rng
pub struct SecureRng(ThreadRng);
impl SecureRng {
    pub fn new() -> Self {
        SecureRng(thread_rng())  // 名不副实
    }
}

// 区块链签名 nonce 用确定性 RNG（RFC 6979 实现检查）
let k = derive_nonce_rfc6979(private_key, message);  // 需验证实现正确性
```

**跨模块保护追踪（L4）：**
- Cargo.toml features：`secure-rng` / `hardware-rng` / `dev` / `test` 配置
- 环境变量：`RNG_SOURCE=thread` / `CRYPTO_PROVIDER=software` 运行时配置
- 构建脚本：`build.rs` 中目标平台检测与 RNG 选择逻辑
- 密码库选择：`ring` / `RustCrypto` / `sodiumoxide` 依赖是否正确使用
- 区块链框架：Substrate `sp-io::crypto` / Solana `solana-sdk` RNG 提供者
- WASM 适配：`wasm-bindgen` / `web-sys` / `getrandom` JS 绑定配置
- 条件编译审计：`#[cfg(target_os = "linux")]` 等平台特定 RNG 实现
- CI/CD 检查：`.github/workflows` / `Makefile` 中 `cargo audit` / `cargo-geiger`
- 依赖树分析：`cargo tree | grep rand` 查看传递依赖版本
- 不安全代码块：`unsafe { }` 内手动系统调用 `/dev/random` / `CryptGenRandom`
- FFI 边界：C 库绑定（OpenSSL/BoringSSL）RNG 调用审计
- Docker 容器：熵池不足检测（`/proc/sys/kernel/random/entropy_avail`）
- 审计日志：启动时记录 RNG 类型 / 熵源类型的日志语句
- 合规文档：`SECURITY.md` / `docs/crypto.md` 声明 RNG 策略

## Classify

**确认漏洞：**
- 区块链钱包私钥/助记词用 `thread_rng` / `SmallRng` / `StdRng` 生成
- 对称加密密钥（AES/ChaCha20）用非 CSPRNG 生成
- 非对称密钥对（RSA/Ed25519/secp256k1）用确定性种子派生
- 数字签名 nonce（ECDSA/Schnorr）用 `thread_rng` 或固定种子
- 会话令牌/JWT 签名密钥用伪随机数生成
- 加密 nonce/IV 用 `rand::random()` 或时间戳派生
- 盐值（密码哈希/KDF）用弱 RNG 生成
- OAuth 授权码/CSRF Token 用 `fastrand` 等非安全 crate
- TLS 预主密钥/会话密钥材料用 `thread_rng`
- 多方计算（MPC）秘密分片用确定性 RNG
- 硬件钱包 Seed 派生未使用硬件 TRNG（降级到软件）
- Solana/Substrate 链上随机数用可预测源（VRF 实现错误）

**研判误报：**
- 单元测试/基准测试（`#[cfg(test)]` / `tests/` 目录）显式用 Mock RNG
- 示例代码（`examples/` 目录 / `///` 文档注释中）演示用途
- 模拟器/Fuzzer 测试工具确定性重现需求（需明确标注）
- 废弃函数明确标注 `#[deprecated]` 且无生产调用
- 开发环境特性门控（`#[cfg(feature = "dev")]` 且生产禁用）
- 性能对比基准（`benches/` 目录 Criterion 测试）
- 日志/调试用随机 ID 生成（trace_id / request_id）无安全含义
- 第三方 crate 内部实现（vendor 代码且项目未直接调用）

**代码异味：**
- Feature flag 可选安全 RNG 但默认 `thread_rng`（需显式启用安全模式）
- 注释标注 "临时实现" / "TODO: 替换为 OsRng" 无 Issue 追踪
- 日志警告 "Using insecure RNG for development" 但生产环境未强制检查
- 性能理由选择弱 RNG（"OsRng 太慢" / "区块链需要确定性"）
- 混合使用：新功能用 OsRng 但旧代码遗留 thread_rng
- 误解确定性需求：签名 nonce 误用确定性种子（应用 RFC 6979）
- 降级逻辑：`getrandom` 失败后自动回退 thread_rng 无告警
- WASM 目标未测试 `getrandom` 失败路径
- 自定义 RNG 实现未经密码学审计（"自研更安全"）
- 依赖项版本固定在已知问题版本（rand 0.6 RUSTSEC 告警）

**关键判断点：**
1. 随机数用途：测试数据/负载均衡 vs 密钥/nonce/签名
2. 安全边界：内部工具/模拟器 vs 生产钱包/交易所/支付
3. 对抗模型：是否需防御状态预测/种子推测攻击
4. 区块链场景：链下密钥 vs 链上随机数（VRF 要求）
5. 合规要求：FIPS 140-2 / CC EAL / SOC 2 密码学模块认证
6. 平台特性：Linux/Windows/macOS vs WASM/嵌入式（熵源差异）
7. 攻击窗口：一次性令牌（短期）vs 长期密钥材料
8. 依赖审计：`cargo audit` RUSTSEC 告警（已知漏洞）
9. 种子泄露风险：种子来源可观测性（时间戳/PID/内存地址）
10. 状态管理：RNG 对象生命周期（短暂 vs 全局静态）

## Low risk

**可接受的低风险场景：**
- 非安全随机 ID 生成（日志 trace_id / 请求路由负载均衡）
- 性能测试数据生成（确定性种子便于复现，无真实价值数据）
- 模糊测试确定性重现（Fuzzer 需 `StdRng::seed_from_u64` 固定种子）
- 开发环境快速原型（`cfg(debug_assertions)` 分支且专网隔离）
- 游戏随机事件（非金融博彩类，纯娱乐随机数）
- 采样/抖动算法（监控系统采样率抖动、UI 动画随机延迟）
- 缓存键扰动（LRU Cache 防冲突，无密码学语义）
- 单元测试确定性（`SmallRng::seed_from_u64(0)` 保证测试稳定）

**降级条件：**
- 数据已公开或极低敏感度（匿名统计 / 公开数据混洗）
- 短期过渡方案有明确里程碑（Sprint/Jira 可查且 < 1 季度）
- 访问严格隔离（HSM 硬件模块 / SGX 飞地 / 专网气隙）
- 外层密钥封装（KEK 用 OsRng，内层 DEK 用 thread_rng 仅性能优化）
- 攻击窗口极短（临时 nonce < 5 秒 + 一次性使用 + 内存清零）
- 多因素补偿（硬件 TPM/TEE + 网络隔离 + 实时监控）
- 已有外层保护（TLS 1.3 + mTLS + 应用层签名多重防护）
- 攻击成本量化评估（破解成本 > 资产价值 100 倍）
- 确定性 RNG 符合标准（RFC 6979 ECDSA 确定性签名审计实现）
- 遗留系统兼容（对接第三方仅支持确定性种子且已风险登记）

**注意：** Rust `thread_rng` 基于 ChaCha12（非 CSPRNG 级）且从线程本地状态派生，不适合密码学用途。应使用 `rand::rngs::OsRng`（Linux `/dev/urandom` / Windows `BCryptGenRandom` / macOS `SecRandomCopyBytes`）或硬件 TRNG。区块链场景需特别关注：助记词熵源（BIP39 要求 128-256 位系统熵）、ECDSA 签名 nonce 重用漏洞（Sony PS3 事件）、链上 VRF 可验证随机函数实现。WASM 目标必须配置 `getrandom = { features = ["js"] }` 并测试浏览器熵源降级路径。Cargo.toml 审计关注 `rand` 版本 >= 0.8（修复已知问题）、`getrandom` 版本 >= 0.2、避免 `fastrand` / `oorandom` / `nanorand` 用于安全场景。任何涉及金融交易、身份认证、PII 加密、区块链钱包、零知识证明的系统必须使用 CSPRNG。低风险评级仅适用非安全关键场景且需文档明确标注用途，长期生产系统应迁移至 `OsRng` 或硬件 RNG（如 Intel RDRAND 通过 `rdrand` crate）。