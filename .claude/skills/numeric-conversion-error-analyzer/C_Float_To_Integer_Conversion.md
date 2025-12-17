# C_Float_To_Integer_Conversion

**漏洞类型**: 浮点与整型转换，浮点数转整型时的精度丢失、截断、溢出导致的逻辑错误

**漏洞成因**

浮点数向整型转换时，会产生精度丢失、数值截断、越界溢出等问题。常见于：
- 浮点数直接强制转换为整型，忽略小数部分
- 浮点数用于内存分配大小、数组索引、缓冲区长度等关键场景
- 浮点数表示范围超出整型可表示范围时的溢出处理
- 浮点数精度不足导致的舍入误差在后续计算中放大
- NaN、Inf 等特殊值的转换未加校验

---

## Details

### 代码示例

**危险模式1：浮点直接转整作为内存分配大小**
```c
void allocate_buffer(float size) {
    int buf_size = (int)size;        // 精度丢失：3.9 → 3
    char *buffer = malloc(buf_size); // 分配过小，后续写入越界
    process_data(buffer, 100);        // 实际需要100字节，但只分配了3字节
}

float user_input = 3.9;
allocate_buffer(user_input);  // 越界写入
```

**危险模式2：浮点数超出整型范围**
```c
void process_coordinate(float x) {
    int coord = (int)x;              // x > INT_MAX 时行为未定义
    int array[256];
    array[coord] = value;            // 未定义行为或数值环绕
}

float large_val = 1e10;  // 远超 INT_MAX
process_coordinate(large_val);
```

**危险模式3：浮点用于数组索引**
```c
int get_table_value(float index, int table[10]) {
    return table[(int)index];  // 负数浮点转正数溢出，或无界访问
}

float idx = -1.5;
get_table_value(idx, table);  // (int)-1.5 = -1，但可能发生符号转换误差
```

**危险模式4：NaN/Inf 转整型未检查**
```c
void handle_measurement(float value) {
    if (value > 0) {
        int size = (int)value;       // NaN 或 Inf 转换结果未定义
        char buf[size];              // VLA 大小异常，可能栈溢出
    }
}

float result = 0.0 / 0.0;  // NaN
handle_measurement(result);
```

**危险模式5：精度丢失导致逻辑错误**
```c
void check_permission(float permission_level) {
    int level = (int)permission_level;
    if (level == 3) {                // 本应为3.9，但被截断为3
        grant_admin_access();         // 权限绕过
    }
}

check_permission(3.9);  // 原意是拒绝，但因截断被接受
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `(int)` 或 `(unsigned int)` 或 `(size_t)` 直接作用于 `float`/`double` 变量
- 浮点变量用于：`malloc`/`calloc` 的大小参数，数组索引，VLA 大小
- 浮点来源于：用户输入、API 返回、网络数据、计算结果
- 浮点计算中出现 `+`、`*`、`/` 的累积运算后立即转整
- 比较浮点与整型常数的条件分支

**快速定位保护机制 [L2-L3]**
- 转换前是否检查：`isnan()`、`isinf()`、`isfinite()`
- 是否验证浮点值在目标整型范围内：`if (val >= INT_MIN && val <= INT_MAX)`
- 是否使用安全转换函数（如 `lround`、`llround`）而非直接强制转换
- 是否对浮点计算启用舍入模式和异常检查
- 编译器标志：`-fno-strict-overflow`、`-ftrapv` 等是否启用

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接强制转整，无任何边界或合法性检查，用于关键操作（内存分配、索引、长度）
2. 浮点值来源于外部输入（用户、网络、文件），且转换后值无再验证
3. 浮点计算中可能发生精度丢失或舍入误差，且该误差被用于安全决策
4. 未检查 NaN/Inf，直接转整后用于内存操作或控制流
5. 浮点值可能超出目标整型范围，转换后结果发生溢出或回绕

**误报/代码异味的特征：**
- 浮点值来源于内部计算且范围明确受控（如固定公式 `size = sqrt(x)` 且 `x` 已限制）
- 转换前明确验证了范围和有效性（`if (isfinite(val) && val > 0 && val < MAX)`）
- 仅涉及展示用途或非关键计算的浮点转整
- 使用标准库安全转换函数（`round`、`lround` 等）且结果再验证
- 已启用编译器浮点异常检查或运行时 trap

---

## Low risk

**以下场景可评为低风险：**

1. **完整的有效性检查**
   - 转换前显式检查：`if (!isnan(val) && !isinf(val) && val >= 0 && val < 1000)`
   - 浮点值范围已验证在目标整型类型的可表示范围内
   - 使用 `nextafter` 或精度感知的比较方式

2. **内部计算结果的受控转换**
   - 浮点来自内部算法（非外部输入），其范围已在代码逻辑上限制
   - 如：`float angle = atan2(y, x)`，范围固定在 [-π, π]，直接转整为 [0, 359]
   - 错误不会导致安全后果（仅显示值或日志）

3. **使用安全转换函数**
   - 采用 `lround`、`llround`、`roundf` 等标准库函数，避免直接强制转换
   - 转换结果再进行范围验证

4. **非关键路径的转换**
   - 浮点转整仅用于统计、计数、显示等非安全决策的场景
   - 不影响内存分配、权限检查、索引访问等敏感操作

