# TypeScript 云存储上传安全漏洞

## Details

### 漏洞成因
TypeScript 后端（NestJS、Express、Next.js API）常将上传文件存储到云服务（S3、GCS、Azure Blob、阿里 OSS）。如果使用永久公开桶、返回固定 URL、未随机命名、缺少签名或加密、权限策略宽泛，攻击者可枚举、下载或覆盖他人文件，甚至上传恶意脚本。Serverless 架构若直接暴露 `putObject` 临时凭证或未验证回调，也会带来风险。

### 代码示例

**易受攻击的代码：**
```typescript
@Post("upload")
async upload(@UploadedFile() file: Express.Multer.File) {
  const key = `uploads/${file.originalname}`; // 可预测文件名
  await this.s3
    .putObject({ Bucket: process.env.BUCKET, Key: key, Body: file.buffer, ACL: "public-read" })
    .promise();
  return { url: `https://${process.env.BUCKET}.s3.amazonaws.com/${key}` };
}
```

```typescript
@Get("presign")
getUploadUrl(@Query("filename") filename: string) {
  // 未校验文件名/类型，且返回长时间有效 URL
  return this.s3.getSignedUrlPromise("putObject", {
    Bucket: process.env.BUCKET,
    Key: filename,
    Expires: 3600 * 24,
  });
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- AWS：`S3`, `PutObjectCommand`, `getSignedUrl`
- GCP/Azure：`bucket.file`, `createWriteStream`, `generateSignedUrl`
- 权限：`ACL`, `publicRead`, `BlobSASPermissions`, `policy`
- 命名：`originalname`, `slug`, `Date.now()`

**定位步骤：**
1. 搜索上传存储逻辑，检查是否使用可预测文件名或公开权限。
2. 查看返回给客户端的 URL 是否需要签名或鉴权。
3. 跳读（L2）确认是否对签名 URL 设置合理有效期、动作限制。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **随机命名：** 使用 UUID、哈希、防止枚举。
- **私有桶/容器：** 设置 ACL 为私有，通过签名 URL 短期访问。
- **限制策略：** 在 IAM/STS 中限制可操作的前缀、大小、Content-Type。
- **加密与版本控制：** 启用服务器端加密、版本化、生命周期规则。
- **回调验证：** 前端直接上传后需服务端验证回调结果。

**定位技巧：**
- 检查 Serverless 授权（STS、签名）是否限定上传类型。
- 查看上传后是否触发扫描、日志记录。
- 确认删除策略，防止敏感文件长时间暴露。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 私有存储 + 短期签名 + 随机命名 | **L0（快速跳过）** | 风险低 |
| 公开桶但仅静态安全资源 | **L2（跳读）** | 检查敏感内容 |
| `public-read` + 可预测文件名 | **L3（逐行读）** | 高风险 |
| 临时凭证可上传任意路径 | **L4（跨模块追踪）** | 需审计全链路 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 上传文件可公开访问且缺乏随机命名或签名控制。
2. 签名 URL 有效期过长或权限范围过大。
3. 攻击者能利用这些缺陷访问敏感数据或覆盖文件。

#### 误报
以下情况可判定为误报：
1. 存储桶为私有，访问需临时签名，限制严格。
2. 上传/下载操作在服务端完成，用户无法直接访问对象存储。
3. 已对上传类型、大小、ACL 进行严格限制与审计。

#### 代码异味
需记录的风险：
1. 将 `accessKey`/`secret` 暴露给客户端，或使用硬编码凭证。
2. 缺少生命周期策略，文件长时间公开。
3. 只有前端校验，后端未验证上传结果。
4. 未记录存储访问日志，难以追踪泄露。

## Low risk

### 低风险评级场景

#### 1. 内部资源
- **场景：** 上传文件仅供内部系统访问，配合 IAM 控制。
- **风险评估：** 攻击面有限，但需防凭证泄露。

#### 2. 短期签名 URL
- **场景：** 上传/下载均需十分钟内有效的签名 URL。
- **风险评估：** 风险较低，需确保存储策略安全。

#### 3. 加密 + 版本化
- **场景：** 对象启用加密、版本控制与自动过期策略。
- **风险评估：** 降低泄露与覆盖风险。

#### 4. 审计告警
- **场景：** 启用 CloudTrail/CloudWatch 等日志与告警。
- **风险评估：** 有助于快速发现问题，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问控制 | 攻击面有限 | 中 |
| 短期签名 + 随机命名 | 技术防护完善 | 低 |
| 加密 + 生命周期 | 降低泄露影响 | 中 |
| 审计告警 | 提升感知能力 | 高（持续优化）|

