# Java_Narrow_To_Wide_Conversion

**漏洞类型**: 窄类型到宽类型转换，byte/short 扩展为 int/long 时的符号扩展导致的逻辑错误

**漏洞成因**

Java 中窄类型（byte、short、char）向宽类型（int、long）转换时，发生符号扩展（sign extension）。byte 和 short 是有符号类型，转换为 int 或 long 时，最高位（符号位）被复制到高位，导致负数扩展后仍为负数，可能引发数组越界、访问控制绕过、整数溢出等安全问题。常见于：

- byte/short 直接用于数组索引、缓冲区偏移、长度计算
- 位运算模拟无符号操作时的符号扩展误差
- 网络协议数据解析中字节的错误转换
- 权限或状态值的符号扩展导致逻辑错误
- 跨越模块边界时的类型转换未加校验

---

## Details

### 代码示例

**危险模式1：byte 直接作为数组索引导致越界**
```java
void process_data(byte[] data, int[] buffer) {
    byte idx = data[0];                    // idx 可能为负数（-128 ~ -1）
    int value = buffer[idx];               // 符号扩展：-1 → -1，越界访问
}

byte[] test = {-50, 10, 20};
int[] arr = new int[256];
process_data(test, arr);  // 访问 buffer[-50]，越界
```

**危险模式2：short 作为缓冲区长度导致缓冲区溢出**
```java
void copy_data(short length, byte[] src, byte[] dst) {
    short len = length;                    // len 可能为负数
    if (len > 0) {
        System.arraycopy(src, 0, dst, 0, len);  // 负数被转为正数的 int
    }
}

short malicious_len = -1;
byte[] source = new byte[100];
byte[] dest = new byte[50];
copy_data(malicious_len, source, dest);  // -1 → 0xFFFFFFFF，引发异常或越界
```

**危险模式3：byte 用于权限检查的符号扩展绕过**
```java
void check_permission(byte permission_mask) {
    int mask = permission_mask;            // -1（0xFF byte）→ -1（0xFFFFFFFF int）
    if ((mask & ADMIN_FLAG) == ADMIN_FLAG) {
        grant_admin_access();
    }
}

byte malicious = (byte)0xFF;  // 符号扩展导致权限位判断错误
check_permission(malicious);
```

**危险模式4：网络协议字节解析的符号扩展**
```java
void parse_packet(byte[] packet) {
    byte size_byte = packet[0];            // 网络数据为无符号：255
    int payload_size = size_byte;          // 符号扩展：-1 （0xFF → 0xFFFFFFFF）
    byte[] payload = new byte[payload_size]; // 负数长度，异常或栈溢出
}

byte[] pkt = {(byte)0xFF, 0x00, 0x01};
parse_packet(pkt);  // 255 被解释为 -1
```

**危险模式5：short 位运算导致的逻辑错误**
```java
void process_flags(short flags) {
    int flag_int = flags;                  // flags = -256（0xFF00）
    if ((flag_int & 0x00FF) != 0) {        // 符号扩展后高位影响判断
        execute_critical_operation();
    }
}

short malicious_flags = (short)0xFF00;
process_flags(malicious_flags);
```

**危险模式6：char 的无符号扩展与有符号操作混用**
```java
void calculate_hash(char c) {
    int hash_val = c;                      // char 是无符号，但扩展后作为有符号处理
    if (hash_val < 0) {                    // 错误的负数判断
        hash_val = -hash_val;
    }
}

char input = 0xFFFF;
calculate_hash(input);
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- 局部变量声明：`byte`、`short` 类型直接赋值给 `int`、`long` 或用于数组操作
- 数组访问：`array[byte_var]`、`array[short_var]`、`bytebuffer.get(short_idx)`
- 方法参数：`byte`/`short` 参数用于 `System.arraycopy` 的 length 或 srcPos
- 网络/文件 I/O：`DataInputStream.readByte()` 或 `readShort()` 后直接用于关键操作
- 位运算：`byte_var & MASK`、`short_var | FLAG`、`~byte_var`
- 字节缓冲操作：`ByteBuffer.get()`、`getShort()` 的结果直接转换

**快速定位保护机制 [L2-L3]**
- 是否在转换前验证范围：`if (byte_val >= 0 && byte_val < ARRAY_SIZE)`
- 是否使用位掩码消除符号位：`int unsigned = byte_val & 0xFF`
- 是否使用 `Byte.toUnsignedInt()`、`Short.toUnsignedInt()` 等安全方法
- 是否对外部输入数据的字节进行显式的符号位处理
- 网络数据解析是否有数据验证层

---

## Classify

**研判为真漏洞的特征：**

1. byte/short 变量直接用于数组索引、缓冲区长度、偏移量，无符号扩展处理
2. 数据源于外部输入（网络包、文件、用户输入），转换后未再验证
3. byte/short 值的负数情况未被代码逻辑覆盖（如认为 byte 只能是 0-127）
4. 位运算中混用有符号和无符号操作，导致符号位扩展后的逻辑错误
5. 权限检查、状态判断基于符号扩展后的值，未加隔离

**误报/代码异味的特征：**
- byte/short 来自受信任的内部常量或固定数据，范围明确在 0-127 或 0-32767
- 已显式使用 `Byte.toUnsignedInt()`、`Short.toUnsignedInt()` 等安全方法
- 转换后立即进行范围检查：`if (val >= 0 && val < MAX_SIZE)`
- 使用位掩码显式消除符号位：`int unsigned = short_val & 0xFFFF`
- byte/short 仅用于非关键路径（日志、统计、显示）

---

## Low risk

**以下场景可评为低风险：**

1. **显式的无符号转换**
   - 使用 `Byte.toUnsignedInt(b)`、`Short.toUnsignedInt(s)` 进行转换
   - 转换后立即验证范围在预期内
   - 代码意图明确是处理无符号值

2. **受控的内部数据**
   - byte/short 来自内部常量或受信任的初始化，范围已在代码逻辑上限制
   - 如：`byte[] valid_indices = {0, 1, 2, 3}`，循环遍历该数组
   - 不涉及外部数据或用户输入

3. **显式的符号位处理**
   - 使用位掩码消除符号位：`int unsigned = byte_val & 0xFF`
   - 对 short 使用 `& 0xFFFF` 等操作
   - 转换后的值再进行明确的范围验证

4. **非关键路径的转换**
   - byte/short 转换仅用于日志、统计、显示等非安全决策路径
   - 不影响数组访问、缓冲区操作、权限检查等敏感操作
   - 错误不会导致信息泄露或权限提升

5. **框架/库提供的安全保障**
   - 使用 `ByteBuffer` 等 NIO 类处理网络数据，框架已做符号处理
   - 使用 `RandomAccessFile` 或安全 API 进行文件字节读取
