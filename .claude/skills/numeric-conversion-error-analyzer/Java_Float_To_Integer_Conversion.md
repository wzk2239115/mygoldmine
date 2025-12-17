# Java_Float_To_Integer_Conversion

**漏洞类型**: 浮点与整型转换，double/float 转 int/long 时的精度丢失

**漏洞成因**

Java 浮点数向整型转换时，会产生精度丢失、数值截断、越界溢出等问题。常见于：
- 浮点数直接强制转换为整型，忽略小数部分，导致精度丢失
- 浮点数用于数组索引、集合容量、缓冲区长度等关键场景
- 浮点数表示范围（如 Double.MAX_VALUE）超出整型可表示范围时的溢出截断
- 浮点计算（加乘除、三角函数）中精度丢失，舍入误差累积后用于安全决策
- NaN、Infinity、-Infinity 等特殊值的转换未加校验，行为未定义
- Math 函数（`sqrt`、`sin`、`cos`、`atan2`）返回浮点结果的转整问题
- 位运算模拟无符号操作与浮点转整结合的误解

---

## Details

### 代码示例

**危险模式1：浮点直接转整作为数组大小/索引**
```java
void processBuffer(double size) {
    int bufSize = (int)size;           // 精度丢失：3.9 → 3
    byte[] buffer = new byte[bufSize]; // 分配过小
    fillBuffer(buffer, 100);           // 实际需要100字节，越界访问
}

double userSize = 3.9;
processBuffer(userSize);  // 越界
```

**危险模式2：浮点数超出整型范围**
```java
void processCoordinate(double x) {
    int coord = (int)x;         // x > Integer.MAX_VALUE 时截断
    int[] array = new int[256];
    array[coord] = value;       // 可能负数或越界
}

double largeVal = 1e10;  // 超过 Integer.MAX_VALUE
processCoordinate(largeVal);
```

**危险模式3：浮点用于集合容量/HashMap初始化**
```java
void initializeMap(double expectedSize) {
    int size = (int)expectedSize;
    Map<String, String> map = new HashMap<>(size);  // 精度丢失
}

double size = 10.1;
initializeMap(size);  // 初始化容量不足
```

**危险模式4：NaN/Infinity 未检查**
```java
void handleMeasurement(double value) {
    if (value > 0) {
        int arrSize = (int)value;      // NaN 或 Infinity 转换为 0
        Object[] arr = new Object[arrSize];
    }
}

double result = Math.sqrt(-1);  // NaN
handleMeasurement(result);
```

**危险模式5：精度丢失导致权限判断错误**
```java
void checkPermission(double level) {
    int intLevel = (int)level;
    if (intLevel == 3) {           // 3.9 被截断为 3
        grantAdminAccess();         // 权限绕过
    }
}

checkPermission(3.9);
```

**危险模式6：Math函数返回浮点转整的权限问题**
```java
void handleDiscount(double percentage) {
    int discountAmount = (int)(price * percentage / 100.0);  // 精度丢失
}

double percent = 33.33;
handleDiscount(percent);  // 累积精度误差
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `(int)` 或 `(long)` 直接作用于 `double`/`float` 变量
- 浮点变量用于：数组索引、集合初始化大小、循环计数
- 浮点来源于：用户输入、API 返回、网络数据、Math 函数结果
- 浮点计算（`+`、`*`、`/`）后立即转整
- 条件判断中浮点与整数常数比较
- `(int)Math.floor/ceil/round` 等函数的返回值转换

**快速定位保护机制 [L2-L3]**
- 转换前是否检查：`Double.isNaN()`、`Double.isInfinite()`、`Double.isFinite()`
- 是否验证浮点值在目标整型范围：`if (val >= Integer.MIN_VALUE && val <= Integer.MAX_VALUE)`
- 是否使用 `Math.round()`、`Math.toIntExact()` 等安全转换函数
- 是否对浮点计算结果先取整再验证（`Math.round()`、`StrictMath`）
- 是否进行了范围检查和异常捕获（`ArithmeticException` for `toIntExact`）

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接强制转整无检查，用于敏感操作（数组索引、集合大小、内存计算）
2. 浮点值来源于外部输入（参数、用户请求、网络数据），转换后无再验证
3. 浮点计算中可能发生精度丢失或舍入误差，用于权限、数量等安全决策
4. 未检查 NaN/Infinity，直接转整作为关键参数
5. 浮点值可能超出 Integer/Long 范围，转换后行为未定义或截断

**误报/代码异味的特征：**
- 浮点值来自内部计算且范围明确受控（如 `angle = Math.atan2(y, x)` 范围固定在 [-π, π]）
- 转换前明确验证了有效性：`if (Double.isFinite(val) && val >= 0 && val < MAX)`
- 仅涉及日志、显示、统计用途，不影响权限或资源分配
- 使用 `Math.toIntExact()` 并捕获 `ArithmeticException`
- 使用 `Math.round()` 替代直接强制转换

---

## Low risk

**以下场景可评为低风险：**

1. **完整的有效性检查**
   - 转换前显式检查：`if (Double.isFinite(val) && val >= Integer.MIN_VALUE && val <= Integer.MAX_VALUE)`
   - 浮点值范围已验证在目标整型类型的可表示范围内
   - 使用边界值严格比较

2. **内部计算结果的受控转换**
   - 浮点来自内部算法（非外部输入），其范围已限制（如角度 [-π, π]）
   - 如：`int degree = (int)Math.toDegrees(angle)`，范围可控
   - 错误不影响安全（仅显示或计数）

3. **使用安全转换函数**
   - 采用 `Math.toIntExact()`、`Math.round()` 或 `StrictMath` 函数
   - 转换结果再进行范围验证或异常处理

4. **非关键路径的转换**
   - 浮点转整仅用于统计、计数、日志等非敏感场景
   - 不影响数组访问、权限判断、内存分配等敏感操作
