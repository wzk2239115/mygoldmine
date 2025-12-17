# Go_Different_Width_Conversion

**漏洞类型**: 不同位宽转换，int8/int16/int32/int64 之间的转换，uint8/uint16/uint32/uint64 之间的转换，导致的值截断、溢出、符号扩展错误

**漏洞成因**

Go 中不同位宽的整数类型之间转换时，高位数据会被丢弃或符号扩展。常见于：
- int64 向 int32/int16/int8 转换导致高位截断
- uint64 向 uint32/uint16/uint8 转换导致高位丢失
- 有符号向无符号或反向转换，符号位被误解
- Protocol Buffer、JSON 等外部数据解析时的位宽不匹配
- 网络字节序转换与位宽转换混用
- unsafe 指针操作中的类型转换
- 系统调用返回值与 Go 类型的位宽差异

---

## Details

### 代码示例

**危险模式1：int64 转 int32 导致高位截断**
```go
func processID(id int64) {
    id32 := int32(id)              // id > INT32_MAX 时高位被截断
    if id32 > 0 {                  // 原本大正数被截断为负数
        database.Write(id32)        // 存储错误的ID
    }
}

processID(int64(3000000000))  // 3000000000 > INT32_MAX(2147483647)
// int32(3000000000) = -1294967296，触发条件判断错误
```

**危险模式2：uint64 转 uint32 丢失高位**
```go
func readMemorySize(sizeBytes uint64) {
    size32 := uint32(sizeBytes)     // 高32位被丢弃
    buffer := make([]byte, size32)  // 分配错误的大小

    // 如果 sizeBytes = 0x100000000（4GB+1），size32 = 1
    // 实际需要4GB，但只分配1字节
}

readMemorySize(1 << 32)  // 4GB 被截断为 0
```

**危险模式3：从JSON解析时的位宽不匹配**
```go
type Config struct {
    Timeout int32 `json:"timeout"`    // 32位字段
    Limit   int32 `json:"limit"`
}

func handleConfig(cfg Config) {
    timeout := time.Duration(cfg.Timeout) * time.Second
    // JSON中 timeout=10000000000（超过INT32_MAX=2147483647）
    // 被截断为负数，导致立即超时
}

json.Unmarshal([]byte(`{"timeout":10000000000}`), &cfg)
// cfg.Timeout = -1294967296，调整为纳秒级的负值导致panic或立即返回
```

**危险模式4：有符号与无符号混合导致符号转换错误**
```go
func validateSize(size int32) {
    usize := uint32(size)           // -1 转无符号：4294967295
    if usize > 1000000 {            // 条件判断被绕过
        return errors.New("too large")
    }
    buffer := make([]byte, usize)   // 分配超大内存
}

validateSize(-1)  // -1 → 4294967295，绕过验证
```

**危险模式5：unsafe.Pointer 与 uintptr 的位宽转换**
```go
func accessMemory(ptr unsafe.Pointer, offset int32) {
    addr := uintptr(ptr) + uintptr(offset)  // offset 为负数时
    // 负数转 uintptr 后成为巨大正数（平台依赖）

    newPtr := unsafe.Pointer(addr)
    val := *((*int)(newPtr))  // 野指针访问
}

accessMemory(basePtr, -1)  // 指针减一位置未定义行为
```

**危险模式6：Protocol Buffer 整数字段的位宽问题**
```go
// .proto 文件
// message Data {
//     int32 value = 1;    // 32位有符号
// }

func processProtoData(data *pb.Data) {
    // 外部数据包含 int32 可表示范围外的值
    // protobuf 编码时会产生负数或截断

    val64 := int64(data.Value)      // int32 → int64：符号扩展
    if data.Value > 1000000000 {    // value 已被截断，判断失效
        // ...
    }
}
```

**危险模式7：位宽转换导致的循环控制错误**
```go
func iterate(count int16) {
    for i := int32(count); i < 100000; i++ {  // count 符号扩展后可能异常
        process(i)
    }
}

iterate(int16(-1))  // int32(-1) → 0xFFFFFFFF，循环执行 2^32 - 100000 次
```

**危险模式8：网络字节序转换与位宽混用**
```go
func parsePort(data []byte) uint16 {
    val := uint32(binary.BigEndian.Uint32(data[:4]))  // 读取32位但需要16位
    port := uint16(val)                                 // 高16位被丢弃
    return port  // 端口号错误
}

// 若数据中 port 号在高16位，会被截断
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- 位宽转换模式：`int32(var)`, `uint16(var)`, `int8(var)` 等，其中 var 来自更宽类型
- 不同大小整数类型的直接赋值或比较
- Protocol Buffer 或 JSON 反序列化后立即使用小位宽类型
- 外部数据（网络包、文件、系统调用）的位宽转换
- unsafe 操作中涉及 uintptr 的类型转换
- 计算结果为大数值后被转换为小位宽类型
- 有符号和无符号类型的混合转换
- 跨包调用时参数位宽不匹配（int vs int32）

**快速定位保护机制 [L2-L3]**
- 转换前是否检查源值在目标位宽范围内
  - 有符号类型：`if val >= typeMin && val <= typeMax`
  - 无符号类型：`if val >= 0 && val <= typeMax`
- 是否使用特殊数据类型库（如 `math` 包常数）进行范围验证
- Protocol Buffer 字段定义是否使用了较大位宽（int64 替代 int32）
- JSON 反序列化是否使用了精确的数据类型绑定
- unsafe 操作是否限制在 platform 支持的指针宽度内
- 编译器标志是否启用了溢出检查（Go 本身不提供，但可用 `go vet` 或 linters）

---

## Classify

**研判为真漏洞的特征：**
1. 外部输入（JSON、protobuf、网络、文件）的大整数直接转为小位宽，无范围验证
2. 位宽转换后用于关键操作：内存分配、数组索引、数据库 ID、时间计算等
3. 有符号和无符号混合转换，特别是负数隐式转为无符号时
4. 计算结果可能超出目标位宽，但转换时无溢出处理
5. unsafe 指针算术中的有符号负数被转为 uintptr，导致指针运算错误
6. Protocol Buffer 或 JSON 中定义过小的字段类型（int32 而实际需要 int64）

**误报/代码异味的特征：**
- 位宽转换用于内部逻辑计算，源值已被上游代码限制在目标范围内
- 转换前有明确的范围检查：`if val <= math.MaxInt32 && val >= math.MinInt32 { i32 := int32(val) }`
- 转换仅用于显示、日志或非安全决策的场景
- 使用 `strconv.ParseInt` 或 `json.Number` 等安全解析函数，转换前再验证
- Protocol Buffer 代码生成自动处理，字段类型设计正确
- 位宽转换在明确受控的循环或条件分支内

---

## Low risk

**以下场景可评为低风险：**

1. **完整的位宽范围验证**
   - 转换前显式检查源值在目标范围内
   - 如：`if val >= math.MinInt32 && val <= math.MaxInt32 { i32 := int32(val) }`
   - 对无符号类型：`if val >= 0 && val <= math.MaxUint32`
   - 负数情况已明确处理（返回错误或使用默认值）

2. **内部受控的位宽转换**
   - 源值来自内部计算（如循环计数、内部算法），范围已确保不超过目标位宽
   - 例：`var idx int32 = int32(loopCounter % (1 << 32))`，其中 loopCounter 已限制
   - 来自 `len()`、`cap()` 等内置函数的值（Go 中返回 int，平台依赖但有隐含限制）

3. **使用安全解析函数**
   - 使用 `strconv.ParseInt(str, 10, 32)` 等限定位宽的函数，返回值直接类型安全
   - 或使用 `json.Number.Int64()` 后再转换，转换前验证范围

4. **正确的 Protocol Buffer 或 JSON 设计**
   - 字段类型与实际数据范围匹配（需要大数则用 int64 而非 int32）
   - 反序列化库已进行类型检查，转换后的值符合预期
   - 使用 `protojson.UnmarshalOptions` 的严格模式

5. **非关键路径的位宽转换**
   - 转换仅用于统计、计数、缓存键等非安全决策的场景
   - 不影响内存分配、指针操作、索引访问或权限决策

6. **显式的 unsafe 指针管理**
   - unsafe 操作已被明确注释和隔离
   - 指针算术严格限制在已申请的内存范围内
   - 使用 `cgo` 时按照 Go 和 C 的类型映射规范转换
