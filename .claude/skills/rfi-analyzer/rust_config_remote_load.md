# Rust 配置远程加载 RFI

## 漏洞成因
Rust 应用的配置加载器允许从用户可控的远程 URL 拉取配置文件（JSON、YAML、TOML 等），缺乏协议和来源限制，若配置包含可执行表达式则导致代码注入。

---

## Details

### 代码示例

```rust
// 危险示例 1: 直接加载远程 YAML 配置
use std::fs;
use serde_yaml::Value;

let config_url = std::env::var("CONFIG_URL")?;
let resp = reqwest::blocking::get(&config_url)?;
let config: Value = serde_yaml::from_str(&resp.text()?)?;

// 危险示例 2: 用户参数指定配置 URL
let url = req.param("config_path");  // http://evil.com/config.json
let config_text = reqwest::blocking::get(url)?.text()?;
let config: AppConfig = serde_json::from_str(&config_text)?;

// 危险示例 3: 配置反序列化导致代码执行
#[derive(Deserialize)]
struct PluginConfig {
    plugin_path: String,  // 可能被 YAML 注入
    #[serde(deserialize_with = "deserialize_expr")]
    expression: String,   // 动态执行表达式
}

// 危险示例 4: 环境变量驱动的远程配置
let remote_config_url = std::env::var("REMOTE_CONFIG")?;
let config = load_config_from_url(&remote_config_url)?;
```

### 快速定位核心操作 (L2: 跳读)
- **HTTP 客户端**：`reqwest`, `hyper`, `ureq`
- **序列化库**：`serde_json`, `serde_yaml`, `toml`, `ron`
- **反序列化**：`serde::Deserialize`, `from_str()`, `from_slice()`
- **配置来源**：用户参数、环境变量、HTTP 响应
- **危险操作**：
  - 配置反序列化后执行表达式
  - 配置字段用于文件路径、URL、命令

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - 预定义的配置 URL 列表
  - `const ALLOWED_CONFIGS: &[&str] = &["...", "..."];`
- **URL 限制**：
  - 协议限制：`if !url.starts_with("https://")`
  - 域名白名单：`url.parse::<Uri>()?.host() == Some("config.internal.com")`
- **内容验证**：
  - 配置签名验证
  - 配置大小限制
  - `Content-Type` 检查
- **沙箱反序列化**：
  - 禁用危险的反序列化选项
  - 自定义 `Deserialize` 实现限制字段值
- **配置隔离**：
  - 配置中的路径进行白名单验证
  - 配置不允许执行表达式

---

## Classify

### 漏洞
- 用户可控的配置 URL
- 无白名单或白名单可绕过
- 配置直接反序列化无验证
- 配置中包含可执行代码或路径、命令

### 误报
- 配置 URL 完全硬编码或来自受保护的配置文件
- 严格白名单验证
- 配置签名被验证
- 配置字段值受严格限制，无法执行任意代码

### 代码异味
- 配置 URL 部分可控但有验证
- 配置反序列化与验证分离
- 使用弱验证如仅检查 `.json` 后缀

---

## Low risk

- **硬编码配置**：配置 URL 或文件路径完全硬编码，非用户控制
- **协议 + 域名双重限制**：仅允许 HTTPS 且仅限特定信任域名
- **签名验证**：配置加载前验证 GPG 或 HMAC 签名
- **配置白名单**：反序列化时仅允许预期字段，额外字段被拒绝
- **表达式禁用**：配置明确不支持表达式或命令执行
- **内网隔离**：应用运行在无外网访问的网络环境

---

## 审计重点

1. 定位所有 HTTP 请求和配置加载
2. 追踪配置 URL 来源
3. 检查反序列化逻辑和自定义字段处理
4. 验证签名或哈希检查
5. 检查配置字段是否可执行代码或控制应用行为
6. 测试 URL 和配置内容的绕过向量
