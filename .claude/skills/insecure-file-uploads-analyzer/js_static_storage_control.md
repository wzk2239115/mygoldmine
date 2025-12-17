# JavaScript (Node.js) 静态资源存储访问控制漏洞

## Details

### 漏洞成因
Node.js 服务通常通过 `express.static`, `serve-static`, `koa-static`, `fastify-static` 或 Nginx/CDN 暴露静态目录。如果将上传文件直接写入这些目录，且未随机命名、缺乏访问鉴权、目录遍历防护与权限配置，攻击者可枚举、访问或覆盖他人文件，甚至上传可执行脚本被解析执行。此外，对象存储或 CDN 若使用公开权限或返回永久 URL 也会导致敏感数据泄露。

### 代码示例

**易受攻击的代码：**
```javascript
app.use("/uploads", express.static(path.join(__dirname, "public/uploads")));

app.post("/upload", upload.single("file"), (req, res) => {
  fs.renameSync(req.file.path, path.join("public/uploads", req.file.originalname));
  res.json({ url: `/uploads/${req.file.originalname}` });
});
```

**另一个不安全示例（S3 公共访问）：**
```javascript
const s3 = new AWS.S3();
async function uploadToS3(file) {
  await s3
    .putObject({
      Bucket: process.env.BUCKET,
      Key: `uploads/${file.originalname}`, // 可预测文件名
      Body: file.buffer,
      ACL: "public-read", // 所有人可访问
    })
    .promise();
  return `https://${process.env.BUCKET}.s3.amazonaws.com/uploads/${file.originalname}`;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 静态中间件：`express.static`, `serve-static`, `app.use("/uploads")`
- 对象存储：`ACL`, `public-read`, `SignedUrl`, `getSignedUrl`
- URL 返回：`res.json({ url })`, `ctx.body = { url }`
- 文件命名：`originalname`, `path.basename`, `uuidv4`

**定位步骤：**
1. 搜索静态目录暴露配置，确认是否与上传目录相同。
2. 检查是否使用随机文件名、目录隔离、防止覆盖。
3. 跳读（L2）查明是否存在访问控制、签名 URL 或权限限制。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **随机命名**：使用 UUID、哈希生成文件名。
- **访问鉴权**：通过签名 URL、短期 token 下载文件。
- **目录隔离**：上传目录禁用执行权限，使用独立域名、子路径。
- **响应头**：设置 `Content-Disposition=attachment`、`X-Content-Type-Options=nosniff`。
- **日志审计**：记录访问日志，检测异常下载/覆盖。

**定位技巧：**
- 检查 CDN/Nginx 配置是否允许目录索引、执行脚本。
- 确认是否使用 `res.sendFile` 直接返回文件而不验证权限。
- 追踪文件删除或过期策略。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 私有存储 + 签名访问 + 随机命名 | **L0（快速跳过）** | 风险低 |
| 静态目录公开但仅存放安全资源 | **L2（跳读）** | 检查是否混入敏感文件 |
| 上传目录通过静态中间件暴露 | **L3（逐行读）** | 高风险 |
| 多服务共用目录 + 无隔离 | **L4（跨模块追踪）** | 需全面审计 |

## Classify

### 研判标准

#### 确认漏洞
认定为漏洞需满足：
1. 上传文件存储在公开可访问目录或公共对象存储。
2. 文件名或路径可预测，或目录允许执行脚本。
3. 缺乏访问控制、签名 URL、权限设置，导致敏感数据泄露或脚本执行。

#### 误报
以下情况可判定为误报：
1. 上传的文件仅为公开静态内容，无敏感信息且不可执行。
2. 存储配置为私有，访问需签名 URL 或后端校验。
3. 文件存储在 CDN 但经过内容审核、随机命名、无覆盖风险。

#### 代码异味
需要关注的焦点：
1. 同时使用 public/private 存储，易因配置错误暴露数据。
2. 缺少删除/过期机制，上传后长时间可访问。
3. 未设置缓存/带宽限制，易遭滥用。
4. 无访问日志，难以追踪数据泄露。

## Low risk

### 低风险评级场景

#### 1. 内部受控环境
- **场景：** 文件仅在内部网络访问，配合 ACL 与 VPN。
- **风险评估：** 攻击面有限，但需防内部威胁。

#### 2. 短期签名/临时 URL
- **场景：** 访问需携带短期签名或一次性令牌。
- **风险评估：** 风险较低，需确保存储安全政策。

#### 3. 加密存储 + 审计
- **场景：** 文件加密保存并定期审计访问记录。
- **风险评估：** 降低泄露影响。

#### 4. 只读 CDN 分发
- **场景：** 上传内容经过审核后部署至只读 CDN，应用不可写。
- **风险评估：** 较为安全，仍需监控恶意内容。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问控制 | 攻击面有限 | 中 |
| 签名 URL + 随机命名 | 技术防护完善 | 低 |
| 加密存储/审计 | 降低泄露价值 | 中 |
| 只读 CDN | 降低覆盖风险 | 高（持续监控）|

