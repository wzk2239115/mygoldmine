# Java_Wide_To_Narrow_Conversion

**漏洞类型**: 宽类型到窄类型转换，int/long 强制转换为 byte/short 时的截断

**漏洞成因**

Java 中宽类型到窄类型的转换（如 long → int、int → short、long → byte）会导致截断。当源值超出目标类型的可表示范围时，高位被丢弃，仅保留低位，导致数值失真、逻辑错误、缓冲区溢出等安全问题。常见于：
- 大整数直接转换为较小的整型，未验证范围
- 算术运算后的结果（可能溢出）转换为窄类型
- 外部输入（网络、文件、用户）经窄类型转换后用于关键操作
- 长整数的大小计算、索引操作、内存分配
- JNI 调用中的类型截断
- 数据库或网络返回的大数值的处理

---

## Details

### 代码示例

**危险模式1：long 直接转 int 用于集合容量**
```java
void allocateBuffer(long len) {
    int bufSize = (int)len;  // len > Integer.MAX_VALUE 时截断成负数或小值
    byte[] buf = new byte[bufSize];  // 分配过小
    fillBuffer(buf, len);  // 实际需要 len，但分配了 bufSize
}

allocateBuffer(3000000000L);  // 超过 Integer.MAX_VALUE，截断后变成负数
```

**危险模式2：算术溢出后转窄类型**
```java
void calculateSize(int width, int height) {
    long size = (long)width * height;  // 避免 int 溢出
    int bufSize = (int)size;  // 再次转回 int，可能截断
    byte[] buffer = new byte[bufSize];
    copyData(buffer, width * height);  // 期望 width*height 字节
}

calculateSize(100000, 100000);  // 1e10 超过 int 范围，截断后异常
```

**危险模式3：long 转 short 作为数组索引**
```java
byte getItem(long index, byte[] items) {
    short idx = (short)index;  // 超大 index 被截断到 [-32768, 32767]
    return items[idx];  // 可能越界访问
}

getItem(1000000000L, array);  // 转为 short 后变成负数或小值
```

**危险模式4：网络接收的长度截断**
```java
void processNetworkData(DataInputStream dis) throws IOException {
    long contentLength = dis.readLong();  // 网络返回 8 字节长度
    if (contentLength > 0 && contentLength < 1_000_000_000L) {
        int len = (int)contentLength;  // 转为 int
        byte[] data = new byte[len];
        dis.readFully(data);
    }
}

// 即使检查了 long 范围，转为 int 后仍可能溢出
```

**危险模式5：权限级别的截断**
```java
void checkAccessLevel(long level) {
    byte accessLevel = (byte)level;  // level > 127 时截断
    if (accessLevel == 127) {  // 权限检查
        grantAdminAccess();
    }
}

checkAccessLevel(255L);  // 255 作为 byte 变成 -1，权限判断异常
```

**危险模式6：文件大小的截断**
```java
void readFile(RandomAccessFile raf) throws IOException {
    long fileSize = raf.length();
    int readSize = (int)fileSize;  // 大文件截断
    byte[] buffer = new byte[readSize];
    raf.readFully(buffer);
}

// 2GB 以上的文件会被截断处理
```

**危险模式7：JNI 调用中的窄类型转换**
```java
public class FileUtil {
    public native void processFile(String path, int size);

    void processLargeFile(String path, long fileSize) {
        int size = (int)fileSize;  // 截断处理
        processFile(path, size);
    }
}

// Native 方法期望的大小被截断，导致处理错误
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]:**
- 宽窄类型转换：`(int)long`, `(short)int`, `(byte)int/long`
- 字段或返回值为宽类型，赋值给窄类型：`int i = obj.getLongValue()`
- 集合相关操作：`new byte[capacity]` 其中 capacity 来自 long
- 网络/数据库操作：`DataInputStream.readLong()`, `ResultSet.getLong()`
- 文件操作：`RandomAccessFile.length()` 返回 long
- JNI 参数转换：本地方法调用中的类型强制转换
- 循环或计数：条件或索引涉及宽窄类型混用

**快速定位保护机制 [L2-L3]:**
- 转换前是否验证范围：`if (longVal >= Integer.MIN_VALUE && longVal <= Integer.MAX_VALUE)`
- 是否使用 `Math.toIntExact()` 进行安全转换
- 是否使用 `Math.min(longVal, Integer.MAX_VALUE)` 饱和
- 转换后是否再验证有效性
- 是否使用异常处理捕获溢出
- 是否在源端验证值范围而非在转换端

---

## Classify

**研判为真漏洞的特征：**
1. 宽类型（long）直接转窄类型（int/short/byte），用于敏感操作，无范围检查
2. 宽类型来源于外部输入（网络、文件、数据库），可能超出范围
3. 算术运算结果的宽类型转换为窄类型，未验证溢出
4. 转换后的值被用于内存分配、数组索引、集合容量等关键位置
5. 多级转换导致的精度丢失（如 long → int → short）
6. JNI 调用中的窄类型转换未进行检查

**误报/代码异味的特征：**
- 宽类型值的范围已被事先限制（如协议规定最大 1MB）
- 转换前明确验证了范围：`if (val >= Integer.MIN_VALUE && val <= Integer.MAX_VALUE)`
- 使用 `Math.toIntExact()` 进行安全转换，配合异常处理
- 仅涉及只读操作或非敏感场景（日志、显示）
- 宽类型值来自内部计算，范围已被逻辑保证
- 转换后的值仅用于比较或验证，不用于关键操作

---

## Low risk

**以下场景可评为低风险：**

1. **完整的范围验证**
   - 转换前显式检查范围：`if (longVal >= Integer.MIN_VALUE && longVal <= Integer.MAX_VALUE)`
   - 使用 `Math.toIntExact()` 并捕获 ArithmeticException
   - 负数情况已被明确处理

2. **内部受控的宽类型值**
   - 宽类型来自内部计算，范围已被逻辑保证在窄类型范围内
   - 如：集合的 size() 方法返回的 int（已隐含在范围内）
   - 数据流明确可控，不经过网络或文件

3. **饱和或截断的有意操作**
   - 使用 `Math.min(longVal, Integer.MAX_VALUE)` 进行饱和
   - 使用 bitwise 掩码进行有意截断（并有注释说明）
   - 结果用于非关键场景

4. **协议规范的限制**
   - 协议规范中明确限制字段范围不超过窄类型上限
   - 如：协议规定长度字段为 4 字节整数，最大 4GB

5. **使用安全的转换方法**
   - 使用库提供的安全转换函数
   - 配合异常处理和错误恢复

6. **非关键路径的操作**
   - 转换后的值仅用于比较、日志、统计等非敏感场景
   - 不影响内存分配、索引访问等关键操作

7. **编译期已知的静态值**
   - 转换的值为编译期常数
   - 编译器可以在编译期验证转换的有效性

