# Java Jackson 批量赋值漏洞

## Details

### 漏洞成因
Jackson 是 Java 中常用的 JSON 序列化框架。若在对象反序列化时未使用 `@JsonIgnore`, `@JsonProperty(access = READ_ONLY)`, `@JsonView` 等注解限制可写字段，攻击者可通过 JSON 提交额外属性覆盖敏感字段（如 `admin`, `enabled`, `balance`, `roles`, `tenantId`）。开启 `MapperFeature.ACCEPT_CASE_INSENSITIVE_PROPERTIES`、`DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES = false` 等配置会扩大攻击面。此外，`ObjectMapper.convertValue`, `readValue` 与 `BeanUtils.copyProperties` 组合使用时，同样存在批量赋值风险。

### 代码示例

**易受攻击的代码：**
```java
@Data
public class UserDTO {
    private String username;
    private String email;
    private boolean admin; // 未加忽略注解
}

@PostMapping("/users")
public ResponseEntity<User> create(@RequestBody UserDTO dto) {
    // JSON 里 admin=true 将被直接映射
    User user = objectMapper.convertValue(dto, User.class);
    return ResponseEntity.ok(userService.save(user));
}
```

**另一个不安全示例（自定义 ObjectMapper）：**
```java
ObjectMapper mapper = new ObjectMapper()
        .configure(MapperFeature.ACCEPT_CASE_INSENSITIVE_PROPERTIES, true)
        .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

public void updateFromJson(String json, Account account) throws IOException {
    // JSON 可覆盖 creditLimit、status
    mapper.readerForUpdating(account).readValue(json);
    accountRepository.save(account);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `@JsonIgnore`, `@JsonProperty(access = JsonProperty.Access.READ_ONLY)`
- `ObjectMapper.readValue`, `convertValue`, `readerForUpdating`
- `FAIL_ON_UNKNOWN_PROPERTIES`, `ACCEPT_CASE_INSENSITIVE_PROPERTIES`
- Lombok `@Data`/`@Setter` 默认生成 setter

**定位步骤：**
1. 搜索 `ObjectMapper` 使用位置，查看配置。
2. 检查 DTO/实体是否对敏感字段施加只读限制。
3. 跳读（L2）了解反序列化结果如何用于更新数据库。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段只读控制：** `@JsonProperty(access = READ_ONLY)`, `@JsonIgnore`
- **视图控制：** `@JsonView` 限制不同场景可写字段。
- **自定义反序列化器：** 手动过滤敏感字段。
- **全局配置：** `FAIL_ON_UNKNOWN_PROPERTIES = true`、禁用大小写不敏感。
- **DTO 分离：** 输入 DTO 不包含敏感字段。

**定位技巧：**
- 确认 Lombok 生成的 setter 是否被禁止（`@Setter(AccessLevel.NONE)`）。
- 检查 `ObjectMapper` 是否注册了安全模块（如 `afterburner` 可能影响逻辑）。
- 对 `readerForUpdating` 等 API，确认是否针对敏感字段做了保护。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| DTO/实体使用只读注解 + 全局禁止未知字段 | **L0（快速跳过）** | 风险低 |
| 部分敏感字段保护到位 | **L2（跳读）** | 检查覆盖程度 |
| `convertValue`/`readerForUpdating` 直接使用 | **L3（逐行读）** | 高风险 |
| 自定义 ObjectMapper 广泛用于内部服务 | **L4（跨模块追踪）** | 需检查所有调用 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **Jackson 反序列化** 接受用户可控输入。
2. **敏感字段未标记只读/忽略**。
3. **反序列化结果用于更新/持久化敏感数据**。

#### 误报
可视为误报的情况：
1. 字段使用 `@JsonIgnore` 或只读访问。
2. JSON 在进入服务前被网关剥离敏感字段（并可验证不可绕过）。
3. 更新逻辑在持久化前重写敏感字段。

#### 代码异味
需记录的风险：
1. 依赖 `FAIL_ON_UNKNOWN_PROPERTIES = false`，允许额外字段。
2. 配置允许大小写不敏感，可能绕过字段名称限制。
3. DTO 与实体复用，后续新增字段易漏保护。
4. 使用 `MixIn` 动态修改序列化行为，理解难度大。

## Low risk

### 低风险评级场景

#### 1. 内部服务调用
- **场景：** JSON 仅在内部服务之间传递，且有签名。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. DTO 只暴露白名单字段
- **场景：** 输入 DTO 不包含敏感字段。
- **风险评估：** 风险较低，但需确保无旁路。

#### 3. 数据库层限制
- **场景：** 敏感列有触发器/权限控制。
- **风险评估：** 降低危害，但仍需修复代码。

#### 4. 审计日志
- **场景：** 对敏感字段更新有审计记录。
- **风险评估：** 有助于发现问题，非根治。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部调用 + 签名 | 攻击面小 | 中 |
| DTO 白名单 | 技术防护到位 | 低 |
| 数据库约束 | 阻止敏感修改 | 中 |
| 审计告警 | 及时发现异常 | 高（持续改进）|

