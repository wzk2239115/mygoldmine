# Go 反射批量赋值漏洞

## Details

### 漏洞成因
在一些 Go 项目中，会通过反射（`reflect` 包）、`mapstructure`、`copier`、`mergo` 等库实现结构体与 `map`/JSON 之间的自动转换。如果转换逻辑未限制字段列表，攻击者可构造 payload 包含敏感字段（如 `IsAdmin`, `OwnerID`, `Credit`, `State`），通过反射赋值覆盖结构体字段。反射操作通常出现在通用配置加载、插件系统、动态表单处理、多语言数据同步等场景，易被忽略。

### 代码示例

**易受攻击的代码：**
```go
func hydrate(dst interface{}, data map[string]interface{}) error {
    v := reflect.ValueOf(dst).Elem()
    for key, val := range data {
        field := v.FieldByName(key) // 未校验 key
        if field.IsValid() && field.CanSet() {
            field.Set(reflect.ValueOf(val).Convert(field.Type()))
        }
    }
    return nil
}

func updateUser(c *gin.Context) {
    var payload map[string]interface{}
    c.ShouldBindJSON(&payload)
    user := &User{}
    hydrate(user, payload) // payload 可含 IsAdmin=true
    db.Save(user)
}
```

**另一个不安全示例（mapstructure）：**
```go
type Config struct {
    Name        string
    MaxWorkers  int
    EnableDebug bool
    AdminToken  string
}

func loadConfig(data map[string]interface{}) (*Config, error) {
    cfg := &Config{}
    decoder, _ := mapstructure.NewDecoder(&mapstructure.DecoderConfig{
        Result:           cfg,
        TagName:          "json",
        WeaklyTypedInput: true,
    })
    decoder.Decode(data) // 未限制字段，AdminToken 可被覆盖
    return cfg, nil
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 反射 API：`reflect.ValueOf`, `FieldByName`, `Set`, `SetString`
- 映射库：`mapstructure`, `mergo.Map`, `copier.Copy`, `structs.New`
- 动态表单/配置函数：`hydrate`, `bind`, `Assign`, `Populate`
- 结构体包含敏感字段：`IsAdmin`, `Role`, `TenantID`, `Secret`

**定位步骤：**
1. 搜索反射赋值函数或第三方库调用。
2. 查看传入的 `map`/JSON 是否来自用户输入。
3. 跳读（L2）确认是否存在字段白名单或敏感字段过滤。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段白名单：** 仅允许特定字段映射（`allowed := map[string]bool{...}`）。
- **敏感字段忽略：** 使用标签 `json:"-"`、自定义 `filter`。
- **特权校验：** 设置敏感字段前检查调用者权限。
- **`mapstructure` 配置：** `IgnoreUntaggedFields`, `TagName`, `MatchName`.
- **结构体分离：** 使用 DTO/视图模型避免包含敏感字段。

**定位技巧：**
- 检查是否启用了 `WeaklyTypedInput`（可能被利用绕过类型检查）。
- 确认 `FieldByName` 查找结果是否区分大小写，防止绕过。
- 追踪通用函数调用处，理解可能的用户输入来源。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 反射赋值前执行白名单校验 | **L0（快速跳过）** | 安全控制充分 |
| 使用标签忽略敏感字段 | **L2（跳读）** | 确认覆盖所有字段 |
| `FieldByName`/`mapstructure` 直接赋值 | **L3（逐行读）** | 高风险 |
| 广泛用于配置/插件/多租户同步 | **L4（跨模块追踪）** | 需分析全链路 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **反射或映射库** 直接使用外部输入。
2. **缺乏字段白名单/过滤**。
3. **敏感字段可被覆盖** 并导致越权、资金篡改等影响。

#### 误报
可视为误报的情况：
1. 映射只针对受控字段，其他字段忽略/报错。
2. 调用者为可信服务，且数据签名不可伪造。
3. 更新后业务逻辑会重写敏感字段（例如从 session 获取）。

#### 代码异味
需关注的风险：
1. 依赖黑名单过滤敏感字段。
2. 使用 `WeaklyTypedInput` 导致类型转换绕过。
3. 程序通过反射处理嵌套结构体，易遗漏深层字段。
4. 没有错误处理，字段无法设置时静默失败。

## Low risk

### 低风险评级场景

#### 1. 内部工具仅供管理员使用
- **场景：** 反射赋值只在内部运维工具生效。
- **风险评估：** 攻击面有限，但需防内部滥用。

#### 2. DTO 分离敏感字段
- **场景：** 输入数据映射到只读 DTO，再由业务层手动拷贝必要字段。
- **风险评估：** 风险较低，需要保持一致。

#### 3. 数据签名校验
- **场景：** 配置数据在写入前通过签名验证。
- **风险评估：** 可降低风险，但需确保签名不可伪造。

#### 4. 审计日志
- **场景：** 对敏感字段变更记录审计并报警。
- **风险评估：** 有助于发现问题，但不替代修复。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部使用 + 权限控制 | 攻击面小 | 中 |
| DTO 白名单映射 | 技术防护完善 | 低 |
| 签名校验 | 防止篡改 | 中 |
| 审计告警 | 提升可见性 | 高（持续改进）|

