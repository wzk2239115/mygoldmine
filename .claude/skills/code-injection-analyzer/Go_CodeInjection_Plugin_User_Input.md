# Go plugin 包动态加载代码执行注入

## 漏洞成因

Go 的 `plugin` 包允许在运行时动态加载编译的共享库（`.so` 文件）。当插件路径来自用户可控的输入时，攻击者可加载恶意插件在应用进程中执行任意代码。由于插件与主程序在同一进程空间，恶意插件拥有主程序的所有权限，可直接访问内存、修改全局状态、调用应用的内部函数。此外，插件的编译、验证、签名等环节缺失时，攻击面更大。

---

## Details

### 代码示例

```go
package main

import (
    "fmt"
    "log"
    "net/http"
    "os"
    "path/filepath"
    "plugin"
)

// 危险模式1：直接使用用户输入加载插件
func handlePluginLoad(w http.ResponseWriter, r *http.Request) {
    pluginName := r.URL.Query().Get("plugin")

    // 危险：pluginName 完全可控，可实现路径遍历
    pluginPath := filepath.Join("./plugins", pluginName)

    p, err := plugin.Open(pluginPath)
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    // 加载符号
    sym, err := p.Lookup("Execute")
    if err != nil {
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }

    // 调用插件函数
    fn, ok := sym.(func())
    if !ok {
        http.Error(w, "invalid function signature", http.StatusBadRequest)
        return
    }

    fn()  // 执行恶意代码
    w.WriteHeader(http.StatusOK)
}

// 危险模式2：从环境变量或配置加载插件路径
func loadPluginFromEnv(pluginName string) {
    pluginDir := os.Getenv("PLUGIN_DIR")  // 危险：环境变量可控
    if pluginDir == "" {
        pluginDir = "./plugins"
    }

    pluginPath := filepath.Join(pluginDir, pluginName+".so")
    p, _ := plugin.Open(pluginPath)

    sym, _ := p.Lookup("Init")
    if fn, ok := sym.(func()); ok {
        fn()
    }
}

// 危险模式3：使用用户输入拼接插件路径
func handleCustomPluginPath(w http.ResponseWriter, r *http.Request) {
    baseDir := r.FormValue("base_dir")
    pluginFile := r.FormValue("plugin")

    // 危险：path.Join 对 ../ 的处理不当，可能导致路径遍历
    // 输入: base_dir="/tmp", plugin="../../etc/passwd"
    // 结果: /tmp/../../etc/passwd = /etc/passwd
    pluginPath := filepath.Join(baseDir, pluginFile)

    p, err := plugin.Open(pluginPath)
    // ...
}

// 危险模式4：从数据库加载插件列表
func loadPluginsFromDB() {
    var plugins []string
    // 从数据库查询插件列表
    db.Find(&plugins)  // 危险：数据库可被污染

    for _, pluginName := range plugins {
        p, _ := plugin.Open("./plugins/" + pluginName + ".so")
        sym, _ := p.Lookup("Run")
        if fn, ok := sym.(func()); ok {
            fn()
        }
    }
}

// 危险模式5：未验证插件签名
func loadUnsignedPlugin(pluginPath string) {
    p, err := plugin.Open(pluginPath)
    if err != nil {
        log.Fatal(err)
    }

    sym, _ := p.Lookup("Handler")
    if fn, ok := sym.(func()); ok {
        fn()  // 危险：没有验证插件的来源和完整性
    }
}

// 危险模式6：使用 plugin.Open 加载任意位置的库
func handleHTTPPluginPath(w http.ResponseWriter, r *http.Request) {
    pluginPath := r.PostFormValue("plugin_path")

    // 危险：可以加载 /lib/x86_64-linux-gnu/libc.so.6 等系统库
    // 或通过 LD_PRELOAD 预加载的恶意库
    p, err := plugin.Open(pluginPath)
    if err != nil {
        return
    }

    sym, _ := p.Lookup("ProcessRequest")
    if fn, ok := sym.(func()); ok {
        fn()
    }
}

// 危险模式7：循环加载多个插件，无资源限制
func loadMultiplePlugins(pluginNames []string) {
    for _, name := range pluginNames {
        p, _ := plugin.Open("./plugins/" + name + ".so")

        // 危险：每次加载都会增加内存使用，无法卸载
        // 恶意攻击者可发送大量请求导致 OOM
        sym, _ := p.Lookup("Execute")
        if fn, ok := sym.(func()); ok {
            fn()
        }
    }
}

// 危险模式8：插件中包含 init() 函数自动执行
func loadPluginWithInit() {
    // plugin.Open 时，插件的 init() 函数会自动执行
    // 危险：即使不调用任何符号，恶意 init() 也会执行
    p, _ := plugin.Open("./plugins/malicious.so")

    // 此时恶意代码已经执行，无法阻止
    sym, _ := p.Lookup("DoSomething")
    // ...
}

// 危险模式9：从文件上传加载插件
func handlePluginUpload(w http.ResponseWriter, r *http.Request) {
    file, _, err := r.FormFile("plugin")
    if err != nil {
        return
    }
    defer file.Close()

    // 危险：直接保存上传的 .so 文件
    tmpFile := "/tmp/uploaded.so"
    dst, _ := os.Create(tmpFile)
    defer dst.Close()

    // 复制上传的文件内容
    // 危险：没有验证文件格式、签名等
    io.Copy(dst, file)

    // 加载上传的插件
    p, _ := plugin.Open(tmpFile)
    sym, _ := p.Lookup("Execute")
    if fn, ok := sym.(func()); ok {
        fn()
    }
}

// 危险模式10：使用 plugin.Open 加载 .a 静态库（可能被编译成 .so）
func loadCompiledArchive() {
    // 如果 .a 文件被编译成了 .so，plugin.Open 可能加载它
    p, _ := plugin.Open("./lib/archive.so")
    // ...
}

// 辅助函数
func init() {
    // 注意：每个 Go 程序的 init 都会执行
}
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `plugin.Open(`
- 搜索 `plugin.Lookup(`
- 搜索变量赋值给 plugin.Open 的参数：查找插件路径的来源
- 搜索字符串拼接或路径操作：`filepath.Join`、`os.path.Join`、字符串连接
- 搜索用户输入来源：`r.URL.Query()`、`r.FormValue()`、`r.PostFormValue()`、环境变量、文件操作
- 搜索 `filepath` 包的使用（特别是 `Join`、`Clean`、`Abs`）
- 搜索 `init()` 函数（plugins 的 init 会自动执行）

**L2 跳读**：
- 定位所有 `plugin.Open(` 调用，记录行号和上下文
- 检查参数（插件路径）的来源：用户输入、环境变量、配置文件、数据库
- 检查是否使用了 `filepath.Join` 等路径操作（可能被路径遍历攻击）
- 检查是否在加载前验证了文件（签名、所有者、权限）
- 检查是否有插件名称的白名单验证
- 检查 `plugin.Lookup` 后的函数是否被安全地调用
- 检查是否处理了加载失败的情况
- 追踪是否在循环或高频操作中加载插件

**L3 逐行读**：
- 确认用户输入的确切来源和传输路径
- 检查插件路径验证的完整性：是否检查了 `..`、绝对路径、符号链接等
- 逐行追踪所有影响 plugin.Open 参数的中间变量
- 检查文件权限验证：是否验证了所有者、权限位
- 检查是否对 plugin.Lookup 返回的符号进行了类型检查
- 检查是否有超时机制防止恶意插件的无限循环
- 检查插件的内存使用情况：是否可能导致 OOM
- 检查是否存在加载后的清理逻辑

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查 plugin.Open 前是否有条件判断或白名单验证
- 搜索白名单关键词：`allowedPlugins`、`PERMITTED_PLUGINS`、`validPlugins`
- 搜索签名验证相关：`crypto/sha256`、`crypto/rsa`、`crypto/ed25519`、`verify`
- 检查是否验证了文件属性：`os.Stat`、权限检查
- 检查是否使用了绝对路径
- 检查是否禁用了 `LD_PRELOAD` 或其他环境变量污染

**L3 逐行读**：
- 分析白名单实现：是否为精确匹配、是否不可被用户修改
- 分析路径验证：`filepath.Clean`、`filepath.Abs` 是否正确使用
- 检查签名验证的完整性：是否验证了公钥、签名算法
- 检查文件权限验证：是否验证了所有者为特定用户、权限为 0755 等
- 检查是否使用了 `filepath.IsAbs` 确保使用了绝对路径
- 检查 `filepath.Join` 的安全性：是否会被 `..` 绕过

**L4 跨模块追踪**：
- 追踪自定义的插件白名单库实现
- 检查是否使用了密码学签名库（如 `golang.org/x/crypto`）
- 查找是否有全局的插件加载验证中间件
- 追踪文件系统权限验证的实现
- 检查是否使用了 SELinux、AppArmor 等强制访问控制
- 查找是否有 Go 编译时的安全标志（如 `-trimpath` 移除路径信息）
- 检查是否有资源隔离机制（如 cgroup 限制内存）

---

## Classify

### 漏洞判定

- **直接使用用户输入作为插件路径** → **确认漏洞**
  - 示例：`plugin.Open(r.Query("plugin_path"))`、`plugin.Open(os.Args[1])`

- **使用用户输入拼接插件路径** → **确认漏洞**
  - 示例：`plugin.Open("./plugins/" + userInput + ".so")`
  - 示例：`filepath.Join(userBaseDir, userPluginFile)`

- **从不可信源加载插件路径，无签名验证** → **确认漏洞**
  - 示例：从数据库、配置文件、环境变量等加载路径，无签名验证

- **插件路径可被路径遍历攻击** → **确认漏洞**
  - 示例：`plugin.Open("./plugins/" + userInput)` 其中 userInput 包含 `../`

- **加载文件上传的插件，无验证** → **确认漏洞**
  - 示例：接收用户上传的 `.so` 文件，直接 plugin.Open

- **未验证插件文件的所有者和权限** → **确认漏洞**
  - 示例：加载非 root 拥有、权限不是 0755 的插件

- **使用黑名单而非白名单** → **高风险**
  - 黑名单容易被绕过

### 误报判定

- **插件路径完全来自硬编码常量** → **误报**
  - 示例：`plugin.Open("./plugins/auth.so")`

- **严格的插件白名单验证** → **误报**
  - 示例：`allowed := ["plugin1", "plugin2"]; if !contains(allowed, name) { error } plugin.Open(...)`

- **验证了文件签名和所有权** → **误报**
  - 示例：验证了 RSA 签名、检查了所有者为 root、权限为 0755

- **使用绝对路径且验证了文件属性** → **误报**
  - 示例：`plugin.Open("/usr/lib/app/plugins/auth.so")` 且通过 stat 验证了权限

- **在受限的沙箱环境中加载** → **误报**
  - 示例：使用 seccomp、容器隔离，限制了系统调用

### 代码异味

- **使用相对路径加载插件** → **高风险**
  - 可被工作目录改变、LD_LIBRARY_PATH 污染等影响

- **使用 filepath.Join 但未验证结果** → **需进一步测试**
  - filepath.Join("./plugins", "../../../etc/passwd") 可能返回危险路径

- **从环境变量读取插件路径** → **高风险**
  - 环境变量可被继承进程污染

- **在循环中加载插件无资源限制** → **DoS 风险**
  - 可能导致内存溢出，且插件无法卸载

- **加载插件后无错误检查** → **潜在风险**
  - 错误信息可能泄漏敏感信息

- **未禁用 LD_PRELOAD** → **高风险**
  - 可被用于加载恶意库

- **plugin.Lookup 后无类型检查** → **潜在风险**
  - 类型断言失败可能导致 panic

### 审计等级

- **L1**：关键词扫描，快速定位所有 plugin.Open 和 plugin.Lookup 调用
- **L2**：跳读确认插件路径来源、是否有白名单验证
- **L3**：逐行读取路径验证逻辑、文件权限验证、签名验证
- **L4**：跨模块追踪白名单实现、签名验证库、环境变量污染防护

---

## Low risk

### 低风险场景

- **插件路径完全来自硬编码常量**：所有可能的插件在代码中明确列举
  - 示例：`const plugins = []string{"auth.so", "cache.so"}; plugin.Open("./plugins/" + plugins[idx])`

- **严格的插件白名单验证**：使用精确匹配，白名单不可被用户修改
  - 示例：`allowed := map[string]bool{"auth": true, "cache": true}; if !allowed[name] { error } plugin.Open(...)`

- **验证了插件文件签名**：使用密码学签名验证插件来源和完整性
  - 示例：验证了 RSA-2048 签名、HMAC-SHA256、ed25519 等

- **验证了文件属性**：检查了所有者、权限、路径
  - 示例：`stat(path) && owner==root && perm==0755 && !symlink && isAbsPath`

- **使用绝对路径**：插件路径为固定绝对路径，不受工作目录影响
  - 示例：`plugin.Open("/usr/lib/app/plugins/auth.so")`

- **参数来源完全受控**：插件名仅来自配置文件、硬编码常量，无用户输入
  - 示例：配置文件仅允许管理员编辑，已通过权限验证

- **功能权限隔离**：插件加载功能仅限管理员或特定角色
  - 示例：`if !user.IsAdmin() { return errors.New("permission denied") }`

- **在隔离的沙箱中执行**：使用容器、seccomp、cgroup 等限制插件权限
  - 示例：运行在容器中，使用 seccomp profile 限制系统调用

- **完整的审计日志和监控**：所有插件加载操作被记录
  - 示例：记录插件名称、文件路径、验证结果、执行用户、时间戳，支持告警

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- Go 的 plugin 机制本身属于高风险操作，插件与主程序共享内存空间，恶意插件可直接访问应用数据，建议评估是否真的需要动态插件加载
- 应定期审查插件白名单的完整性，确保无遗漏可加载恶意插件的路径
- 应建立完整的测试覆盖，确保路径遍历、符号链接、LD_PRELOAD 等攻击向量被充分检验
- 应实施强制的密码学签名验证，使用长期密钥，定期轮换
- 应验证文件的所有者和权限，确保仅 root 拥有、权限为 0755 或类似的严格权限
- 应禁用环境变量对插件加载路径的影响，如 `LD_LIBRARY_PATH`、`LD_PRELOAD` 等
- 应监控插件的内存使用情况，使用 cgroup 等机制限制内存，防止 OOM
- 应定期审计插件的源代码和二进制文件，检查是否存在恶意代码或后门
- Go plugin 无法卸载（因为 Go runtime 不支持），一旦加载就会占用内存，应限制加载的插件数量
- 应在隔离的容器或虚拟机中运行需要加载动态插件的应用，使用 seccomp 等限制系统调用
- 应避免在高并发、高频率的操作中加载插件（如处理每个 HTTP 请求时加载插件）
