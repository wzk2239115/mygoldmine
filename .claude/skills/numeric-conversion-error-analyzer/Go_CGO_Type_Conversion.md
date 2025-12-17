# Go_CGO_Type_Conversion

**漏洞类型**: CGO 类型转换，CGO 调用中的类型转换问题

**漏洞成因**

Go 与 C 互操作时，类型系统差异导致的转换错误是常见漏洞源。CGO（C Go）在跨语言边界时涉及：
- C 的 `int`、`long`、`char*` 等类型与 Go 的 `int`、`int32`、`int64`、`string`、`[]byte` 的映射差异
- 指针大小假设（32位 vs 64位）导致的截断或溢出
- 有符号/无符号的隐式转换（如 C 的 `unsigned int` 映射到 Go 的有符号 `int`）
- 结构体字段对齐、字节序差异导致的数值误读
- C 库返回值（如 `int` 形式的错误码、状态码）未正确转换
- 内存指针从 `unsafe.Pointer` 转换为整数后的越界访问
- CGO 跨边界传递数组/切片时的长度截断或溢出

---

## Details

### 代码示例

**危险模式1：C int 到 Go int 的符号扩展错误**
```go
// C 端声明
// int get_user_id();  // 返回用户ID，可能返回 -1 表示错误

import "C"

func getUserID() int {
    id := C.get_user_id()      // id 为 C.int
    return int(id)             // 有符号转换，-1 保留为 -1
}

// 调用端
func processUser(userID int) {
    users := []string{"alice", "bob", "charlie"}
    return users[userID]       // -1 会导致 panic（无符号转换后变成巨大正数）
}

// 问题：C 的 -1 表示错误标志，但在 Go 中作为索引时被解释为巨大无符号值
```

**危险模式2：long/size_t 到 int 的截断**
```go
// C 端声明
// size_t get_buffer_size(void* buf);

func (buf *Buffer) getSize() int {
    // C.size_t 通常是 uint64（在64位系统），转为 int（可能为32位）
    size := C.get_buffer_size(unsafe.Pointer(buf.data))
    return int(size)  // 64位无符号数被截断为32位有符号
}

// 调用端
func validateBuffer(buf *Buffer) {
    sz := buf.getSize()
    if sz > 0 && sz < 1000000 {
        allocate(sz)  // 若原 size 为 0x100000000（4GB+），被截断后变成 0
    }
}
```

**危险模式3：指针转整数的地址假设错误**
```go
func computeOffset(ptr unsafe.Pointer, idx int) unsafe.Pointer {
    // 假设指针可安全转为 int64，但在32位系统会溢出
    addr := int64(uintptr(ptr)) + int64(idx)
    if addr < 0 {
        return nil  // 负地址被误判为错误
    }
    return unsafe.Pointer(uintptr(addr))
}

// 实际上在32位系统上：
// uintptr(0x80000000) + int64(1000) 转换时可能发生溢出
```

**危险模式4：结构体字段转换时的对齐和字节序问题**
```go
// C 结构体可能使用 #pragma pack，Go 不支持
// C: struct { int a; char b; int c; } - 可能12字节（无对齐）或16字节（对齐）
// Go: struct { A int32; B byte; C int32 } - 通常16字节（Go 自动对齐）

import "C"

func parseMessage(data []byte) C.struct_Message {
    // 如果假设 Go 的 unsafe.Pointer(&data[0]) 直接对应 C 结构体
    // 字段偏移错误会导致读取错误的数据
    msg := (*C.struct_Message)(unsafe.Pointer(&data[0]))
    return *msg
}

// 问题：对齐差异导致 C 的第三个字段被误读为对齐填充
```

**危险模式5：CGO 传递切片时的长度转换**
```go
// C 端: void process_array(int* arr, unsigned int len);

func processArray(data []int) {
    if len(data) > 0 {
        // C.uint 通常为32位，len(data) 为64位
        // 若 len(data) > 2^32，被截断后 C 函数接收到错误的长度
        C.process_array((*C.int)(unsafe.Pointer(&data[0])), C.uint(len(data)))
    }
}
```

**危险模式6：C 返回值的错误码误判**
```go
// C: int read_data(char* buf, int len);  // 返回读取字节数，-1 表示错误

func readData(buf []byte) int {
    n := C.read_data((*C.char)(unsafe.Pointer(&buf[0])), C.int(len(buf)))
    return int(n)  // -1 被转为 -1（有符号），但之后可能被当作无符号使用
}

// 调用端
func processRead() {
    buf := make([]byte, 1024)
    n := readData(buf)
    if n > 0 {
        process(buf[:n])  // 若 n = -1，转为 uint 后变成巨大值，panic
    }
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `C.int`、`C.long`、`C.char`、`C.uint`、`C.size_t`、`C.ulong` 等 C 类型直接转为 Go 类型
- `int(C.someFunc())`、`int64(C.someVar)` 等强制类型转换
- `unsafe.Pointer(&cData[0])` 或 `unsafe.Pointer(cPtr)` 用于 Go/C 互操作
- `uintptr(ptr)` 与 `int`/`int64` 的混用
- C 返回值（特别是作为长度、大小、偏移的返回值）未检查边界
- `CGO_ENABLED` 相关的条件编译代码
- 导入 `"C"` 的包中存在类型转换

**快速定位保护机制 [L2-L3]**
- 转换前是否检查值范围：`if n < 0 || n > math.MaxInt32`
- 是否使用安全转换函数或包装函数
- C 返回值是否通过错误检查（如检查 -1）后再使用
- 指针运算时是否验证边界：`if addr < 0 || addr > maxAddr`
- 是否在类型转换后再次验证有效性（二次检查）
- 是否显式处理 C 和 Go 的大小差异（如 `if unsafe.Sizeof(C.int) != 4`）

---

## Classify

**研判为真漏洞的特征：**
1. C 函数返回有符号值（如 `-1` 表示错误），直接转换后用于无符号上下文（索引、大小、偏移）
2. 跨界转换（`C.long` → `int`、`size_t` → `int`）无范围检查，值可能超出目标类型范围
3. `unsafe.Pointer` 与整数的往返转换用于指针运算，无地址有效性验证
4. CGO 传递的数组长度（如 `len(data)` 转为 `C.int`）可能溢出，C 侧接收到错误长度
5. 结构体序列化/反序列化时，假设对齐或字节序，未显式处理 C 与 Go 的差异
6. C 返回的状态码未验证就用于决策（如假设返回值 > 0 为成功）

**误报/代码异味的特征：**
- 类型转换前明确验证范围：`if n >= 0 && n <= math.MaxInt32`
- C 返回值通过明确的错误检查后再使用（如 `if err := C.func(); err != 0`）
- 使用包装函数统一处理 C/Go 类型转换，函数内部已完成验证
- 仅在内部受控的路径中进行转换，未从外部输入接收 C 类型值
- 指针运算时明确限制范围，已验证指针不超出已分配内存边界
- 已显式处理字节序（使用 `binary.LittleEndian` 等）和对齐（使用 `unsafe.Alignof`）

---

## Low risk

**以下场景可评为低风险：**

1. **完整的值范围验证**
   - 转换前显式检查：`if n < 0 || n > math.MaxInt32 { return err }`
   - C 函数文档明确说明返回值范围，代码与文档匹配
   - 特殊值（如 `-1`）已显式检查和处理

2. **错误值的显式处理**
   - C 函数约定返回 `-1` 表示错误，代码中检查：`if n == -1 { return nil, err }`
   - 返回值被分为有效范围和错误代码，两者都处理
   - 使用类型别名或包装类型隐藏 C 类型，接口层做好验证

3. **内部受控的 CGO 调用**
   - CGO 仅在包内部使用，参数由内部生成且范围已确保
   - 未接收外部输入直接传递给 C 函数
   - C 库为可信的、版本固定的标准库（如 POSIX C 库）

4. **显式的类型转换保护**
   - 使用 `math.MaxInt64`、`math.MaxUint32` 等常数进行边界检查
   - 指针转换时使用 `uintptr`（不是 `int64`），确保与平台指针大小一致
   - 结构体序列化使用 `encoding/binary` 等标准库，避免假设对齐

5. **字节序和对齐的显式处理**
   - C 结构体通过 `#pragma pack(1)` 或类似机制固定，Go 端使用 `unsafe` 时验证
   - 使用 `unsafe.Sizeof`、`unsafe.Alignof` 确认大小和对齐一致
   - 网络协议或文件格式的数据通过 `binary.Read/Write` 转换，非 `unsafe.Pointer`

6. **第三方 CGO 库的安全使用**
   - 使用知名库（如 `sqlite3`、`uuid` 的 C 包装）的官方高级接口
   - 库的类型转换由库维护者负责，应用层直接使用安全类型
   - 库版本固定，已知其类型转换的正确性

