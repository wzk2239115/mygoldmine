# Go_Unsafe_Type_Conversion

**漏洞类型**: unsafe 包类型转换，unsafe.Pointer 和类型转换的安全问题

**漏洞成因**

Go 中数值类型转换错误常见于有符号/无符号类型转换、不同位宽类型转换、CGO 调用、unsafe 包使用等场景。Go 的类型系统相对严格，但在类型转换时仍需注意溢出、截断等问题，特别是在 unsafe 包和 CGO 调用中。主要风险包括：
- unsafe.Pointer 任意类型转换，绕过类型安全
- 指针与整数间的错误转换，导致内存混乱
- 有符号/无符号类型转换时的符号扩展误差
- 不同位宽整型转换导致的截断或符号反转
- 通过 reflect 和 unsafe 包进行的反射强制转换
- CGO 中的类型不匹配和指针转换

---

## Details

### 代码示例

**危险模式1：unsafe.Pointer 任意转换**
```go
func arbitraryRead(addr uintptr) int {
    ptr := unsafe.Pointer(addr)
    // 直接转为 *int，无类型验证，可读取任意内存
    val := *(*int)(ptr)
    return val
}

func main() {
    arbitraryRead(0x1000)  // 读取任意地址
}
```

**危险模式2：指针与整数不安全转换**
```go
func pointerArithmetic(data []byte, offset int) int {
    ptr := unsafe.Pointer(&data[0])

    // 将指针转为 uintptr，执行算术运算，再转回指针
    newPtr := unsafe.Pointer(uintptr(ptr) + uintptr(offset))

    // 无边界检查，可能越界访问
    return *(*int)(newPtr)
}

data := []byte{1, 2, 3, 4, 5}
pointerArithmetic(data, 1000)  // 越界读取
```

**危险模式3：有符号/无符号转换误差**
```go
func processSize(size int) {
    // int 被转为 uint，-1 变为 uint(18446744073709551615)
    usize := uint(size)
    buf := make([]byte, usize)  // 申请巨大内存
    copy(buf, data)              // 可能 OOM 或堆溢出
}

processSize(-1)  // 符号转换误差
```

**危险模式4：结构体字段的 unsafe 转换**
```go
type SafeStruct struct {
    field1 int
    field2 string
}

func unsafeFieldAccess(s interface{}) string {
    ptr := unsafe.Pointer(uintptr(unsafe.Pointer(&s)) + 16)
    // 硬编码偏移，结构体布局变化时发生读取错误或逃逸
    return *(*string)(ptr)
}

var s interface{} = SafeStruct{1, "test"}
unsafeFieldAccess(s)  // 可能读取错误数据或 panic
```

**危险模式5：类型断言与 unsafe 结合**
```go
func unsafeCast(v interface{}) int64 {
    ptr := unsafe.Pointer(uintptr(unsafe.Pointer(&v)) + 24)
    // 无验证直接读取，如果实际类型非数值类型，读取任意内存
    return *(*int64)(ptr)
}

var v interface{} = "string data"
unsafeCast(v)  // 读取字符串内部的指针或长度字段
```

**危险模式6：通过 unsafe 修改常量或只读数据**
```go
func modifyConstant() {
    const constVal = 100
    ptr := unsafe.Pointer(uintptr(unsafe.Pointer(&constVal)))
    *(*int)(ptr) = 200  // 修改常量，行为未定义
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `unsafe.Pointer()` 的使用，特别是跨类型转换：`(*Type)(unsafe.Pointer(...))`
- `uintptr` 与指针间的转换：`uintptr(unsafe.Pointer(...))` 或 `unsafe.Pointer(uintptr(...))`
- 指针算术运算：`uintptr(...) + uintptr(offset)`
- 硬编码的字段偏移：`unsafe.Pointer(uintptr(...) + 8)` 或 `+ 16`
- `reflect.ValueOf(...).UnsafePointer()`
- `reflect.SliceHeader`、`reflect.StringHeader` 的直接构造和转换
- CGO 指针转换未做类型检查：`(*C.Type)(unsafe.Pointer(goPtr))`

**快速定位保护机制 [L2-L3]**
- 转换前是否有类型检查或断言：`if v, ok := x.(Type); ok`
- 指针偏移是否有边界验证：`if offset > len(data)`
- 是否使用 `unsafe.Sizeof` 计算偏移而非硬编码
- 是否对从外部输入的地址或偏移进行验证
- 是否在 CGO 调用时使用类型转换验证或中间层包装
- 是否启用 race detector 或 memory sanitizer 检测
- 注释中是否明确说明为何必须使用 unsafe（合理的 unsafe 会有清晰注释）

---

## Classify

**研判为真漏洞的特征：**
1. 无条件的 unsafe.Pointer 任意类型转换，转换后指针指向的结构体或类型不匹配
2. 通过 unsafe 转换后的指针直接解引用，无任何边界或类型检查
3. 指针算术运算中使用了来自外部输入或不可信源的偏移值，无验证
4. 硬编码字段偏移，结构体定义可能变化，导致读写错误字段或越界
5. 有符号/无符号转换发生在内存大小、数组长度等关键参数，转换结果无验证
6. 通过 unsafe 修改应为不可变或只读的数据（常量、全局变量、共享数据）
7. 在 CGO 调用中不匹配的指针类型转换，跨越 Go 与 C 的类型边界

**误报/代码异味的特征：**
- unsafe.Pointer 用于类型转换前进行了充分的类型检查或断言
- 指针偏移是通过 `unsafe.Sizeof` 和已验证的字段顺序计算，非硬编码
- 转换针对的是同一结构体的已知字段，偏移计算在编译期确定
- 外部输入的地址或偏移被严格范围检查后再使用
- unsafe 代码块有明确注释说明为何必须使用，且代码审查合理
- 仅在极少数性能关键路径中使用，且有替代方案但被明确拒绝
- CGO 调用中使用了官方提供的类型映射或验证层

---

## Low risk

**以下场景可评为低风险：**

1. **字段偏移通过编译期计算获得**
   - 使用 `unsafe.Offsetof` 获取结构体字段的精确偏移
   - 针对同一个已知结构体类型，偏移在代码中静态确定
   - 如：`ptr := unsafe.Pointer(uintptr(unsafe.Pointer(s)) + unsafe.Offsetof(s.field))`

2. **指针转换前进行完整类型检查**
   - 转换前通过类型断言或 reflect 验证实际类型
   - 如：`if v, ok := v.(ConcreteType); ok { ptr := unsafe.Pointer(&v) }`
   - 仅在类型匹配后才进行 unsafe 转换

3. **指针算术的严格范围限制**
   - 偏移值来自内部计算且范围已在逻辑上限制
   - 偏移值来自外部输入但有严格范围检查：`if offset >= 0 && offset < maxOffset`
   - 使用 `unsafe.Sizeof` 进行边界验证

4. **已知安全的 unsafe 模式**
   - 在字节切片与结构体间进行零拷贝转换，且有明确注释和审查
   - 使用官方推荐的 reflect 模式（如 `SliceHeader` for 特定场景）
   - CGO 调用中使用了官方 C 库绑定或已审计的转换函数

5. **性能优化中的受控使用**
   - unsafe 用于已知安全的性能关键路径
   - 存在充分的测试覆盖和运行时检查（如 race detector 通过）
   - 代码注释清晰说明风险和限制条件
