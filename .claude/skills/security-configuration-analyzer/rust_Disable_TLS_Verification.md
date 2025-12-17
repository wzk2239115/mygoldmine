# Rust - Disable TLS Verification

## Details

### 代码示例

```rust
// 示例1: reqwest 禁用证书验证
use reqwest::Client;
let client = Client::builder()
    .danger_accept_invalid_certs(true)  // 危险配置
    .build()?;

// 示例2: reqwest 禁用主机名验证
let client = Client::builder()
    .danger_accept_invalid_hostnames(true)
    .build()?;

// 示例3: rustls 自定义危险验证器
use rustls::{ClientConfig, ServerCertVerifier};
struct NoVerifier;
impl ServerCertVerifier for NoVerifier {
    fn verify_server_cert(&self, ...) -> Result<...> {
        Ok(())  // 直接返回成功，跳过验证
    }
}
let config = ClientConfig::builder()
    .with_custom_certificate_verifier(Arc::new(NoVerifier));

// 示例4: hyper + native-tls 禁用验证
use native_tls::TlsConnector;
let connector = TlsConnector::builder()
    .danger_accept_invalid_certs(true)
    .build()?;

// 示例5: actix-web 客户端禁用验证
use actix_web::client::Client;
let client = Client::builder()
    .disable_ssl_verification()  // 旧版API
    .finish();

// 示例6: tokio-tls 不验证证书链
use tokio_native_tls::TlsConnector;
let cx = native_tls::TlsConnector::builder()
    .danger_accept_invalid_certs(true)
    .build()?;
let cx = tokio_native_tls::TlsConnector::from(cx);
```

### 快速定位核心操作（审计技巧）

**L1 - 关键词扫描：**
- 危险方法：`danger_accept_invalid_certs`、`danger_accept_invalid_hostnames`、`disable_ssl_verification`
- 自定义验证器：`ServerCertVerifier`、`with_custom_certificate_verifier`、`with_cert_verifier`
- 配置构建：`ClientConfig::builder()`、`TlsConnector::builder()`、`Client::builder()`
- 不安全选项：`rustls::NoClientAuth`、`AcceptAnyServerCert`（第三方）

**L2 - 跳读：**
- HTTP客户端初始化：定位 `reqwest::Client`、`hyper::Client`、`awc::Client` 的构建链
- TLS上下文配置：查找 `ClientConfig`、`TlsConnector` 的配置方法调用
- 全局单例客户端：检查 `lazy_static!`、`OnceCell`、`static` 中的客户端配置
- 条件编译块：`#[cfg(debug_assertions)]` 或 `#[cfg(test)]` 中的不安全配置

**L3 - 逐行读：**
- 验证器实现：检查 `impl ServerCertVerifier` 中是否直接返回 `Ok(())`
- 错误处理链：追踪 `Result` 传播路径，确认验证错误是否被 `.unwrap_or(true)` 忽略
- 证书加载逻辑：`add_root_certificate`、`with_root_certificates` 是否为空或被跳过
- 特性标志（Feature flags）：`Cargo.toml` 中的 `dangerous_configuration` 特性是否启用

**L4 - 跨模块追踪：**
- 工厂函数封装：追踪 `create_client()`、`get_http_client()` 等工厂方法的实现
- 依赖注入配置：检查 DI 容器（如 `shaku`）中客户端的注册配置
- 环境变量控制：查找 `std::env::var("SKIP_TLS_VERIFY")` 等运行时开关
- Trait 默认实现：检查自定义 `HttpClient` trait 的默认验证行为

### 快速定位保护机制（审计技巧）

**L1 - 关键词扫描：**
- 安全默认值：`webpki_roots`、`native_roots`、`with_native_roots()`
- 证书固定：`add_root_certificate`、`Certificate::from_pem`、`with_custom_roots`
- 严格模式：`require_ecdsa`、`with_safe_defaults`、`enable_sni(true)`

**L2 - 跳读：**
- 检查 `Cargo.toml` 依赖版本：`rustls` >= 0.20 默认更严格
- 查找证书文件加载：`include_bytes!("ca-bundle.crt")`、`fs::read("certs/")`
- 确认 `.danger_*` 方法调用前是否有条件判断（如 `if !cfg!(production)`）
- 验证是否存在证书撤销检查（CRL/OCSP）相关代码

**L3 - 逐行读：**
- 自定义验证器完整性：检查 `verify_server_cert` 是否实际调用了 `webpki::verify_server_cert`
- 错误传播路径：确认 TLS 错误未被 `.ok()`、`let _ = ` 吞噬
- 测试覆盖：检查是否有针对证书验证失败的单元测试
- 日志记录：验证失败时是否有 `log::warn!` 或安全日志记录

**L0 - 快速跳过：**
- 集成测试目录：`tests/` 中使用自签名证书的测试客户端
- 示例代码：`examples/` 目录中的快速演示
- Mock HTTP服务：使用 `mockito`、`wiremock` 等库的测试代码
- 文档注释：`/// # Examples` 中的代码片段

## Classify

### 确认为漏洞的判定标准：
- 生产代码中显式调用 `danger_accept_invalid_certs(true)` 或等效方法
- 自定义 `ServerCertVerifier` 实现未执行实际验证逻辑，直接返回成功
- 通过环境变量或配置文件控制禁用验证，且生产环境配置为 `true`
- TLS 客户端构建时未指定根证书且未使用系统默认证书库

### 误报的常见场景：
- 单元测试或集成测试中的 Mock HTTP 服务器（通过 `#[cfg(test)]` 隔离）
- 示例代码中明确注释"仅用于开发环境"的演示客户端
- 工具脚本（如 `scripts/`）中用于调试的临时客户端
- 文档生成工具（如 `cargo doc`）引用的示例代码片段

### 代码异味的判定：
- 使用条件编译但边界模糊：如 `#[cfg(not(production))]` 但 `production` 特性未在 CI 中强制启用
- 环境变量控制开关但无默认安全值：`env::var("VERIFY_SSL").unwrap_or("false")`
- 自定义验证器仅检查证书存在性但不验证签名链
- 日志中警告"跳过证书验证"但仍继续执行而非失败

### 研判流程：
1. 确认代码路径：通过 `#[cfg(...)]` 属性判断是否仅限测试/开发环境
2. 检查调用上下文：追踪客户端使用场景（内部微服务调用 vs 外部API请求）
3. 评估威胁模型：内网环境自签名证书 vs 公网服务绕过CA验证
4. 验证运行时配置：检查 `.env`、`config.toml`、Kubernetes ConfigMap 中的实际值

## Low Risk

### 低风险场景评级标准：

**场景1：开发环境本地服务**
- 通过 `#[cfg(debug_assertions)]` 严格限制在开发构建
- 仅连接 `localhost` 或 `127.0.0.1` 的自签名服务
- 代码注释明确标注"本地开发环境专用"
- 生产构建通过 `--release` 自动排除该代码路径

**场景2：隔离测试环境**
- 位于 `tests/` 或 `benches/` 目录，仅在 `cargo test` 时编译
- 使用 `wiremock`、`httpmock` 等库生成的临时 HTTPS 端点
- 测试中显式使用 `rcgen` 生成临时自签名证书
- CI/CD 流水线中无法访问生产网络

**场景3：内部信任网络（需谨慎评估）**
- 企业内网所有服务使用统一自签名根证书（应优先通过 `add_root_certificate` 添加企业CA）
- Kubernetes 集群内 Service Mesh 场景（如 Istio mTLS，但仍建议正确配置证书）
- 硬件设备固件 HTTPS 接口使用出厂证书（需确认设备物理隔离）

**场景4：工具脚本与调试**
- `bin/` 目录中的运维工具明确注释"内部工具"
- 临时调试代码且通过 Git 历史确认未合并至主分支
- 开发者本地 `.cargo/config.toml` 覆盖配置（不在版本控制中）

**评级降级条件（即使符合低风险也需提升等级）：**
- 代码中存在运行时开关可动态禁用验证（如命令行参数 `--insecure`）
- 配置文件中存在 `verify_ssl: false` 选项且无环境区分
- 自定义验证器虽在测试中，但可被外部 crate 直接导入复用
- 历史提交显示曾因证书问题临时禁用验证后未恢复
- Docker 镜像或二进制发布包中包含该配置
