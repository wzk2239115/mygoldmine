# Rust 弱哈希 Crate 审计

## Details

### 典型代码特征
```rust
// 场景1: rust-crypto（已废弃 2016 年）
extern crate crypto;
use crypto::md5::Md5;
use crypto::digest::Digest;

let mut hasher = Md5::new();
hasher.input_str(&password);
let hash = hasher.result_str();

// 场景2: 使用 md-5 / sha-1 crate
use md5::{Md5, Digest};
let mut hasher = Md5::new();
hasher.update(b"password");
let result = hasher.finalize();

use sha1::{Sha1, Digest};
let mut hasher = Sha1::new();
hasher.update(token.as_bytes());
let hash = hasher.finalize();

// 场景3: 区块链钱包地址生成
use sha1::Sha1;
fn generate_wallet_address(pubkey: &[u8]) -> String {
    let mut hasher = Sha1::new();
    hasher.update(pubkey);
    let hash = hasher.finalize();
    hex::encode(hash)
}

// 场景4: 密码存储使用 MD5
use md5;
struct User {
    password_hash: String,
}

impl User {
    fn set_password(&mut self, pwd: &str) {
        self.password_hash = format!("{:x}", md5::compute(pwd));
    }
    
    fn verify_password(&self, pwd: &str) -> bool {
        format!("{:x}", md5::compute(pwd)) == self.password_hash
    }
}

// 场景5: API 签名验证
use sha1::{Digest, Sha1};
fn verify_signature(data: &[u8], sig: &str) -> bool {
    let mut hasher = Sha1::new();
    hasher.update(data);
    hasher.update(SECRET_KEY);
    let computed = format!("{:x}", hasher.finalize());
    computed == sig
}

// 场景6: Session Token 生成
use md5::Digest;
fn create_session_token(user_id: u64, timestamp: i64) -> String {
    let data = format!("{}:{}", user_id, timestamp);
    format!("{:x}", md5::compute(data.as_bytes()))
}

// 场景7: 自定义哈希组合
fn custom_hash(input: &str) -> Vec<u8> {
    let md5_hash = md5::compute(input);
    let mut sha1_hasher = sha1::Sha1::new();
    sha1_hasher.update(&md5_hash.0);
    sha1_hasher.finalize().to_vec()  // MD5+SHA1 仍弱
}

// 场景8: 智能合约地址派生
use sha1::Sha1;
fn derive_contract_address(creator: &Address, nonce: u64) -> Address {
    let mut hasher = Sha1::new();
    hasher.update(creator.as_bytes());
    hasher.update(&nonce.to_le_bytes());
    Address::from_slice(&hasher.finalize()[0..20])
}

// 场景9: HMAC 使用弱哈希
use hmac::{Hmac, Mac};
use sha1::Sha1;
type HmacSha1 = Hmac<Sha1>;

fn sign_message(msg: &[u8], key: &[u8]) -> Vec<u8> {
    let mut mac = HmacSha1::new_from_slice(key).unwrap();
    mac.update(msg);
    mac.finalize().into_bytes().to_vec()
}

// 场景10: 依赖项配置弱哈希
// Cargo.toml
[dependencies]
rust-crypto = "0.2"  // 2016 年废弃
md-5 = "0.9"
sha-1 = "0.9"

// 场景11: 特征约束使用弱算法
use digest::Digest;
fn hash_data<D: Digest>(data: &[u8]) -> Vec<u8> {
    let mut hasher = D::new();
    hasher.update(data);
    hasher.finalize().to_vec()
}

// 调用时指定 MD5
let hash = hash_data::<md5::Md5>(password.as_bytes());

// 场景12: 多轮迭代弱哈希
fn pbkdf_md5(password: &str, iterations: usize) -> Vec<u8> {
    let mut hash = md5::compute(password).0.to_vec();
    for _ in 0..iterations {
        hash = md5::compute(&hash).0.to_vec();
    }
    hash  // 迭代不能修复 MD5 弱点
}

// 场景13: 条件编译保留弱算法
#[cfg(feature = "legacy")]
use md5::Md5;
#[cfg(not(feature = "legacy"))]
use sha2::Sha256;

// 场景14: 宏生成哈希函数
macro_rules! hash {
    ($data:expr) => {
        format!("{:x}", md5::compute($data))
    };
}

let pwd_hash = hash!(password.as_bytes());

// 场景15: 异步任务使用弱哈希
async fn hash_async(data: Vec<u8>) -> String {
    tokio::task::spawn_blocking(move || {
        format!("{:x}", md5::compute(&data))
    }).await.unwrap()
}
```

### 快速定位核心操作（L1-L3）

**关键符号扫描（L1）：**
```bash
# 依赖审计
grep -rn "rust-crypto" --include="Cargo.toml"
grep -rn "md-5\|md5" --include="Cargo.toml"
grep -rn "sha-1\|sha1" --include="Cargo.toml" | grep -v "sha1.*="
grep -rn "crypto\s*=" --include="Cargo.toml"

# 代码扫描
rg "use\s+(md5|sha1|crypto::md5|crypto::sha1)" --type rust
rg "Md5::new\(\)|Sha1::new\(\)" --type rust
rg "md5::compute|sha1::compute" --type rust
rg "extern\s+crate\s+crypto" --type rust
rg "Hmac<(Md5|Sha1)>" --type rust
rg "digest::Digest.*Md5|Sha1" --type rust
```

**高危 API 模式（L2 跳读）：**
- `use md5::` / `use sha1::` / `use crypto::md5`
- `Md5::new()` / `Sha1::new()` / `Md5Digest::new()`
- `md5::compute()` / `sha1::compute()` 宏快捷方式
- `hasher.update()` + `hasher.finalize()` 模式
- `format!("{:x}", md5::compute(...))` 十六进制编码输出
- `Hmac<Md5>` / `Hmac<Sha1>` 类型别名
- `extern crate crypto` 废弃 crate 引用
- `password_hash` / `token` 变量进入弱哈希函数
- `derive_*` / `generate_*` 函数内部使用弱算法
- 区块链相关：`wallet_address` / `contract_address` 生成
- `#[cfg(feature = "legacy")]` 条件编译保留弱算法
- `Digest` trait bound 泛型函数被 `Md5` / `Sha1` 实例化
- `to_vec()` / `as_bytes()` 与哈希结果转换

**函数调用链追踪（L3 逐行）：**
- 定位哈希入口：`hash()` / `digest()` / `sign()` 函数实现
- 追踪数据源：`password` / `api_key` / `secret` / `token` 参数流向
- 检查存储路径：`Database::insert()` / `redis.set()` / `serde_json::to_string()`
- 认证逻辑：`verify_password()` / `check_signature()` / `validate_token()`
- Actix-Web / Rocket：路由 Handler 中认证中间件
- Tokio 异步：`spawn_blocking` / `tokio::task` 异步哈希
- gRPC 服务：`tonic::Request` 签名验证拦截器
- Diesel ORM：自定义类型 `impl FromSql` / `impl ToSql`
- Serde 序列化：`#[serde(serialize_with)]` 自定义哈希字段
- 宏展开：`macro_rules!` 生成的哈希工具函数
- 特征实现：`impl Hash for CustomType` 自定义哈希逻辑
- 区块链库：`web3` / `ethers-rs` 地址/交易哈希
- 配置解析：`config.toml` / `.env` 文件加载时密钥处理
- 中间件层：`tower::Service` / `actix_web::middleware` 请求签名

### 快速定位保护机制（L2-L4）

**无保护特征（L2 跳读）：**
- `Cargo.toml` 缺少 `sha2` / `sha3` / `blake2` / `argon2` 等现代哈希 crate
- 直接使用 `md5::compute()` / `sha1::compute()` 宏无封装
- 硬编码算法选择：无 `match hash_algorithm { ... }` 配置逻辑
- 密码字段类型 `String` 无 `secrecy::Secret<String>` 保护
- 直接比较：`hash1 == hash2` 而非 `subtle::ConstantTimeEq`
- 单次哈希无盐：无 `salt` 参数或 `pepper` 混合
- 注释显示 "quick hash" / "legacy compatibility"

**伪保护识别（L3 逐行）：**
```rust
// 加盐但仍用 MD5
use rand::Rng;
fn hash_password(pwd: &str) -> (String, String) {
    let salt: String = rand::thread_rng()
        .sample_iter(&rand::distributions::Alphanumeric)
        .take(16)
        .map(char::from)
        .collect();
    let hash = format!("{:x}", md5::compute(format!("{}{}", pwd, salt)));
    (hash, salt)  // MD5 + salt 仍可 GPU 暴力破解
}

// 迭代不足
fn pbkdf_weak(password: &str, iterations: u32) -> Vec<u8> {
    let mut result = md5::compute(password).0.to_vec();
    for _ in 0..iterations {
        result = md5::compute(&result).0.to_vec();
    }
    result  // 应用 PBKDF2/Argon2 而非自定义迭代
}

// HMAC 使用弱哈希基础
use hmac::{Hmac, Mac};
type HmacMd5 = Hmac<md5::Md5>;  // HMAC-MD5 仍受碰撞攻击影响

// 算法组合仍弱
fn double_hash(data: &[u8]) -> Vec<u8> {
    let md5_hash = md5::compute(data);
    sha1::compute(&md5_hash.0).to_vec()  // 组合不增强安全性
}

// 条件降级
fn hash_adaptive(data: &[u8], secure: bool) -> Vec<u8> {
    if secure {
        use sha2::{Sha256, Digest};
        let mut hasher = Sha256::new();
        hasher.update(data);
        hasher.finalize().to_vec()
    } else {
        md5::compute(data).0.to_vec()  // 危险降级
    }
}

// 特征约束但默认弱算法
fn hash_generic<D: digest::Digest + Default>(data: &[u8]) -> Vec<u8> {
    let mut hasher = D::default();
    hasher.update(data);
    hasher.finalize().to_vec()
}

// 实际调用用 MD5
let hash = hash_generic::<md5::Md5>(password.as_bytes());

// 多层封装但底层弱
struct Hasher {
    inner: Box<dyn digest::DynDigest>,
}

impl Hasher {
    fn new_md5() -> Self {
        Hasher { inner: Box::new(md5::Md5::new()) }
    }
}

// Feature flag 保留弱算法
#[cfg(feature = "fast")]
type HashAlgorithm = md5::Md5;
#[cfg(not(feature = "fast"))]
type HashAlgorithm = sha2::Sha256;

// 宏掩盖实现
macro_rules! quick_hash {
    ($data:expr) => {{
        use md5::Digest;
        let mut h = md5::Md5::new();
        h.update($data);
        h.finalize()
    }};
}
```

**跨模块保护追踪（L4）：**
- `Cargo.toml`：依赖版本审计，检查 `rust-crypto = "0.2"` / `md-5` / `sha-1`
- `Cargo.lock`：确认实际使用的 crate 版本
- `build.rs`：构建脚本是否动态选择哈希算法
- Feature 配置：`cargo build --features legacy` 启用弱算法路径
- 环境变量：`std::env::var("HASH_ALGO")` 运行时选择
- 配置文件：`config.toml` / `Settings.toml` 中 `hash_algorithm = "md5"`
- Workspace 依赖：多 crate 项目共享依赖版本
- 条件编译：`#[cfg(target_os = "legacy")]` 平台特定逻辑
- 宏展开检查：`cargo expand` 查看宏生成的实际代码
- 静态分析：`cargo clippy -- -W clippy::weak_crypto_hash` linter 规则
- 依赖审计：`cargo audit` 检查已知漏洞 crate
- 文档注释：`/// # Security` 部分是否声明算法选择
- 测试覆盖：`tests/` 是否验证强哈希要求
- CI/CD：`.github/workflows` / `.gitlab-ci.yml` 是否禁用弱哈希 feature
- Docker 镜像：多阶段构建中 `--features` 参数
- Kubernetes ConfigMap：注入的环境变量控制算法选择

## Classify

**确认漏洞：**
- 用户密码存储使用 MD5/SHA-1 哈希（无论是否加盐）
- JWT/JWS 签名使用 HMAC-MD5 / HMAC-SHA-1
- API Token/访问密钥生成使用弱哈希
- 区块链钱包私钥派生/地址生成使用 SHA-1
- 智能合约地址计算使用弱哈希（非 Keccak-256）
- 会话令牌/CSRF Token 生成使用 MD5
- OAuth 授权码/刷新令牌使用弱哈希
- 支付签名验证使用 MD5/SHA-1
- 密钥派生函数（KDF）基于弱哈希实现
- 证书指纹/数字签名使用 SHA-1（2017 年后禁用）
- 加密密钥本身用 MD5 派生（KEK 弱加密）
- 数据完整性校验用于安全关键场景
- TOTP/HOTP 种子生成使用弱哈希
- Merkle Tree / 哈希链使用 MD5（区块链/审计日志）

**研判误报：**
- 单元测试代码（`#[cfg(test)]` / `tests/` 目录）
- 示例代码（`examples/` 目录 / 文档注释 `/// # Example`）
- 已废弃函数标注 `#[deprecated]` 且无调用引用
- 第三方 crate 内部实现（`target/` / `.cargo/` 路径）
- 条件编译永不满足：`#[cfg(all(false))]`
- Benchmark 基准测试对照组（`benches/` 目录）
- Mock 实现（`#[cfg(test)]` 测试辅助代码）
- 教学材料演示（Rust By Example 类型项目）

**代码异味：**
- 配置可选 SHA-256 但默认 MD5
- 注释 "TODO: migrate to SHA-3" 无时间表
- Feature flag `legacy` 保留弱算法无迁移计划
- 泛型约束 `Digest` 但文档推荐 `Md5` 示例
- 性能理由选择 MD5（"MD5 fastest for checksums"）
- 算法白名单包含 `["md5", "sha1", "sha256"]`
- 新旧数据不同算法但未统一升级
- 日志输出 "Using MD5 for compatibility" 无预警
- 函数命名 `secure_hash()` 但实现用 MD5
- 多轮迭代误认为增强安全（`for _ in 0..10000`）

**关键判断点：**
1. 哈希目标：测试数据 vs 密码/密钥/PII
2. 安全边界：内部工具 vs 公开 API/区块链网络
3. 数据敏感度：调试信息 vs 金融交易/健康数据
4. 对抗模型：是否需防御碰撞攻击/彩虹表/GPU 暴力破解
5. 生命周期：临时缓存（分钟级）vs 长期存储（年）
6. 替代方案：系统是否有 `sha2` / `argon2` / `blake3` 依赖
7. 合规要求：NIST SP 800-107 / PCI DSS / GDPR / 等保 2.0
8. 区块链特殊性：以太坊 Keccak-256 / 比特币 SHA-256 标准
9. Rust 生态：`RustCrypto` 组织维护的现代 crate 可用性
10. 性能要求：高频调用场景（Blake3 > SHA-256 > MD5 安全性差异）

## Low risk

**可接受的低风险场景：**
- 非安全用途的缓存键生成（ETag / 内容寻址存储）
- 日志追踪 ID / Request ID 生成（无对抗需求）
- 文件去重标识（内部备份系统，非防篡改）
- 分布式锁键生成（Redis / Etcd）
- 消息幂等性校验（短期窗口 < 5 分钟）
- 开发环境快速原型（`#[cfg(debug_assertions)]` 分支）
- 性能基准测试对照组（比较哈希速度差异）
- 内部工具脚本（运维自动化，专网隔离）
- 读取历史归档数据（一次性迁移，仅解密旧格式）

**降级条件：**
- 数据已公开或低敏感度（公开文章哈希 / 匿名统计）
- 短期过渡方案有明确迁移里程碑（Sprint 可查）
- 访问受严格网络隔离（VPC 专网 + mTLS 双向认证）
- 仅向后兼容读取，新数据用 SHA-256 / Blake3
- 攻击窗口极短（一次性令牌 < 5 分钟 + TLS 1.3）
- 已有外层强保护（TLS + 应用层加密）
- 攻击成本远高于资产价值（量化评估）
- 监控告警覆盖（异常哈希调用频率检测）
- 明确文档化非安全用途（代码注释 + ADR）
- 依赖审计通过（`cargo audit` 无 CRITICAL 警告）

**注意：** MD5 已实用碰撞攻击（2008 年伪造 CA 证书），SHA-1 于 2017 年 SHAttered 攻击证明可碰撞。`rust-crypto` crate 自 2016 年废弃，应迁移至 `RustCrypto` 组织维护的 `sha2` / `sha3` / `blake2` / `blake3`。密码哈希应使用 `argon2` / `scrypt` / `bcrypt` 专用 KDF。区块链项目应遵循协议标准（比特币 SHA-256、以太坊 Keccak-256）。Rust 编译器无法静态检测弱哈希使用，需结合 `cargo-audit` / `cargo-deny` / Clippy 自定义 lint。任何涉及身份认证、数字签名、区块链共识、PCI DSS / FIPS 140-2 合规的系统应立即替换为 NIST 推荐算法（SHA-256 / SHA-3 / Blake2）。低风险评级仅适用于非安全关键场景，长期使用需评估安全债务。