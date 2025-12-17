# Rust 动态库加载代码注入

**漏洞成因**：使用 `libloading` 或 `dlopen` 等方式动态加载用户可控的库文件路径，导致攻击者可加载恶意共享库。常见于插件系统、模块加载、动态扩展等场景。动态库加载具有完整的代码执行权限，攻击者可通过恶意库执行任意代码、获取敏感数据、篡改程序行为。

---

## Details

**代码示例**：
```rust
// 危险：直接使用用户输入的库路径
let lib_path = std::env::args().nth(1).unwrap_or_default();
let lib = unsafe { libloading::Library::new(&lib_path) }?;

// 危险：从请求参数加载库
let lib_name = query.get("lib").unwrap_or("default");
let lib = unsafe { libloading::Library::new(format!("./plugins/{}", lib_name)) }?;

// 危险：从环境变量或配置文件加载
let lib_path = std::env::var("PLUGIN_PATH")?;
unsafe { libloading::Library::new(lib_path) }?;

// 危险：动态库符号解析后调用用户可控函数
type InitFn = unsafe extern "C" fn() -> i32;
let init: libloading::Symbol<InitFn> = unsafe { lib.get(b"init")? };
unsafe { init() };

// 危险：dlopen 与 RTLD_GLOBAL 标志（符号全局可见）
unsafe { libc::dlopen(lib_path.as_ptr(), libc::RTLD_LAZY | libc::RTLD_GLOBAL) };
```

**快速定位核心操作**（L1-L2）：
- 关键词：`libloading::Library::new(`、`libloading::Library::open(`、`libc::dlopen(`、`libc::dlsym(`
- 查看库路径参数是否直接或间接来自用户输入（命令行、环境变量、网络请求、文件、数据库）
- 检查路径构造：拼接、格式化、字符串插值（如 `format!()`、f-string）
- 追踪用户输入来源：`std::env::args()`、`std::env::var()`、Web 框架的请求参数、配置解析

**快速定位保护机制**（L2-L3）：
- 是否使用白名单验证库名：预定义的库列表、库名称规范（如仅允许字母数字）
- 是否验证库文件路径：`Path::new()` + `canonicalize()` 确保在预期目录内
- 是否签名验证：检查库文件的密码学签名
- 是否有 SELinux/AppArmor 等强制访问控制（MAC）限制库加载
- 是否限制 dlopen 标志：避免使用 `RTLD_GLOBAL` 等危险标志

**审计等级**：**L2-L4**
- **L2**：跳读含有 `Library::new/open` 的代码块，快速定位库路径参数来源
- **L3**：逐行读取路径参数构造逻辑，确认是否包含用户输入及其他防护机制
- **L4**：跨模块追踪用户输入到库加载的完整数据流，验证所有转换和校验点

---

## Classify

**确认为漏洞**：
- 库路径直接由用户输入拼接或参数化（无路径规范化）
- 库文件位置可由攻击者控制（如 Web 可写目录、临时目录、PATH 环境变量目录）
- 存在路径遍历漏洞：如 `./plugins/{user_input}` 允许 `../../../tmp/evil.so`
- 无文件签名验证或签名验证可绕过
- 使用危险的 dlopen 标志（如 `RTLD_GLOBAL`）导致符号污染
- 库的初始化函数（如 `init()`、`plugin_load()`）本身也存在代码注入漏洞

**误报**：
- 库路径为完全硬编码常量，不含任何用户可控数据
- 库文件存储在只读目录（如系统目录 `/usr/lib`），且文件权限严格限制
- 库文件来自受信任的源（如官方软件包管理器），与用户输入无关
- 虽使用 `libloading`，但仅加载系统库（无自定义库），且无格式化构造

**代码异味**：
- 库路径使用格式化或字符串拼接构造，但声称有输入验证（未验证实现）
- 库加载存在但位于不可信代码路径（权限控制依赖前端或 session）
- 业务逻辑可用模块系统或宏替代，无需动态库加载
- 存在相对路径加载（如 `./plugins/lib.so`），未使用绝对路径或 `canonicalize()` 规范化

---

## Low Risk

以下情况可评为低风险：
- **受限执行环境**：容器/虚拟机内执行，库文件存储在只读挂载点，攻击者无法替换库文件
- **严格的白名单**：库名称通过严格白名单限制，且白名单存储在不可篡改的配置或代码中
- **密码学签名验证**：库文件加载前进行完整性校验（如 RSA/HMAC 签名），签名验证正确实现
- **权限隔离**：使用容器 capabilities、SELinux、AppArmor 等强制访问控制，限制库加载路径
- **源控制**：库文件来自官方软件包管理器或受信任的内部仓库，与用户输入完全隔离
- **审计日志完整**：所有库加载事件被完整记录、监控，包括库路径、时间戳、调用者
- **内网隔离**：仅限管理员或特定 IP 段的内网服务访问动态库加载功能
