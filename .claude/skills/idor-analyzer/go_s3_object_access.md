# Go S3对象访问IDOR

## Details

**代码示例：**
```go
// 漏洞示例：直接使用用户输入的objectKey访问S3
func DownloadFile(w http.ResponseWriter, r *http.Request) {
    objectKey := r.URL.Query().Get("key")  // 用户可控
    result, err := s3Client.GetObject(&s3.GetObjectInput{
        Bucket: aws.String("user-files"),
        Key:    aws.String(objectKey),  // 未验证所有权
    })
    // 返回对象内容
}
```

**快速定位核心操作（L2:跳读）：**
- 搜索关键API：`GetObject`、`GetObjectInput`、`DownloadFile`、`HeadObject`
- 关注handler中的查询参数：`r.URL.Query()`、`chi.URLParam`、`mux.Vars`、`gin.Param`
- 追踪objectKey/path变量从请求到S3调用的流转路径
- 检查Key构造方式：是否包含用户ID前缀或路径拼接

**快速定位保护机制（L3:逐行读）：**
- 查找所有权验证：数据库查询匹配`user_id`与`object_owner`
- 元数据检查：`HeadObject`后验证返回的`Metadata`字段
- ACL验证：调用`GetObjectAcl`检查访问权限
- 路径约束：检查是否限制Key必须包含当前用户目录
- 预签名URL：是否使用带权限的`Presign`而非直接GetObject
- 若以上均缺失且Key完全用户可控→高危

## Classify

**漏洞特征：**
- 用户输入的objectKey直接传入S3 API，无任何所有权校验逻辑
- Key构造允许路径穿越（如`../`）或完全可控
- 无数据库关联验证（未查询对象归属关系表）

**误报场景：**
- 公共资源bucket（如静态CDN文件），Key指向公开内容
- 前置中间件已完成统一鉴权（需跨模块追踪验证）
- Key由服务端映射表转换，用户仅提供映射ID

**代码异味：**
- 验证逻辑存在但可绕过（如仅检查文件扩展名）
- 仅依赖前端隐藏而无后端校验
- 验证存在TOCTOU竞态（检查后Key被篡改）

## Low risk

**低风险场景判定：**
1. **权限范围受限**：即使绕过也仅能访问同一租户/组织内的其他用户文件
2. **数据敏感度低**：对象为公开可访问的低敏感度数据（缓存图片、公开日志）
3. **Key空间可预测性低**：使用UUID/哈希作为Key且无枚举接口
4. **读写分离**：仅GetObject漏洞但无DeleteObject/PutObject风险
5. **已有补偿控制**：CloudTrail日志监控异常访问、存在访问频率限制

**注意：**即使评为低风险，仍需标注为缺陷并建议修复，避免后续数据敏感度升级或攻击面扩大。