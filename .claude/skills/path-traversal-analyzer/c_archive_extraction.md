# C/C++ 归档解压路径遍历漏洞审计指南

## Details

### 典型代码模式

**libarchive 场景：**
```c
struct archive *a = archive_read_new();
struct archive_entry *entry;
archive_read_open_filename(a, archive_path, 10240);
while (archive_read_next_header(a, &entry) == ARCHIVE_OK) {
    const char *name = archive_entry_pathname(entry);
    // 危险：直接拼接目标路径，未检查 "../" 或绝对路径
    char dest[PATH_MAX];
    snprintf(dest, sizeof(dest), "%s/%s", target_dir, name);
    archive_read_extract(a, entry, flags);
}
```

**minizip 场景：**
```c
unzFile uf = unzOpen(zip_path);
unz_global_info gi;
unzGetGlobalInfo(uf, &gi);
for (int i = 0; i < gi.number_entry; i++) {
    char filename[256];
    unzGetCurrentFileInfo(uf, NULL, filename, sizeof(filename), NULL, 0, NULL, 0);
    // 危险：未验证 filename 是否包含 "../"
    FILE *out = fopen(filename, "wb");
}
```

**手动解压场景：**
```cpp
tar_extract(const char *archive, const char *dest) {
    TAR *t;
    tar_open(&t, archive, NULL, O_RDONLY, 0, 0);
    while (th_read(t) == 0) {
        char *path = th_get_pathname(t);
        // 危险：path 未规范化处理
        string full = string(dest) + "/" + path;
        tar_extract_file(t, (char*)full.c_str());
    }
}
```

### 快速定位核心操作技巧（L2: 跳读）

**入口函数特征：**
- libarchive: `archive_read_new`, `archive_read_open*`, `archive_read_next_header`, `archive_read_extract`
- minizip/zlib: `unzOpen`, `unzGetCurrentFileInfo`, `unzOpenCurrentFile`, `unzReadCurrentFile`
- libzip: `zip_open`, `zip_fopen_index`, `zip_stat_index`, `zip_get_name`
- tar.h: `tar_open`, `th_read`, `th_get_pathname`, `tar_extract_file`
- 手动实现: `fopen` + 循环 + 路径拼接

**关键变量追踪：**
- 条目路径: `archive_entry_pathname()`, `th_get_pathname()`, `zip_get_name()` 返回值
- 目标路径: `snprintf`/`sprintf`/`strcat` 的 dest 参数
- 写入操作: `fopen`, `open`, `creat`, `archive_entry_set_pathname`

### 快速定位保护机制技巧（L1: 关键词扫描）

**路径验证函数：**
- `strstr(path, "..")` / `strchr(path, '.')` - 检查相对路径
- `realpath(path, resolved)` - 路径规范化
- `canonicalize_file_name(path)` - GNU 扩展
- `strncmp(resolved, base_dir, len)` - 前缀匹配验证
- `path[0] == '/'` - 绝对路径检查

**白名单过滤：**
- 正则匹配: `^[a-zA-Z0-9_/.-]+$`
- 路径段校验: 循环检查每个 `/` 分隔的部分
- symlink 检查: `lstat`, `S_ISLNK(st.st_mode)`

**库内建保护：**
- libarchive: `ARCHIVE_EXTRACT_SECURE_NODOTDOT`, `ARCHIVE_EXTRACT_SECURE_SYMLINKS` flags
- 自定义 callback: `archive_read_extract2` 的 lookup 参数

**审计等级标注：**
- **L0（快速跳过）**: 存在 `realpath` + 前缀校验 + 错误处理完整
- **L1（关键词扫描）**: 搜索 `".."`, `realpath`, `SECURE` flags
- **L2（跳读）**: 锁定解压循环，检查路径来源与目标拼接
- **L3（逐行读）**: 无明显保护时，逐行分析路径处理逻辑
- **L4（跨模块追踪）**: 路径来源非直接从归档获取，需跨函数追踪数据流

## Classify

### 确认为真实漏洞的条件：
1. **可控路径源**: 归档条目名称直接用于文件系统操作，无清洗
2. **路径拼接缺陷**: 直接 `strcat`/`snprintf` 拼接，未规范化
3. **越界影响**: 能向目标目录外写入文件（覆盖系统文件、配置文件）

### 误报判定：
1. **沙箱隔离**: 解压在 chroot/namespace/容器内，无法逃逸
2. **只读解析**: 仅读取归档元数据，不执行实际写入操作
3. **硬编码路径**: 归档路径不可控，由程序内部生成

### 代码异味（潜在风险）：
1. **部分校验**: 只检查 `".."` 但允许绝对路径 `/etc/passwd`
2. **竞态条件**: 先检查路径，后创建文件，中间可被 symlink 攻击
3. **依赖库版本**: 旧版 libarchive 默认不开启安全标志

## Low risk

### 降低风险的场景：

1. **受限目录权限**:
   - 目标目录仅当前用户可写，非特权进程
   - 部署在受限用户环境（非 root/admin）

2. **临时目录隔离**:
   - 解压到 `/tmp` 下随机子目录，使用后立即删除
   - 不涉及系统关键路径

3. **内容类型限制**:
   - 仅解压特定文件类型（如 `.txt`, `.json`）
   - 不包含可执行文件或配置文件

4. **用户可见操作**:
   - 解压前显示文件列表供用户确认
   - 有审计日志记录所有解压操作

5. **覆盖限制**:
   - 解压到空目录，不存在覆盖风险
   - 设置 `O_EXCL` 标志拒绝覆盖已有文件

6. **来源可信**:
   - 归档来源经过签名验证
   - 仅处理内部生成的归档文件（需证明生成过程无污染）