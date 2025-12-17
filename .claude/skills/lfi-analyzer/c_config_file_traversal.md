# C/C++ 配置文件路径遍历与本地文件包含

## Details

### 漏洞成因

C/C++ 应用常在启动时或运行期间从配置文件读取各种参数，包括日志路径、数据文件路径、插件路径等。若应用从配置文件中读取的路径参数未进行规范化和白名单验证，攻击者可通过修改配置文件（在有权限的情况下）或注入恶意配置，导致应用读取/写入任意位置的文件，实现信息泄露或权限提升。此漏洞常见于系统服务、守护进程、配置管理系统等场景。

### 代码示例

**易受攻击的代码（配置文件读取）：**
```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Config {
    char log_file[256];
    char data_dir[256];
    char plugin_dir[256];
};

void load_config(const char *config_path, struct Config *cfg) {
    // config_path = "/etc/app/config.conf"
    FILE *fp = fopen(config_path, "r");
    if (fp == NULL) {
        perror("fopen");
        return;
    }

    char line[512];
    while (fgets(line, sizeof(line), fp) != NULL) {
        if (strncmp(line, "log_file=", 9) == 0) {
            // 直接从配置文件读取路径，无验证
            sscanf(line, "log_file=%255s", cfg->log_file);
        }
        // cfg->log_file = "../../etc/passwd"
    }
    fclose(fp);
}

void write_log(const struct Config *cfg, const char *message) {
    FILE *fp = fopen(cfg->log_file, "a");  // 写入任意位置
    if (fp != NULL) {
        fprintf(fp, "%s\n", message);
        fclose(fp);
    }
}
```

**数据文件路径配置：**
```c
#include <stdio.h>

struct AppConfig {
    char data_file[512];
};

void load_data(const struct AppConfig *cfg) {
    // cfg->data_file = "../../sensitive_data.db"
    FILE *fp = fopen(cfg->data_file, "rb");
    if (fp == NULL) {
        perror("Cannot open data file");
        return;
    }

    // 读取敏感数据
    unsigned char buffer[1024];
    size_t bytes_read = fread(buffer, 1, sizeof(buffer), fp);
    fclose(fp);
}
```

**插件路径配置 + dlopen：**
```c
#include <dlfcn.h>
#include <stdio.h>

void load_plugins_from_config(const char *config_content) {
    // 从配置文件解析插件路径
    // config_content = "plugins=/../../evil.so"
    char plugin_path[256];
    sscanf(config_content, "plugins=%255s", plugin_path);

    void *handle = dlopen(plugin_path, RTLD_NOW);
    if (handle != NULL) {
        void (*init)(void) = (void (*)(void))dlsym(handle, "init");
        if (init) init();  // 执行恶意代码
    }
}
```

**缓冲区溢出风险：**
```c
#include <string.h>
#include <stdio.h>

void parse_config(const char *config_line) {
    char log_path[64];
    char temp[256];

    // 从配置读取路径，超长字符串导致缓冲区溢出
    if (sscanf(config_line, "log_path=%s", temp) == 1) {
        strcpy(log_path, temp);  // log_path 只有 64 字节，temp 可能更长
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L3）

**关键词扫描：**
- 配置读取：`fopen()`, `fgets()`, `fscanf()`, `sscanf()`, `getline()`
- 路径参数解析：包含 `_path`, `_dir`, `_file` 的变量
- 文件路径使用：这些配置变量用于 `fopen()`, `dlopen()`, `stat()` 等
- 缓冲区操作：`strcpy()`, `strcat()`, `sscanf()` 与路径相关的操作
- 写入操作：将配置中的路径用于 `fopen(..., "w")` 等写操作

**定位步骤：**
1. 搜索配置文件读取代码（通常在 `main()` 或初始化函数）。
2. 识别包含路径的配置参数（如 `log_file`, `data_dir`, `plugin_dir`）。
3. 追踪这些参数如何被使用（是否直接用于文件操作）。
4. 检查是否有路径验证或规范化。

#### 保护机制定位（审计等级：L2-L4）

**检查是否存在：**
- **路径规范化：** 在使用前对配置的路径使用 `realpath()`
- **白名单验证：** 验证路径是否在允许的基础目录内
- **前缀校验：** 检查 `strstr()` 基础目录前缀
- **符号链接检查：** 使用 `lstat()` 检测符号链接
- **权限验证：** 配置文件本身的权限是否限制（应为 root 可写）
- **缓冲区安全：** 使用 `snprintf()` 限制字符串长度
- **配置验证：** 是否验证了配置文件的签名或校验和

**定位技巧：**
- 检查配置文件的权限，如果普通用户可写则风险极高。
- 确认路径参数是否直接用于 `fopen()` 或 `dlopen()`。
- 查看是否对从配置读取的任何值进行了验证。
- 验证缓冲区大小是否合适，防止溢出。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 配置文件只读 + realpath 验证 | **L1（快速扫描）** | 验证路径验证逻辑 |
| 配置文件可编辑 + 无验证 | **L3（逐行读）** | 极高风险 |
| 符号链接 + 配置可控 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **配置文件中的路径参数可被攻击者修改**（文件权限过宽或通过其他漏洞）。
2. **路径参数直接用于文件操作**，无规范化或白名单验证。
3. **能够读取敏感文件或写入任意位置**。

#### 误报

可视为误报的情况：
1. **配置文件仅由 root 可写**，普通用户无法修改。
2. **路径经过 `realpath()` 规范化并检查前缀**。
3. **配置参数使用白名单验证**，仅允许预定义的路径。

#### 代码异味

需记录的潜在问题：
1. **配置文件权限过宽**（非 root 用户可写）。
2. **直接使用配置中的路径，无任何验证**。
3. **缓冲区大小与输入大小不匹配**，可能导致溢出。
4. **符号链接未检查**，可指向任意文件。
5. **配置文件未签名或验证**，可被篡改。
6. **错误处理泄露路径信息**。

## Low risk

### 低风险评级场景

#### 1. 配置文件只读 + 路径规范化

- **场景：** 配置文件仅由 root 可写（权限 0644 或更严格），且路径经过 `realpath()` 验证。
- **风险评估：** 防护有效，但普通用户获得 root 权限后仍可修改。

#### 2. 白名单路径验证

- **场景：** 配置中的路径经过白名单验证，仅允许预定义的目录。
- **风险评估：** 防护有效，定期审查白名单。

#### 3. 受限的配置参数

- **场景：** 配置文件中的路径参数仅用于读取公开的、预定义的文件。
- **风险评估：** 危害有限，但仍建议添加白名单验证。

#### 4. 配置签名或校验和

- **场景：** 配置文件经过数字签名或校验和验证，防止篡改。
- **风险评估：** 防护有效，但签名验证实现需正确。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 配置文件只读 | 防止普通用户修改 | 中 |
| 路径规范化 + 前缀检查 | 有效防护 | 低 |
| 白名单路径验证 | 限制访问范围 | 低 |
| 配置签名或校验和 | 深度防御 | 低 |
