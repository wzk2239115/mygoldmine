# Go_Signed_Unsigned_Conversion

**漏洞类型**: 有符号/无符号转换，int 与 uint 之间的转换问题

**漏洞成因**

Go 中有符号整数向无符号类型转换时，负数会被解释为巨大的正数值。常见于：
- 有符号整数直接转换为无符号类型，用于内存分配、长度校验、数组索引
- 有符号值来自外部输入（用户、网络、JSON/protobuf），未验证就转换为无符号
- 比较操作中混用有符号和无符号整数导致的类型提升错误
- unsafe.Pointer 和 uintptr 之间的转换
- CGO 调用中 C 无符号类型与 Go 有符号类型的混用

---

## Details

### 代码示例

**危险模式1：负数转无符号导致缓冲区溢出**
```go
func processData(data []byte, len int) {
    size := uint(len)                 // 负数转无符号：-1 → 18446744073709551615
    buffer := make([]byte, 256)
    copy(buffer, data[:size])         // 远大于256的拷贝导致溢出
}

processData(userInput, -1)  // len 为 -1，转无符号后巨大
```

**危险模式2：有符号长度校验绕过**
```go
func readData(size int) {
    if size > 1000 {                  // 检查：size <= 1000
        return
    }
    usize := uint(size)               // -1 转无符号：巨数
    buf := make([]byte, usize)        // 分配超大内存导致 OOM/DoS
    io.ReadFull(reader, buf)
}

readData(-1)  // 通过有符号检查，但转无符号后变巨数
```

**危险模式3：数组索引越界**
```go
func getArrayElement(index int, array []int) int {
    idx := uint(index)                // -5 转无符号：18446744073709551611
    if idx < uint(len(array)) {       // 无符号比较：条件可能被绕过
        return array[idx]             // 越界访问
    }
    return -1
}

getArrayElement(-5, arr)  // idx 为巨数，可能绕过边界检查
```

**危险模式4：unsafe.Pointer 与 uintptr 的转换**
```go
func unsafeMemCopy(src unsafe.Pointer, offset int) {
    ptr := uintptr(src) + uintptr(offset)  // offset 为 -1：ptr 减 1
    if offset < 0 {                         // 检查可能被上面的运算绕过
        dst := (*byte)(unsafe.Pointer(ptr))
        process(dst)
    }
}

unsafeMemCopy(ptr, -100)  // 负偏移导致指针计算错误
```

**危险模式5：JSON 反序列化的有符号到无符号**
```go
type Request struct {
    Count int `json:"count"`
}

func handleRequest(data []byte) {
    var req Request
    json.Unmarshal(data, &req)
    size := uint(req.Count)           // JSON 中负数 → 巨大无符号
    buf := make([]byte, size)         // OOM
}

// JSON: {"count": -1}
```

**危险模式6：slice 操作中的有符号长度**
```go
func sliceSubset(start, end int, data []byte) []byte {
    ustart := uint(start)
    uend := uint(end)
    if ustart < uend && uend <= uint(len(data)) {  // -1 < 0 为真
        return data[ustart:uend]       // 实际是 data[巨数:0]
    }
}

sliceSubset(-1, 10, data)
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]:**
- 有符号转无符号：`uint(signed)`, `uint32(s)`, `uint64(s)`, `uintptr(s)`
- 反向转换：`int(unsigned)`, `int32(u)`, `int64(u)`
- 有符号值用于：`make()` 的 len/cap，`unsafe.Pointer` 运算，数组索引，slice 操作
- 有符号值来源：JSON/protobuf 字段，函数参数，用户输入，外部库返回值
- 混合有符号无符号的比较操作：`if s < u`, `if s > u`
- unsafe 包的指针运算：`uintptr() + int`, `uintptr() - int`

**快速定位保护机制 [L2-L3]:**
- 有符号转无符号前是否验证非负：`if s >= 0`
- 是否在转换后再验证范围：`if u <= MAX_ALLOWED`
- slice 索引操作是否先检查边界：`if start >= 0 && start < len()`
- JSON/protobuf 字段类型是否声明为无符号（`uint`, `uint32`）而非有符号
- unsafe 指针运算是否使用有符号偏移：应该使用 `unsafe.Add()` 而非 `+ uintptr(int)`
- 是否启用 `go vet` 或 `golangci-lint` 的符号转换检查

---

## Classify

**研判为真漏洞的特征：**
1. 有符号值直接转无符号，未验证非负，用于关键操作（内存分配、长度、索引、指针运算）
2. 有符号值来源于外部输入（JSON、protobuf、网络、用户参数），可能为负数
3. 转换后的无符号值被用于内存操作、slice 访问、数组索引等敏感位置
4. 存在有符号无符号混合比较，依赖隐式类型提升，可绕过安全检查
5. 负数转无符号后的巨数会导致内存分配失败、缓冲区溢出或逻辑错误

**误报/代码异味的特征：**
- 有符号值来自内部计算，范围已被逻辑保证为非负（如循环计数器）
- 转换前显式验证了非负条件：`if v >= 0 { u := uint(v) }`
- 有符号值的负数情况已在上游被过滤或明确处理
- 同向转换（有符号→无符号）且后续有范围再验证
- 启用 `go vet` 无相关警告

---

## Low risk

**以下场景可评为低风险：**

1. **完整的非负性验证**
   - 有符号值在转换前显式检查：`if v >= 0 { u := uint(v) }`
   - 或转换后再验证范围：`u := uint(v); if u <= MAX_SIZE { use(u) }`
   - 负数情况已被明确处理或断言

2. **内部受控的有符号值**
   - 有符号值来自内部逻辑计算（如循环计数 `i := 0; i < len`），确保非负
   - 范围已在代码逻辑上限制，不依赖外部数据
   - 如：`idx := i` 其中 i 来自 for 循环，Go 保证非负

3. **正确的类型设计**
   - JSON/protobuf 结构体字段直接定义为无符号类型：`Count uint \`json:"count"\``
   - slice/array 操作使用无符号索引变量

4. **非关键路径的转换**
   - 有符号转无符号仅用于计数、统计、日志等非敏感操作
   - 不影响内存分配、指针运算、索引访问

5. **编译器/静态分析保护启用**
   - `go vet` 无符号转换相关警告
   - `golangci-lint` 中 `gosec` 无警告

