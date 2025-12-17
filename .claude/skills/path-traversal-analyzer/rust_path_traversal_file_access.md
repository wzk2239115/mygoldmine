# Rust 路径遍历与文件包含漏洞

## Details

### 漏洞成因
Rust 服务端或 CLI 工具在处理文件访问时常使用 `std::fs::File`, `std::fs::read_to_string`, `tokio::fs`, `async_std::fs` 等 API；Web 框架（Actix Web、Warp、Rocket）也常通过 `NamedFile`, `FileServer`, `fs::read` 返回文件。如果直接将用户输入（URL 参数、JSON 字段、命令行参数）拼接进路径，且未进行 `std::fs::canonicalize` 或前缀校验，攻击者可利用 `../`, `%2e%2e/`, 符号链接等绕过限制读取配置、源码、凭证文件。插件系统或模板引擎（Tera, Handlebars）若允许动态加载文件，也可能导致本地文件包含或远程资源执行。使用 `zip`、`tar` crate 解压用户提供的归档时，若未检查条目路径同样存在目录遍历风险。

### 代码示例

**易受攻击的代码（Actix Web 下载接口）：**
```rust
use actix_files::NamedFile;
use actix_web::{HttpRequest, Result};
use std::path::PathBuf;

pub async fn download(req: HttpRequest) -> Result<NamedFile> {
    let file = req.query_string(); // file=../../../../etc/passwd
    let path: PathBuf = ["/var/app/logs", file].iter().collect();
    Ok(NamedFile::open(path)?) // 未 canonicalize 或前缀校验
}
```

**命令行工具读取配置：**
```rust
use std::fs;

fn read_config(path: &str) -> std::io::Result<String> {
    let content = fs::read_to_string(format!("/etc/app/{}", path))?;
    Ok(content)
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件 API：`File::open`, `fs::read`, `fs::read_to_string`, `std::fs::copy`, `NamedFile::open`
- 异步文件：`tokio::fs::File`, `async_std::fs::File`
- 路径操作：`Path::join`, `PathBuf::from`, `format!` 拼接、`push`
- 模板/插件：`Tera::render`, `handlebars::register_template_file`, `include_str!`, `libloading::Library::new`
- 解压：`zip::ZipArchive`, `tar::Archive`, `walkdir`

**定位步骤：**
1. 搜索上述函数，查找与 `req.match_info`, `query`, `Json`, `Path<String>`, CLI 参数等输入共现的代码段。
2. 关注文件下载、静态资源服务、插件加载、模板渲染、归档处理的模块。
3. 跳读（L2）检查是否进行 `canonicalize`、`strip_prefix` 或白名单映射。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径规范化：** `std::fs::canonicalize`, `Path::canonicalize`
- **根目录校验：** `canonical.starts_with(base_dir)` 或 `Path::strip_prefix`
- **白名单映射：** 将逻辑名称映射为固定路径或资源 ID
- **符号链接检测：** 使用 `metadata` + `file_type().is_symlink()` 拒绝不可信链接
- **模板/插件白名单：** 基于配置文件固定可加载项
- **归档解压保护：** 对 `ZipFile::name()`、`entry.path()` 做 canonicalize + 前缀校验

**定位技巧：**
- 确认 `canonicalize` 结果被使用，且错误时拒绝访问。
- 检查异步文件 API 是否使用相同防护逻辑（例如 `tokio::fs::canonicalize`）。
- 对 `Path::strip_prefix`，注意其返回 `Result`，错误时应拒绝请求。
- 对宏如 `include_str!`，确认传入路径是否可能由用户控制。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用白名单资源或嵌入式文件 | **L0（快速跳过）** | 用户无法自定义路径 |
| `canonicalize` + `strip_prefix` | **L2（跳读）** | 检查异常分支 | 
| 直接拼接用户输入路径 | **L3（逐行读）** | 高风险，需要逐行分析 |
| 动态插件/模板加载、归档解压 | **L4（跨模块追踪）** | 需追踪多模块处理链 |

## Classify

### 研判标准

#### 确认漏洞
判定漏洞需满足：
1. **用户可控路径** 被用于文件访问/模板/插件加载。
2. **缺乏标准化或前缀校验**（未使用 `canonicalize`、`strip_prefix`、白名单）。
3. **敏感影响**：可读取/写入受限文件或执行任意插件。

#### 误报
以下情况可判定为误报：
1. **路径来自固定枚举/配置映射**，不可自定义。
2. **`canonicalize` 后验证目录前缀**，异常即拒绝。
3. **访问目录仅包含无敏感内容的公开资源**，部署时已隔离。

#### 代码异味
需记录但暂不构成漏洞的情况：
1. **仅使用 `Path::join` 或字符串替换过滤 `..`**。
2. **校验存在但忽略 `Result` 错误**，可能绕过保护。
3. **不同平台路径兼容性不足**（忽略 Windows/Unix 差异）。
4. **依赖外部网关/代理限制** 而无应用内校验。

## Low risk

### 低风险评级场景

#### 1. 受控后台命令
- **场景：** CLI 仅在受限环境或管控后台执行。
- **风险评估：** 攻击面小，但需防横向利用。

#### 2. 只读公开目录
- **场景：** 仅暴露公共静态文件目录。
- **风险评估：** 危害有限，但可能泄露目录结构。

#### 3. 最小权限运行
- **场景：** 进程使用受限用户/容器，访问范围小。
- **风险评估：** 降低破坏面，但仍应修复根因。

#### 4. 安全监控与审计
- **场景：** 使用日志/告警监控检测异常路径访问。
- **风险评估：** 提供侦测能力，但无法阻止攻击。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 仅内部调用 | 攻击面有限 | 中 |
| `canonicalize` + `strip_prefix` | 技术封堵遍历 | 低 |
| 最小权限或容器隔离 | 限制危害 | 中 |
| 完整日志与告警 | 提升可见性 | 高（持续推进修复）|

