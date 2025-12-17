# Rust JWT 静态密钥漏洞审计

## Details

**代码特征示例：**
```rust
// 典型漏洞模式
let secret = "my_secret_key"; // 硬编码密钥
let token = encode(&Header::default(), &claims, &EncodingKey::from_secret(secret.as_ref()))?;

// 或
const JWT_SECRET: &str = "hardcoded_secret_123";
let key = EncodingKey::from_secret(JWT_SECRET.as_ref());
```

**快速定位核心操作技巧（L2:跳读）：**
- 搜索关键函数：`encode()`, `EncodingKey::from_secret()`, `DecodingKey::from_secret()`
- 搜索常见 crate 导入：`use jsonwebtoken::{encode, decode, EncodingKey, DecodingKey}`
- 关注字符串字面量紧邻密钥操作：`.from_secret("xxx".as_ref())` 或 `.from_secret(b"xxx")`
- 查找 const/static 声明：`const JWT_SECRET`, `static SECRET_KEY`

**快速定位保护机制技巧（L3:逐行读）：**
- 检查密钥来源：`env::var("JWT_SECRET")`, `fs::read_to_string()`, 配置文件加载
- 确认是否使用密钥管理服务：AWS KMS、Vault 等 API 调用
- 验证密钥轮转逻辑：时间戳检查、版本号、多密钥支持
- 审查配置结构体：`Config::from_env()`, `dotenv!()`, `lazy_static!` 中的动态加载
- 排除测试代码：检查 `#[cfg(test)]` 或 `#[test]` 标注

## Classify

**漏洞判定标准：**
- 生产环境使用硬编码密钥且无动态覆盖机制
- 静态密钥直接写在业务代码逻辑中
- 密钥值为弱密钥（如 "secret", "123456", "test"）

**误报排除条件：**
- 测试代码或示例代码（含 `#[cfg(test)]` 或位于 `tests/` 目录）
- 硬编码仅作默认值，运行时从环境变量/配置文件强制覆盖
- 开发环境专用配置，明确与生产隔离（需验证部署流程）

**代码异味识别：**
- 静态密钥但长度足够（>32字节）且有注释说明需手动配置
- 使用 `lazy_static!` 但仍从硬编码初始化，未关联外部源
- 密钥定义与使用分散在多个模块，缺乏统一管理

## Low Risk

**低风险场景评级条件：**
- 仅用于内部服务间通信且网络隔离严格（需确认网络架构）
- Token 有效期极短（<5分钟）且有其他认证层（如 mTLS）
- 系统即将下线或处于 POC 阶段，非长期运行
- 配合 IP 白名单、VPN 等额外访问控制
- 密钥已在安全审计后确认为临时方案且有修复计划（需文档佐证）

**注意：** 即使评为低风险，仍需在审计报告中标注为改进项，建议迁移至动态密钥管理。

## 审计专业技巧

### 1. 深层审计技巧

**Cargo.toml 依赖分析：**
- 检查 `jsonwebtoken` crate 版本是否过旧（v9.0 前安全性较弱）
- 注意 `dotenv`, `config`, `envy` 等配置加载库的使用方式
- 确认是否集成了 `vault`, `aws-kms`, `azure-keyvault` 等密钥管理依赖

**隐蔽硬编码识别：**
```rust
// 变种1：Base64编码掩盖
const SECRET: &[u8] = b"bXlfc2VjcmV0X2tleQ=="; // my_secret_key

// 变种2：字符串拼接延迟暴露
fn get_secret() -> String {
    let mut s = String::from("my_");
    s.push_str("secret_key");
    s
}

// 变种3：宏展开隐藏
const SECRET: &str = concat!("my", "_secret_key");
```
审计时需追踪宏展开和字符串操作的最终结果。

**构建配置检查：**
- 查看 `build.rs` 是否在编译期嵌入密钥
- 检查 feature flags（`--features prod` vs `--features dev`）是否影响密钥加载逻辑
- 验证 profile 配置（debug/release）对密钥源的影响

### 2. 真实漏洞与误报区分

**案例1：真实漏洞 - GitHub 提交历史暴露**
```rust
// src/auth.rs 当前版本
const JWT_SECRET: &str = env!("JWT_SECRET");

// ❌ 但历史版本（git log）中有：
// const JWT_SECRET: &str = "SuP3r_S3cr3t_P@ssw0rd";
```
→ 判定：**真实漏洞**。即使当前代码动态加载，历史密钥仍可被恢复攻击，需检查是否已轮转。

**案例2：误报 - 测试用密钥与生产隔离**
```rust
#[cfg(test)]
mod tests {
    const TEST_SECRET: &str = "test_secret_key";

    #[test]
    fn test_token_validation() {
        let key = EncodingKey::from_secret(TEST_SECRET.as_ref());
        // test code
    }
}

// 生产代码
fn get_production_secret() -> String {
    env::var("JWT_SECRET").expect("JWT_SECRET not set")
}
```
→ 判定：**误报**。测试密钥与生产完全隔离，不会进入生产镜像。

**案例3：边界情况 - 开发环境硬编码**
```rust
#[cfg(not(feature = "production"))]
const DEFAULT_SECRET: &str = "dev_secret_key";

#[cfg(feature = "production")]
fn get_secret() -> String {
    env::var("JWT_SECRET").expect("production secret required")
}
```
→ 判定：**风险需确认**。需验证：
  - CI/CD 是否显式启用 `production` feature
  - 容器镜像/部署清单中是否强制激活该 feature
  - dev 配置是否可能被误用于生产

### 3. 高级审计检查清单

**密钥熵与强度评估：**
- 硬编码密钥长度 < 32 字节 → 信息熵不足，判定为漏洞
- 密钥仅含字母/数字（无特殊字符）→ 手动生成的可能性大，风险升级
- 密钥中出现常见模式（"password", "secret", "test", "admin"）→ 必判漏洞

**作用域隔离验证：**
```rust
// 检查密钥是否限制在特定模块
mod auth {
    const SECRET: &str = "..."; // 私有常量

    pub fn create_token() { /* use SECRET */ }
    pub fn verify_token() { /* use SECRET */ }
}
// ❌ 如果 SECRET 被 pub static 暴露或泄露到其他模块
```

**依赖传递链分析：**
- 审查是否通过间接依赖暴露密钥（如日志库、监控库无意记录）
- 检查错误处理是否在异常消息中泄露密钥片段

### 4. 常见误报避坑

**误报1：`env!()` 宏的混淆**
```rust
// 正确做法（运行时读取）
const SECRET: &str = env!("JWT_SECRET");

// ❌ 审计误区：认为这是硬编码
// 实际上 env!() 在编译期捕获环境变量，不是字符串字面量
```
→ 但需注意：如果编译环境与运行环境不同，`env!()` 仍可能固化错误值。

**误报2：开发工具中的示例代码**
- 查看 `examples/` 目录、CLI 工具、测试夹具中的硬编码密钥
- 这些通常不会被编译进产物，但需在文档中标注不可用于生产

**误报3：注释中的历史密钥**
```rust
// TODO: 删除以下测试密钥
// const OLD_SECRET: &str = "test_123";
```
→ 注释不会进入编译产物，但建议清理以降低可维护性风险。

## 实战审计建议

1. **多层面验证**：不仅查看代码，还需检查：
   - 构建日志中是否暴露密钥
   - Docker/K8s 配置是否正确传入环境变量
   - CI/CD 日志、镜像扫描报告

2. **密钥轮转历史**：
   - 即使当前代码正确，也要查看是否曾使用泄露密钥
   - 联动红队测试：尝试用历史密钥伪造 Token

3. **上下文综合评分**：
   - 硬编码 + 对外暴露 API = 高危
   - 硬编码 + 仅内网访问 + 短有效期 = 低危
   - 硬编码 + 已在审计中确认轮转完成 = 改进项