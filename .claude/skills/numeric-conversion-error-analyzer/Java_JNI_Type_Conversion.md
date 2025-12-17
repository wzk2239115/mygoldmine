# Java_JNI_Type_Conversion

**漏洞类型**: JNI 类型转换错误，Java Native Interface 调用中的 Java/C 类型转换不当导致的类型混淆、数据截断、符号扩展错误

**漏洞成因**

JNI 调用中 Java 类型与 C 原生类型的转换存在以下风险：
- Java `int`/`long` 与 C `int`/`long` 在不同平台大小不一致（64位系统 `long` 差异）
- Java `boolean`（逻辑值）与 C `int`（数值）的转换，导致值误解
- Java 无符号操作（位运算）与 C 有符号类型混淆，符号扩展错误
- JNI 返回值或缓冲区指针的强制转换，未考虑平台位宽差异
- 数组索引、内存偏移从 `long` 转为 `int` 导致截断
- 直接操作 `Unsafe` 或 `FileDescriptor` 等系统级对象时的类型不匹配

---

## Details

### 代码示例

**危险模式1：JNI 中 long 到 int 的隐式截断**
```java
// Java 端
private native long getNativeFileDescriptor();

public void processFile() {
    long fd = getNativeFileDescriptor();  // C 返回 long（64位）
    int fileHandle = (int)fd;             // 无符号值截断为 int
    System.arraycopy(buffer, 0, output, fileHandle, 100);  // 索引越界
}
```

```c
// C 端
JNIEXPORT jlong JNICALL Java_MyClass_getNativeFileDescriptor(JNIEnv *env, jobject obj) {
    int native_fd = open("file.bin", O_RDONLY);
    return (jlong)native_fd;  // 符号扩展或截断不一致
}
```

**危险模式2：Boolean 与整数的类型混淆**
```java
// Java 端
private native int validatePermission(boolean isAdmin);

public void checkAccess() {
    boolean isAdmin = false;
    int result = validatePermission(isAdmin);  // JNI 传递 0
    if (result != 0) {
        grantAccess();  // C 端可能返回任意非零值被误解为权限
    }
}
```

```c
// C 端
JNIEXPORT jint JNICALL Java_MyClass_validatePermission(JNIEnv *env, jobject obj, jboolean isAdmin) {
    // jboolean 在 JNI 中定义为 unsigned char，值为 0 或 1
    // 但 C 代码可能返回其他值（如错误码 -1）
    return check_admin_status(isAdmin);  // 返回值在 Java 端被误解
}
```

**危险模式3：Unsafe 直接操作中的类型大小不匹配**
```java
public class UnsafeOperation {
    private static final Unsafe unsafe = getUnsafe();
    private static final long OFFSET = unsafe.objectFieldOffset(Field.get("value"));

    public void updateValue(Object obj, int newVal) {
        unsafe.putInt(obj, OFFSET, newVal);  // 32位写入
        long val = unsafe.getLong(obj, OFFSET);  // 64位读取
        // 在小端系统中可能读到垃圾数据或不完整的值
    }
}
```

**危险模式4：数组索引从 long 转 int**
```java
private native long getArrayIndex();

public void accessArray() {
    int[] data = new int[100];
    long index = getArrayIndex();
    int value = data[(int)index];  // 高位丢失，访问错误位置
}
```

**危险模式5：指针类型转换中的符号问题**
```java
private native long getPointerAddress();

public void directMemoryAccess() {
    long addr = getPointerAddress();  // C 返回 unsigned long
    if (addr < 0) {
        // 在 Java 中 addr 可能被误解为负数
        // 但在 C 原语境是 unsigned 的高值
    }
    ByteBuffer buffer = ByteBuffer.allocateDirect(1024);
    // 使用 addr 作为内存操作的基址时产生混淆
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `native` 方法声明，特别是返回 `long`/`int` 类型
- `(int)` 或 `(long)` 强制转换作用于 native 返回值
- JNI 调用中传递 `boolean` 到 C 端处理数值比较
- `Unsafe.putInt/putLong` 与 `Unsafe.getInt/getLong` 混用，大小不匹配
- 数组索引来自 `long` 类型或 native 调用未验证范围
- `FileDescriptor`、`DirectBuffer` 等系统对象的类型转换
- JNI 函数签名中 `jlong`/`jint`/`jboolean` 与 Java 端类型不对应

**快速定位保护机制 [L2-L3]**
- 转换前是否验证返回值范围：`if (fd >= 0 && fd < Integer.MAX_VALUE)`
- 是否对 `boolean` 值显式检查为 true/false：`if (isAdmin == true)` 或 `if ((int)isAdmin != 0 && (int)isAdmin != 1)`
- 是否在 native 层明确定义返回值的符号性和大小（文档或注释）
- `Unsafe` 操作是否在大小对齐上做验证（读写的字段大小是否一致）
- 是否使用 `@Deprecated` 标记或 `@Stable` 注解来约束 native 接口的稳定性
- 64 位/32 位平台兼容性测试是否覆盖类型转换边界

---

## Classify

**研判为真漏洞的特征：**
1. Native 返回值为 `long` 但 Java 端直接强制转 `int` 用于数组索引或内存操作，无范围检查
2. `boolean` 参数在 JNI 中被当作 `int` 处理，且 C 端可能返回非 0/1 的值导致逻辑错误
3. 使用 `Unsafe` 时读写操作的字段大小（`putInt` 后 `getLong`）不一致，导致读到脏数据
4. Native 调用返回的指针或文件描述符未验证符号性，直接用于系统调用参数
5. 跨平台代码中 `jlong` 在 32 位和 64 位系统上行为差异，32 位下截断导致功能异常
6. `FileDescriptor.getFD()` 或类似系统级接口的返回值，类型转换后越界访问数组或缓冲区

**误报/代码异味的特征：**
- Native 方法返回值在 JNI 层已明确验证范围，转换后再检查（如 `if (result > 0 && result < MAX_INT)`）
- `boolean` 参数仅用于条件分支，未涉及数值操作或误解
- `Unsafe` 操作中读写字段大小一致，且字段类型明确声明和对齐
- Native 调用返回的指针立即转为 `long` 并作为内存地址，符号性在文档中明确
- 代码已启用 `-XX:+StrictFP` 或编译平台一致性检查
- 单线程且非关键路径的类型转换，错误不导致数据泄露或权限提升

---

## Low risk

**以下场景可评为低风险：**

1. **明确的范围验证**
   - Native 返回值在转换前验证：`if (val >= 0 && val <= Integer.MAX_VALUE) { int i = (int)val; }`
   - `boolean` 值显式检查：`if ((int)isAdmin == 1) { grantAccess(); }`
   - Unsafe 操作在获取 Field offset 时已验证字段类型与读写操作一致

2. **类型对应已文档化**
   - Native 方法签名清晰标注返回值的符号性和有效范围
   - JNI 参数传递在注释中明确说明 Java 类型与 C 类型的对应关系
   - 版本升级或平台变更时的类型转换已添加兼容性测试

3. **内部计算结果的受控转换**
   - 类型转换应用于内部计算结果（非 native 调用），范围已在代码逻辑上受限
   - 如：`long timestamp = System.currentTimeMillis(); int seconds = (int)(timestamp / 1000);`
   - 错误仅影响展示或统计，不涉及内存访问或权限决策

4. **使用安全的 JNI 包装库**
   - 采用封装好的 JNI 库（如 JNA、Netty）处理类型转换
   - 转换逻辑已在库层经过充分测试和文档化

