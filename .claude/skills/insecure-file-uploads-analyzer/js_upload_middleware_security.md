# JavaScript (Node.js) 上传中间件安全漏洞

## Details

### 漏洞成因
Node.js 框架（Express、Koa、Nest）常使用 `multer`, `busboy`, `formidable`, `fastify-multipart` 等中间件处理文件上传。如果仅依赖扩展名或 `req.file.mimetype` 判断类型，未限制文件大小、数量、路径、临时目录和随机文件名，攻击者可上传 WebShell、恶意脚本或压缩炸弹，导致执行任意代码、覆盖静态资源或造成拒绝服务。

### 代码示例

**易受攻击的代码：**
```javascript
const multer = require("multer");
const upload = multer({ dest: "public/uploads/" }); // 默认随机名但目录可访问

app.post("/upload", upload.single("file"), (req, res) => {
  const { originalname, path } = req.file;
  if (!originalname.endsWith(".jpg")) {
    return res.status(400).send("invalid file"); // 仅依赖扩展名
  }
  fs.renameSync(path, `public/uploads/${originalname}`); // 恢复原始文件名
  res.send("ok");
});
```

**另一个不安全示例（未限制大小）：**
```javascript
const upload = multer({ storage: multer.memoryStorage() }); // 内存存储

router.post("/api/upload", upload.array("files"), (req, res) => {
  // 未限制文件大小，攻击者可上传超大文件导致内存耗尽
  res.json({ success: true });
});
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 中间件：`multer`, `busboy`, `formidable`, `fastify-multipart`
- 存储配置：`diskStorage`, `memoryStorage`, `dest`, `storage`
- 类型判断：`originalname`, `mimetype`, `path.extname`
- 临时路径：`os.tmpdir`, `tmp`, `uploads`

**定位步骤：**
1. 搜索上传路由，检查是否设置 `limits`（文件大小、数量、字段数）。
2. 查看是否验证 MIME/文件头、使用白名单、随机文件名。
3. 跳读（L2）确认存储目录是否可执行或对外暴露。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **limits 配置：** `limits: { fileSize, files, fields }`。
- **自定义过滤：** `fileFilter` 校验 MIME、扩展名，读取文件头。
- **随机命名与隔离：** 使用 `diskStorage` 自定义文件名，保存到不可执行目录。
- **访问控制：** 上传文件通过签名 URL 或受限路由访问。
- **清理与扫描：** 上传后进行扫描，失败时删除临时文件。

**定位技巧：**
- 检查是否使用 `memoryStorage` 处理大文件导致内存 DoS。
- 确认 `busboy` 等低级库的事件处理是否防止路径穿越。
- 追踪上传后续处理链路（如图像处理、对象存储）。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| limits + fileFilter + 隔离目录 | **L0（快速跳过）** | 风险低 |
| 部分控制但仍使用 public 目录 | **L2（跳读）** | 需检查绕过 |
| 无限制直接保存至可访问目录 | **L3（逐行读）** | 高风险 |
| 上传后触发额外执行逻辑 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 上传中间件缺乏大小、数量、类型限制或未随机命名。
2. 文件保存目录可被执行或直接访问，缺乏鉴权。
3. 攻击者可实现代码执行、覆盖文件或 DoS。

#### 误报
以下情况可判定为误报：
1. 上传仅供可信内部服务，且链路安全（签名、VPN）。
2. 文件保存到私有目录或对象存储，通过签名 URL 访问。
3. 已配置 `limits`、`fileFilter`、内容扫描并确认有效。

#### 代码异味
需记录的风险：
1. 未处理 `multer` 错误回调，攻击尝试可能被忽略。
2. 使用 `memoryStorage` 处理未知大小文件。
3. 临时文件未删除，可能泄露敏感数据或占用磁盘。
4. 缺少上传日志与告警。

## Low risk

### 低风险评级场景

#### 1. 内部管理接口
- **场景：** 上传口仅对管理员开放，并记录操作日志。
- **风险评估：** 攻击面有限，但需防凭证泄露。

#### 2. 对象存储转存
- **场景：** 上传后立即转存私有对象存储，返回签名 URL。
- **风险评估：** 可降低执行风险，但仍需校验内容。

#### 3. 定期清理
- **场景：** 上传目录定期清理、临时文件及时删除。
- **风险评估：** 减少滥用风险，仍需防恶意内容。

#### 4. 监控与告警
- **场景：** 配合 WAF/IDS、日志监控检测异常上传。
- **风险评估：** 有助于快速响应，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用 | 攻击面有限 | 中 |
| 对象存储 + 签名访问 | 技术防护完善 | 低 |
| 定期清理 | 降低持久化风险 | 中 |
| 监控告警 | 提升发现能力 | 高（持续优化）|

