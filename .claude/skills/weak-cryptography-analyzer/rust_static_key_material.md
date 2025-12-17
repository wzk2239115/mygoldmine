# Rust 静态密钥材料硬编码审计

## Details

### 典型代码特征
```rust
// 场景1: 区块链钱包硬编码私钥
use secp256k1::{SecretKey, Secp256k1};
const PRIVATE_KEY: &str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
let secret_key = SecretKey::from_slice(&hex::decode(PRIVATE_KEY).unwrap()).unwrap();
let secp = Secp256k1::new();
let public_key = secp256k1::PublicKey::from_secret_key(&secp, &secret_key);

// 场景2: AES 对称密钥硬编码
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use aes_gcm::aead::Aead;
const AES_KEY: [u8; 32] = [
    0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42,
    0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42,
    0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42,
    0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42, 0x42,
];
let cipher = Aes256Gcm::new(&AES_KEY.into());
let ciphertext = cipher.encrypt(&nonce, plaintext).unwrap();

// 场景3: ChaCha20 静态密钥
use chacha20poly1305::{ChaCha20Poly1305, Key};
lazy_static! {
    static ref ENCRYPTION_KEY: Key = *Key::from_slice(b"an example very very secret key.");
}
let cipher = ChaCha20Poly1305::new(&ENCRYPTION_KEY);

// 场景4: JWT HMAC 签名密钥
use hmac::{Hmac, Mac};
use sha2::Sha256;
type HmacSha256 = Hmac<Sha256>;
const JWT_SECRET: &[u8] = b"super_secret_jwt_key_12345";
fn sign_jwt(payload: &str) -> Vec<u8> {
    let mut mac = HmacSha256::new_from_slice(JWT_SECRET).unwrap();
    mac.update(payload.as_bytes());
    mac.finalize().into_bytes().to_vec()
}

// 场景5: 数据密封静态 HKDF Salt
use hkdf::Hkdf;
use sha2::Sha256;
const STATIC_SALT: &[u8] = b"application_salt_v1";
fn derive_key(input: &[u8]) -> [u8; 32] {
    let hk = Hkdf::<Sha256>::new(Some(STATIC_SALT), input);
    let mut okm = [0u8; 32];
    hk.expand(b"context", &mut okm).unwrap();
    okm
}

// 场景6: 硬编码 Ed25519 签名种子
use ed25519_dalek::{Keypair, Signer, SECRET_KEY_LENGTH};
const SEED: [u8; SECRET_KEY_LENGTH] = [0x42; SECRET_KEY_LENGTH];
let keypair = Keypair::from_bytes(&SEED).unwrap();
let signature = keypair.sign(message);

// 场景7: Ring 库硬编码密钥
use ring::aead::{Aad, LessSafeKey, Nonce, UnboundKey, AES_256_GCM};
static KEY_BYTES: [u8; 32] = [1u8; 32];
fn encrypt_data(data: &[u8]) -> Vec<u8> {
    let unbound_key = UnboundKey::new(&AES_256_GCM, &KEY_BYTES).unwrap();
    let key = LessSafeKey::new(unbound_key);
    // ... 加密逻辑
}

// 场景8: 配置文件密钥字符串常量
pub struct Config {
    encryption_key: String,
}
impl Default for Config {
    fn default() -> Self {
        Config {
            encryption_key: "default_encryption_key_abcdef1234567890".to_string(),
        }
    }
}

// 场景9: TLS 预共享密钥（PSK）
use rustls::{ServerConfig, server::AllowAnyAuthenticatedClient};
const PSK_IDENTITY: &[u8] = b"client_identity";
const PSK_SECRET: &[u8] = b"preshared_secret_key_value";
fn setup_tls() -> ServerConfig {
    // ... PSK 配置
}

// 场景10: WebSocket 握手密钥
use tungstenite::handshake::server::ServerHandshake;
const WS_KEY: &str = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"; // 虽是标准但检查自定义密钥

// 场景11: Session Token 生成密钥
use rand::Rng;
use base64;
const SESSION_SECRET: &[u8] = b"session_signing_key_v2024";
fn generate_session(user_id: u64) -> String {
    let mut mac = HmacSha256::new_from_slice(SESSION_SECRET).unwrap();
    mac.update(&user_id.to_le_bytes());
    base64::encode(mac.finalize().into_bytes())
}

// 场景12: 硬编码 BIP39 助记词种子
use bip39::{Mnemonic, Language, Seed};
const MNEMONIC_PHRASE: &str = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about";
let mnemonic = Mnemonic::from_phrase(MNEMONIC_PHRASE, Language::English).unwrap();
let seed = Seed::new(&mnemonic, "");

// 场景13: OAuth2 Client Secret
struct OAuth2Config {
    client_id: String,
    client_secret: String, // 硬编码在代码中
}
const OAUTH_SECRET: &str = "oauth_client_secret_abc123xyz";

// 场景14: 数据库加密密钥
use sqlx::{Pool, Postgres};
const DB_ENCRYPTION_KEY: &str = "db_field_encryption_key_2024";
async fn store_encrypted(pool: &Pool<Postgres>, data: &str) {
    let encrypted = encrypt_with_key(data, DB_ENCRYPTION_KEY);
    sqlx::query("INSERT INTO secrets (value) VALUES ($1)")
        .bind(encrypted)
        .execute(pool)
        .await
        .unwrap();
}

// 场景15: P2P 网络节点 ID 派生密钥
use libp2p::identity::Keypair;
const NODE_SEED: [u8; 32] = [0xAB; 32];
fn create_peer_id() -> libp2p::PeerId {
    let keypair = Keypair::ed25519_from_bytes(NODE_SEED.to_vec()).unwrap();
    keypair.public().to_peer_id()
}

// 场景16: TOTP 双因素认证密钥
use totp_rs::{TOTP, Algorithm};
const TOTP_SECRET: &str = "JBSWY3DPEHPK3PXP"; // Base32 编码密钥
fn verify_totp(token: &str) -> bool {
    let totp = TOTP::new(
        Algorithm::SHA1,
        6,
        1,
        30,
        TOTP_SECRET.as_bytes().to_vec(),
    ).unwrap();
    totp.check_current(token).unwrap()
}

// 场景17: 自定义加密 Crate 中硬编码
mod crypto {
    const MASTER_KEY: [u8; 64] = [0xFF; 64];
    pub fn seal(data: &[u8]) -> Vec<u8> {
        // 使用 MASTER_KEY 加密
        data.iter().zip(MASTER_KEY.iter().cycle())
            .map(|(d, k)| d ^ k)
            .collect()
    }
}

// 场景18: Cookie 签名密钥
use cookie::{Cookie, CookieJar, Key};
const COOKIE_KEY: [u8; 64] = [0x5A; 64];
fn sign_cookie(jar: &mut CookieJar) {
    let key = Key::from(&COOKIE_KEY);
    jar.private(&key).add(Cookie::new("session", "value"));
}

// 场景19: Actix-web 中间件密钥
use actix_web::middleware::session::CookieSessionBackend;
const SESSION_KEY: &[u8; 32] = b"actix_session_key_0123456789ab";
fn setup_session() -> CookieSessionBackend {
    CookieSessionBackend::signed(SESSION_KEY).secure(false)
}

// 场景20: 智能合约部署私钥
use web3::types::{H256, Address};
const DEPLOYER_PRIVATE_KEY: &str = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";
async fn deploy_contract() {
    let private_key = H256::from_slice(&hex::decode(&DEPLOYER_PRIVATE_KEY[2..]).unwrap());
    // 合约部署逻辑
}
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
grep -rn "const.*KEY" --include="*.rs"
grep -rn "const.*SECRET" --include="*.rs"
grep -rn "const.*SEED" --include="*.rs"
grep -rn "static.*KEY.*=.*\[" --include="*.rs"
grep -rn "lazy_static.*KEY\|lazy_static.*SECRET" --include="*.rs"
grep -rn "from_slice.*0x[0-9a-fA-F]" --include="*.rs"
grep -rn "SecretKey::from_slice\|PrivateKey::from" --include="*.rs"
grep -rn "Keypair::from_bytes\|Keypair::ed25519_from_bytes" --include="*.rs"
grep -rn "Key::from_slice.*b\"" --include="*.rs"
grep -rn "HMAC.*new_from_slice.*b\"" --include="*.rs"
grep -rn "const.*: &\[u8\] = b\"" --include="*.rs"
grep -rn "Mnemonic::from_phrase.*\".*abandon" --include="*.rs"
```

**高危 API 模式（L2 跳读）：**
- `const KEY: [u8; N] = [...]` 常量字节数组密钥
- `const SECRET: &str = "..."` 字符串常量密钥
- `static KEY_BYTES: [u8; 32] = [0x..; 32]` 静态密钥材料
- `lazy_static! { static ref KEY: ... }` 懒加载密钥常量
- `SecretKey::from_slice(&hex::decode("..."))` 硬编码十六进制私钥
- `Keypair::from_bytes(&SEED)` 固定种子生成密钥对
- `Key::from_slice(b"...")` 字节字符串密钥
- `HmacSha256::new_from_slice(b"...")` 硬编码 HMAC 密钥
- `impl Default` 中初始化密钥字段
- `Mnemonic::from_phrase("abandon abandon...")` BIP39 测试助记词
- `const PRIVATE_KEY: &str = "0x..."` 以太坊私钥十六进制字符串
- `Hkdf::new(Some(b"static_salt"), ...)` 硬编码派生盐
- `UnboundKey::new(..., &KEY_BYTES)` Ring 库固定密钥
- `CookieSessionBackend::signed(&KEY)` Session 密钥硬编码
- `TOTP::new(..., SECRET.as_bytes())` 双因素密钥固定

**函数调用链追踪（L3 逐行）：**
- 定位密钥使用入口：`encrypt()` / `sign()` / `seal()` / `derive()` 函数
- 追踪密钥来源：`const` / `static` / `lazy_static!` / `Config::default()`
- 检查存储路径：数据库插入 / 文件写入 / Redis 缓存 / 区块链交易
- 认证逻辑：JWT 验证 / Session 解密 / API 签名校验
- 区块链模块：钱包初始化 / 交易签名 / 智能合约调用
- Web 框架：Actix-web / Rocket / Warp 中间件密钥配置
- 配置加载：`config.toml` / `.env` 解析时默认值
- Serde 反序列化：`#[derive(Deserialize)]` 结构体密钥字段
- 加密 Crate：`ring` / `rustls` / `sodiumoxide` / `rust-crypto` 参数
- P2P 网络：`libp2p` / `tokio` 节点身份密钥生成
- 数据密封：`age` / `orion` / 自定义加密模块
- RPC 服务：gRPC / JSON-RPC 签名密钥

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- 硬编码字节数组：`[0x42; 32]` / `[1u8; 32]` 重复模式
- 明文字符串密钥：`b"super_secret_key"`
- 十六进制字符串常量：`"0xe3b0c442..."`
- 配置默认值：`Default::default()` 返回固定密钥
- 测试助记词：`"abandon abandon..."`（BIP39 标准测试词）
- 注释显示 "for testing" / "example key" / "CHANGE THIS"
- Cargo.toml 依赖过时：`rust-crypto` / `sha1` / `md-5`

**伪保护识别（L3 逐行）：**
```rust
// 环境变量回退到硬编码
fn get_key() -> String {
    env::var("ENCRYPTION_KEY")
        .unwrap_or_else(|_| "fallback_default_key".to_string())
}

// 配置文件缺失时使用默认密钥
impl Config {
    fn load() -> Self {
        std::fs::read_to_string("config.toml")
            .ok()
            .and_then(|s| toml::from_str(&s).ok())
            .unwrap_or_else(|| Config {
                key: "default_hardcoded_key".to_string(),
            })
    }
}

// 构建时常量但仍硬编码
const KEY: &[u8] = include_bytes!("../keys/master.key"); // 密钥文件提交到版本控制

// 编译时环境变量仍是固定值
const COMPILE_TIME_KEY: &str = env!("BUILD_SECRET"); // CI/CD 固定值

// XOR 混淆但密钥可见
const OBFUSCATED_KEY: [u8; 32] = [0xAB ^ 0xFF; 32];
fn deobfuscate() -> [u8; 32] {
    OBFUSCATED_KEY.map(|b| b ^ 0xFF) // 可逆变换
}

// 伪随机但种子固定
use rand::SeedableRng;
use rand_chacha::ChaCha20Rng;
const RNG_SEED: [u8; 32] = [0x12; 32];
fn generate_key() -> [u8; 32] {
    let mut rng = ChaCha20Rng::from_seed(RNG_SEED);
    let mut key = [0u8; 32];
    rng.fill(&mut key);
    key // 每次生成相同
}

// 密钥派生但盐静态
use pbkdf2::pbkdf2_hmac;
const PBKDF2_SALT: &[u8] = b"static_application_salt";
fn derive_from_password(password: &str) -> [u8; 32] {
    let mut key = [0u8; 32];
    pbkdf2_hmac::<Sha256>(password.as_bytes(), PBKDF2_SALT, 100000, &mut key);
    key // 盐可预测，彩虹表预计算
}

// 分割存储但仍硬编码
const KEY_PART1: [u8; 16] = [0x01; 16];
const KEY_PART2: [u8; 16] = [0x02; 16];
fn assemble_key() -> [u8; 32] {
    let mut full = [0u8; 32];
    full[..16].copy_from_slice(&KEY_PART1);
    full[16..].copy_from_slice(&KEY_PART2);
    full
}

// 条件编译但两个分支都硬编码
#[cfg(debug_assertions)]
const KEY: &[u8] = b"debug_key_1234567890";
#[cfg(not(debug_assertions))]
const KEY: &[u8] = b"prod_key_abcdefghijk"; // 仍硬编码

// 单例模式包装
use once_cell::sync::Lazy;
static GLOBAL_KEY: Lazy<Vec<u8>> = Lazy::new(|| {
    vec![0x5A; 32] // 懒加载仍是常量
});

// 宏生成但值固定
macro_rules! get_key {
    () => {
        &[0x42u8; 32]
    };
}
```

**跨模块保护追踪（L4）：**
- Cargo.toml：依赖版本 / features 启用状态（如 `rustls/dangerous_configuration`）
- .env 文件：`MASTER_KEY=` / `JWT_SECRET=` 是否存在
- build.rs：构建脚本是否从外部源加载密钥
- 配置管理：`config-rs` / `figment` 库配置源（文件 / 环境变量 / KMS）
- Secrets 管理：是否集成 Vault / AWS Secrets Manager / Azure Key Vault
- Docker 镜像：Dockerfile 中 `ENV SECRET=...` / 密钥文件 COPY
- Kubernetes：ConfigMap / Secret 资源定义
- CI/CD：GitHub Actions / GitLab CI 环境变量加密状态
- Git 历史：`.git/logs` 检查密钥是否曾提交后删除
- 审计工具：`cargo-audit` / `cargo-deny` 配置
- 文档：README / SECURITY.md 中密钥管理说明
- 测试代码：`tests/` 目录密钥常量是否泄露到生产
- 示例代码：`examples/` 中硬编码密钥被复制使用
- 依赖锁定：`Cargo.lock` 检查过时加密库版本
- 合规检查：SAST 工具扫描结果（Clippy / RustSec）

## Classify

**确认漏洞：**
- 生产环境私钥/对称密钥硬编码在源代码常量中
- 区块链钱包私钥或助记词种子硬编码
- JWT / OAuth2 / API 签名密钥为字符串常量
- Session / Cookie 签名密钥写死在代码中
- 数据库字段加密密钥硬编码
- TLS 预共享密钥（PSK）静态定义
- TOTP 双因素密钥常量化
- 加密密钥（KEK）本身硬编码
- P2P 节点身份密钥固定种子生成
- 智能合约部署账户私钥明文字符串
- 配置文件默认值使用真实生产密钥
- 密钥派生盐全局静态（无随机化）

**研判误报：**
- 单元测试 / 集成测试专用密钥（`#[cfg(test)]` 内部）
- `examples/` 目录演示代码
- 文档字符串中示例（`/// # Example`）
- 已废弃函数明确标注 `#[deprecated]` 且无调用
- 第三方 Crate 内部实现（非项目直接引用）
- 性能基准测试对照组（`benches/` 目录）
- Mock 测试工具（`#[cfg(feature = "mock")]`）
- 开发工具脚本（`tools/` / `scripts/` 非编译目标）
- 注释掉的历史代码（`// const OLD_KEY = ...`）

**代码异味：**
- 环境变量缺失时回退到硬编码默认值
- 配置可选外部密钥但默认内置
- 注释 "TODO: move to environment" 无执行时间表
- 测试密钥与生产密钥使用相同代码路径
- 日志输出 "using default key" 警告
- 条件编译 Debug/Release 都硬编码
- 密钥拆分存储但仍在代码中
- 懒加载包装常量密钥
- 宏定义返回固定值
- Build 脚本生成但值预测
- 文档声称"安全密钥管理"实际硬编码

**关键判断点：**
1. 密钥类型：对称密钥 / 私钥 / 签名密钥 / 种子 / 盐
2. 使用场景：测试 vs 生产 / 内网 vs 公网
3. 数据敏感度：公开数据 vs 用户隐私 / 金融 / 医疗
4. 密钥生命周期：临时（< 1 小时）vs 长期（数月/年）
5. 对抗模型：源码是否开源 / 编译产物逆向难度
6. 替代方案：环境变量 / 配置文件 / KMS / HSM 是否集成
7. 合规要求：等保 / GDPR / PCI DSS / SOC 2 适用性
8. 版本控制：密钥是否曾提交 Git 历史
9. 部署环境：容器化 / 云原生 / 裸金属服务器
10. 访问控制：代码库权限 / 构建流水线安全

## Low risk

**可接受的低风险场景：**
- 单元测试固定密钥（`#[cfg(test)]` 隔离且无生产数据）
- 性能基准测试可复现性要求（`criterion` 固定输入）
- 示例代码教学用途（明确标注 "DO NOT USE IN PRODUCTION"）
- 开发环境本地调试（`.env.example` 模板密钥）
- 一次性数据迁移脚本（历史数据格式转换工具）
- 内部网络工具临时方案（VPN 隔离 + IP 白名单）
- 非敏感日志脱敏映射（可逆 ID 混淆，无真实隐私价值）
- 代码混淆对抗逆向（非加密用途，配合其他保护）

**降级条件：**
- 数据公开或无敏感度（公开区块链测试网 / 演示数据）
- 短期过渡方案有明确迁移计划（Sprint 可追溯，Jira/GitHub Issue）
- 访问严格隔离（专网 + 防火墙 + mTLS + 审计日志）
- 仅向后兼容读取历史数据，新数据用 HSM/KMS
- 攻击窗口极短（临时令牌 < 5 分钟 + 单次使用 + HTTPS）
- 外层强保护（TLS 1.3 + 端到端加密 + 硬件加密卡）
- 开源项目但密钥仅用于自托管用户自行替换
- 攻击成本远高于资产价值（内部低价值测试系统）
- 明确文档说明非生产用途且 CI 检查禁止生产部署

**注意：** 硬编码密钥一旦源码泄露（Git 历史 / 反编译 / 内部人员）即完全失效。Rust 编译为二进制但 `strings` / `binwalk` 可提取常量字符串。区块链私钥硬编码可导致资产永久丢失。应使用环境变量（`std::env::var`）、配置文件（`config-rs`）、密钥管理服务（Vault / AWS KMS / HashiCorp）、硬件安全模块（HSM / TPM）或构建时注入（`build.rs` 从安全存储读取）。低风险评级不代表长期可接受，必须有明确迁移路线图和责任人。生产系统应启用 `cargo-audit` / `cargo-deny` 自动检测依赖漏洞，使用 Clippy Lints 规则禁止常见密钥模式（`clippy::hardcoded_keys`）。