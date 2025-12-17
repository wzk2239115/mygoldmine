# Go 批量赋值漏洞

## Details

### 漏洞成因
Go Web 框架（Gin、Echo、Fiber、Beego 等）常通过 `ShouldBind`、`BindJSON`、`Context.Bind` 或标准库 `json.Unmarshal` 将请求体映射到结构体。当结构体包含敏感字段（如 `Role`, `OwnerID`, `Price`, `Status`）且未使用 `json:"-"` 或自定义标签过滤时，攻击者可以提交额外字段覆盖这些值。ORM（GORM、xorm、bun）在执行 `Updates`, `Save`, `Create` 时，若直接使用 `map[string]interface{}` 或结构体指针，也可能触发批量赋值漏洞。

### 代码示例

**易受攻击的代码：**
```go
type User struct {
    ID        uint
    Email     string `json:"email"`
    Password  string `json:"password"`
    Role      string `json:"role"` // 未做保护，可被修改为 admin
    Active    bool   `json:"active"`
}

func updateUser(c *gin.Context) {
    var payload User
    if err := c.ShouldBindJSON(&payload); err != nil {
        c.AbortWithStatus(http.StatusBadRequest)
        return
    }
    db.Model(&User{}).Where("id = ?", c.Param("id")).Updates(&payload)
}
```

**另一个不安全示例（GORM map 更新）：**
```go
func updateOrder(c *gin.Context) {
    var data map[string]interface{}
    if err := c.ShouldBindJSON(&data); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    // data 可包含 tenant_id、is_paid 等敏感字段
    db.Model(&Order{}).Where("id = ?", c.Param("id")).Updates(data)
    c.JSON(http.StatusOK, gin.H{"ok": true})
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 框架绑定：`ShouldBind`, `BindJSON`, `Bind`, `Decode`, `json.Unmarshal`
- ORM 更新：`Updates`, `Save`, `UpdateColumns`, `map[string]interface{}`
- 结构体标签：`json:"-"`, `binding:"required"`, `form:""`
- 自定义解码器：`mapstructure.Decode`, `yaml.Unmarshal`

**定位步骤：**
1. 搜索控制器/handler 中的绑定函数，查看目标结构体定义。
2. 检查结构体是否包含角色、权限、金额、租户等敏感字段。
3. 跳读（L2）确认是否有 `json:"-"`、单独赋值或字段过滤逻辑。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段白名单：** 自定义 DTO，仅暴露可写字段。
- **忽略敏感字段：** 使用 `json:"-"`, `binding:"-"` 或自定义 tag。
- **手动映射：** `allowed := struct { ... }{}`，逐个字段赋值。
- **权限校验：** 更新前校验当前用户是否允许修改目标字段。
- **GORM 配置：** 使用 `Select` 指定字段或 `Omit` 忽略敏感字段。

**定位技巧：**
- 确认使用 `mapstructure` 或 `yaml` 时是否启用 `WeaklyTypedInput`（易被绕过）。
- 检查 `Updates` 是否搭配 `Select`/`Omit` 使用。
- 对 `struct` 更新，注意零值字段是否会被忽略（`Updates` 默认忽略零值，需要 `map[string]interface{}` 才写入）。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| DTO 分离 + 手动赋值 | **L0（快速跳过）** | 无自动映射风险 |
| 使用绑定但敏感字段 `json:"-"` | **L2（跳读）** | 确认敏感字段完整 |
| 直接绑定结构体并执行 `Updates` | **L3（逐行读）** | 高风险 |
| 多租户/批量更新逻辑 | **L4（跨模块追踪）** | 需确认租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件判定为漏洞：
1. **自动绑定或 `Updates`** 使用未经筛选的输入。
2. **敏感字段可被外部控制**。
3. **导致权限、租户、金额等关键字段被篡改**。

#### 误报
可视为误报的情况：
1. **结构体敏感字段标记 `json:"-"`**，无法通过请求覆盖。
2. **更新操作使用 `Select` 指定白名单字段**。
3. **接口仅供受信任内部服务调用并有签名验证**。

#### 代码异味
需关注的模式：
1. **使用 `map[string]interface{}` 更新**，后续维护易遗漏敏感字段。
2. **通过反射遍历字段赋值**，缺乏白名单。
3. **混用绑定结构体与原始 `map` 数据**，导致逻辑复杂。
4. **自定义解码器允许未知字段**，无告警。

## Low risk

### 低风险评级场景

#### 1. 内部服务接口
- **场景：** 仅对内部网段或鉴权服务开放。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. DTO 与模型完全解耦
- **场景：** 输入 DTO 不包含敏感字段，保存时手动赋值。
- **风险评估：** 风险较低，但需持续维护。

#### 3. 数据库约束/触发器
- **场景：** 触发器阻止特定字段被直接修改。
- **风险评估：** 降低危害，但仍需代码层控制。

#### 4. 审计日志与告警
- **场景：** 对关键字段修改进行日志记录与告警。
- **风险评估：** 有助于监测，但不能替代修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 + 强鉴权 | 攻击面小 | 中 |
| DTO 手动赋值 | 技术防护到位 | 低 |
| 数据库约束 | 阻止关键字段修改 | 中 |
| 审计告警 | 及时发现问题 | 高（仍需修复）|

