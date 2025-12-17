# Node.js S3下载未检查权限 - IDOR漏洞

## Details

**典型代码模式：**
```javascript
// 易损模式：直接使用用户输入的key/fileId
app.get('/download/:fileId', async (req, res) => {
  const { fileId } = req.params;
  const s3Params = { Bucket: 'my-bucket', Key: fileId };
  const stream = s3.getObject(s3Params).createReadStream();
  stream.pipe(res);
});

// 或Express + AWS SDK v3
app.get('/file', async (req, res) => {
  const key = req.query.key;  // 直接信任用户输入
  const command = new GetObjectCommand({ Bucket: bucket, Key: key });
  const data = await s3Client.send(command);
  res.send(data.Body);
});
```

**快速定位核心操作（L1-L2）：**
- L1关键词：`getObject`、`GetObjectCommand`、`getSignedUrl`、`createReadStream`、`download`、`Bucket`、`Key`
- L2跳读：追踪路由参数/query参数到S3操作的数据流，检查Key值来源是否可控

**快速定位保护机制（L2-L4）：**
- L2跳读：扫描S3操作前是否有ACL检查、数据库关联查询（`findOne({userId, fileId})`）
- L3逐行：检查中间件（`authMiddleware`、`checkOwnership`）是否真正验证资源归属
- L4跨模块：追踪Key是否经过白名单/映射表转换，或是否查询metadata验证owner字段

## Classify

**漏洞判定：**
- 用户可控的Key/路径参数直接用于S3操作，且无权限验证或仅依赖客户端过滤
- 存在会话机制（登录用户），但未将`userId`与资源关联验证
- 测试可通过枚举或猜测Key访问其他用户资源

**误报识别：**
- S3 Bucket配置了严格的IAM策略或Object ACL，已在云服务层面限制访问（需确认配置）
- Key经过加密哈希或HMAC签名校验，攻击者无法伪造有效Key
- 仅处理公开资源（如CDN静态资源），业务逻辑本就允许任意访问

**代码异味：**
- 存在权限检查但实现存在逻辑缺陷（如条件绕过、类型混淆）
- 仅验证文件存在性，未验证归属关系

## Low risk

**低风险场景：**
- 访问的对象均为公开文件（用户协议、公告附件），无敏感信息
- Key的可枚举空间极小且受业务限制（如仅限当天日志），实际越权价值有限
- 存在速率限制和审计日志，攻击成本高且可追溯
- 已有二次鉴权（如需短信验证码才能完成下载），降低利用风险
- 文件内容为加密数据，且解密密钥独立管理（用户特定），即使下载也无法解密