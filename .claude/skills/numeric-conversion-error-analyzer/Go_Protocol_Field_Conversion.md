# Go_Protocol_Field_Conversion

**漏洞类型**: 协议字段解包转换，binary 包解析中的类型转换

**漏洞成因**

Go 中协议字段解包转换涉及从网络字节流或文件字节流中提取多字节数据，通过 `encoding/binary` 或手动字节操作进行类型转换。常见问题包括：
- 从网络/文件读取的字节直接转换为整数而无范围检查
- 有符号/无符号类型混淆导致边界绕过
- 长度字段、偏移量字段直接用于内存分配或切片索引
- `unsafe.Pointer()` 转换后访问无边界验证
- 多字段组合操作（如 offset + length）未完整验证
- 类型截断或溢出导致值表示错误

---

## Details

### 代码示例

**危险模式1：协议长度字段直接用于内存分配**
```go
func parsePacket(buf []byte) {
    var length uint32
    binary.Read(bytes.NewReader(buf), binary.BigEndian, &length)
    payload := make([]byte, length)  // 无范围检查，可能分配巨大内存
    copy(payload, buf[4:])
}
```

**危险模式2：有符号/无符号转换导致边界绕过**
```go
func extractData(buf []byte) {
    var offset int16
    binary.Read(bytes.NewReader(buf), binary.BigEndian, &offset)
    data := buf[offset:]  // offset 可能为负，导致 panic 或跳过验证
}
```

**危险模式3：多字段组合未验证**
```go
func processFrame(buf []byte) {
    offsetVal := binary.BigEndian.Uint32(buf[0:4])
    lengthVal := binary.BigEndian.Uint32(buf[4:8])
    payload := buf[offsetVal : offsetVal+lengthVal]  // offset+length 可能超出缓冲区
}
```

**危险模式4：unsafe.Pointer 转换后访问**
```go
func readHeader(buf []byte) {
    hdr := (*Header)(unsafe.Pointer(&buf[0]))  // 未验证 buf 长度 >= sizeof(Header)
    size := hdr.Length
    return buf[hdr.Offset:]  // Offset 可能超出范围
}
```

**危险模式5：字段用于循环计数**
```go
func processItems(buf []byte) {
    count := binary.BigEndian.Uint32(buf[0:4])
    for i := 0; i < int(count); i++ {  // count 无上限，可能导致 DoS
        processItem(buf[i*itemSize:])
    }
}
```

**危险模式6：字节序混淆导致值解释错误**
```go
func validatePort(buf []byte) bool {
    port := binary.BigEndian.Uint16(buf[0:2])
    if port == 8080 {  // 网络字节序 8080 != 本地字节序 8080
        return true
    }
    return false
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]:**
- `binary.Read()`, `binary.ReadVarint()`, `binary.Unmarshal()` 调用
- `binary.BigEndian.Uint*()`, `binary.LittleEndian.Uint*()` 调用
- 手动字节操作：`buf[:N]`, `buf[offset:]`, `buf[a:b]`
- `unsafe.Pointer()` 类型转换
- 协议字段转换为 int/uint 类型用于内存分配
- 转换结果用于数组索引、切片操作、循环计数

**快速定位保护机制 [L2-L3]:**
- 转换后数值是否有范围检查：`if length > maxSize`、`if offset+size <= len(data)`
- 是否使用 `io.LimitedReader` 限制读取大小
- 有符号/无符号转换是否有负值判断
- 多字段组合操作是否完整验证（offset + length 是否超出缓冲区）
- `unsafe.Pointer()` 的指针是否来自已验证的数据
- 是否对类型溢出进行检查

## Classify

**研判为真漏洞的特征：**
1. 协议字段解包后直接用于内存分配、数组索引、指针偏移，无任何范围检查
2. 有符号/无符号转换导致边界绕过：如 `int16` 被转换为 `uint` 用于切片索引
3. 多字段组合操作（offset + length）未完整验证，可能超出缓冲区
4. `unsafe.Pointer()` 转换后访问，未验证指针指向的数据有效范围
5. 协议字段用于循环条件，无迭代次数上限检查
6. 字段值来源于不可信的网络/文件，转换后无再验证

**误报/代码异味的特征：**
- 转换后立即进行范围验证：`len := binary.BigEndian.Uint32(data); if len > maxSize { return err }`
- 使用 `io.LimitedReader` 预防：`reader := io.LimitReader(netConn, 1<<20); binary.Read(reader, ...)`
- 协议规范明确限制字段范围（如协议规定 uint8 最多 255，自动安全）
- 字段仅用于校验码、版本号、类型识别等非关键操作
- 指针转换来自已验证的内部数据：`data := make([]byte, n); ... unsafe.Pointer(&data[0])`
- 字段值已在初始化时受限制（如已知范围内的常量）

## Low risk

**以下场景可评为低风险：**

1. **完整的范围检查**
   - 字段转换后立即进行范围验证：`len := binary.BigEndian.Uint32(data); if len > maxAllowed { return err }`
   - 多字段组合操作完整验证：`if offset + length <= len(data) { payload := data[offset:offset+length] }`
   - 有符号/无符号转换时确认已处理边界情况：`if offset >= 0 && offset < len(data)`

2. **使用受限读取器**
   - 读取前使用 `io.LimitedReader` 限制字节流大小：`reader := io.LimitReader(netConn, maxSize); binary.Read(reader, ...)`
   - 字段值被事先限制在安全范围内

3. **使用安全的协议库**
   - 使用已验证的第三方协议库（如 protobuf、msgpack）自动处理类型转换
   - 库已对范围进行了验证

4. **非关键字段解析**
   - 字段仅用于校验码、版本号、类型识别、顺序号等元数据
   - 字段不直接影响内存分配、索引计算、权限决策

5. **协议规范的静态限制**
   - 协议规范中明确限制字段范围（如 uint8 字段最多 255、版本号固定 1-10）
   - 类型本身的范围已满足需求

6. **已验证的指针转换**
   - `unsafe.Pointer()` 的指针来自已验证的内部数据：`data := make([]byte, n); ... unsafe.Pointer(&data[0])`
   - 指针指向的数据范围已知且可控

---

## Audit Skills

### 专业审计技巧

**关键点1：网络字节流的不可信性**
- 字节流默认不可信：来自 socket、HTTP body、文件的数据可能被篡改或构造
- 追踪完整数据流：读取源 → 类型转换 → 使用点（索引/分配/比较）
- 协议字段通常包含长度、偏移、计数等关键值，必须验证范围

**关键点2：binary 包的解析特性**
- `binary.Read()` 和 `binary.Unmarshal()` 仅进行字节解释，不检查数值范围
- 大端/小端转换本身正确，但转换后值未验证导致漏洞
- `binary.ReadUvarint()`/`binary.ReadVarint()` 返回值需检查是否超过预期范围

**关键点3：有符号无符号转换陷阱**
- 网络协议中的长度字段通常为 uint（无符号），但 Go 切片索引需 int（有符号）
- 无符号值转有符号时可能产生负数，导致 panic 或跳过验证
- 关键检查模式：`length := binary.BigEndian.Uint32(data); arr[length:]` 需验证 length ≤ len(arr)

**关键点4：unsafe.Pointer 的危险**
- `unsafe.Pointer()` 完全绕过类型检查，后续访问可能越界
- 常用于性能优化或 CGO，但需确保对齐、范围、有效性
- 典型漏洞模式：`ptr := unsafe.Pointer(...); *((*int32)(ptr))` 未验证指向数据有效范围

**关键点5：内存分配溢出**
- 高危模式：`make([]byte, int(protocolLength))`，若无检查可分配巨大内存导致 DoS
- 检查模式：`if length > 1<<20 { return fmt.Errorf("packet too large") }`
- 注意类型截断：`make([]byte, int(uint64Value))` 在 32 位系统上可能丢失高位

**关键点6：协议字段交叉验证**
- 多字段组合漏洞：长度字段 + 偏移字段、多个段的总长度等
- 必须同时验证所有约束：`if offset + length <= len(buffer)`
- checksum/CRC 验证应涵盖所有数据，不能在验证前被篡改

### 真实漏洞 vs 误报区分

**这是漏洞的表现**：
1. 从网络读取长度字段直接分配内存：`len := binary.BigEndian.Uint32(data); buf := make([]byte, len)` 无上限
2. 有符号/无符号混用导致边界绕过：`offset := int16(data[0]); arr[offset:]` offset 可为负
3. 指针转换后无边界验证：`ptr := unsafe.Pointer(data); *((*uint64)(ptr))` 未检查 len(data) ≥ 8
4. 多字段未全验证：从 buf 的 offset 处读取 length 长度数据，仅检查其中一个
5. 循环计数无上限：`for i := 0; i < int(count); i++` 其中 count 直接来自协议字段

**这是误报的表现**：
1. 长度字段转换后立即验证：`if len > maxSize { return fmt.Errorf(...) }`
2. 使用 `io.LimitedReader` 预先限制：`reader := io.LimitReader(netConn, 1<<20); binary.Read(reader, ...)`
3. 协议规范固定范围：字段为 uint8（0-255）或协议明确规定最大值
4. 字段仅用于元数据：版本号、消息类型、标志位等转换且不参与内存操作
5. 指针转换已验证来源：`data := make([]byte, n); ... unsafe.Pointer(&data[0])` 长度已知

### 审计检查清单

- [ ] 定位所有 `binary.Read()`, `binary.Unmarshal()`, `binary.ReadUvarint()` 调用
- [ ] 追踪转换后的数值（长度、偏移、计数）是否用于切片索引或内存分配
- [ ] 检查转换前/后是否存在范围验证（如 `if len > maxSize`）
- [ ] 验证有符号↔无符号转换，是否处理了负值情况
- [ ] 检查多字段组合操作是否完整验证（offset + length 是否超出缓冲区）
- [ ] 扫描 `unsafe.Pointer()` 的所有使用，确认指针有效性和范围
- [ ] 查看 `make()` 调用的 len/cap 参数，确认来自已验证的字段
- [ ] 检查循环条件使用协议字段时是否有迭代次数上限
- [ ] 验证 io.Reader 是否被限制（`io.LimitedReader` 等）
- [ ] 追踪数据来源（网络/文件/用户输入），确认不可信性评估

