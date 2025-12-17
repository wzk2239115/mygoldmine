# C/C++ 压缩/解析型上传漏洞

## Details

### 漏洞成因
C/C++ 应用在接收上传的压缩包（ZIP、TAR、GZ 等）或需要对图像、音视频、文档进行解析时，往往使用 `libarchive`、`zlib`、`libpng`、`libjpeg` 等底层库。如果在解压或转换阶段缺乏文件名白名单、目录穿越防护、尺寸/像素限制、流量控制以及出错处理，攻击者可构造压缩炸弹、携带相对路径/符号链接的归档文件，或利用解析库中的内存漏洞获取任意文件写入、覆盖系统配置甚至实现远程代码执行。

### 代码示例

**易受攻击的代码：**
```c
int extract_zip(const char *zip_path, const char *dest_dir) {
    struct archive *a = archive_read_new();
    archive_read_support_format_zip(a);
    archive_read_open_filename(a, zip_path, 10240);

    struct archive_entry *entry;
    while (archive_read_next_header(a, &entry) == ARCHIVE_OK) {
        const char *name = archive_entry_pathname(entry);
        // 未校验路径，攻击者可使用 ../../etc/passwd
        char fullpath[PATH_MAX];
        snprintf(fullpath, sizeof(fullpath), "%s/%s", dest_dir, name);
        archive_entry_set_pathname(entry, fullpath);
        archive_read_extract(a, entry, ARCHIVE_EXTRACT_TIME);
    }
    archive_read_free(a);
    return 0;
}
```

**另一个不安全示例（图像解析缺少限制）：**
```cpp
bool processImage(const std::vector<uint8_t> &payload) {
    // 未判断尺寸、像素，可能触发内存分配过大导致 DoS/RCE
    png_structp png = png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    png_infop info = png_create_info_struct(png);
    png_set_read_fn(png, (png_voidp)&payload, custom_read);
    png_read_png(png, info, PNG_TRANSFORM_IDENTITY, NULL);
    // ...
    return true;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 解压/归档：`archive_read`, `zip_open`, `unzOpen`, `tar_extract`, `minizip`
- 解析库：`libpng`, `libjpeg`, `libav`, `pdfium`, `ghostscript`
- 临时文件/落盘：`mkstemp`, `tmpfile`, `fopen`, `write`
- 路径处理：`snprintf`, `strcat`, `PathCombine`

**定位步骤：**
1. 搜索处理压缩/解析的函数，实现中是否对文件名、大小、路径进行校验。
2. 留意 `archive_entry_pathname`、`unzGetCurrentFileInfo` 等字段是否直接使用。
3. 跳读（L2）确认是否限制像素、帧数、压缩比以及是否检测符号链接。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **路径规范化：** 使用 `realpath`、`canonicalize_file_name` 并验证前缀。
- **尺寸/像素限制：** 在解析前检查 `width * height`、文件大小、帧数。
- **压缩炸弹防护：** 限制压缩比、展开后的总数据量以及解压时间。
- **符号链接处理：** 禁止提取符号链接或在写入前重写路径。
- **隔离执行：** 在沙箱/容器内进行解析转换，防止外溢。

**定位技巧：**
- 查看错误处理逻辑，确认库在解析失败时是否释放资源、避免泄露。
- 检查是否使用最新库版本并修复已知 CVE。
- 追踪转换后的文件存储路径与访问权限。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 解压/解析前全面校验 + 沙箱处理 | **L0（快速跳过）** | 安全基线较高 |
| 对路径/大小做部分限制 | **L2（跳读）** | 需检查是否覆盖所有入口 |
| 无任何限制直接解压/解析 | **L3（逐行读）** | 高风险 |
| 解压后立刻执行或与其他服务交互 | **L4（跨模块追踪）** | 需跟踪跨组件影响 |

## Classify

### 研判标准

#### 确认漏洞
认定为上传解析漏洞需满足：
1. 上传的压缩/媒体文件在解压或解析时缺乏路径、尺寸、格式的安全控制。
2. 攻击者可利用构造数据覆盖任意文件、造成过度资源占用或触发解析库漏洞。
3. 解压结果可被访问或执行，影响系统安全。

#### 误报
以下情况可能判定为误报：
1. 解压/解析前明确限制了文件名、路径、尺寸，并在沙箱中执行。
2. 解压结果仅存储于隔离目录且无对外暴露或执行路径。
3. 或者仅对高可信来源（签名校验、内部管道）执行解析。

#### 代码异味
需关注但未必立即构成漏洞的情况：
1. 忘记禁用符号链接提取或未验证 `archive_entry_type`.
2. 解析库版本陈旧，但暂未发现利用路径。
3. 压缩文件经多层处理，缺乏统一的资源限制策略。
4. 对错误处理、异常路径缺乏日志，难以追踪。

## Low risk

### 低风险评级场景

#### 1. 受控内部批量处理
- **场景：** 压缩文件仅通过内部管道导入，源可靠。
- **风险评估：** 攻击面小，但需防范误操作或内部威胁。

#### 2. 只读解析且无输出
- **场景：** 解析仅用于读取元数据，结果不落盘。
- **风险评估：** 危害降低，但仍需限制资源。

#### 3. 外部沙箱处理
- **场景：** 上传文件由独立服务解析，主系统仅获取安全结果。
- **风险评估：** 大幅降低影响，但需确保沙箱安全。

#### 4. 多重检测机制
- **场景：** 解压前后进行签名、杀毒、内容策略校验。
- **风险评估：** 风险较低，但仍需审查流程完整性。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部可信源 | 攻击面有限 | 中 |
| 沙箱/隔离解析 | 影响范围受限 | 低 |
| 只读/不落盘 | 减少持久化风险 | 中 |
| 多层检测 | 能及时发现恶意数据 | 高（仍需保持更新）|

