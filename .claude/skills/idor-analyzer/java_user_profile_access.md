# Java - 用户资料访问未授权漏洞

## Details

**代码示例：**
```java
// 典型漏洞模式 - Spring Boot
@PostMapping("/api/user/profile")
public UserProfile getUserProfile(@RequestBody UserRequest request) {
    Long userId = request.getUserId();  // 从请求体提取ID
    return userService.findById(userId);  // 直接查询无权限校验
}

// REST风格路径参数
@GetMapping("/api/users/{id}")
public ResponseEntity<User> getUser(@PathVariable Long id) {
    User user = userRepository.findById(id).orElseThrow();  // 未验证访问权限
    return ResponseEntity.ok(user);
}

// Servlet直接获取参数
protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
    String userId = req.getParameter("userId");  // 从Query或Form获取
    User user = dao.selectUserById(userId);  // 直接查询
    resp.getWriter().write(toJson(user));
}

// MyBatis隐蔽场景
@PostMapping("/profile/detail")
public ProfileDTO getProfileDetail(@RequestBody Map<String, Object> params) {
    String uid = (String) params.get("uid");  // 动态参数提取
    return profileMapper.selectByUserId(uid);  // Mapper直接查询
}
```

**快速定位核心操作（L2:跳读）：**
- **参数来源识别**：
  - 注解标记：`@RequestBody`、`@PathVariable`、`@RequestParam`、`@RequestHeader`
  - Servlet API：`getParameter()`、`getAttribute()`、`getInputStream()`
  - 参数对象：DTO/VO类中的`userId`、`id`、`accountId`等字段
  - 动态参数：`Map<String, Object>`、`JSONObject`中提取的ID值
- **数据查询入口**：
  - Spring Data：`findById()`、`findOne()`、`getOne()`、`getReferenceById()`
  - JPA/Hibernate：`em.find()`、`session.get()`、`session.load()`
  - MyBatis：`selectByPrimaryKey()`、`selectById()`、`@Select`注解SQL
  - JDBC：`PreparedStatement`后的`executeQuery()`
  - 关注敏感实体：User、Profile、Account、Order、Document、Payment
- **定位技巧**：
  - 搜索控制器方法 → 提取参数名 → 追踪至查询语句 → 验证中间无过滤

**快速定位保护机制（L3-L4:逐行读/跨模块追踪）：**
- **L3同层检查**：
  - **会话校验**：
    - `HttpSession.getAttribute("userId")`、`SecurityContextHolder.getContext().getAuthentication()`
    - `@PreAuthorize`、`@Secured`注解是否存在
  - **所有权判断**：
    - 查询前：`if (!userId.equals(currentUser.getId())) throw ForbiddenException`
    - 查询后：`if (!user.getOwnerId().equals(sessionUserId)) return null`
    - SQL条件：`WHERE id = ? AND owner_id = ?`（检查占位符数量）
  - **方法级拦截器**：
    - 切面拦截：`@Aspect`类中的`@Before`、`@Around`切点
    - 拦截器链：`HandlerInterceptor.preHandle()`是否校验
- **L4跨模块追踪**：
  - **Service层封装**：
    - 追踪`userService.getProfile(id, currentUserId)`实现，检查参数是否双重比对
    - 确认Service方法是否注入`Authentication`或自定义权限上下文
  - **Repository层过滤**：
    - JPA：检查`@Query`注解SQL是否包含`AND created_by = :currentUser`
    - MyBatis XML：`<select>`标签内是否有`AND owner_id = #{ownerId}`
  - **安全框架集成**：
    - Spring Security：`FilterSecurityInterceptor`、自定义`AccessDecisionVoter`
    - Shiro：`@RequiresPermissions("user:read:self")`、`Subject.checkPermission()`
  - **AOP权限切面**：
    - 搜索`@annotation()`切点表达式，确认是否覆盖目标方法
    - 检查切面逻辑内是否对比请求ID与身份ID

## Classify

**漏洞确认标准：**
- **可横向越权**：修改请求中的`userId`参数可访问任意用户资料，无需额外凭证
- **敏感数据泄露**：响应包含手机号、邮箱、身份证、地址、余额等隐私字段
- **零防护特征**：既无框架级拦截器、也无业务层if判断、更无SQL条件约束

**误报排除依据：**
- **公开资源设计**：用户基本信息（昵称、头像）本身为公开展示设计，业务允许查看
- **前置拦截有效**：
  - 全局过滤器已校验token，且token生成时绑定了用户ID范围
  - API网关层已强制鉴权，后端仅处理已授权请求
- **字段投影安全**：
  - 查询后DTO转换时仅映射公开字段：`BeanUtils.copyProperties(user, publicDTO, "phone", "email")`
  - MyBatis ResultMap明确排除敏感列

**代码异味识别：**
- **防御不完整**：仅校验ID格式（正则匹配数字）或范围（> 0），未校验所有权
- **条件性保护**：仅在`isAdmin == false`分支校验，管理员走通用流程存在遗漏
- **客户端依赖**：前端过滤不展示他人ID，后端无二次验证
- **异常处理不当**：查询失败返回null而非抛异常，导致未执行后续权限检查

## Low risk

**可降级为低风险的场景：**
- **数据脱敏充分**：
  - 手机号中间4位打*、邮箱前缀脱敏、姓名仅显示姓氏
  - 金额类字段返回null或固定值，非真实数据
- **影响范围受限**：
  - 仅泄露用户等级、注册时间、头像URL等低敏感度信息
  - 返回的DTO通过白名单属性严格控制（需代码确认）
- **外部控制层**：
  - 数据库已配置RLS策略（如PostgreSQL），自动按当前会话过滤
  - API Gateway/Service Mesh实施统一鉴权，配置已覆盖全部路由
  - WAF规则拦截异常ID访问模式（需确认规则有效性）
- **间接利用门槛高**：
  - 需先通过其他漏洞获取有效ID列表（ID为UUID且无序）
  - 查询接口存在验证码或高频限流，批量遍历成本高
- **业务场景限制**：
  - 内部管理系统，用户间本可互查（需业务确认）
  - 测试/开发环境，不包含真实用户数据
  - 历史遗留API已下线或流量为零