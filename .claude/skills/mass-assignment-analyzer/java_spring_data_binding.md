# Java 批量赋值漏洞

## Details

### 漏洞成因
Java Web 框架（Spring MVC/Boot、Struts、Play 等）通常支持将请求参数自动绑定到 POJO/实体。若未通过 `@InitBinder`、`@JsonIgnore`、`@JsonProperty(access = READ_ONLY)`、`@JsonView` 或 BeanValidation 限制可写字段，攻击者可在表单/JSON 中添加敏感属性（如 `role`, `status`, `tenantId`, `balance`）覆盖服务端状态。使用 JPA/Hibernate 的 `save`, `merge`, `update` 时直接接受用户构造的实体对象，也会造成越权更新或多租户逃逸。

### 代码示例

**易受攻击的代码：**
```java
@PostMapping("/users/{id}")
public User updateUser(@PathVariable Long id, @RequestBody User payload) {
    User user = userRepository.findById(id).orElseThrow();
    // 未限制可写字段，payload 可携带 role=ADMIN
    BeanUtils.copyProperties(payload, user);
    return userRepository.save(user);
}
```

**另一个不安全示例（Jackson 反序列化）：**
```java
@Data
public class AccountDto {
    private String owner;
    private BigDecimal quota;
    private boolean active;
    private boolean admin; // 未加 @JsonIgnore
}

@PostMapping("/accounts")
public ResponseEntity<Account> create(@RequestBody AccountDto dto) {
    Account account = modelMapper.map(dto, Account.class);
    return ResponseEntity.ok(accountService.save(account));
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 自动绑定接口：`@RequestBody`, `@ModelAttribute`, `BeanUtils.copyProperties`, `ModelMapper`
- ORM 操作：`save`, `saveAndFlush`, `merge`, `update`, `persist`
- JSON 配置：`ObjectMapper`, `Jackson2ObjectMapperBuilder`, `@JsonIgnore`, `@JsonProperty`
- Lombok/Record 自动生成的 setter

**定位步骤：**
1. 搜索 `copyProperties`, `setAll`, 或控制器接收实体的接口。
2. 检查 DTO/Entity 上是否有敏感字段，如 `role`, `status`, `price`, `tenantId`。
3. 跳读（L2）确认是否使用白名单绑定或移除敏感字段。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **白名单绑定：** `binder.setAllowedFields("name", "email")`
- **敏感字段只读：** `@JsonProperty(access = JsonProperty.Access.READ_ONLY)`、`@Setter(AccessLevel.NONE)`
- **分层 DTO：** 使用输入 DTO 与实体分离
- **权限验证：** 更新前校验调用者角色/租户
- **字段过滤：** `BeanUtils.copyProperties(src, dest, "role", "status")`

**定位技巧：**
- 确认 `@InitBinder` 是否在相关控制器生效。
- 检查全局 `ObjectMapper` 是否启用 `FAIL_ON_UNKNOWN_PROPERTIES` 等安全配置。
- 对 `BeanUtils` 使用，确认是否提供 `ignoreProperties` 参数。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 明确使用 DTO + 手动赋值 | **L0（快速跳过）** | 不存在自动绑定 |
| 自动绑定但结合白名单/排除敏感字段 | **L2（跳读）** | 验证配置是否覆盖所有字段 |
| 直接 `copyProperties` / `save` 用户实体 | **L3（逐行读）** | 高风险 |
| 多租户/跨上下文批量更新 | **L4（跨模块追踪）** | 需验证租户/权限隔离 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **自动绑定或实体拷贝** 使用未经筛选的输入。
2. **输入可控**，可插入敏感字段。
3. **导致敏感状态被覆盖**（权限、金额、租户、审批状态等）。

#### 误报
可判定为误报的情形：
1. **使用读写分离注解**，敏感字段标记只读。
2. **控制器层显式剥离敏感字段**。
3. **接口仅对内部可信调用方开放且签名校验通过**。

#### 代码异味
需要关注的风险：
1. **黑名单过滤而非白名单**，易遗漏。
2. **DTO 与实体共享同一类**，未来改动易引入问题。
3. **全局 `ObjectMapper` 允许未知字段**，增加攻击面。
4. **测试用内置字段在生产环境仍可写**。

## Low risk

### 低风险评级场景

#### 1. 后台管理员接口
- **场景：** update 接口仅限高权限人员，附带 MFA。
- **风险评估：** 攻击面小，但需防账号被盗。

#### 2. DTO 与实体分离
- **场景：** 输入 DTO 不包含敏感字段，实体更新手动完成。
- **风险评估：** 风险较低，需确认无旁路。

#### 3. 数据库存储过程强制校验
- **场景：** 更新逻辑在存储过程中进行权限判断。
- **风险评估：** 可降低风险，但需验证逻辑不被绕过。

#### 4. 审计日志完善
- **场景：** 所有字段更新均记录审计并有告警。
- **风险评估：** 有助于检测异常，仍应修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员专用且强鉴权 | 攻击面有限 | 中 |
| DTO 手动赋值 + 白名单 | 技术防护完备 | 低 |
| 存储过程/触发器校验 | 数据层阻拦 | 中 |
| 完整审计告警 | 快速发现异常 | 高（继续改进）|

