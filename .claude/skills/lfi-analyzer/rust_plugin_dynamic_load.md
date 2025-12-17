# Rust 插件动态加载路径遍历漏洞

## Details

### 代码示例

```rust
// 漏洞代码：直接使用用户输入加载动态库
use libloading::Library;

fn load_plugin(plugin_path: &str) -> Result<Library, Box<dyn Error>> {
    // 危险：未验证路径，可遍历至系统敏感库
    unsafe { Library::new(plugin_path) }
}

// 或使用废弃的 dynamic_lib
use std::dynamic_lib::DynamicLibrary;
let lib = DynamicLibrary::open(Some(Path::new(&user_input)))?;
```

### 快速定位核心操作的技巧 **[审计等级: L1-L2]**

**L1 关键词扫描：**
- `libloading::Library::new`
- `DynamicLibrary::open`
- `dlopen`（FFI 调用）
- `load_library`、`load_plugin` 等自定义加载函数

**L2 跳读定位：**
- 追踪参数来源：检查传入路径是否来自 HTTP 参数、配置文件、环境变量
- 关注 `unsafe` 块中的库加载操作
- 识别插件系统、扩展机制的入口点

### 快速定位保护机制的技巧 **[审计等级: L2-L3]**

**L2 跳读防护：**
- 路径前缀校验：`path.starts_with(PLUGIN_DIR)`
- 白名单检查：硬编码允许的库名称列表
- 文件扩展名限制：`.so`、`.dylib`、`.dll`

**L3 逐行审计：**
- `std::fs::canonicalize()` 规范化路径后的边界检查
- `Path::components()` 过滤 `..` 和绝对路径
- 沙箱环境检查（如 seccomp、AppArmor 策略）
- 签名验证：加载前校验库文件数字签名

**关键反模式：**
```rust
// 不安全的拼接
let path = format!("{}/{}", PLUGIN_DIR, user_input); // 可被 ../../../etc/passwd 绕过

// 仅检查扩展名不足
if user_input.ends_with(".so") { /* 仍可遍历 */ }
```

## Classify

### 确认为漏洞的条件
1. **可控路径源**：参数来自外部输入（HTTP、RPC、配置文件、环境变量）
2. **缺失边界校验**：未使用 `canonicalize()` 或未验证规范化后的路径在安全目录内
3. **实际危害**：可加载系统库（libc.so）或攻击者上传的恶意库，导致任意代码执行

### 判定为误报的情况
- 路径完全硬编码或仅从编译时常量构建
- 已正确使用 `canonicalize()` 并验证结果路径在允许范围内
- 在隔离环境运行（容器/沙箱），且文件系统访问受严格限制

### 代码异味（需进一步人工确认）
- 路径来自"可信"配置文件，但配置文件本身可被篡改
- 有白名单机制但列表过于宽泛（如允许 `/usr/lib/*`）
- 依赖操作系统级权限控制，但应用以高权限运行

## Low risk

以下场景可评估为低风险，但仍建议加固：

1. **受限执行环境**
   - 应用运行在受限用户权限下（非 root/administrator）
   - 部署在容器内，挂载点为只读或白名单路径
   - 启用了 SELinux/AppArmor 强制访问控制

2. **有效的外围防护**
   - 插件目录仅管理员可写，普通用户无法植入恶意库
   - 路径输入经过部分校验（如禁止 `..`），但可能存在绕过
   - 加载前进行哈希校验或权限检查

3. **攻击链不完整**
   - 攻击者可控路径，但无法上传自定义 `.so` 文件
   - 仅能加载系统库，但目标库不包含可利用的导出函数

4. **仅内部使用**
   - 功能仅暴露给本地管理员或可信内部服务
   - 非面向公网的生产环境

**注意**：低风险不等于无风险，应结合实际部署环境和攻击面综合评估。