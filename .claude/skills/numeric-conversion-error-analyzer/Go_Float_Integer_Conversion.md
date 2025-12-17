# Go_Float_Integer_Conversion

**漏洞类型**: 浮点与整型转换，float32/float64 与整数类型之间的转换

**漏洞成因**

Go 中浮点与整型转换时，会产生精度丢失、截断、溢出等问题。常见于：
- 浮点数直接强制转整，忽略小数部分
- 浮点数用于内存分配大小、数组索引、时间计算等关键场景
- 浮点数表示范围超出整型可表示范围时的溢出处理
- NaN、Inf 等特殊值的转换未加校验
- 外部数据（JSON、protobuf）中的浮点值直接转整用于敏感操作

---

## Details

### 代码示例

**危险模式1：浮点直接转整作为内存分配大小**
```go
func allocateBuffer(size float64) {
    bufSize := int(size)          // 精度丢失：3.9 → 3
    buffer := make([]byte, bufSize)
    copy(buffer, data[:100])       // 实际需要100字节，但只分配3字节
}

allocateBuffer(3.9)  // 溢出
```

**危险模式2：浮点超出整型范围**
```go
func processCoordinate(x float64) {
    coord := int(x)               // x > math.MaxInt64 时行为未定义
    array := make([]int, 256)
    array[coord] = value          // 溢出或范围错误
}

processCoordinate(1e20)  // 远超 math.MaxInt64
```

**危险模式3：浮点用于数组索引**
```go
func getTableValue(index float64, table []int) int {
    return table[int(index)]      // 负数浮点转整后符号错误
}

getTableValue(-1.5, table)
```

**危险模式4：NaN/Inf 转整型未检查**
```go
func handleMeasurement(value float64) {
    if value > 0 {
        size := int(value)         // NaN 或 Inf 转换结果 0 或环绕
        buffer := make([]byte, size)
        process(buffer)
    }
}

handleMeasurement(math.NaN())   // 危险
handleMeasurement(math.Inf(1))  // 危险
```

**危险模式5：JSON 反序列化的浮点转整**
```go
type Config struct {
    Timeout float64 `json:"timeout"`  // JSON 中浮点可能超出整数范围
    Limit   float64 `json:"limit"`
}

func handleConfig(cfg Config) {
    timeoutMs := int64(cfg.Timeout * 1000)  // 精度丢失+溢出
    if timeoutMs > 0 {
        http.TimeoutHandler(mux, time.Duration(timeoutMs)*time.Millisecond, msg)
    }
}

// JSON: {"timeout": 9223372036854775.8, ...}  超过 int64 范围
```

**危险模式6：浮点用于循环计数**
```go
func iterate(count float64) {
    for i := 0; i < int(count); i++ {  // count=1.9 → 1，循环次数错误
        process(i)
    }
}

iterate(100.1)  // 实际执行100次，不是101次
```

**危险模式7：浮点精度丢失导致权限判断错误**
```go
func checkPermission(level float64) bool {
    permLevel := int(level)        // 3.9 → 3
    return permLevel >= 4           // 本应拒绝，精度丢失后通过
}

checkPermission(3.9)  // 应该为4才允许，但截断为3
```

**危险模式8：Protobuf 浮点字段的精度问题**
```go
type Request struct {
    Amount float32 `protobuf:"bytes,1,opt,name=amount"`  // 32位精度
    UserID int64   `protobuf:"varint,2,opt,name=user_id"`
}

func processRequest(req *Request) {
    amountCents := int64(req.Amount * 100)  // 精度丢失：1.005 → 100 而非 100.5
    charge(amountCents)
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]:**
- 浮点到整型的显式转换：`int(float_var)`, `int32(float_var)`, `int64(float_var)`
- 浮点到无符号整型：`uint(f)`, `uint32(f)`, `uintptr(f)`
- 浮点变量用于：`make()` 的 len/cap 参数，数组索引，时间计算 (`time.Duration`)
- JSON/Protobuf 反序列化中的 float 字段立即转整
- 浮点运算结果（`+`, `*`, `/`）直接转整
- 浮点值来源：用户输入、API 返回、计算结果、外部数据

**快速定位保护机制 [L2-L3]:**
- 转换前是否检查特殊值：`math.IsNaN()`, `math.IsInf()`, `math.IsFinite()`
- 是否验证浮点值在目标整型范围内：`if f >= float64(math.MinInt64) && f <= float64(math.MaxInt64)`
- 是否使用安全转换方法（如四舍五入后转换）：`int64(math.Round(f))`
- 浮点精度是否满足实际需求（float32 vs float64）
- JSON/Protobuf 字段类型是否选择正确（float32 精度不足时是否用 float64）
- 转换结果是否在后续操作前再次验证范围
- `go vet` 或 linter 是否标记相关警告

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接强制转整，无任何边界或合法性检查，用于关键操作（内存分配、索引、时间、金额）
2. 浮点值来源于外部输入（JSON、protobuf、网络、API）且转换后值无再验证
3. 浮点可能是 NaN/Inf，转换时无检查导致溢出或 0 值
4. 浮点计算中可能发生精度丢失或舍入误差，且该误差被用于安全/业务决策
5. 浮点值可能超出目标整型范围（如 float64 的 1e20 → int64），转换后发生溢出或回绕
6. float32 精度不足（仅 6-7 位有效数字）但被用于金额、权限等高精度场景

**误报/代码异味的特征：**
- 浮点值来源于内部受控计算，其范围已确保在目标整型范围内
- 转换前明确验证了范围和有效性：`if math.IsFinite(f) && f >= min && f <= max`
- 转换仅用于显示、日志、缓存键等非关键操作
- 使用 `strconv.ParseFloat` 后再进行范围验证
- 浮点精度已被代码设计所考虑（使用 float64 满足精度需求、或显式四舍五入）
- 已启用 Go 的静态分析工具（`go vet`、`golangci-lint` 等）无相关告警

---

## Low risk

**以下场景可评为低风险：**

1. **完整的有效性检查**
   - 转换前显式检查特殊值和范围：`if !math.IsFinite(f) { error } if f >= min && f <= max { i64 := int64(f) }`
   - 浮点值范围已验证在目标整型类型的可表示范围内
   - 负数情况已被明确处理

2. **内部计算的浮点值**
   - 浮点来自内部算法（非外部输入），其范围已在代码逻辑上限制
   - 如：`angle := math.Atan2(y, x)` 范围固定在 [-π, π]，转整为 [0, 359] 不会溢出
   - 错误后果不影响安全决策

3. **使用安全转换方法**
   - 采用 `math.Round()` 或 `math.Ceil()` 等库函数处理精度，转换后再验证
   - 或使用 `big.Float` 处理高精度需求，转换前验证范围

4. **非关键路径的浮点转整**
   - 浮点转整仅用于统计、计数、显示、日志、缓存键等非安全决策的场景
   - 不影响内存分配、数组访问、权限检查、金额计算等敏感操作

5. **正确的数据类型设计**
   - JSON/Protobuf 中使用了足够大的整数类型（int64 而非 int32）而非浮点
   - 或明确使用字符串/十进制类型（Decimal）处理金额，转换时已验证

6. **受控的浮点精度**
   - float32 和 float64 的精度差异已被充分理解和处理
   - 场景中所有浮点值源头和精度需求已文档化

