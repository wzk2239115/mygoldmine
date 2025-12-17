# C/C++ fopen/open 路径遍历与文件包含

## Details

### 漏洞成因

C/C++ 应用使用 `fopen()`、`open()`、`opendir()` 等函数读取文件时，若直接将用户输入拼接到文件路径而未做路径规范化和白名单验证，攻击者可利用 `../` 相对路径实现目录遍历，访问应用目录外的敏感文件。此漏洞常见于服务器程序、系统工具、文件服务接口等场景。C/C++ 的低级特性使得路径验证更加复杂，需谨慎处理缓冲区、符号链接、权限等问题。

### 代码示例

**易受攻击的代码（使用 fopen）：**
```c
#include <stdio.h>
#include <string.h>

void serve_file(const char *filename) {
    // filename = "../../etc/passwd"
    char filepath[256];
    snprintf(filepath, sizeof(filepath), "/var/www/uploads/%s", filename);

    FILE *fp = fopen(filepath, "r");
    if (fp == NULL) {
        perror("fopen failed");
        return;
    }

    char buffer[1024];
    while (fgets(buffer, sizeof(buffer), fp) != NULL) {
        printf("%s", buffer);
    }
    fclose(fp);
}
```

**使用 open() 的版本：**
```c
#include <fcntl.h>
#include <unistd.h>

int read_file(const char *filename) {
    // filename = "../../config.json"
    char filepath[512];
    strcpy(filepath, "/app/data/");  // 缓冲区溢出风险
    strcat(filepath, filename);

    int fd = open(filepath, O_RDONLY);
    if (fd < 0) {
        perror("open failed");
        return -1;
    }

    // ... 读取文件 ...
    close(fd);
    return 0;
}
```

**查看目录列表（高危）：**
```c
#include <dirent.h>

void list_directory(const char *dir_path) {
    // dir_path = "../../"
    DIR *dir = opendir(dir_path);
    if (dir == NULL) {
        perror("opendir failed");
        return;
    }

    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        printf("%s\n", entry->d_name);
    }
    closedir(dir);
}
```

**缓冲区溢出风险的拼接：**
```c
#include <stdio.h>
#include <string.h>

void vulnerable_concat(const char *user_input) {
    char path[64];  // 缓冲区太小
    strcpy(path, "/var/www/");  // 不安全的 strcpy
    strcat(path, user_input);  // user_input = "../../etc/passwd" + 长路径

    FILE *fp = fopen(path, "r");
    // ...
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）

**关键词扫描：**
- 文件打开：`fopen()`, `open()`, `fopen_s()`, `_open()`
- 目录操作：`opendir()`, `readdir()`, `scandir()`, `glob()`
- 路径拼接：`sprintf()`, `snprintf()`, `strcpy()`, `strcat()`, `memcpy()`
- 字符串操作：`strncpy()`, `strncat()`, `realpath()`, `getcwd()`
- 权限相关：`stat()`, `lstat()`, `fstat()`, `access()`

**定位步骤：**
1. 搜索 `fopen(`, `open(`, `opendir(` 等函数调用。
2. 检查这些调用的参数是否包含变量，特别是来自输入的变量。
3. 追踪变量的来源：命令行参数、网络输入、配置文件。
4. 确认是否有过滤或验证逻辑。

#### 保护机制定位（审计等级：L2-L3）

**检查是否存在：**
- **路径规范化：** `realpath()`, `resolvepath()`, 符号链接解析
- **前缀校验：** 验证规范化后的路径是否在允许的基础目录内
- **白名单验证：** 将用户输入与已知安全文件列表对比
- **符号链接检查：** `lstat()` 检测符号链接，禁止跨越链接访问
- **缓冲区安全：** 使用 `snprintf()` 而非 `sprintf()`, `strncat()` 而非 `strcat()`
- **权限检查：** 确认文件权限后再访问

**定位技巧：**
- 确认 `realpath()` 是否被正确使用，注意返回值检查。
- 检查是否使用了不安全的字符串函数（`strcpy`, `strcat`, `sprintf`）。
- 验证前缀检查是否可被绕过（如符号链接、相对路径）。
- 查看是否对 `lstat()` 结果进行了处理，禁止符号链接。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单映射 | **L0（快速跳过）** | 用户输入仅为键值 |
| `realpath()` + 前缀校验 | **L2（跳读）** | 确认校验逻辑完备 |
| 直接拼接用户输入 | **L3（逐行读）** | 极高风险 |
| 符号链接 + 目录遍历 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **用户可控路径** 用于文件读取或目录访问。
2. **缺乏有效防护**（无路径规范化、白名单、符号链接检查）。
3. **能够访问敏感资源**（读取配置、密钥、系统文件）。

#### 误报

可视为误报的情况：
1. **输入仅用于索引白名单数组**，返回固定文件。
2. **使用 `realpath()` 规范化并检查前缀**。
3. **使用固定常量拼接路径，不受用户输入影响**。

#### 代码异味

需记录的潜在问题：
1. **使用不安全的字符串函数**（`strcpy`, `strcat`, `sprintf`）。
2. **缓冲区大小与输入长度不匹配**（可能导致缓冲区溢出）。
3. **符号链接未检查**，攻击者可创建符号链接绕过目录限制。
4. **异常处理泄露路径信息**，错误消息显示尝试的路径。
5. **权限检查不完整**，仅检查父目录权限。

## Low risk

### 低风险评级场景

#### 1. 受控后台操作

- **场景：** 功能仅对特定用户开放，进程以最小权限运行。
- **风险评估：** 外部攻击面小，但需防止权限提升。

#### 2. 白名单保护 + 路径规范化

- **场景：** 使用 `realpath()` 规范化路径，检查前缀，且白名单完整。
- **风险评估：** 防护有效，但需确认白名单覆盖所有包含点。

#### 3. 容器/沙箱隔离

- **场景：** 应用运行在 chroot 环境或容器中，文件系统受限。
- **风险评估：** 限制破坏面，但建议修复代码根本问题。

#### 4. 只读公开目录

- **场景：** 仅访问公开静态资源，无敏感信息。
- **风险评估：** 危害有限，但仍可能泄露目录结构。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员限定 | 攻击面小 | 中 |
| `realpath()` + 前缀校验 | 有效防护 | 低 |
| 符号链接检查 + 白名单 | 深度防御 | 低 |
| chroot/容器隔离 | 限制影响面 | 高（持续跟进修复）|
