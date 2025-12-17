# Go 上传存储与访问控制漏洞

## Details

### 漏洞成因
Go 后端通常将上传文件保存到本地目录、NFS、对象存储或 CDN。如果保存路径可公开访问、文件名可预测、ACL 设置为公开读写或缺少访问鉴权，攻击者可以枚举、下载或覆盖他人文件，甚至执行恶意脚本。常见问题包括直接写入 `./public`, `http.FileServer` 暴露上传目录、S3 设置 `ACL: "public-read"`, CDN 未配置签名 URL 等。

### 代码示例

**易受攻击的代码：**
```go
func saveFile(c *gin.Context) (string, error) {
    file, err := c.FormFile("file")
    if err != nil {
        return "", err
    }
    // 使用原始文件名，写入静态目录
    path := filepath.Join("public/uploads", file.Filename)
    if err := c.SaveUploadedFile(file, path); err != nil {
        return "", err
    }
    return "/uploads/" + file.Filename, nil
}
```

```go
func uploadToS3(body io.ReadSeeker, filename string) (string, error) {
    _, err := s3.PutObject(&s3.PutObjectInput{
        Bucket: aws.String(bucket),
        Key:    aws.String("uploads/" + filename), // 未随机
        Body:   body,
        ACL:    aws.String("public-read"),          // 任意用户可访问
    })
    if err != nil {
        return "", err
    }
    return fmt.Sprintf("https://%s.s3.amazonaws.com/uploads/%s", bucket, filename), nil
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `http.FileServer`, `fs.Sub`, `gin.Static`, `fiber.Static`
- 保存路径：`public`, `static`, `uploads`, `os.Create`
- 对象存储：`s3.PutObject`, `minioClient.PutObject`, `gcs.NewWriter`
- 访问控制：`ACL`, `PresignedURL`, `SignedURL`, `GeneratePresigned`

**定位步骤：**
1. 搜索返回上传结果 URL 的代码，检查是否带鉴权。
2. 查看服务器是否使用 `http.FileServer` 暴露上传目录。
3. 跳读（L2）验证文件命名、权限、访问策略是否安全。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **随机命名：** 使用 UUID/hmac 生成文件名，避免枚举与覆盖。
- **访问鉴权：** 通过签名 URL、短期 token 访问文件。
- **权限最小化：** 对象存储使用私有 ACL，服务端代理下载。
- **响应头控制：** 设置 `Content-Disposition=attachment`，防止 XSS。
- **日志审计：** 启用访问日志、告警异常访问。

**定位技巧：**
- 检查是否存在批量下载或列目录的接口。
- 确认旧文件是否可能被覆盖或删除。
- 审核 CDN/反向代理是否允许跨域访问或脚本执行。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 私有存储 + 随机命名 + 鉴权访问 | **L0（快速跳过）** | 风险低 |
| 公共访问但仅静态资源 | **L2（跳读）** | 检查是否存在敏感文件 |
| 公共目录 + 原始文件名 | **L3（逐行读）** | 高风险 |
| 文件跨服务共享 + 无隔离 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件可判定为漏洞：
1. 上传文件可被未经授权的用户访问或覆盖。
2. 文件名或路径可预测，或存储目录具有执行权限。
3. 缺乏访问控制、签名或加密，导致敏感数据泄露或脚本执行。

#### 误报
以下情形属于误报：
1. 上传的仅为可公开访问的静态资源，且不影响安全。
2. 文件访问需签名 URL，且存储配置为私有。
3. 保存时使用随机文件名，并经过内容审核后才发布。

#### 代码异味
需记录的风险：
1. 对象存储使用 `public-read` ACL，无统一安全策略。
2. `http.FileServer` 暴露目录，可枚举或执行脚本。
3. 缺少删除/过期策略，文件长期可访问。
4. 未记录访问日志，难以追踪泄露事件。

## Low risk

### 低风险评级场景

#### 1. 内部系统
- **场景：** 上传仅供内部服务使用，需认证与授权。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. 短期签名 URL
- **场景：** 下载需签名 URL，有效期极短。
- **风险评估：** 风险较低，需确保存储策略安全。

#### 3. 加密存储
- **场景：** 文件加密保存，并启用版本控制。
- **风险评估：** 降低泄露影响，但仍需控制访问。

#### 4. 审计告警
- **场景：** 对象存储/HTTP 访问有日志与异常告警。
- **风险评估：** 有助于发现问题，需结合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问控制 | 攻击面有限 | 中 |
| 签名 URL + 随机命名 | 技术防护完善 | 低 |
| 加密存储 | 降低泄露价值 | 中 |
| 日志与告警 | 提升感知能力 | 高（持续改进）|

