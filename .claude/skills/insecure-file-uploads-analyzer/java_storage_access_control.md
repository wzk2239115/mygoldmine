# Java 文件存储与访问控制漏洞

## Details

### 漏洞成因
上传文件保存到文件系统、对象存储或 CDN 时，如果缺少严格的访问控制、随机命名、目录隔离或签名校验，攻击者可通过构造 URL 访问他人文件、枚举文件名、覆盖现有文件，甚至直接执行恶意脚本。常见问题包括保存于 `webapp/uploads` 目录、使用原始文件名、未设置 `Content-Disposition`、未限制读取权限或 CDN 未配置鉴权。

### 代码示例

**易受攻击的代码：**
```java
@PostMapping("/upload")
public String upload(@RequestParam MultipartFile file) throws IOException {
    Path path = Paths.get("/var/www/html/uploads/" + file.getOriginalFilename());
    Files.copy(file.getInputStream(), path, StandardCopyOption.REPLACE_EXISTING);
    // 直接返回可公开访问的 URL，未鉴权
    return "https://static.example.com/uploads/" + file.getOriginalFilename();
}
```

**另一个不安全示例（对象存储公开读）：**
```java
public String uploadToS3(MultipartFile file) {
    PutObjectRequest request = PutObjectRequest.builder()
            .bucket(bucket)
            .key("user-content/" + file.getOriginalFilename()) // 原名作为 key
            .acl("public-read") // 所有人可读
            .build();
    s3Client.putObject(request, RequestBody.fromInputStream(file.getInputStream(), file.getSize()));
    return s3Client.utilities().getUrl(bucket, request.key()).toString();
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件保存：`Files.copy`, `transferTo`, `OutputStream`, `java.nio.file`
- 对象存储：`AmazonS3`, `OSSClient`, `BlobServiceClient`
- URL 返回：`https://`, `cdn`, `static`, `fileUrl`
- 访问控制：`acl`, `public-read`, `setPublicReadAccess`

**定位步骤：**
1. 搜索保存文件与返回 URL 的函数，确认是否使用随机命名。
2. 检查访问控制配置（ACL、签名 URL、临时凭证）。
3. 跳读（L2）验证是否存在覆盖旧文件、缺乏鉴权或目录穿越。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **随机命名/目录隔离：** 使用 UUID、哈希生成文件名，按租户/用户拆分目录。
- **访问鉴权：** 仅通过签名 URL、临时凭证访问文件。
- **元数据配置：** 设置 `Content-Type`、`Content-Disposition`，防止浏览器执行脚本。
- **权限最小化：** 对象存储使用私有 ACL，应用通过服务端代理访问。
- **加密与审计：** 启用服务器端加密并记录访问日志。

**定位技巧：**
- 检查是否允许覆盖已有文件、是否存在版本控制。
- 查看 CDN 或反向代理是否限制访问方法、Referer。
- 确认删除流程是否彻底，避免残留敏感数据。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 随机命名 + 私有存储 + 签名访问 | **L0（快速跳过）** | 风险较低 |
| 公共读但文件仅静态资源 | **L2（跳读）** | 检查是否存在敏感文件 |
| 公开目录 + 原始文件名 | **L3（逐行读）** | 高风险 |
| 存储与业务耦合跨多服务 | **L4（跨模块追踪）** | 需全面审计访问链路 |

## Classify

### 研判标准

#### 确认漏洞
判定为存储访问漏洞需满足：
1. 上传文件可被未经授权的用户访问或覆盖。
2. 没有随机化文件名/目录，容易被枚举或与脚本执行结合。
3. 文件访问方式缺少鉴权或签名控制，导致敏感数据泄露或恶意脚本执行。

#### 误报
以下情形可判定为误报：
1. 文件仅作为公开静态资源，且不包含敏感信息。
2. 存储设置了严格的访问控制，所有访问需签名或服务端校验。
3. 文件在返回给客户端前进行严格的内容审核和处理。

#### 代码异味
需要关注的模式：
1. 同时存在公开和私有文件，但缺乏区分逻辑。
2. 生成 URL 时未设置 `Content-Disposition=attachment`，易触发 XSS。
3. 未记录文件访问日志，难以追踪泄露。
4. 缺少清理机制，导致敏感文件长期可访问。

## Low risk

### 低风险评级场景

#### 1. 内部业务场景
- **场景：** 上传文件仅供内部系统查看，需登录且有权限控制。
- **风险评估：** 攻击面较小，但需防权限绕过。

#### 2. 短期签名 URL
- **场景：** 访问需要带有短期有效的签名或临时凭证。
- **风险评估：** 风险低，但需确保签名机制安全。

#### 3. 加密存储
- **场景：** 文件入库前加密，泄露后也难以利用。
- **风险评估：** 可降低危害，但仍需控制访问。

#### 4. 访问审计
- **场景：** 结合对象存储访问日志、异常检测与告警。
- **风险评估：** 有助于发现问题，仍需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问控制 | 攻击面有限 | 中 |
| 签名 URL + 随机命名 | 技术防护完善 | 低 |
| 加密存储 | 降低泄露价值 | 中 |
| 日志与告警 | 提升发现速度 | 高（持续优化）|

