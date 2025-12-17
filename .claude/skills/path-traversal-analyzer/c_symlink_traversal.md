# C/C++ 符号链接遍历漏洞

## Details

### 漏洞成因
C/C++ 应用在处理用户提供的路径参数访问配置文件、日志文件或临时文件时，多数开发者会关注 `../` 路径遍历攻击并使用 `realpath` 或字符串过滤进行防护，但容易忽视符号链接（Symlink）攻击面。攻击者可在可写目录（如 `/tmp`、上传目录、缓存目录）中创建指向敏感文件的符号链接，当应用使用 `open`、`fopen`、`access`、`stat` 等 API 跟随符号链接访问时，即可绕过沙箱限制读取 `/etc/passwd`、`/etc/shadow`、密钥文件等敏感资源。若应用允许写入操作（如日志轮转、缓存清理、配置更新），则可能覆盖系统文件或提权配置。此类漏洞在多租户环境、容器逃逸、特权服务中尤为危险。

### 代码示例

**易受攻击的代码（日志文件访问）：**
```c
// 用户请求 filename=malicious.log（攻击者预先在日志目录创建符号链接）
// ln -s /etc/shadow /var/app/logs/malicious.log
void read_log_file(const char *filename) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "/var/app/logs/%s", filename);
    
    // realpath 检查路径在合法目录内
    char resolved[PATH_MAX];
    if (realpath(path, resolved) == NULL) {
        perror("realpath failed");
        return;
    }
    
    // 前缀校验通过（因为 /var/app/logs/malicious.log 本身在目录内）
    if (strncmp(resolved, "/var/app/logs/", 14) != 0) {
        fprintf(stderr, "Path traversal blocked\n");
        return;
    }
    
    // 打开文件时跟随符号链接，读取了 /etc/shadow
    FILE *fp = fopen(resolved, "r");  // 未使用 O_NOFOLLOW
    if (fp) {
        char buf[1024];
        while (fgets(buf, sizeof(buf), fp)) {
            printf("%s", buf);  // 泄露敏感文件
        }
        fclose(fp);
    }
}
```

**配置文件覆盖风险：**
```c
void update_config(const char *config_name, const char *content) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "/var/app/config/%s", config_name);
    
    // 未检查符号链接
    // 攻击者上传包中含：ln -s /etc/crontab /var/app/config/settings.conf
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);  // 缺少 O_NOFOLLOW
    if (fd == -1) return;
    
    write(fd, content, strlen(content));  // 覆盖系统文件
    close(fd);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件操作 API：`open`、`fopen`、`openat`、`creat`、`access`、`stat`、`lstat`、`std::ifstream`
- 路径处理：`realpath`、`canonicalize_file_name`、`snprintf`、`std::filesystem::path`
- 特权操作：`chown`、`chmod`、`rename`、`unlink`、`symlink`
- 解压/安装：`archive_entry_pathname`、`tar_extract`、`system("cp")`、`system("ln")`

**定位步骤：**
1. 搜索上述文件操作函数，重点关注以下场景：
   - 访问可能被用户控制内容的目录（上传目录、临时目录、日志目录）
   - 特权服务以 root/高权限用户运行的文件操作
   - 接受用户输入文件名后直接操作（即使经过前缀校验）
2. 快速筛选（L1）：查找是否使用 `O_NOFOLLOW`、`lstat`（不跟随符号链接）。
3. 跳读（L2）：确认是否存在"TOCTOU"（Time-of-Check-Time-of-Use）问题，即 `realpath` 后到真正使用文件之间的窗口。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **符号链接检测：** 使用 `lstat` 而非 `stat`，拒绝 `S_ISLNK` 类型
- **不跟随标志：** `open` 使用 `O_NOFOLLOW`，`openat` 使用 `AT_SYMLINK_NOFOLLOW`
- **原子性操作：** 使用 `openat` + 目录文件描述符避免 TOCTOU
- **沙箱隔离：** 使用 `chroot`、`pivot_root`、Linux Namespace 隔离文件系统
- **权限最小化：** 非必要不以特权用户运行，配合 `setuid`/`setgid` 降权
- **白名单映射：** 用户只能选择预定义文件 ID，后端映射到实际路径

**定位技巧：**
- 搜索 `O_NOFOLLOW`、`lstat` 关键词，确认是否在关键路径使用。
- 检查 `realpath` 后是否立即使用文件，中间是否有其他线程/进程可修改文件系统（TOCTOU）。
- 对于特权服务，确认是否先降权再操作用户控制的路径。
- 对解压/安装操作，检查是否在解压前扫描归档中的符号链接条目。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用白名单映射 + 原子性 `openat` + `O_NOFOLLOW` | **L0（快速跳过）** | 完整防护链路 |
| `realpath` 校验 + `lstat` 检查 | **L2（跳读）** | 确认检查顺序与 TOCTOU |
| 仅 `realpath` 前缀校验，使用 `open`/`fopen` | **L3（逐行读）** | 高风险，未防符号链接 |
| 特权服务操作用户可控目录 | **L4（跨模块追踪）** | 需追踪权限切换、并发操作、降权时机 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件可判定为符号链接遍历漏洞：
1. **用户可控路径或内容：** 文件名、目录内容、上传包、临时文件等可被用户直接或间接影响。
2. **缺乏符号链接检测：** 未使用 `lstat`、`O_NOFOLLOW` 或跳过符号链接验证。
3. **敏感访问或特权操作：** 可读取受限文件、覆盖系统文件，或服务以高权限运行。
4. **沙箱逃逸可能：** 在容器、chroot、多租户环境中可突破隔离。

#### 误报
以下情况可视为误报：
1. **白名单映射：** 用户仅能选择预定义文件 ID，后端固定映射路径。
2. **完整符号链接保护：** 使用 `O_NOFOLLOW` + `lstat` 验证，拒绝符号链接。
3. **只读且无敏感文件：** 访问目录部署时已确保不含敏感内容，且以最小权限运行。
4. **原子性防护：** 使用 `openat` + 目录 fd，避免 TOCTOU 竞态。

#### 代码异味
需要关注但未必立即构成漏洞的情况：
1. **仅依赖 `realpath` 前缀校验：** 无法防止符号链接指向目标，需配合 `lstat` 或 `O_NOFOLLOW`。
2. **存在 TOCTOU 窗口：** `realpath` 检查与 `open` 使用之间有时间间隔，攻击者可利用竞态。
3. **部分路径使用保护：** 读取时使用 `O_NOFOLLOW`，写入时忘记使用。
4. **依赖外部校验：** 假设上传包、解压工具已过滤符号链接，但未在代码中验证。
5. **特权不必要：** 服务以 root 运行但可降权，增大攻击危害。

## Low risk

### 低风险评级场景

#### 1. 目录权限严格限制
- **场景：** 操作目录所有权为服务专用用户，权限 700，其他用户无法创建符号链接。
- **风险评估：** 用户无法在目标目录预置符号链接，但需防提权或横向攻击。

#### 2. 只读访问且非特权运行
- **场景：** 服务以普通用户运行，仅读取日志或配置，无写入或特权操作。
- **风险评估：** 即便跟随符号链接，影响面限于服务自身权限范围，但仍可能泄露敏感配置。

#### 3. 容器/沙箱隔离
- **场景：** 应用运行在容器内，文件系统隔离，敏感文件未挂载进容器。
- **风险评估：** 符号链接攻击受限于容器文件系统范围，但需防逃逸。

#### 4. 仅内部可信源
- **场景：** 文件路径来自受信管道，普通用户无法干预目录内容。
- **风险评估：** 攻击面小，但需确认无横向利用或提权可能。

#### 5. 读写分离且写入无特权
- **场景：** 写操作对象为临时文件，不涉及系统文件或配置覆盖。
- **风险评估：** 即使符号链接攻击成功，危害范围有限。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 目录权限严格（仅服务用户可写） | 用户无法预置符号链接 | 低 |
| 只读访问 + 非特权运行 | 危害面限于服务权限 | 中 |
| 容器/Namespace 隔离 | 限制访问范围 | 中 |
| 输入来自受信源 | 攻击面小 | 中 |
| 外部安全策略（MAC/审计） | 提供检测或限制 | 高（仍需修复根因）|
