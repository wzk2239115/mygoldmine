# C/C++ dlsym() 动态符号解析代码执行注入

## 漏洞成因

C/C++ 的 `dlsym()` 函数用于在动态加载的共享库中查找符号地址。当符号名称来自用户可控的输入时，攻击者可加载并执行任意库中的任意函数。结合 `dlopen()` 动态加载库，可实现完整的代码执行。此外，通过解析符号表、GOT（全局偏移表）污染等技术，可进一步扩大攻击面。

---

## Details

### 代码示例

```c
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// 危险模式1：直接使用用户输入作为符号名
void handle_symbol_lookup(const char *symbol_name) {
    void *handle = dlopen(NULL, RTLD_LAZY);  // 打开当前进程
    if (!handle) {
        fprintf(stderr, "dlopen failed: %s\n", dlerror());
        return;
    }

    // 危险：symbol_name 完全可控
    typedef int (*func_t)(void);
    func_t fn = (func_t) dlsym(handle, symbol_name);
    if (!fn) {
        fprintf(stderr, "dlsym failed: %s\n", dlerror());
        dlclose(handle);
        return;
    }

    fn();  // 执行任意函数
    dlclose(handle);
}

// 危险模式2：从用户输入加载库，再解析符号
void load_and_execute(const char *lib_path, const char *func_name) {
    void *handle = dlopen(lib_path, RTLD_LAZY);  // 危险：lib_path 可控
    if (!handle) {
        fprintf(stderr, "dlopen failed: %s\n", dlerror());
        return;
    }

    typedef int (*func_t)(void);
    func_t fn = (func_t) dlsym(handle, func_name);  // 危险：func_name 可控
    if (!fn) {
        fprintf(stderr, "dlsym failed: %s\n", dlerror());
        dlclose(handle);
        return;
    }

    fn();
    dlclose(handle);
}

// 危险模式3：使用用户输入拼接符号名
void handle_method_call(const char *class_name, const char *method_name) {
    void *handle = dlopen("./libapp.so", RTLD_LAZY);
    if (!handle) {
        fprintf(stderr, "dlopen failed\n");
        return;
    }

    // 构造符号名：_ZN[class][method]...
    char symbol[256];
    snprintf(symbol, sizeof(symbol), "_ZN%s%s", class_name, method_name);  // 危险

    typedef int (*func_t)(void);
    func_t fn = (func_t) dlsym(handle, symbol);
    if (!fn) {
        fprintf(stderr, "dlsym failed\n");
        dlclose(handle);
        return;
    }

    fn();
    dlclose(handle);
}

// 危险模式4：从环境变量或配置加载库路径
void handle_plugin_loading(void) {
    const char *plugin_dir = getenv("PLUGIN_DIR");  // 危险：环境变量可控
    if (!plugin_dir) {
        plugin_dir = "./plugins";
    }

    char lib_path[512];
    snprintf(lib_path, sizeof(lib_path), "%s/plugin.so", plugin_dir);

    void *handle = dlopen(lib_path, RTLD_LAZY);
    if (!handle) {
        fprintf(stderr, "dlopen failed\n");
        return;
    }

    typedef int (*init_t)(void);
    init_t init_fn = (init_t) dlsym(handle, "plugin_init");
    if (!init_fn) {
        fprintf(stderr, "dlsym failed\n");
        dlclose(handle);
        return;
    }

    init_fn();
    dlclose(handle);
}

// 危险模式5：利用 GOT 污染
void vulnerable_got_overwrite(const char *func_name) {
    void *handle = dlopen(NULL, RTLD_LAZY);
    if (!handle) return;

    // 获取函数指针
    typedef int (*func_t)(void);
    func_t original = (func_t) dlsym(handle, "strcpy");  // 库函数

    // 危险：可能通过符号解析污染 GOT
    func_t overwritten = (func_t) dlsym(handle, func_name);  // 用户输入
    if (overwritten) {
        // 如果 dlsym 返回相同地址，意味着符号被覆盖
        if (original == overwritten) {
            printf("GOT pollution detected\n");
        }
    }

    dlclose(handle);
}

// 危险模式6：从 HTTP 请求获取符号名
void handle_http_request(char *symbol_name) {
    // 假设 symbol_name 来自 HTTP 请求参数
    void *handle = dlopen(NULL, RTLD_LAZY);
    if (!handle) return;

    typedef void (*fn_t)(void);
    fn_t fn = (fn_t) dlsym(handle, symbol_name);  // 危险
    if (fn) {
        fn();
    }

    dlclose(handle);
}

// 危险模式7：循环加载多个库
void load_multiple_plugins(const char *plugin_names[]) {
    for (int i = 0; plugin_names[i]; i++) {
        // 危险：plugin_names[i] 完全可控
        char lib_path[256];
        snprintf(lib_path, sizeof(lib_path), "./plugins/%s.so", plugin_names[i]);

        void *handle = dlopen(lib_path, RTLD_LAZY);
        if (handle) {
            typedef int (*init_t)(void);
            init_t init = (init_t) dlsym(handle, "plugin_init");
            if (init) init();
            dlclose(handle);
        }
    }
}

// 危险模式8：使用 dlsym 进行 ASLR 绕过
void exploit_aslr_bypass(const char *symbol_name) {
    void *handle = dlopen(NULL, RTLD_LAZY);
    if (!handle) return;

    // 获取 symbol 地址用于 ROP/JOP 攻击
    void *symbol_addr = dlsym(handle, symbol_name);  // 危险
    if (symbol_addr) {
        printf("Symbol address: %p\n", symbol_addr);  // 泄漏地址信息
        // 可用于构造 ROP chain、heap spray 等高级攻击
    }

    dlclose(handle);
}

// 辅助函数
int unsafe_function(void) {
    char buffer[64];
    strcpy(buffer, "malicious data");  // 缓冲区溢出示例
    return 0;
}
```

### 快速定位核心操作 (L1-L3)

**L1 关键词扫描**：
- 搜索 `dlsym(`
- 搜索 `dlopen(`
- 搜索 `dlerror()`、`dlclose()`（表示动态加载使用）
- 搜索强制类型转换为函数指针：`(func_t)`、`(void*)`、`(int (*)(...))`
- 搜索用户输入来源：`argv`、`getenv`、HTTP 参数、文件读取、socket 接收
- 搜索字符串拼接或格式化用于库路径或符号名：`snprintf`、`sprintf`、`strcat`
- 搜索符号名处理：C++ 名称 mangling（`_ZN` 前缀）

**L2 跳读**：
- 定位所有 `dlsym(` 调用，记录行号和上下文
- 检查第二个参数（符号名）的来源：用户输入、环境变量、配置文件、网络
- 检查 `dlopen()` 的第一个参数（库路径）是否可控
- 检查获取的函数指针如何被使用：直接调用、传递给其他函数、用于内存访问
- 检查是否有符号名白名单或黑名单验证
- 检查是否使用了 `RTLD_LAZY`（延迟绑定）或 `RTLD_NOW`（立即绑定）
- 追踪是否在循环中多次加载库（可能导致资源泄漏或 DoS）

**L3 逐行读**：
- 确认用户输入的确切来源和传输路径
- 检查输入是否进行了长度、格式、白名单验证
- 逐行追踪所有影响 dlsym 参数的中间变量
- 检查 `dlerror()` 返回值是否正确处理
- 检查函数指针调用时的参数校验
- 检查内存安全：缓冲区大小、指针有效性
- 检查是否存在格式字符串漏洞、缓冲区溢出等经典漏洞
- 检查获取的符号是否被用于信息泄漏（ASLR 绕过）

### 快速定位保护机制 (L2-L4)

**L2 跳读**：
- 检查 dlsym 前是否有严格的条件判断或白名单验证
- 搜索白名单关键词：`allowedSymbols`、`PERMITTED_FUNCTIONS`、`validLibraries`
- 搜索黑名单关键词：`system`、`exec`、`fork`、`dlopen`、`dlsym`、`mmap`、`mprotect`
- 检查是否使用了 `RTLD_GLOBAL`、`RTLD_NODELETE` 等标志
- 检查是否验证了库文件的签名、所有权、权限

**L3 逐行读**：
- 分析白名单实现：精确匹配还是前缀/后缀匹配？
- 分析黑名单实现：是否全面？可否被大小写、路径遍历等绕过？
- 检查符号名验证的完整性：是否允许了特殊字符、路径遍历字符等
- 分析库路径验证：是否使用了绝对路径、是否检查了符号链接
- 检查权限控制：dlopen/dlsym 是否限制了用户访问
- 检查是否对 ASLR 信息泄漏进行了防护（如不输出符号地址）

**L4 跨模块追踪**：
- 追踪自定义的符号白名单库实现
- 检查是否使用了 `nm`、`objdump` 等工具生成符号白名单
- 查找是否有全局的符号验证中间件
- 追踪库搜索路径配置：`LD_LIBRARY_PATH`、`/etc/ld.so.conf`、`rpath`
- 检查是否使用了 `LD_PRELOAD` 防护（但本身也可被攻击）
- 查找是否有 SELinux、AppArmor 策略限制库加载
- 检查编译时是否使用了 `-fPIE`、`-fPIC`、`-fstack-protector` 等防护选项

---

## Classify

### 漏洞判定

- **直接使用用户输入作为符号名** → **确认漏洞**
  - 示例：`dlsym(handle, user_input)`、`dlsym(handle, argv[1])`

- **直接使用用户输入作为库路径** → **确认漏洞**
  - 示例：`dlopen(user_input, RTLD_LAZY)`、`dlopen(getenv("LIB_PATH"), RTLD_LAZY)`

- **使用用户输入拼接符号名或库路径** → **确认漏洞**
  - 示例：`snprintf(symbol, sizeof(symbol), "_ZN%s%s", class_name, method_name)`

- **符号名或库路径来自不可信源且无验证** → **确认漏洞**
  - 示例：从 HTTP 请求、socket、文件等获取，无白名单检查

- **获取的符号地址被泄漏或用于信息泄漏攻击** → **确认漏洞**
  - 示例：输出符号地址用于 ASLR 绕过、或访问不应访问的内存

- **使用黑名单而非白名单验证** → **高风险**
  - 黑名单容易被绕过

### 误报判定

- **符号名和库路径完全来自硬编码常量** → **误报**
  - 示例：`dlsym(handle, "strlen")`、`dlopen("./libapp.so", RTLD_LAZY)`

- **严格的符号名白名单验证** → **误报**
  - 示例：`const char *allowed[] = {"init", "cleanup", "run"}; if (!in_array(symbol_name, allowed)) return error;`

- **使用绝对路径且验证了文件权限** → **误报**
  - 示例：库路径为固定绝对路径，且检查了文件所有者为 root、权限为 0755 等

- **仅加载系统库，不加载用户库** → **误报**
  - 示例：`dlopen(NULL, RTLD_LAZY)` 仅在当前进程符号空间中查找

- **符号名来自受信任的配置文件，无用户输入** → **误报**
  - 示例：符号名从配置文件读取，配置文件仅允许管理员编辑

### 代码异味

- **使用黑名单检查危险函数名** → **需进一步测试**
  - 可被大小写、符号 mangling、别名等绕过

- **仅验证符号名，未验证库路径** → **潜在风险**
  - 库路径可被 `LD_LIBRARY_PATH` 污染

- **使用环境变量控制库路径** → **高风险**
  - 环境变量可被继承进程污染、或通过权限提升攻击修改

- **未检查 dlerror() 返回值** → **可能掩盖攻击**
  - 攻击者可能利用错误处理的差异

- **符号名或库路径长度无限制** → **DoS 风险**
  - 可能导致缓冲区溢出或栈溢出

- **在循环中加载库未做资源限制** → **DoS 风险**
  - 可能导致内存溢出

- **ASLR 绕过风险** → **高风险**
  - 符号地址泄漏可用于构造 ROP 链

### 审计等级

- **L1**：关键词扫描，快速定位所有 dlsym/dlopen 调用
- **L2**：跳读确认符号名和库路径来源、验证机制
- **L3**：逐行读取数据流、分析所有验证逻辑、检查内存安全
- **L4**：跨模块追踪符号白名单、库搜索路径配置、编译防护选项

---

## Low risk

### 低风险场景

- **符号名和库路径完全来自硬编码常量**：所有可能的符号和库在代码中明确列举
  - 示例：`const char *symbols[] = {"init", "cleanup"}; dlsym(handle, symbols[index])`

- **严格的符号名白名单验证**：使用白名单精确匹配，白名单不可被用户修改
  - 示例：`if (strcmp(symbol_name, "init") != 0 && strcmp(symbol_name, "run") != 0) { return error; } dlsym(handle, symbol_name)`

- **库路径使用绝对路径且验证了文件属性**：库路径固定且检查了所有者、权限
  - 示例：`if (stat("/usr/lib/libapp.so", &st) != 0 || st.st_uid != 0 || st.st_mode != 0755) { return error; } dlopen("/usr/lib/libapp.so", ...)`

- **仅加载系统库**：使用 `dlopen(NULL, RTLD_LAZY)` 仅在当前进程符号空间查找
  - 示例：查找已链接的标准库函数，不加载用户库

- **参数来源完全受控**：符号名和库路径来自配置文件、环境变量（已验证）、硬编码常量
  - 示例：配置文件仅允许管理员编辑，已验证其完整性

- **功能权限隔离**：此功能仅限管理员或特定角色访问
  - 示例：`if (!is_root()) { return PERMISSION_DENIED; }`

- **使用 ASLR 信息泄漏防护**：不输出符号地址，不允许地址计算
  - 示例：使用符号功能但不泄漏地址、或使用 PIE/ASLR 使地址不可预测

- **完整的编译时防护**：使用 `-fPIE`、`-fPIC`、`-fstack-protector`、`-D_FORTIFY_SOURCE=2`
  - 示例：编译时启用堆栈保护、堆边界检查等

- **完整的审计日志和监控**：所有 dlsym 和 dlopen 调用被记录
  - 示例：记录符号名、库路径、调用者、时间戳，支持实时告警

### 注意事项

即使满足低风险条件，仍应在审计报告中说明：
- 动态符号加载本身属于高风险操作，建议评估业务场景是否真的需要，是否可以使用插件系统、策略模式等替代
- 应定期审查符号白名单、库路径配置的完整性，确保无遗漏可执行危险操作的路径
- 应建立完整的测试覆盖，确保符号名注入、库路径遍历、ASLR 绕过等攻击向量被充分检验
- 应关注 `LD_LIBRARY_PATH`、`LD_PRELOAD` 等环境变量污染风险，考虑使用 `-Wl,-rpath` 锁定库搜索路径
- 应检查所有强制类型转换，确保函数签名正确，防止栈溢出和内存损坏
- 应验证从 dlsym 获取的函数指针的有效性，检查 `dlerror()` 返回值
- 应避免在信号处理函数中调用 dlsym（可能导致死锁或崩溃）
- 应使用 `-fvisibility=hidden` 限制符号导出，减少攻击面
- 应定期更新依赖库版本，检查是否存在已知漏洞
- 若必须使用 dlopen/dlsym，应在沙箱或容器环境中运行，使用 seccomp 限制系统调用
