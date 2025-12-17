# Java - 文件下载IDOR漏洞

## Details

**代码示例：**
```java
// 典型漏洞模式 - 直接使用文件ID
@GetMapping("/download/{fileId}")
public ResponseEntity<Resource> downloadFile(@PathVariable String fileId) {
    File file = fileService.getFileById(fileId);  // 未校验所有权
    return ResponseEntity.ok()
        .header("Content-Disposition", "attachment; filename=" + file.getName())
        .body(new FileSystemResource(file));
}

// 通过文件名下载 - 路径拼接风险
@RequestMapping("/attachment")
public void downloadAttachment(String filename, HttpServletResponse response) {
    String path = "/uploads/" + filename;  // 直接拼接
    FileInputStream fis = new FileInputStream(path);  // 无权限检查
    IOUtils.copy(fis, response.getOutputStream());
}

// Spring MVC常见变体
@GetMapping("/files")
public void getFile(@RequestParam("id") Long id, HttpServletResponse resp) {
    Attachment att = attachmentMapper.selectById(id);  // MyBatis直接查询
    resp.setHeader("Content-Type", "application/octet-stream");
    Files.copy(Paths.get(att.getPath()), resp.getOutputStream());
}

// RESTful API下载
@Path("/document/{docId}")
@GET
public Response download(@PathParam("docId") String docId) {
    Document doc = dao.findById(docId);  // 未验证所属关系
    return Response.ok(doc.getContent()).build();
}
```

**快速定位核心操作（L1-L3 关键词扫描/跳读/逐行）：**
- **Controller注解（L1）**：`@GetMapping`、`@RequestMapping`、`@RestController`、`@Path`
- **下载特征（L1）**：`Content-Disposition`、`FileSystemResource`、`InputStreamResource`、`attachment`
- **参数获取（L2）**：`@PathVariable`、`@RequestParam`、`@RequestBody`、`HttpServletRequest.getParameter()`
- **文件操作（L2）**：`FileInputStream`、`Files.copy()`、`IOUtils.copy()`、`BufferedInputStream`、`Paths.get()`
- **数据库查询（L3）**：`Mapper.selectById()`、`Repository.findById()`、`dao.get()`、`entityManager.find()`、`jdbcTemplate.queryForObject()`
- **敏感资源（L2）**：File、Attachment、Document、Invoice、Report、Contract、UserFile等实体

**快速定位保护机制（L3-L4 逐行/跨模块）：**
- **同层校验（L3）**：在文件操作前后寻找：
  - 会话校验：`SecurityContextHolder.getContext().getAuthentication()`、`request.getSession().getAttribute("userId")`
  - 所有权判断：`if (!file.getOwnerId().equals(currentUserId))`、`file.getUserId() == loginUser.getId()`
  - 权限注解：`@PreAuthorize`、`@Secured`、`@RolesAllowed`（需确认表达式是否包含资源级权限）
  - 异常处理：`throw new AccessDeniedException()`、`return ResponseEntity.status(403)`
- **拦截器/过滤器（L3）**：检查注册配置：
  - `WebMvcConfigurer.addInterceptors()`
  - `FilterRegistrationBean`
  - `@Component HandlerInterceptor` 实现类
  - JAX-RS `@Provider ContainerRequestFilter`
- **AOP切面（L3-L4）**：
  - 搜索 `@Aspect`、`@Around("@annotation(RequireOwnership)")`
  - 追踪切面逻辑是否验证资源归属
- **服务层封装（L4）**：
  - 追踪 `fileService.getFile(id, userId)` 方法签名，检查是否强制传入用户标识
  - 检查自定义Repository查询：`findByIdAndUserId()`、`@Query` 中是否包含所有权条件
  - ORM实体监听器：`@EntityListeners`、`@PreLoad` 钩子是否注入权限逻辑
- **框架级方案（L4）**：
  - Spring Security ACL：`@PostFilter`、`@PreAuthorize("hasPermission(#id, 'File', 'read')")`
  - 数据权限插件：MyBatis-Plus DataPermissionInterceptor配置检查
  - Shiro：`subject.isPermitted("file:download:" + fileId)`

## Classify

**漏洞判定标准：**
- 参数可控且可遍历：文件ID/名称来自外部输入，可通过修改参数访问其他用户文件
- 缺乏所有权验证：Controller、Service、DAO全链路均未校验当前用户与资源所属关系
- 敏感文件可获取：能下载包含隐私、财务、业务机密的文件内容

**误报常见场景：**
- 公开资源：下载的是产品手册、公告附件等设计上允许所有用户访问的内容
- 前置拦截：虽然业务代码未检查，但拦截器/Filter已根据token限制可访问的文件ID范围
- 数据库约束：Repository方法签名强制关联userId（如 `findByIdAndUserId()`），无法跨用户查询
- ACL框架：Spring Security Permission Evaluator或Shiro已在框架层统一验证（需确认配置覆盖完整性）

**代码异味识别：**
- 防御不完整：仅校验文件存在性（`file.exists()`）但未验证归属关系
- 软删除绕过：检查了 `deleted=0` 但未检查 `owner_id`
- 条件保护：仅在特定角色下校验（如 `if (role != ADMIN) checkOwnership()`）
- 依赖客户端：后端信任前端传递的userId参数进行验证
- 路径遍历混淆：修复了路径遍历但遗漏了IDOR权限检查

## Low risk

**可降级为低风险的场景：**
- **文件内容脱敏**：下载前已移除敏感字段或进行水印/加密处理
- **影响范围受限**：
  - 仅泄露文件元数据（文件名、大小、创建时间），无法获取实际内容
  - 文件为临时生成的报表摘要，不包含原始敏感数据
  - ID使用不可预测的UUID且无枚举价值
- **业务逻辑限制**：
  - 下载需消耗积分/额度，攻击成本高且有审计追踪
  - 需配合其他高权限操作才能获取有效fileId（如需先通过管理接口列举）
- **外部控制机制**：
  - 文件存储在支持细粒度ACL的对象存储（S3/OSS），后端仅签发临时URL且验证了身份
  - API网关层已实施资源级鉴权策略（需审查策略配置的准确性）
  - 数据库触发器或视图强制过滤非当前用户的记录
- **只读且低价值**：文件为系统日志、公开数据集的副本，即使越权访问也无实质危害
- **完善的监控**：所有下载行为记录完整审计日志，异常访问可实时告警和阻断