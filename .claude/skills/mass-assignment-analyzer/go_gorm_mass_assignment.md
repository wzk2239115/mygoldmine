# Go GORM 批量赋值漏洞

## Details

### 漏洞成因
使用 GORM 操作数据库时，常见的更新方式包括 `Updates`, `Save`, `Create`、`Model(&obj).Updates(map[string]interface{}{})`。如果这些操作直接接受客户端传入的结构体或 `map`，且未使用 `Select`/`Omit` 指定字段，攻击者可覆盖 `role`, `tenant_id`, `price`, `status`, `is_admin` 等敏感列。此外，GORM 对 `map` 会忽略零值判断，更容易写入恶意字段；`Updates` 默认允许更新所有列，除非明确排除。

### 代码示例

**易受攻击的代码：**
```go
func updateProfile(c *gin.Context) {
    var user User
    if err := c.ShouldBindJSON(&user); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    // 直接保存，payload 可包含 Role="admin"
    if err := db.Save(&user).Error; err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    c.JSON(http.StatusOK, user)
}
```

**另一个不安全示例（map 更新）：**
```go
func partialUpdate(c *gin.Context) {
    id := c.Param("id")
    var payload map[string]interface{}
    if err := c.ShouldBindJSON(&payload); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    // payload 可覆盖 tenant_id、is_paid 等字段
    db.Model(&Order{}).Where("id = ?", id).Updates(payload)
    c.JSON(http.StatusOK, gin.H{"ok": true})
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- `db.Save`, `db.Updates`, `db.UpdateColumns`, `db.Create`, `Assign`
- `map[string]interface{}`, `gin.H`, `request.Body`
- `Omit`, `Select`, `Scopes`, `UpdateColumn`
- 模型字段标签：`gorm:"-"`, `json:"-"`, `serializer:""`

**定位步骤：**
1. 搜索所有 GORM 更新调用，检查参数来源。
2. 关注结构体中 `Role`, `Status`, `OwnerID`, `Balance` 等字段。
3. 跳读（L2）确认是否存在 `Select`/`Omit` 或敏感字段过滤。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段白名单：** 使用 `Select("name", "email")` 指定可更新字段。
- **字段黑名单（需谨慎）：** `Omit("role", "tenant_id")`（注意新增字段）。
- **模型配置：** `gorm:"-"` 禁止 GORM 写入。
- **权限校验：** 更新前验证当前用户是否允许修改目标字段。
- **事务检查：** 在事务中重写敏感字段或校验租户信息。

**定位技巧：**
- 检查 `BeforeUpdate`/`BeforeSave` 钩子是否重置敏感字段。
- 确认 `Save` 是否用于非主键更新（可能在无意中创建新记录）。
- 对批量操作 (`Updates` with struct slice) 核查同样逻辑。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| `Select` 指定可更新字段 + 权限校验 | **L0（快速跳过）** | 风险低 |
| `Omit` 忽略敏感字段 + DTO 分离 | **L2（跳读）** | 验证覆盖范围 |
| `Save`/`Updates` 直接使用用户实体 | **L3（逐行读）** | 高风险 |
| 多租户/跨域批量更新 | **L4（跨模块追踪）** | 需检查租户隔离 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件可认定为漏洞：
1. **GORM 更新操作** 直接使用来自请求的结构体或 map。
2. **敏感字段未受保护**。
3. **实际可篡改权限、租户、金额等关键字段**。

#### 误报
以下情况可视为误报：
1. `Select`/`Omit` 覆盖所有敏感字段且经过测试验证。
2. 模型字段标记 `gorm:"-"` 或仅通过自定义 Setter 修改。
3. 更新接口仅供可信服务调用并附带签名。

#### 代码异味
需记录的风险：
1. 依赖黑名单 `Omit`，易遗漏新增字段。
2. 在 `Save` 前修改结构体默认值，未来更改可能引发漏洞。
3. 使用 `map[string]interface{}` 合并更新，难以维护。
4. 未开启 `FullSaveAssociations` 但结构体内嵌敏感关联。

## Low risk

### 低风险评级场景

#### 1. DTO 仅包含非敏感字段
- **场景：** 控制层将 DTO 映射到实体时手动指定字段。
- **风险评估：** 风险较低，但需防新字段加入。

#### 2. 数据库层触发器限制
- **场景：** 对敏感列设置触发器/约束拒绝修改。
- **风险评估：** 降低危害，但仍需代码层控制。

#### 3. 内部服务调用
- **场景：** 接口仅对可信后端服务开放。
- **风险评估：** 攻击面有限，但注意凭证泄露。

#### 4. 审计日志完整
- **场景：** 对敏感字段修改实现审计与告警。
- **风险评估：** 有助于检测异常，但不替代修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| DTO 白名单 | 技术防护到位 | 低 |
| 数据库触发器 | 阻断敏感修改 | 中 |
| 内部调用 + 签名 | 攻击面较小 | 中 |
| 审计告警 | 快速发现问题 | 高（持续改进）|

