# C_Signed_Unsigned_Conversion

**漏洞类型**: 有符号/无符号类型转换导致的溢出，有符号整数转换为无符号时符号位被解释为数值

**漏洞成因**

有符号整数向无符号类型转换时，负数会被解释为巨大的正数值。常见于：
- 有符号整数直接转换为无符号类型，用于内存分配、长度校验、数组索引
- 有符号值来自外部输入（用户、网络、文件），未验证就转换为无符号
- 比较操作中混用有符号和无符号整数导致的符号扩展
- 结构体中字段宽度不匹配导致的隐式转换
- 函数参数类型不一致，有符号传入无符号形参

---

## Details

### 代码示例

**危险模式1：负数转无符号导致缓冲区溢出**
```c
void process_data(char *data, int len) {
    unsigned int size = len;           // 负数转无符号：-1 → 4294967295
    char buffer[256];
    memcpy(buffer, data, size);        // 远大于256的拷贝导致栈溢出
}

process_data(user_input, -1);          // len 为 -1，转无符号后巨大
```

**危险模式2：有符号长度校验绕过**
```c
int read_file(int size) {
    if (size > 1000) {                 // 检查：size <= 1000
        return -1;
    }
    unsigned int usize = size;         // -1 转无符号：4294967295
    char *buf = malloc(usize);         // 分配超大内存导致DoS
    read_data(buf, usize);
}

read_file(-1);  // 通过有符号检查，但转无符号后是巨数
```

**危险模式3：数组索引越界**
```c
int get_array_element(int index, int *array, int len) {
    unsigned int idx = index;          // -5 转无符号：4294967291
    if (idx < len) {                   // 无符号比较总是真（与len无关）
        return array[idx];             // 越界访问
    }
    return -1;
}

int arr[10] = {...};
get_array_element(-5, arr, 10);        // idx = 4294967291，未被正确拒绝
```

**危险模式4：有符号无符号混合比较**
```c
void validate_length(int user_len, unsigned int max_len) {
    if (user_len < max_len) {          // 有符号 vs 无符号：-1 < max_len 为真（转无符号）
        process(user_len);
    }
}

validate_length(-1, 100);  // -1被解释为巨大无符号数，但比较被提升为无符号
```

**危险模式5：字段位宽导致的符号变化**
```c
struct Packet {
    unsigned int flags : 4;            // 4位无符号字段
    int size : 12;                     // 12位有符号字段
};

void handle_packet(struct Packet *pkt) {
    unsigned int total = pkt->size;    // 负数字段转无符号
    malloc(total);                     // 分配负-as-unsigned 大小内存
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- 有符号变量赋值给无符号变量：`unsigned int u = signed_var`
- 类型转换符：`(unsigned)signed_var` 或 `(size_t)signed_var`
- 有符号参数传入无符号形参的函数调用
- 混合有符号无符号的比较：`if (signed_val < unsigned_val)`
- 有符号值用于：`malloc`/`calloc` 参数，`memcpy` 长度，数组索引
- 有符号值来源：用户输入、网络数据、外部函数返回、系统调用

**快速定位保护机制 [L2-L3]**
- 有符号转无符号前是否验证非负：`if (signed_val >= 0)`
- 是否在转换后再验证范围：`if (u <= MAX_ALLOWED)`
- 比较操作是否显式转换为统一类型：`if ((unsigned)s < u)`
- 函数签名是否一致，参数类型是否匹配
- 是否启用编译器警告：`-Wsign-conversion`、`-Wconversion`

---

## Classify

**研判为真漏洞的特征：**
1. 有符号值直接转无符号，未验证其非负，用于关键操作（内存分配、长度、索引）
2. 有符号值来源于外部输入（用户、网络、文件），可能为负数
3. 转换后的无符号值被用于缓冲区操作、数组访问、长度校验等敏感位置
4. 存在有符号无符号混合比较，依赖隐式类型提升，可绕过安全检查
5. 负数转无符号后导致的巨数会引发缓冲区溢出、内存分配失败或逻辑错误

**误报/代码异味的特征：**
- 有符号值来自内部计算，范围已被逻辑保证为非负（如循环计数器）
- 转换前显式验证了非负条件：`if (val >= 0) { unsigned u = val; }`
- 有符号值的负数情况已在上游被过滤或断言
- 仅涉及同向传递（有符号→无符号）且后续再验证
- 编译器启用 `-Wsign-conversion` 无警告输出

---

## Low risk

**以下场景可评为低风险：**

1. **完整的非负性验证**
   - 有符号值在转换前显式检查：`if (val >= 0) { unsigned u = val; }`
   - 或转换后再验证范围：`unsigned u = val; if (u <= MAX_SIZE) use(u);`
   - 负数情况已被明确处理（返回错误或提前退出）

2. **内部受控的有符号值**
   - 有符号值来自内部逻辑计算（如循环计数 `i < len`，已保证非负）
   - 范围已在代码逻辑上限制，不依赖运行时数据
   - 如：`int idx = loop_counter;`，loop_counter 由编程语言保证非负

3. **非关键路径的转换**
   - 有符号转无符号仅用于计数、统计、日志等非安全决策场景
   - 不影响内存分配、指针运算、索引访问等敏感操作

4. **显式类型转换配合验证**
   - 使用 `(unsigned)` 前已验证范围，且转换后再确认
   - 或使用类型安全的包装函数进行转换和验证

5. **编译器保护启用**
   - 启用 `-Wsign-conversion` 并无相关警告
   - 或启用运行时 sanitizer：`-fsanitize=signed-integer-overflow`
