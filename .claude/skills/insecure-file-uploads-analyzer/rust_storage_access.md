# Rust 上传存储访问控制漏洞

## Details

### 漏洞成因
Rust 服务常使用 `tokio::fs`, `async_std::fs`, `s3::Client`, `gcs`, `azure_storage` 等库将上传文件存储到本地或对象存储。若保存路径可预测、缺乏随机命名、权限控制或签名 URL，攻击者可访问、覆盖或执行上传文件，导致敏感数据泄露或 WebShell 攻击。多租户系统若共享目录也会造成越权。

### 代码示例

**易受攻击的代码：**
```rust
pub async fn save_file(file: &TempFile<'_>) -> Result<String> {
    let filename = file.raw_name().unwrap().as_str();
    let path = Path::new("./public/uploads").join(filename); // 可预测
    file.persist(&path).await?;
    Ok(format!("/uploads/{}", filename))
}
```

```rust
pub async fn upload_s3(client: &Client, key: &str, bytes: Bytes) -> Result<String> {
    client.put_object()
        .bucket("my-public-bucket")
        .key(format!("uploads/{}", key))
        .body(bytes.clone().into())
        .acl(ObjectCannedAcl::PublicRead) // 公开访问
        .send()
        .await?;
    Ok(format!("https://my-public-bucket.s3.amazonaws.com/uploads/{}", key))
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 本地存储：`std::fs`, `tokio::fs`, `PathBuf`, `create_dir_all`
- 对象存储：`aws_sdk_s3`, `google_cloud_storage`, `azure_storage`
- URL 生成：`format!("https://", ...)`, `PresigningConfig`, `signed_url`
- 权限设置：`set_permissions`, `chmod`, `ObjectCannedAcl`

**定位步骤：**
1. 搜索保存/返回 URL 的代码，确认是否随机命名和隔离目录。
2. 检查对象存储配置是否使用 `public-read` 或无签名的永久 URL。
3. 跳读（L2）验证是否根据租户/用户设置目录，避免越权。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **随机命名：** 使用 `uuid::Uuid`, `hash`, `timestamp + random`.
- **权限控制：** 设置文件为不可执行，ACL 为私有，访问需签名 URL。
- **加密与版本控制：** 启用 SSE、版本化、生命周期规则。
- **访问审计：** 记录下载/覆盖行为，告警异常访问。
- **隔离策略：** 按租户分目录或存储桶，防止互相访问。

**定位技巧：**
- 确认 `Path::join` 后是否使用 `canonicalize` 防止目录穿越。
- 检查删除/过期策略，防止敏感文件长期暴露。
- 查看 `PresigningConfig::expires_in` 是否设置合理有效期。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 私有存储 + 签名 URL + 随机命名 | **L0（快速跳过）** | 风险低 |
| 公共访问但仅静态资源 | **L2（跳读）** | 检查是否包含敏感文件 |
| 公共目录 + 可预测文件名 | **L3（逐行读）** | 高风险 |
| 多租户共享存储无隔离 | **L4（跨模块追踪）** | 需全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 上传文件可被未经授权访问或覆盖。
2. 未使用随机命名或隔离目录，易被枚举或执行。
3. 存储访问无鉴权/签名，导致敏感数据泄露或代码执行。

#### 误报
以下情况视为误报：
1. 存储配置为私有，访问需短期签名 URL。
2. 上传仅供内部系统使用，且目录权限严格。
3. 文件名随机不可预测，并经多层审核后发布。

#### 代码异味
需记录的风险：
1. 同时使用公共和私有存储策略但缺乏区分。
2. 缺少访问日志，无法追踪泄露或覆盖。
3. 未设置生命周期，敏感文件长期存在。
4. 对象存储凭证范围过大，允许任意路径写入。

## Low risk

### 低风险评级场景

#### 1. 内部访问
- **场景：** 文件仅供内部服务访问，配合 IAM/WAF。
- **风险评估：** 攻击面有限，但需防凭证泄露。

#### 2. 短期签名 URL
- **场景：** 所有下载需短期签名且限制操作。
- **风险评估：** 风险较低，需确保存储策略安全。

#### 3. 加密 + 版本控制
- **场景：** 启用加密、版本化和过期策略。
- **风险评估：** 降低泄露与覆盖风险。

#### 4. 审计告警
- **场景：** 启用日志、告警系统监控异常访问。
- **风险评估：** 有助于发现问题，仍需配合防护。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问控制 | 攻击面有限 | 中 |
| 签名 URL + 随机命名 | 技术防护完善 | 低 |
| 加密/版本化 | 降低泄露影响 | 中 |
| 审计告警 | 提升感知能力 | 高（持续优化）|

