# C_Array_Index_Conversion

**漏洞类型**: 数组索引转换，数组索引计算中的类型转换问题

**漏洞成因**
C/C++ 中数组索引通常为 `size_t`（无符号）或 `int`（有符号）类型。当使用有符号整数计算索引值时，若中间转换或强制转换处理不当，负数会被误解释为巨大的正数，导致越界访问。常见于：
- 有符号整数直接用于数组索引
- 有符号整数隐式转换为无符号类型后用于索引
- 数组索引计算未验证边界
- 整数溢出导致索引值异常

---

## Details

### 代码示例

**危险模式1：有符号整数直接作为数组索引**
```c
void process_array(int index, int array[]) {
    int value = array[index];  // index 为负数时越界访问
}

char buffer[256];
int idx = get_user_input();    // 用户输入可能为负数
buffer[idx] = 'x';             // 负数转无符号后变成巨大正数
```

**危险模式2：有符号到无符号的隐式转换**
```c
void copy_data(int offset, char *src, char *dst, size_t size) {
    memcpy(dst, src + offset, size);  // offset 为负数时，+ 运算转为无符号，指针越界
}

char arr[100];
int delta = -10;
size_t actual_size = (size_t)delta;  // -10 转 size_t 变成极大数
```

**危险模式3：计算后转换未验证**
```c
int get_index(int a, int b) {
    int result = a + b;  // 可能溢出
    return (unsigned char)result;  // 截断转换导致索引异常
}

char table[256];
table[get_index(200, 100)] = data;
```

**危险模式4：数组遍历中的类型混用**
```c
for (short i = 0; i < array_count; i++) {
    process(array[i]);  // short 与 size_t 比较可能存在隐式转换
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `array[` 或 `ptr[` 后跟 `int`、`signed`、`short` 类型变量
- `(unsigned)` 或 `(size_t)` 的强制转换，特别是对负数来源的转换
- `memcpy(..., ptr + signed_offset, ...)` 模式
- 混合使用 `int`/`size_t`/`ptrdiff_t` 的索引或偏移操作

**快速定位保护机制 [L2-L3]**
- 是否在索引使用前检验：`if (index < 0 || index >= size)`
- 是否使用 `assert` 或类似宏检查范围
- 是否采用范围检查函数如 `safe_index()`
- 编译器警告标记：`-Wconversion` 是否启用
- 是否使用静态检查工具（clang-analyzer、Coverity 等）

---

## Classify

**研判为真漏洞的特征：**
1. 负数直接或间接用于数组索引，且无任何范围检查
2. 有符号整数计算结果（可能溢出）转换为无符号，用作索引
3. 指针算术中使用有符号偏移，且未验证溢出情况
4. 强制转换操作（如 `(unsigned char)` 或 `(size_t)`）应用于有符号源，导致值误解

**误报/代码异味的特征：**
- 单纯使用无符号索引变量，无符号源的计算
- 虽有类型转换但明确限制了操作范围（如 `if (idx >= 0 && idx < size)`）
- 对内部计算的索引（非用户输入驱动）且范围已控制
- 仅涉及编译时已知大小和非负索引的访问

---

## Low risk

**以下场景可评为低风险：**

1. **范围已限制的索引操作**
   - 索引来源已通过验证函数确保在 [0, size) 范围内
   - 循环计数器为无符号类型，条件为 `i < size` 形式
   - 数组访问明确受限于已验证的边界

2. **内部封装的安全索引**
   - 通过安全索引函数（如自定义的 `safe_get()` 或第三方库）进行，函数内部已处理类型转换和边界检查
   - 编译器启用了 `-Wconversion` 并通过了编译（表示无隐式危险转换）

3. **栈上小数组的已知范围操作**
   - 编译期确定大小的栈数组，索引值来源明确且无符号化危险

4. **指针偏移明确受控**
   - 偏移值为编译期常数或通过验证函数限制
   - 使用 `ptrdiff_t` 且明确检查了范围

