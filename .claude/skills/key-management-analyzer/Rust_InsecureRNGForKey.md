# Rust_InsecureRNGForKey

**Rust**（适用于智能合约如 Solana 程序或 Off-chain 服务）  
常出现在密钥派生、签名服务、密钥轮换逻辑中：使用 `rand::thread_rng`、`rand::random` 等非加密安全的随机数生成器生成密钥，可被预测攻击。

## Details

**代码示例：**
```rust
use rand::{thread_rng, Rng};

// 危险：使用非加密安全 RNG 生成私钥
let mut rng = thread_rng();
let mut private_key = [0u8; 32];
rng.fill(&mut private_key);

// 危险：直接使用 random()
let seed = rand::random::<u64>();
```

**快速定位核心操作技巧（L1-L2）：**
- **L1关键词扫描**：搜索 `use rand::`、`thread_rng()`、`rand::random`、`StdRng`、`SmallRng`
- **L2跳读**：关注密钥生成函数（`generate_keypair`、`derive_key`、`create_wallet`），检查是否调用上述 RNG
- 特别注意：`fill`、`fill_bytes`、`gen` 方法的 RNG 来源，查看是否为 `OsRng` 或 `CryptoRng` trait

**快速定位保护机制技巧（L2-L3）：**
- **L2跳读**：查找 `use rand::rngs::OsRng`、`use rand_core::CryptoRng`、`getrandom::getrandom` 等安全来源
- **L3逐行读**：验证密钥生成路径是否从 `OsRng` 初始化，检查是否有泛型约束 `R: CryptoRng + RngCore`
- Solana 特定：检查是否使用 `solana_sdk::signer::keypair::Keypair::new()` 而非手动 RNG

## Classify

**漏洞判定：**
- 直接用于生成私钥、助记词种子、签名随机数（nonce）：**高危漏洞**
- 用于密钥派生过程中的盐值或 IV：**中危漏洞**

**误报排除：**
- RNG 仅用于非敏感场景（如负载均衡、缓存键、测试数据）：误报
- 代码路径被 `#[cfg(test)]` 或 `#[cfg(feature = "insecure")]` 包裹：测试代码，视为低风险

**代码异味：**
- 在链下服务使用 `thread_rng` 生成临时 session token，但未用于长期密钥：降级为代码异味，建议改进

## Low risk

- RNG 输出仅用作确定性密钥派生（如 BIP32/BIP44）的**额外熵混合**，主密钥来自安全源
- 系统运行在可信执行环境（TEE/SGX），且 RNG 状态已通过远程认证验证
- 仅用于开发/演示环境的密钥生成，代码有明确的 `DO NOT USE IN PRODUCTION` 标记且未部署到主网
- 密钥生命周期极短（<1秒）且仅在内存中使用一次后立即擦除，无持久化或网络传输

## 审计专业技巧与误报区分

### 真实漏洞的特征识别

**模式1：直接密钥生成链条**
```rust
// 真实漏洞示例（Solana Phantom钱包风险模式）
fn create_signer_from_random() -> Keypair {
    let mut rng = thread_rng();
    let seed: [u8; 32] = rng.gen();  // 直接用非加密RNG生成私钥种子
    Keypair::from_secret_key(&SecretKey::from_bytes(&seed).unwrap())
}
```
**审计要点**：追踪种子/密钥的使用深度，查看是否直接签署交易。深度越浅（直接签署）= 风险越高。

**模式2：多层随机化陷阱**
```rust
// 误导性代码：看似安全但实际高危
let mut master_seed = vec![0u8; 32];
OsRng.fill_bytes(&mut master_seed);  // 安全源初始化
let mut rng = StdRng::seed_from_u64(master_seed[0] as u64);  // 从单字节派生！
rng.fill_bytes(&mut private_key);  // 高危：熵完全丧失
```
**审计要点**：不仅要看 RNG 源，还要看初始化时的熵损失。单字节、低字节截断是高风险信号。

**模式3：条件分支陷阱**
```rust
// 易被忽视的真实漏洞
fn generate_key_for_network(network: &str) -> [u8; 32] {
    if network == "testnet" {
        let mut rng = thread_rng();
        rng.gen()  // 开发者认为这是测试专用，实际可能被误用
    } else {
        // 线上网络使用安全RNG...
    }
}
```
**审计要点**：检查网络标识符的来源。如果由用户输入或配置文件提供，条件分支保护形同虚设。

### 常见误报场景与排除方法

**误报1：缓存键与压力测试数据混淆**
- **信号**：搜到 `thread_rng` 但跟踪发现用于 HashMap 键、缓存 ID、测试fixture
- **确认方法**：
  - 检查该值是否被序列化到链上 `serialize()` / `to_bytes()`
  - 检查是否被用于签名验证路径 `verify()` / `sign()`
  - 如都否 → 误报，建议降级为代码审美建议

**误报2：特征边界保护（Feature-Gated）**
- **信号**：代码被 `#[cfg(feature = "dev-keys")]` 或 `#[cfg(test)]` 包裹
- **排除标准**：
  - 必须确认该特征在 `Cargo.toml` 中 **default feature 列表为空**
  - 检查 CI/CD 流程是否显式排除该特征的编译 `cargo build --release --no-default-features`
  - **关键**：团队内部是否有约定使用 `dev-*` 特征，且文档标注此特征不得用于生产构建

**误报3：确定性推导中的额外熵**
```rust
// 可能被误判为漏洞
let master_key = derive_from_seed(secure_seed);  // BIP32安全推导
let nonce = thread_rng().gen::<u32>();  // 额外随机化nonce
let final_key = mix_with_entropy(&master_key, &nonce);  // 额外保险
```
**排除方法**：
- 核实主密钥推导路径的密码学强度（BIP32/PBKDF2/Argon2等）
- 如主密钥已足够强，额外弱RNG只是"锦上添花"，**风险等级降低50%**
- 但仍需建议改用 `getrandom::getrandom()` 替代

### 区分真实漏洞的三层审计框架

**第一层：数据流追踪（Taint Analysis）**
1. 定位 `thread_rng()` 调用点，记录变量名（如 `seed`）
2. 向下追踪该变量的所有使用：
   - 直接用于 `Keypair::from_bytes(seed)` → **高危**
   - 作为 `derive_key(seed, ...)` 的入参 → **中危**
   - 用作缓存键 `HashMap::insert(seed, value)` → **无关**

**第二层：上下文隔离检查**
1. 查看函数签名：是否被 `pub` 导出 / 被其他模块调用
2. 查看注释：是否有 `// TODO: use CryptoRng` 或 `FIXME` 标记
3. 查看错误处理：是否有 `.unwrap()` / `.expect()` 在关键路径（表示开发中代码）

**第三层：密码学边界确认**
1. 在密钥使用点（`sign()` / `encrypt()` / 合约部署）打断点
2. 反问：此密钥是否必须满足 2^-128 的破解成本下限？
   - 是 → `thread_rng` 是严重漏洞
   - 否 → 可能误报

### 实战案例：Solana 生态审计经验

**真实案例1：魔鬼细节的弱RNG**
- 发现某钱包库使用 `StdRng::seed_from_u64(timestamp)` 生成签名密钥
- 虽使用了 `StdRng`（看似比 `thread_rng` 强），但熵源仅为时间戳（32-bit有效熵）
- **判定**：高危，误报率极低（100%真实漏洞）

**真实案例2：条件分支陷阱导致生产事故**
- 某项目在开发阶段使用 `thread_rng()` 生成测试账户，后期忘记移除分支
- 生产环境意外触发该分支，导致批量账户私钥可预测
- **教训**：代码审计时必须验证分支条件的真实可达性，不能仅看代码文本

**真实案例3：合约部署脚本中的隐形漏洞**
- Off-chain 脚本使用 `rand::random()` 生成一次性交易 ID（非密钥）
- 审计员初判误报，直到发现该 ID 被用作确定性账户推导（PDA）的种子
- **关键**：同一个随机值在不同上下文有不同风险等级，需综合判断
