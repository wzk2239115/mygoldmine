# TypeScript NestJS 上传验证漏洞

## Details

### 漏洞成因
NestJS 等 TypeScript 框架通常使用 `@UploadedFile`, `@UploadedFiles`, `FileInterceptor`, `multer` 适配器处理上传。如果 DTO、管道（`ValidationPipe`）、拦截器未启用白名单、大小限制、类型验证和随机命名，攻击者可上传恶意脚本、WebShell 或压缩炸弹，进一步利用 SSR/渲染逻辑实现 RCE 或 DoS。GraphQL 上传、Fastify 适配器等也需要类似防护。

### 代码示例

**易受攻击的代码：**
```typescript
@Post("upload")
@UseInterceptors(FileInterceptor("file", { dest: "public/uploads" }))
upload(@UploadedFile() file: Express.Multer.File) {
  if (!file.originalname.endsWith(".png")) {
    throw new BadRequestException("invalid file");
  }
  // 将原名写入静态目录
  fs.renameSync(file.path, `public/uploads/${file.originalname}`);
  return { url: `/uploads/${file.originalname}` };
}
```

**另一个不安全示例（缺少管道配置）：**
```typescript
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.useGlobalPipes(new ValidationPipe()); // 未启用 whitelist/forbidNonWhitelisted
  await app.listen(3000);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 装饰器：`@UploadedFile`, `@UploadedFiles`, `FileInterceptor`, `AnyFilesInterceptor`
- Multer 配置：`FileInterceptor("file", options)`, `storage`, `limits`
- DTO：`class UploadDto`, `@IsMimeType`, `@IsOptional`
- 管道：`ValidationPipe({ whitelist, forbidNonWhitelisted })`, `ParseFilePipe`

**定位步骤：**
1. 搜索上传控制器，检查是否使用 `ParseFilePipe`, `FileValidator`, `FileTypeValidator`.
2. 查看 Multer 配置是否设置 `limits.fileSize`, `fileFilter`.
3. 跳读（L2）确认文件保存位置、随机命名、访问控制。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **ValidationPipe 配置：** `whitelist: true`, `forbidNonWhitelisted: true`.
- **自定义验证器：** `FileTypeValidator`, `MaxFileSizeValidator`.
- **随机命名与隔离目录：** 使用 `diskStorage` 自定义 fileName，避免 public 目录。
- **访问权限：** 通过签名 URL 或后端校验返回文件。
- **内容扫描：** 上传后触发杀毒或 DLP 服务。

**定位技巧：**
- 检查 DTO 是否显式排除敏感字段并使用 `@IsNotEmpty`.
- 确认 GraphQL 上传 (`GraphQLUpload`) 是否进行类型校验。
- 追踪文件是否传递给其他模块（如模板渲染、云存储）。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| ValidationPipe whitelist + 自定义验证器 + 隔离存储 | **L0（快速跳过）** | 风险低 |
| 仅使用默认拦截器 | **L2（跳读）** | 需检查防护覆盖面 |
| 直接保存原始文件到静态目录 | **L3（逐行读）** | 高风险 |
| 上传结合 SSR/模板动态包含 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 上传入口缺乏 `ParseFilePipe`、类型/大小验证或随机命名。
2. 文件存储在可执行/可访问目录，或后续处理缺乏隔离。
3. 攻击者可利用上传执行代码、覆盖资源或触发 DoS。

#### 误报
以下情况可判定为误报：
1. 上传功能仅对受信渠道开放并带签名/权限校验。
2. 文件存储在私有位置，访问需二次鉴权且已扫描。
3. DTO + 管道明确限制类型、大小并启用随机文件名。

#### 代码异味
需记录的风险：
1. 未启用 `whitelist`，DTO 以外字段可被注入。
2. 使用 `memoryStorage` 处理大文件，易导致内存 DoS。
3. 缺少日志，无法追踪异常上传。
4. 上传异常处理不完整，可能泄露临时文件。

## Low risk

### 低风险评级场景

#### 1. 管理员专用接口
- **场景：** 上传仅供后台管理员使用，并记录审计。
- **风险评估：** 攻击面有限，但需防身份被盗。

#### 2. 上传后转存对象存储
- **场景：** 文件经校验后转存私有对象存储，访问使用签名 URL。
- **风险评估：** 风险较低，但仍需校验。

#### 3. 定期清理 + 只读发布
- **场景：** 上传目录定期清理，文件经审核后发布至只读 CDN。
- **风险评估：** 降低滥用风险。

#### 4. 监控告警
- **场景：** 集成监控对上传流量与失败事件告警。
- **风险评估：** 有助于快速响应，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用 | 攻击面有限 | 中 |
| 私有存储 + 签名访问 | 技术防护完善 | 低 |
| 定期清理/只读发布 | 降低持续风险 | 中 |
| 监控告警 | 提升发现能力 | 高（持续优化）|

