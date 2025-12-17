# Rust 配置路径包含漏洞

## 漏洞描述
使用配置加载器（如 `config`、`toml`、`serde` 等）读取用户可控路径的配置文件时，缺乏路径规范化、边界检查或符号链接检测，可导致任意文件读取。

---

## Details

### 代码示例

**漏洞模式1：直接拼接配置路径**
```rust
// 危险：用户输入直接用于文件读取
fn load_config(user_path: &str) -> Result<String, std::io::Error> {
    let config_path = format!("configs/{}", user_path);
    std::fs::read_to_string(&config_path)  // 可被 "../../../etc/passwd" 穿越
}

// API 场景
#[get("/config/<name>")]
fn get_config(name: String) -> Result<String, Status> {
    load_config(&name).map_err(|_| Status::NotFound)
}
```

**漏洞模式2：未验证符号链接**
```rust
use std::path::PathBuf;

fn load_user_config(config_name: &str) -> Result<Vec<u8>, std::io::Error> {
    let mut path = PathBuf::from("/app/configs");
    path.push(config_name);  // 未检查符号链接
    std::fs::read(path)      // 可读取链接指向的任意文件
}
```

**漏洞模式3：配置库未限制路径**
```rust
use config::{Config, File};

fn load_dynamic_config(filename: &str) -> Result<Config, config::ConfigError> {
    Config::builder()
        .add_source(File::with_name(filename))  // 用户可控，未验证
        .build()
}
```

### 快速定位核心操作（L2：跳读）
1. **搜索文件读取函数**：`std::fs::read`、`read_to_string`、`File::open`、`include_str!`
2. **搜索配置加载库**：`config::`、`toml::from_str`、`serde_yaml::from_reader`
3. **追踪路径拼接**：`PathBuf::push`、`format!`、`Path::join`
4. **关注动态参数**：函数参数中的 `&str`、`String`、`PathBuf` 类型
5. **回溯数据来源**：HTTP 路由参数（`#[get]`、`Path<>`）、命令行参数（`clap`）、环境变量

### 快速定位保护机制（L3：逐行读）
1. **路径规范化检查**：
   - `canonicalize()` + `starts_with()` 组合验证路径前缀
   - 示例：`path.canonicalize()?.starts_with("/app/configs")`
   
2. **符号链接检测**：
   - `fs::symlink_metadata()` 检查 `is_symlink()`
   - 示例：`!metadata.file_type().is_symlink()`

3. **路径成分验证**：
   - 检查 `..` 或绝对路径：`!path.contains("..")` 
   - 过滤路径分隔符：`!name.contains(['/', '\\'])`

4. **白名单限制**：
   - 扩展名白名单：`path.extension() == Some("toml")`
   - 文件名白名单：预定义合法配置列表

5. **沙箱机制**（L4：跨模块追踪）：
   - 使用 `chroot` 或 `landlock` 限制文件系统访问
   - 容器化部署时的只读挂载点检查

---

## Classify

### 漏洞判定
- **确认漏洞**：用户输入直接或拼接后用于文件系统操作，无任何路径验证，可读取配置目录外文件
- **高危场景**：读取敏感文件（`/etc/passwd`、私钥、数据库配置）或符号链接指向特权文件

### 误报判定
- 路径完全硬编码，无外部输入影响
- 已使用 `canonicalize()` 并严格验证规范化路径在允许目录内
- 符号链接已检测且拒绝，或文件系统挂载为 `nosymfollow` 选项
- 使用 `include_str!` 宏且路径为编译时常量（宏在编译期展开，无运行时风险）

### 代码异味
- 有路径检查但实现不完整（如仅检查 `..` 但未规范化，可被 `./` 或多重编码绕过）
- 依赖扩展名过滤但未验证路径边界（可读取同目录其他敏感文件）
- 符号链接检测存在 TOCTOU 竞态窗口（检测后到读取前文件可能被替换）
- 错误处理泄露路径信息（如 `NotFound` 错误返回完整路径）

---

## Low risk

### 低风险场景
1. **容器化隔离**：应用运行在受限容器中，挂载点仅包含配置文件，无敏感文件可读
2. **最小权限运行**：进程以低权限用户运行，敏感文件本身不可读（依赖 DAC 保护）
3. **只读文件系统**：配置目录为只读挂载，且不存在符号链接到敏感位置
4. **受限文件类型**：仅能读取特定格式配置文件（如 TOML），即使读取也无法有效利用（如二进制文件无法解析）
5. **审计与监控**：有完善的文件访问审计（如 `auditd`），异常读取可快速检测响应
6. **非公开端点**：配置加载接口仅限内部服务调用，需额外认证且有调用日志

### 风险降级条件
- 结合业务逻辑，读取文件内容需经过严格解析（如必须为合法 TOML/YAML），攻击者难以控制输出
- 读取结果不直接返回给用户，仅用于内部配置生效（信息泄露风险低）
- 已有 WAF 或入口网关过滤路径遍历特征（`../`、编码变体等）