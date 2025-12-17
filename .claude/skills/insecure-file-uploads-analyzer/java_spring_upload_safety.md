# Java Spring 文件上传安全漏洞

## Details

### 漏洞成因
在 Spring MVC/Spring Boot 等框架中，常使用 `MultipartFile`, `CommonsMultipartResolver`, `ServletFileUpload` 等处理用户上传。如果仅依赖前端传递的扩展名或 `Content-Type`，未使用白名单验证、文件头检测、大小/数量限制、随机文件名以及访问控制，攻击者可上传 WebShell、JSP、EL 脚本或压缩炸弹，从而实现远程代码执行、覆盖静态资源或造成拒绝服务。同时，直接将文件保存到 Web 根目录或通过 `ResourceHttpRequestHandler` 暴露也会放大风险。

### 代码示例

**易受攻击的代码：**
```java
@PostMapping("/upload")
public String upload(@RequestParam("file") MultipartFile file) throws IOException {
    String filename = file.getOriginalFilename();
    if (!filename.endsWith(".jpg") && !filename.endsWith(".png")) {
        throw new IllegalArgumentException("invalid file");
    }
    // 直接存放到静态目录
    Path target = Paths.get("src/main/resources/static/uploads/", filename);
    Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
    return "/uploads/" + filename;
}
```

**另一个不安全示例（缺少文件头校验与大小限制）：**
```java
public void save(MultipartFile file) throws IOException {
    if (file.getSize() > 100 * 1024 * 1024) { // 未限制数量、未防止压缩炸弹
        throw new IllegalArgumentException();
    }
    File dest = new File(uploadDir, file.getOriginalFilename());
    file.transferTo(dest); // 未检查实际 MIME，未使用随机文件名
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 上传入口：`MultipartFile`, `@RequestPart`, `CommonsMultipartResolver`, `StandardServletMultipartResolver`
- 文件保存：`transferTo`, `Files.copy`, `FileOutputStream`
- 类型判断：`getOriginalFilename`, `getContentType`, `MediaType`
- 静态资源映射：`ResourceHandlerRegistry`, `addResourceLocations`, `WebMvcConfigurer`

**定位步骤：**
1. 搜索所有 `MultipartFile` 使用位置，检查是否有白名单和大小限制。
2. 审核保存路径，确认是否写入可执行目录或静态映射路径。
3. 跳读（L2）了解是否对文件进行扫描、随机命名、访问控制。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **类型验证：** 读取文件头（如 magic number）或使用第三方库检测 MIME。
- **白名单策略：** 仅允许指定扩展名 + MIME，并在服务端重新命名。
- **大小/数量限制：** 配置 `spring.servlet.multipart.max-file-size`、`max-request-size`。
- **存储隔离：** 使用非 Web 根目录，配合对象存储或 CDN，禁止脚本执行。
- **访问控制：** 文件访问需鉴权或通过签名 URL，避免直接暴露。

**定位技巧：**
- 检查 `MultipartResolver` 配置是否允许临时文件泄露。
- 确认文件名是否使用随机 UUID，避免覆盖已有文件。
- 对压缩、图像处理链路，跟踪是否在沙箱中执行。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用白名单 + 魔术字校验 + 隔离存储 | **L0（快速跳过）** | 安全基线较高 |
| 仅基于扩展名判断但另有访问控制 | **L2（跳读）** | 检查是否存在绕过 |
| 直接 `transferTo` 静态目录 | **L3（逐行读）** | 高风险 |
| 上传后触发模板/脚本解析 | **L4（跨模块追踪）** | 需深入分析跨组件 |

## Classify

### 研判标准

#### 确认漏洞
判断上传漏洞需满足：
1. 上传入口允许任意用户提交文件，缺乏可信的类型/内容验证或大小限制。
2. 文件存储或访问策略存在缺陷（可执行路径、公开访问、固定文件名）。
3. 攻击者可通过上传获取执行权限、覆盖文件或引发 DoS。

#### 误报
以下情形可视为误报：
1. 上传功能仅对受信渠道开放并具备签名/令牌验证。
2. 文件经多层扫描、随机命名且存储于不可执行的隔离目录。
3. 访问需鉴权或通过短期签名 URL，避免直接访问。

#### 代码异味
需要记录的潜在问题：
1. 仅依赖 `getContentType()` 的值，可能被篡改。
2. 缺少上传异常日志，难以追踪恶意尝试。
3. 上传目录权限过大，未来配置变更可能导致执行。
4. 未开启 `MultipartResolver` 的临时文件清理机制。

## Low risk

### 低风险评级场景

#### 1. 内部管理上传
- **场景：** 上传接口仅供后台管理员使用，并结合 MFA。
- **风险评估：** 攻击面有限，但需防账号泄露。

#### 2. 上传即转存对象存储
- **场景：** 文件先上传至隔离目录，安全校验后再存入对象存储。
- **风险评估：** 可降低执行风险，但仍需校验内容。

#### 3. 静态 CDN 只读分发
- **场景：** 成功上传的文件由 CDN 分发，Web 服务器不可写。
- **风险评估：** 降低覆盖风险，仍需防恶意内容传播。

#### 4. 安全监控与告警
- **场景：** 结合 WAF、IDS、审计日志实时监控异常上传行为。
- **风险评估：** 有助于快速响应，需配合代码修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用接口 | 攻击面小 | 中 |
| 白名单 + 隔离存储 | 技术防护到位 | 低 |
| 对象存储/只读分发 | 降低执行/覆盖风险 | 中 |
| 实时监控告警 | 提高发现速度 | 高（持续优化）|

