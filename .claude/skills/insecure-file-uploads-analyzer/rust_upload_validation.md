# Rust Web 上传验证漏洞

## Details

### 漏洞成因
Rust Web 框架（Actix Web、Rocket、Axum、Warp 等）通过 `Multipart`, `TempFile`, `Form` 解析上传文件。若仅根据文件名或 `content_type` 判断类型，未检查魔术字、大小、数量、路径规范化，也未使用随机文件名与隔离目录，攻击者可上传恶意脚本、压缩炸弹或利用目录穿越覆盖任意文件，从而实现代码执行或拒绝服务。

### 代码示例

**易受攻击的代码：**
```rust
pub async fn upload(mut payload: Multipart) -> impl Responder {
    while let Some(field) = payload.next().await {
        let mut field = field.unwrap();
        let content_type = field.content_type().unwrap().to_string();
        if !content_type.contains("image") {
            return HttpResponse::BadRequest().finish();
        }
        let filename = field.content_disposition().get_filename().unwrap();
        let filepath = format!("./static/uploads/{}", filename); // 未 Clean
        let mut f = web::block(|| std::fs::File::create(filepath)).await.unwrap();
        while let Some(chunk) = field.next().await {
            let data = chunk.unwrap();
            f = web::block(move || f.write_all(&data).map(|_| f)).await.unwrap();
        }
    }
    HttpResponse::Ok().finish()
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- Actix：`Multipart`, `Field`, `TempFile`, `NamedFile`
- Rocket：`TempFile`, `Data::open`, `FromForm`
- Axum/Warp：`Multipart`, `Part`, `FormData`
- 路径处理：`format!`, `PathBuf::from`, `join`, `fs::create_dir_all`

**定位步骤：**
1. 搜索上传处理函数，检查是否针对 `content_type`、扩展名、魔术字进行校验。
2. 查看是否调用 `Path::join` + `canonicalize` 防止目录穿越。
3. 跳读（L2）确认是否限制文件大小、数量、随机命名、访问权限。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **类型验证：** 使用 `infer`, `magic`, 读取前几个字节判断真实类型。
- **大小限制：** 设置 `PayloadConfig`、`DataLimits`, 使用 `Content-Length` 检查。
- **随机命名与隔离：** 使用 `uuid`, `tempfile`, 保存到不可执行目录。
- **访问控制：** 上传文件通过签名 URL 或后端校验返回。
- **内容扫描：** 集成杀毒、DLP 服务。

**定位技巧：**
- 检查是否使用 `NamedFile` 直接暴露上传目录。
- 追踪后续处理（解压、解析）是否安全。
- 确认临时文件清理逻辑。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 类型验证 + 随机命名 + 隔离目录 | **L0（快速跳过）** | 风险低 |
| 部分验证但依赖前端 | **L2（跳读）** | 需补齐防护 |
| 无校验、直接写入静态目录 | **L3（逐行读）** | 高风险 |
| 上传文件进入解析/执行流程 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 上传入口缺乏可靠的类型、大小、路径校验或随机命名。
2. 文件可被访问或执行，或导致后续处理链路执行恶意代码。
3. 攻击者可实现 RCE、覆盖文件或 DoS。

#### 误报
以下情况可视为误报：
1. 上传仅对受信渠道开放，并附带签名/权限校验。
2. 文件存储于不可执行目录，访问需鉴权，已实施扫描。
3. 框架内建限制（如 `TempFile::persist` 仅允许指定目录）并已启用。

#### 代码异味
需记录的风险：
1. 使用 `PathBuf::from` 拼接路径但未 `canonicalize`。
2. `actix-web` 默认临时目录未清理，可能泄露数据。
3. 缺少错误日志，难以识别恶意尝试。
4. 未使用 `Data::open` 大小限制，易被压缩炸弹攻击。

## Low risk

### 低风险评级场景

#### 1. 后台/内部上传
- **场景：** 上传仅供可信用户使用并记录审计。
- **风险评估：** 攻击面有限，但需防凭证泄露。

#### 2. 上传即转存对象存储
- **场景：** 经校验后转存私有对象存储，访问通过签名。
- **风险评估：** 风险较低，仍需扫描内容。

#### 3. 定期清理 + 只读发布
- **场景：** 上传目录定期清理，文件经审核后发布至只读 CDN。
- **风险评估：** 降低滥用风险。

#### 4. 监控告警
- **场景：** 集成日志与告警监控异常上传行为。
- **风险评估：** 有助于快速响应，需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员/内部专用 | 攻击面有限 | 中 |
| 隔离存储 + 签名访问 | 技术防护完善 | 低 |
| 定期清理/只读发布 | 减少长期风险 | 中 |
| 监控告警 | 提升发现能力 | 高（持续优化）|

