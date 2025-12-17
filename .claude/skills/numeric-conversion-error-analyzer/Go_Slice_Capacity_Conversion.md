# Go_Slice_Capacity_Conversion

**漏洞类型**: 切片容量转换，切片容量计算中的类型转换

**漏洞成因**

Go 中切片 (slice) 的容量在 `make([]T, length, capacity)` 或切片截断操作中通过整数指定。当容量值来自类型转换、计算或外部输入时，以下场景易导致漏洞：
- 有符号整数（可能为负）转为无符号作为容量，被误解为巨大正数
- 不同位宽整数转换导致高位截断或符号扩展，实际容量异常
- 整数溢出后的结果直接用于容量，导致过小或过大的分配
- unsafe 包中通过 uintptr 计算容量值，有符号偏移未验证
- 从 JSON、Protocol Buffer 等外部数据解析容量值未验证
- 切片截断操作 `data[start:end]` 中 start 或 end 的类型转换

---

## Details

### 代码示例

**危险模式1：有符号整数直接作为切片容量**
```go
func allocateBuffer(size int, data []byte) []byte {
    buffer := make([]byte, 0, size)  // size 为负数时内存分配异常
    return append(buffer, data...)
}

userSize := readUserInput()  // 用户可能输入负数
buf := allocateBuffer(userSize, myData)
```

**危险模式2：有符号到无符号的隐式转换导致巨大分配**
```go
func copyWithCapacity(offset int, originalData []byte) []byte {
    // 若 offset 为负，转为 uint 后成为巨大正数
    capacity := uint(offset) + uint(len(originalData))
    buffer := make([]byte, 0, capacity)  // 分配超大内存
    return buffer
}

copyWithCapacity(-10, largeSlice)  // uint(-10) ≈ 18446744073709551606
```

**危险模式3：int64 转 int32 导致容量值截断**
```go
func allocateWithInt32Cap(capacity int64) []int {
    cap32 := int32(capacity)         // capacity > INT32_MAX 时高位截断
    if cap32 > 0 {
        return make([]int, 0, cap32)  // 实际容量远小于预期
    }
    return nil
}

allocateWithInt32Cap(int64(3000000000))  // int32(3000000000) = -1294967296
```

**危险模式4：从JSON解析容量值未验证**
```go
type BufferConfig struct {
    Capacity int64 `json:"capacity"`
}

func initBuffer(cfg BufferConfig) []byte {
    return make([]byte, 0, cfg.Capacity)  // 可能为负数或超大值
}

json.Unmarshal([]byte(`{"capacity":-1}`), &cfg)
// cfg.Capacity = -1，导致 panic 或分配异常
```

**危险模式5：切片截断中的容量计算溢出**
```go
func sliceWithCapacity(start, end int, data []byte) []byte {
    // 若 end 或 start 为负，或计算溢出，容量值异常
    capacity := end - start
    if capacity <= 0 {
        return data[:0]
    }
    return data[start:end]
}

sliceWithCapacity(-100, 50, largeData)  // capacity = 150，但索引使用有问题
```

**危险模式6：unsafe 中通过 uintptr 计算容量**
```go
func unsafeAllocateCapacity(base unsafe.Pointer, offset int) []byte {
    addr := uintptr(base) + uintptr(offset)  // offset 为负转 uintptr 后为巨大数
    size := uintptr(1024)
    sliceHeader := (*reflect.SliceHeader)(unsafe.Pointer(&addr))
    sliceHeader.Len = int(size)
    sliceHeader.Cap = int(size)  // 容量值异常
    return *(*[]byte)(unsafe.Pointer(sliceHeader))
}

unsafeAllocateCapacity(ptr, -1)
```

**危险模式7：Protocol Buffer 字段作为容量**
```go
// .proto: int32 capacity = 1;

func useProtoCapacity(cfg *pb.Config) []byte {
    return make([]byte, 0, cfg.Capacity)  // int32 可能为负
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `make([]...`, `0,` 后跟有符号整数变量或计算结果（`int`, `int64`, `int32`）
- `make(map[...]`, 第二个参数为有符号整数
- 直接赋值：`cap := readInput()` 随后 `make([]byte, cap)` 或 `make([]byte, 0, cap)`
- 来自 JSON/Protocol Buffer 的整数字段直接作为容量
- 有符号到无符号的显式转换：`uint(signedVal)` 用作容量
- 位宽转换：`int32(largeInt)` 或 `int(int64Var)` 作为容量参数
- 切片截断操作中 `data[idx1:idx2:cap]` 中 cap 的计算
- 跨包调用，函数参数为有符号整数且用作 make 的容量

**快速定位保护机制 [L2-L3]**
- 容量参数使用前是否验证非负：`if capacity < 0 { return err }`
- 是否验证容量在合理范围内：`if capacity > maxAllowedSize`
- 是否使用 `uint` 或 `uintptr` 等无符号类型直接作为容量参数
- 是否通过自定义函数封装 make，函数内部进行范围检查
- 是否使用 `strconv.ParseUint` 等安全转换函数且配合范围验证
- JSON/Protocol Buffer 反序列化后是否有验证步骤

---

## Classify

**研判为真漏洞的特征：**
1. 有符号整数直接或通过转换用作 make 的容量参数，无范围验证
2. 容量值来自外部输入（用户输入、网络数据、JSON、protobuf 等），可能为负数或超大值
3. 有符号到无符号的隐式或显式转换，导致负数被解释为巨大正数
4. 位宽转换（int64→int32、int→uint）导致容量值截断或溢出
5. 计算后的有符号整数（可能溢出）直接用作容量，无验证
6. unsafe 操作中有符号偏移用于 uintptr 计算导致容量异常
7. 切片截断 `data[start:end:cap]` 中任何参数的类型转换未验证

**误报/代码异味的特征：**
- 有符号整数来自内部封闭的逻辑控制流，范围已确保非负（如循环计数器）
- 容量参数使用前有明确的范围检查：`if capacity < 0 || capacity > maxSize { return err }`
- 使用 `uint` 或 `uintptr` 等无符号类型直接作为容量参数
- 从外部输入解析后明确验证：`if cap < 0 { return err }`
- 通过安全转换库进行验证（如 `math` 包的范围常数）
- 已启用 `go vet` 检查且无相关警告输出

---

## Low risk

**以下场景可评为低风险：**

1. **完整的容量范围验证**
   - 容量参数使用前显式检查：`if capacity < 0 { return err }`
   - 或检查上限：`if capacity > maxAllowedCapacity { return err }`
   - 边界条件已由逻辑保证（如内部计算确保非负）

2. **内部受控的有符号整数**
   - 容量值来自内部计算（如算法结果），其负数情况在上游已被排除
   - 例：`cap := len(data) - offset`，其中 offset 已验证范围
   - 来自 `len()`、`cap()` 等内置函数的值（固有非负性）

3. **使用无符号类型作为容量源**
   - 直接使用 `uint`、`uint64` 等无符号类型作为容量
   - 或通过 `uint(signedVal)` 显式转换但转换前已验证非负

4. **非关键路径的容量操作**
   - 容量溢出仅导致 panic（已有 recover 捕获处理）
   - 或用于统计、缓存等非关键功能的分配

5. **第三方库的安全容量管理**
   - 使用知名库（如 `bytes.Buffer`、`strings.Builder`）的 API 管理容量
   - 库内部已完成类型转换和范围验证

6. **编译器和工具支持**
   - 启用 `go vet` 检查且通过（包括 `-unsafeptr` 检查）
   - 启用 `golangci-lint` 的 `vet` 和 `ineffassign` 规则且无告警
