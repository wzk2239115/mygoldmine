# Java_Signed_Unsigned_Conversion

**漏洞类型**: 有符号/无符号转换，Java 中通过位运算模拟无符号时的转换问题

**漏洞成因**

Java 中没有原生的无符号类型，但通过位运算可以模拟无符号行为。当有符号值直接用于需要非负数的业务逻辑（如数组索引、内存分配、长度验证）时，负数在位运算后会被误解释为巨大的正数，导致缓冲区溢出、权限绕过等安全问题。常见于：
- 有符号整数直接用于数组索引或集合容量
- 有符号值来自外部输入，转换后未验证非负性
- 混合有符号/无符号的比较导致边界绕过
- JNI 调用中的类型转换误用
- 字节转整数时未进行无符号处理（`byte & 0xFF`)
- 网络协议解析中的有符号字段直接使用

---

## Details

### 代码示例

**危险模式1：有符号值直接用于数组索引**
```java
void processArray(int index, byte[] array) {
    byte value = array[index];  // index 为负数时越界访问
}

byte[] buffer = new byte[256];
int idx = getUserInput();  // 可能为负数
buffer[idx] = 'x';  // 负数直接作为索引
```

**危险模式2：有符号长度用于集合初始化**
```java
void initializeMap(int expectedSize) {
    if (expectedSize > 0 && expectedSize < 1_000_000) {
        Map<String, String> map = new HashMap<>(expectedSize);  // 仅检查上界
    }
}

initializeMap(-1);  // -1 通过条件，直接用于初始化容量
```

**危险模式3：字节转整数未处理符号**
```java
void parseData(byte[] buf) {
    int value = (buf[0] << 24) | (buf[1] << 16) | (buf[2] << 8) | buf[3];
    // buf[i] 为有符号 byte，移位后符号扩展导致错误
    if (value > 0) {
        processValue(value);
    }
}

parseData(new byte[]{(byte)0xFF, 0, 0, 0});  // 0xFF 作为 byte 是 -1，移位结果异常
```

**危险模式4：有符号权限判断**
```java
void checkPermission(byte level) {
    int intLevel = level;  // byte 到 int 转换，负数变成负整数
    if (intLevel == 3) {  // 仅检查特定值
        grantAdminAccess();
    }
}

checkPermission((byte)(-1));  // -1 != 3，虽然通过，但逻辑不完整
```

**危险模式5：有符号字段用于数据偏移**
```java
void extractData(DataInputStream dis) throws IOException {
    int offset = dis.readInt();  // 从网络读取，可能为负
    int length = dis.readInt();
    byte[] data = new byte[length];
    dis.readFully(data);  // offset 可能为负，后续处理时越界
}
```

**危险模式6：混合有符号无符号比较**
```java
void validateSize(int size, long maxSize) {
    if (size < maxSize) {  // 有符号 int 与无符号 long 比较
        allocateBuffer(size);  // size 为负时，比较结果意外
    }
}

validateSize(-100, 1000L);  // -100 < 1000L 为真，但 -100 用于分配
```

**危险模式7：JNI 调用中的转换**
```java
public class NativeUtil {
    public native void processBuffer(int size, byte[] buf);

    void callNative(int userSize) {
        processBuffer(userSize, new byte[256]);  // 负数传入 native 方法
    }
}

// Native 代码期望 size 为无符号，但收到负有符号值
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]:**
- 有符号值作为数组/集合的索引或容量：`array[int]`, `HashMap(int)`, `ArrayList(int)`
- 有符号值来源：用户输入、网络数据、JNI 返回值
- 位运算操作：`<<`, `>>`, `>>>`, `&`, `|` 作用于 byte 或 short
- 字节数组解析：`buffer[0] << 24` 等位移操作
- DataInputStream 操作：`readInt()`, `readByte()`, `readShort()`
- JNI 本地方法调用中的参数转换

**快速定位保护机制 [L2-L3]:**
- 有符号值使用前是否验证非负：`if (size >= 0)`
- 是否检查上界：`if (size <= MAX_SIZE)`
- 字节转整数时是否进行无符号处理：`(byte & 0xFF)`, `Byte.toUnsignedInt()`
- 是否使用安全方法：`Math.toIntExact()`, `Math.addExact()`
- 是否进行范围检查后再使用：在条件内使用转换后的值
- JNI 参数是否进行了类型验证

---

## Classify

**研判为真漏洞的特征：**
1. 有符号值直接用于数组索引、集合容量、内存分配，无范围检查
2. 有符号值来源于外部输入（参数、网络、文件），可能为负数
3. 转换后的值被直接用于敏感操作而未再验证
4. 混合有符号/无符号的比较，依赖隐式类型转换
5. 字节转整数时未进行无符号处理（缺少 `& 0xFF`）
6. JNI 调用中的类型转换未进行检查

**误报/代码异味的特征：**
- 有符号值来自内部计算，范围已被逻辑保证为非负
- 转换前明确验证了非负条件：`if (val >= 0) { use(val); }`
- 字节转整数时正确使用了无符号处理：`(byte & 0xFF)` 或 `Byte.toUnsignedInt()`
- 使用 `Math.toIntExact()` 进行安全转换，配合异常处理
- 仅涉及只读操作或非敏感场景（日志、显示）
- JNI 参数已在调用前进行验证

---

## Low risk

**以下场景可评为低风险：**

1. **完整的非负性验证**
   - 转换前显式检查非负：`if (size >= 0) { use(size); }`
   - 检查上界：`if (size >= 0 && size <= MAX_SIZE)`
   - 负数情况已被明确处理

2. **内部受控的有符号值**
   - 有符号值来自内部计算，范围已被逻辑保证为非负
   - 如：循环计数器、集合大小等
   - 数据流明确可控，不经过用户输入

3. **正确的无符号处理**
   - 字节转整数时使用：`(byte & 0xFF)` 或 `Byte.toUnsignedInt()`
   - Short 转整数使用：`(short & 0xFFFF)` 或 `Short.toUnsignedInt()`
   - 其他位运算操作时使用适当的掩码

4. **使用安全的转换方法**
   - 使用 `Math.toIntExact()`, `Math.addExact()` 等检查方法
   - 配合 try-catch 处理 ArithmeticException

5. **非关键路径的操作**
   - 有符号值仅用于比较、日志等非敏感场景
   - 不影响数组访问、集合初始化等敏感操作

6. **JNI 调用的保护**
   - 参数在调用前已进行范围验证
   - 使用类型安全的包装方法

7. **协议规范的限制**
   - 协议规范中明确限制字段为非负值
   - 类型本身的范围已满足需求

