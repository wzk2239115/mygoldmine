# Java_Array_Index_Conversion

**漏洞类型**: 数组索引转换，数组索引计算中的类型转换和边界检查

**漏洞成因**

Java 中数组索引计算涉及类型转换时，可能发生数值溢出、符号扩展错误、强制转换截断等问题。常见于：
- 长整型（long）强制转换为整型（int）作为数组索引，导致溢出
- 无符号整数模拟通过位运算后的转换截断
- 用户输入的数值直接强制转换为索引，无边界检查
- 计算表达式结果超出整型范围后用作索引
- 字节（byte）或短整型（short）符号扩展导致的索引异常

---

## Details

### 代码示例

**危险模式1：long 强制转 int 作为数组索引**
```java
void processArray(long index) {
    int[] array = new int[256];
    array[(int)index] = value;  // index > INT_MAX 时溢出，访问错误位置
}

long large_idx = 1000000000000L;  // 远超 INT_MAX
processArray(large_idx);  // 数组越界
```

**危险模式2：用户输入直接强制转换索引**
```java
void readValue(String userInput) {
    int[] data = new int[10];
    try {
        long idx = Long.parseLong(userInput);  // 用户可输入任意数值
        return data[(int)idx];                  // 无边界检查直接强制转换
    } catch (NumberFormatException e) {}
}

readValue("999999999999");  // 溢出后越界访问
```

**危险模式3：计算结果溢出后作为索引**
```java
void getElement(int x, int y) {
    int[] buffer = new int[1000];
    int index = x * y;              // x,y 都很大，乘积溢出
    return buffer[index];           // 使用溢出后的结果作为索引
}

getElement(100000, 100000);  // 乘积溢出，索引错误
```

**危险模式4：字节强制转 int 索引的符号问题**
```java
void byteIndexing(byte[] data) {
    int[] lookup = new int[256];
    for (byte b : data) {
        return lookup[(int)b];      // byte -1 转 int 后为 -1，越界访问
    }
}
```

**危险模式5：位运算后的截断**
```java
void bitwiseIndex(long value) {
    int[] array = new int[128];
    int index = (int)(value & 0xFFFFFFFFL);  // 模拟无符号，但截断丢失高位信息
    array[index] = newValue;        // 可能超出数组边界
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `(int)` 强制转换作用于 `long`、`Long`、`BigInteger` 变量
- 索引计算涉及：乘法、除法、位运算后立即强制转换
- 用户输入经 `Integer.parseInt()`、`Long.parseLong()` 后直接用作索引
- 数组访问前无 `if (index >= 0 && index < array.length)` 检查
- 跨模块传递的索引参数未在使用处再验证

**快速定位保护机制 [L2-L3]**
- 索引是否在使用前进行了范围检查：`if (index >= 0 && index < array.length)`
- 强制转换前是否验证源值在目标类型范围内：`if (value >= Integer.MIN_VALUE && value <= Integer.MAX_VALUE)`
- 是否使用 `Math.toIntExact()`、`Math.floorDiv()` 等安全转换
- 计算表达式是否可能溢出，是否使用更大的中间类型（long）或 BigInteger
- 是否启用了字节码检查或静态分析工具检测越界访问

---

## Classify

**研判为真漏洞的特征：**
1. 长整型或大整数直接强制转 int，无边界验证，用作数组索引
2. 用户输入的数值未经有效性检查直接作为索引
3. 涉及乘法、幂运算等易溢出的计算，结果未检查就用作索引
4. 跨方法传递索引参数，接收端无再验证
5. 索引计算涉及循环或迭代，上界条件与实际数组长度不一致

**误报/代码异味的特征：**
- 强制转换源值已在上层函数明确限制在整型范围内
- 索引使用前有显式范围检查：`if (0 <= idx && idx < arr.length)`
- 使用 `Math.toIntExact()` 等安全函数，超出范围时主动抛异常
- 索引仅来自内部常量或已受控的计算，无外部输入参与
- 使用泛型集合（`ArrayList`、`HashMap`）替代数组，自动处理越界

---

## Low risk

**以下场景可评为低风险：**

1. **完整的边界检查**
   - 强制转换前明确验证：`if (value >= Integer.MIN_VALUE && value <= Integer.MAX_VALUE)`
   - 使用前再检查：`if (index >= 0 && index < array.length)`
   - 超出范围时明确处理（抛异常或返回错误值）

2. **源值范围受控**
   - 索引来自内部常量、枚举或配置参数，范围已在编译期确定
   - 循环计数器直接作为索引，上界与数组长度关联：`for (int i = 0; i < array.length; i++)`
   - 使用已验证的不可变集合

3. **安全转换函数**
   - 使用 `Math.toIntExact()`、`Math.floorDiv()`、`Math.multiplyExact()` 等，异常安全
   - 异常捕获后有明确处理逻辑

4. **非关键操作**
   - 索引越界不影响安全（如统计聚合、只读查询）
   - 使用 `ArrayList`、`HashMap` 等自动边界检查的容器类
