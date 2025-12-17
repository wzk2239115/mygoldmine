# Go_Array_Index_Conversion

**漏洞类型**: 数组索引转换，数组和切片索引中的类型转换问题

**漏洞成因**

Go 中数组和切片的索引必须为非负整数。当从外部输入或类型转换中获取索引值时，若处理不当会导致：
- 有符号整数（可能为负）隐式或显式转换为无符号，被误解为巨大正数
- 不同位宽的整数类型转换导致截断或溢出
- 整数计算溢出导致索引值异常
- unsafe.Pointer 与 uintptr 转换的指针越界访问
- 从外部数据（JSON、Protocol Buffer 等）解析索引值未验证

---

## Details

### 代码示例

**危险模式1：有符号整数直接作为切片索引**
```go
func getElement(index int, data []int) int {
    return data[index]  // index 为负数时panic
}

userIdx := readUserInput()  // 用户可能输入负数
result := getElement(userIdx, mySlice)
```

**危险模式2：有符号到无符号的隐式转换**
```go
func processSlice(offset int, data []byte) {
    end := int(len(data)) + offset  // offset 为负数导致 end 可能为负
    slice := data[:end]              // 负数索引被转为无符号后越界
}

processSlice(-10, largeSlice)
```

**危险模式3：从JSON解析索引值未验证**
```go
type Request struct {
    Index int64 `json:"index"`
}

func handleRequest(req Request, items []string) string {
    return items[req.Index]  // req.Index 可能为负数、超大数或负数溢出
}

json.Unmarshal([]byte(`{"index":-1}`), &req)
```

**危险模式4：unsafe.Pointer 与 uintptr 混用**
```go
func accessArray(base unsafe.Pointer, offset int) int {
    addr := uintptr(base) + uintptr(offset)  // offset 为负数被转为巨大无符号数
    ptr := unsafe.Pointer(addr)
    return *((*int)(ptr))  // 未检查指针有效性
}

accessArray(ptr, -1)
```

**危险模式5：不同位宽整数的类型转换**
```go
func iterateArray(count int16, array [1000]byte) {
    for i := int(count); i < len(array); i++ {  // count 溢出被截断
        process(array[i])
    }
}

iterateArray(-1, arr)  // int16(-1) 转 int，可能导致循环异常
```

**危险模式6：Protocol Buffer 字段作为索引**
```go
message ProtoReq {
    int32 index = 1;  // 有符号32位整数
}

func useProtoIndex(idx int32, data []int) int {
    return data[idx]  // int32 直接用作索引，可能为负
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `slice[` 或 `array[` 后跟有符号整数变量（`int`, `int64`, `int32`, `int16`, `int8`）
- 直接赋值/转换：`idx := readInput()` 随后 `data[idx]` 或 `data[:idx]`
- 来自 JSON/Protocol Buffer 的整数字段用作索引
- `unsafe.Pointer` 与 `uintptr` 的指针运算
- `int` 或其他有符号类型的计算结果直接用于切片/数组索引
- 跨包调用，函数参数为有符号整数且用作索引

**快速定位保护机制 [L2-L3]**
- 索引使用前是否验证非负：`if idx >= 0 && idx < len(data)`
- 是否使用 `uint` 或 `uintptr` 等无符号类型作为索引
- 是否通过自定义函数封装索引访问，函数内部进行范围检查
- 是否使用 `strconv.ParseUint` 等安全转换函数且配合范围验证
- 是否启用 `go vet` 静态分析检查（会检测部分索引问题）
- Protocol Buffer 代码生成是否有版本控制和范围验证

---

## Classify

**研判为真漏洞的特征：**
1. 有符号整数直接或通过转换用于数组/切片索引，无任何范围验证
2. 有符号值来自外部输入（用户输入、网络数据、JSON、protobuf 等），可能为负数
3. 计算后的有符号整数（可能溢出）直接用作索引
4. unsafe.Pointer 与 uintptr 混用，有符号偏移未验证导致指针越界
5. 切片截断操作 `data[:idx]` 中 idx 为负数或超大无符号值

**误报/代码异味的特征：**
- 有符号整数来自内部封闭的逻辑控制流，范围已确保非负（如循环计数器）
- 索引使用前有明确的范围检查：`if idx >= 0 && idx < len(data)`
- 使用 `uint` 或 `uintptr` 等无符号类型作为索引源
- 从外部输入解析后明确验证：`if parsedIdx < 0 || parsedIdx >= len(data) { return err }`
- 通过安全转换库（如 `github.com/go-playground/validator`）进行验证
- 已启用 `go vet` 检查且无相关警告输出

---

## Low risk

**以下场景可评为低风险：**

1. **完整的范围验证**
   - 索引使用前显式检查：`if idx < 0 || idx >= len(data) { return err }`
   - 或使用条件表达式限制：`idx := min(userIdx, len(data)-1)`
   - 边界条件已由逻辑保证（如循环边界）

2. **内部受控的有符号整数**
   - 有符号值来自内部计算（如算法结果），其负数情况在上游已被排除
   - 例：`idx := len(data) - offset`，其中 offset 已验证范围
   - 来自 `len()`、`cap()` 等内置函数的值（固有非负性）

3. **使用无符号类型作为索引源**
   - 直接使用 `uint`、`uint64`、`uintptr` 等无符号类型作为索引
   - 或通过 `uint(signedVal)` 显式转换但转换前已验证非负

4. **非关键路径的索引操作**
   - 索引越界仅导致 panic（已有 recover 捕获处理）
   - 或用于统计、日志等非安全决策的访问

5. **第三方库的安全索引**
   - 使用知名库（如 `github.com/pkg/errors`、标准库 `container/ring` 等）的安全接口
   - 库内部已完成类型转换和范围验证

6. **编译器和工具支持**
   - 启用 `go vet` 检查且通过（包括 `-unsafeptr` 检查）
   - 启用 `golangci-lint` 的 `range` 和 `vet` 规则且无告警
