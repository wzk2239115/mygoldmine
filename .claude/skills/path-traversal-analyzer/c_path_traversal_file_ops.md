# C/C++ 路径遍历与文件包含漏洞

## Details

### 漏洞成因
在 C/C++ 应用中，开发者常通过 `open`、`fopen`、`ifstream`、`stat`、`mkdir` 等 API 读取或写入文件。如果将用户可控的路径参数直接拼接到文件系统调用，且未做标准化（canonicalization）与根目录校验，攻击者可使用 `../`、绝对路径、符号链接或环境变量来突破沙箱限制，读取敏感文件或覆盖系统文件。若应用允许根据路径动态加载脚本/模板（如 `dlopen`、自定义插件加载器），还可能引发本地文件包含（LFI）甚至远程文件包含（RFI）。加之 C/C++ 习惯于自行处理缓冲区，若处理不慎还可能扩大发生缓冲区溢出、提权等风险。

### 代码示例

**易受攻击的代码（下载日志接口）：**
```c
// 用户请求中传入 filename=../../../../etc/passwd
void send_log_file(int client_fd, const char *filename) {
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "/var/app/logs/%s", filename);

    int fd = open(path, O_RDONLY);
    if (fd == -1) {
        dprintf(client_fd, "File not found\n");
        return;
    }

    // 逐字节发送文件内容
    char buf[4096];
    ssize_t n;
    while ((n = read(fd, buf, sizeof(buf))) > 0) {
        write(client_fd, buf, n);
    }
    close(fd);
}
```

**符号链接绕过示例（解压上传包）：**
```c
void extract_archive(const char *archive_path, const char *dest_dir) {
    struct archive *a = archive_read_new();
    archive_read_support_format_tar(a);
    archive_read_open_filename(a, archive_path, 10240);

    struct archive_entry *entry;
    while (archive_read_next_header(a, &entry) == ARCHIVE_OK) {
        const char *entry_path = archive_entry_pathname(entry);
        char full_path[PATH_MAX];
        snprintf(full_path, sizeof(full_path), "%s/%s", dest_dir, entry_path);

        // 未检查 canonical path，可能写到 dest_dir 之外
        archive_entry_set_pathname(entry, full_path);
        archive_read_extract(a, entry, ARCHIVE_EXTRACT_TIME);
    }
    archive_read_free(a);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件操作 API：`open`、`fopen`、`readFile`、`std::ifstream`、`fread`、`fwrite`
- 路径处理函数：`snprintf`、`strcat`、`strcpy`、`sprintf`、`std::filesystem::path`
- 解压/解档：`libarchive`、`zip_open`、`unzOpen`、`tar_extract`
- 动态加载：`dlopen`、`LoadLibrary`、`system`（间接触发路径解析）

**定位步骤：**
1. 全局搜索 `/`、`../` 与上述函数共现的代码段。
2. 关注将用户输入（HTTP 参数、命令行参数、环境变量、配置文件）拼接到路径中的场景。
3. 跳读（L2）附近逻辑，确认是否存在必要的目录白名单或 `realpath` 校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径规范化：** `realpath`、`canonicalize_file_name`、`std::filesystem::canonical`
- **根目录校验：** 比较规范化后路径前缀是否等于受限根目录
- **白名单映射：** 使用枚举映射将逻辑名称映射到物理文件
- **符号链接/硬链接检查：** 使用 `lstat` 检查条目类型，拒绝跟随符号链接
- **文件权限控制：** 以最小权限用户运行，限制可访问目录

**定位技巧：**
- 若发现路径拼接后未调用任何标准化函数，应提升审计等级（L3 逐行读）。
- 对上传/解压流程，检查每个条目写入前是否比较 canonical path。
- 对动态加载器，确认只允许白名单中的模块。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 统一使用白名单映射 + canonical 校验 | **L0（快速跳过）** | 明确只允许预定义文件 |
| 拼接路径但使用 `realpath` 且验证前缀 | **L2（跳读）** | 快速确认校验逻辑是否正确 |
| 直接拼接用户输入路径，无校验 | **L3（逐行读）** | 高风险，需跟踪数据来源与访问范围 |
| 涉及归档解压/符号链接/动态加载 | **L4（跨模块追踪）** | 需跨函数追踪完整处理链路 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件可判定为路径遍历/LFI/RFI 漏洞：
1. **存在可控路径拼接：** 用户输入直接或间接成为文件系统调用的参数。
2. **缺乏有效防护：** 未进行路径规范化、白名单验证或根目录前缀校验。
3. **访问敏感资源：** 可以读取/写入应用根目录之外的文件，或动态包含任意脚本。

#### 误报
以下情况可视为误报：
1. **输入值经白名单枚举映射：** 用户只能选择预定义文件标识。
2. **路径经过 canonical 校验并限制在固定目录：** 严格比较前缀且拒绝异常。
3. **文件操作对象为不敏感临时文件且目录权限隔离：** 即使遍历也无法突破宿主目录。

#### 代码异味
需要关注但未必立即构成漏洞的情况：
1. **仅依赖字符串过滤 `..`/`/`：** 易被 URL 编码、Unicode 绕过。
2. **未处理符号链接：** 攻击者可利用 symlink 在受控目录内指向敏感文件。
3. **混用拼接与白名单：** 部分分支绕过白名单逻辑。
4. **缺乏错误处理/日志：** 容易掩盖攻击尝试。

## Low risk

### 低风险评级场景

#### 1. 输入源自受控管道
- **场景：** 路径来自内部服务的固定协议或受限后台账号。
- **风险评估：** 攻击面受限，但需确认无被横向利用的可能。

#### 2. 只读访问且限定目录
- **场景：** 代码对路径进行 canonical 校验，并强制前缀在单一目录。
- **风险评估：** 若目录本身不含敏感文件，风险较低。

#### 3. 运行用户权限受限
- **场景：** 服务使用 chroot/jail 或最小权限账号运行。
- **风险评估：** 即便越界访问，影响范围有限，但仍应修复根因。

#### 4. 外部安全策略防护
- **场景：** 文件系统被 AppArmor/SELinux 限制，或部署层有审计告警。
- **风险评估：** 可降低成功概率，但不可作为永久解决方案。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 输入仅来自高可信源 | 外部攻击难度大 | 中 |
| 有效 canonical + 前缀校验 | 基本消除遍历能力 | 低 |
| 运行用户受限 | 限制危害面 | 中 |
| 有额外强制访问控制（MAC） | 有硬性限制 | 高（仍需保留代码修复计划）|

