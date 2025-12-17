# Go 文件上传验证漏洞

## Details

### 漏洞成因
Go 应用常使用标准库 `http.Request.FormFile`、`ParseMultipartForm` 或 Gin/Echo 框架的 `Context.FormFile`、`SaveUploadedFile` 处理上传。若仅基于文件扩展名或 `Header.Get("Content-Type")` 校验，未检查文件头、大小、数量、名称合法性及路径规范化，攻击者可上传 WebShell、恶意脚本、压缩炸弹或利用目录穿越覆盖任意文件，继而实现代码执行或 DoS。

### 代码示例

**易受攻击的代码：**
```go
func uploadHandler(w http.ResponseWriter, r *http.Request) {
    file, header, err := r.FormFile("file")
    if err != nil { http.Error(w, "bad request", 400); return }
    defer file.Close()

    if !strings.HasSuffix(header.Filename, ".jpg") && !strings.HasSuffix(header.Filename, ".png") {
        http.Error(w, "invalid file", 400)
        return
    }
    // 直接保存，未限制大小、未使用随机名称
    out, _ := os.Create("./static/uploads/" + header.Filename)
    defer out.Close()
    io.Copy(out, file)
}
```

**另一个不安全示例（目录穿越）：**
```go
func saveUpload(file multipart.File, header *multipart.FileHeader) error {
    path := filepath.Join("/var/www/html/uploads", header.Filename) // 未调用 filepath.Clean
    out, err := os.Create(path)
    if err != nil { return err }
    defer out.Close()
    _, err = io.Copy(out, file)
    return err
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 标准库上传：`FormFile`, `ParseMultipartForm`, `multipart.FileHeader`
- 框架方法：`c.FormFile`, `c.SaveUploadedFile`, `fiber.Ctx.FormFile`
- 存储逻辑：`os.Create`, `io.Copy`, `ioutil.WriteFile`
- 类型判断：`strings.HasSuffix`, `header.Header.Get("Content-Type")`

**定位步骤：**
1. 搜索所有上传处理函数，检查是否执行扩展名和 MIME 白名单校验。
2. 检查 `filepath.Join` 使用是否配合 `filepath.Clean`、是否使用随机文件名。
3. 跳读（L2）确认是否限制大小、数量、防止压缩炸弹。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **类型验证：** 使用 `net/http/sniff`、读取文件头、第三方库读取魔术字。
- **大小限制：** 使用 `r.ParseMultipartForm(maxSize)`、设置 `MaxBytesReader`、反向代理限制。
- **随机命名与目录隔离：** 使用 `uuid.New().String()`、临时目录、对象存储。
- **权限控制：** 上传目录不可执行，访问需鉴权，通过签名 URL。
- **内容扫描：** 集成杀毒/安全扫描服务。

**定位技巧：**
- 检查是否清理临时文件夹（`os.Remove`）。
- 确认 `Gin` 配置 `MaxMultipartMemory`，防止内存耗尽。
- 追踪后续处理链路（图像/文档解析）是否安全。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单 + 随机命名 + 隔离存储 | **L0（快速跳过）** | 风险低 |
| 仅进行部分校验 | **L2（跳读）** | 需确认覆盖所有入口 |
| 直接保存至可执行目录 | **L3（逐行读）** | 高风险 |
| 上传文件用于后续敏感处理 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. 上传入口缺乏可靠的类型、大小、路径校验或随机命名。
2. 文件存储在可访问或可执行目录，或后续处理链路未隔离。
3. 攻击者可利用上传覆盖文件、执行代码或引发 DoS。

#### 误报
以下情况可判定为误报：
1. 上传功能仅限可信客户端，并使用签名/令牌验证。
2. 文件限制严格且存储在不可执行目录，访问需后端鉴权。
3. 已部署多层防护（类型验证、扫描、隔离）并确认不可利用。

#### 代码异味
需记录的风险：
1. 使用 `strings.HasSuffix` 判断扩展名，易被绕过。
2. 未释放 `multipart.File`, 可能导致文件描述符泄漏。
3. 缺少日志记录和告警，无法监控异常上传。
4. 临时目录无清理，易占满磁盘。

## Low risk

### 低风险评级场景

#### 1. 内部运维接口
- **场景：** 上传仅由内部工具使用，配合身份验证。
- **风险评估：** 攻击面有限，但需防凭证泄露。

#### 2. 上传即转存对象存储
- **场景：** 上传后立即存入 S3/GCS 等私有桶，返回签名 URL。
- **风险评估：** 可降低执行风险，但仍需校验内容。

#### 3. 定期清理 + 审计
- **场景：** 上传目录启用自动清理，并记录访问日志。
- **风险评估：** 风险较低，需确保审计有效。

#### 4. 安全监控
- **场景：** 搭配 WAF/IDS 对上传流量进行检测。
- **风险评估：** 有助于发现问题，需配合代码修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 | 攻击面小 | 中 |
| 隔离存储 + 签名访问 | 技术防护完善 | 低 |
| 定期清理/审计 | 降低持续风险 | 中 |
| 安全监控 | 提高响应能力 | 高（持续优化）|

