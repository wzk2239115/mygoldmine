# C/C++ dlopen 动态库加载本地文件包含

## Details

### 漏洞成因

C/C++ 应用使用 `dlopen()` 动态加载共享库（`.so` 或 `.dll` 文件）时，若库文件路径由用户输入控制且未做白名单验证，攻击者可加载任意恶意动态库实现远程代码执行。此漏洞常见于模块化应用、插件系统、动态链接库加载框架等场景。与文件读取不同，`dlopen()` 加载的代码会在应用进程中直接执行，危害极高。

### 代码示例

**易受攻击的代码（dlopen）：**
```c
#include <dlfcn.h>
#include <stdio.h>

int load_library(const char *lib_name) {
    // lib_name = "../../evil.so"
    char lib_path[256];
    snprintf(lib_path, sizeof(lib_path), "/opt/libs/%s.so", lib_name);

    void *handle = dlopen(lib_path, RTLD_NOW);
    if (handle == NULL) {
        fprintf(stderr, "dlopen failed: %s\n", dlerror());
        return -1;
    }

    // 加载函数指针
    int (*init_func)(void) = (int (*)(void))dlsym(handle, "init");
    if (init_func == NULL) {
        fprintf(stderr, "dlsym failed: %s\n", dlerror());
        dlclose(handle);
        return -1;
    }

    return init_func();
}
```

**无验证的库路径：**
```c
#include <dlfcn.h>

void *load_module(const char *module_path) {
    // module_path = "../../../lib/evil.so.1.0"
    void *handle = dlopen(module_path, RTLD_LAZY | RTLD_GLOBAL);
    if (handle == NULL) {
        printf("Error: %s\n", dlerror());
        return NULL;
    }
    return handle;
}
```

**配置文件指定库路径（高危）：**
```c
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>

void load_configured_library(const char *config_content) {
    // 从配置文件解析库路径
    // config_content = "lib_path=/../../evil.so"
    char *lib_path = strstr(config_content, "lib_path=");
    if (lib_path) {
        lib_path += strlen("lib_path=");
        char path[256];
        sscanf(lib_path, "%255s", path);

        void *handle = dlopen(path, RTLD_NOW);
        if (handle != NULL) {
            // 执行库中的初始化函数
            void (*run)(void) = (void (*)(void))dlsym(handle, "run");
            if (run) run();
        }
    }
}
```

**LD_PRELOAD 滥用风险：**
```c
#include <dlfcn.h>

int main(int argc, char *argv[]) {
    // 虽然直接使用 dlopen，但若应用依赖环境变量加载库
    // 攻击者可通过 LD_PRELOAD 注入恶意库
    // LD_PRELOAD=/tmp/evil.so ./app

    void *libc = dlopen("libc.so.6", RTLD_LAZY);
    // ...
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L3）

**关键词扫描：**
- 动态加载：`dlopen()`, `LoadLibrary()` (Windows), `dlsym()`, `GetProcAddress()`
- 库路径操作：`sprintf()`, `snprintf()`, `strcpy()`, `strcat()`
- 配置解析：从配置文件、网络、数据库读取库路径
- 环境变量：`getenv()`, `LD_LIBRARY_PATH`, `LD_PRELOAD`
- 输入源：命令行参数、网络输入、配置文件、数据库

**定位步骤：**
1. 搜索 `dlopen()` 调用。
2. 检查 `dlopen()` 的参数是否包含变量。
3. 追踪变量的来源：配置文件、网络、数据库、环境变量。
4. 确认是否有白名单验证或路径规范化。

#### 保护机制定位（审计等级：L2-L4）

**检查是否存在：**
- **白名单验证：** 允许加载的库列表（必需）
- **路径规范化：** `realpath()` 规范化路径
- **前缀校验：** 规范化后检查 `strstr()` 固定目录前缀
- **符号链接检查：** `lstat()` 检测符号链接
- **文件权限检查：** 确保库文件仅由 root/管理员可写
- **不使用相对路径：** 禁止从当前目录或任意目录加载
- **禁用 LD_PRELOAD：** 检查应用是否设置了 `RTLD_DEEPBIND` 标志

**定位技巧：**
- 白名单是必需的，仅依赖路径规范化不够安全。
- 验证 `dlopen()` 是否使用了完整路径（如 `/usr/lib/libfoo.so`）。
- 检查是否使用了相对路径（最危险，可被 LD_LIBRARY_PATH 影响）。
- 查看文件权限检查，确保库文件不可被普通用户修改。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单 + 固定扩展名 | **L0（快速跳过）** | 用户输入仅为键值 |
| 白名单 + 路径规范化 | **L1（快速扫描）** | 验证白名单完整性 |
| 直接拼接用户输入 | **L3（逐行读）** | 极高风险 |
| 使用相对路径或环境变量 | **L4（跨模块追踪）** | 远程代码执行 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **库文件路径由用户输入控制**。
2. **缺乏白名单验证**，允许加载任意路径的库。
3. **能够加载恶意库导致代码执行**。

#### 误报

可视为误报的情况：
1. **库名称仅用于索引白名单数组**，返回固定库。
2. **使用完整路径（如 `/usr/lib/libfoo.so.1`）且路径不受用户控制**。
3. **库仅由管理员安装，用户无法修改**。

#### 代码异味

需记录的潜在问题：
1. **使用相对路径加载库**（如 `dlopen("libfoo.so", RTLD_NOW)`）。
2. **使用字符串替换而非白名单**（如 `str.replace("..", "")` 可被绕过）。
3. **库路径来自用户可编辑的配置文件**。
4. **符号链接未检查**，可指向任意 `.so` 文件。
5. **库文件权限过宽**，普通用户可修改。
6. **未设置 `RTLD_DEEPBIND` 标志**，易受 LD_PRELOAD 攻击。
7. **错误处理泄露信息**，`dlerror()` 显示加载路径。

## Low risk

### 低风险评级场景

#### 1. 严格的白名单 + 完整路径

- **场景：** 只允许加载预定义库，使用完整路径（如 `/usr/lib/libfoo.so.1`）。
- **风险评估：** 防护有效，但需定期审查白名单，确保库文件权限正确。

#### 2. 受限加载目录 + 路径规范化

- **场景：** 库只能从固定目录加载，使用 `realpath()` + 前缀检查，禁用 `LD_PRELOAD`。
- **风险评估：** 防护层次清晰，但需验证规范化逻辑。

#### 3. 受控后台操作

- **场景：** 库加载功能仅对管理员开放，需要多重认证。
- **风险评估：** 攻击面小，但管理员账号泄露仍会导致 RCE。

#### 4. 库文件权限限制

- **场景：** 库文件仅由 root 可写，普通用户无法修改，权限设置为 0555（只读）。
- **风险评估：** 有效防御，但需定期验证权限。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 严格的库白名单 | 限制加载范围 | 低 |
| 完整路径 + 权限限制 | 有效防护 | 低 |
| 路径规范化 + 符号链接检查 | 深度防御 | 低 |
| 管理员限定 | 攻击面小 | 中 |
