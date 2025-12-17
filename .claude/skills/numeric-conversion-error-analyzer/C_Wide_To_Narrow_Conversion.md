# C_Wide_To_Narrow_Conversion

**漏洞类型**: 宽类型到窄类型转换，长整型截断为短整型时的溢出和截断

**漏洞成因**

C/C++ 中宽类型到窄类型的转换（如 long → int、int → short、size_t → int）会导致截断。当源值超出目标类型的可表示范围时，高位被丢弃，仅保留低位，导致数值失真、逻辑错误、缓冲区溢出等安全问题。常见于：
- 大整数直接转换为较小的整型，未验证范围
- 算术运算后的结果（可能溢出）转换为窄类型
- 外部输入（文件、网络、用户）经窄类型转换后用于关键操作
- 循环计数、大小计算、索引等场景的类型转换

---

## Details

### 代码示例

**危险模式1：size_t 直接转 int 用于内存操作**
```c
void copy_data(size_t len, const void *src, void *dst) {
    int copy_len = (int)len;      // len > INT_MAX 时截断成负数或小值
    memcpy(dst, src, copy_len);   // 实际复制远小于预期
}

size_t large_len = 3000000000UL;  // 超过 INT_MAX
copy_data(large_len, src, dst);   // 仅复制前部分数据
```

**危险模式2：算术溢出后转窄类型**
```c
void allocate_buffer(int width, int height) {
    int size = width * height;        // 若 width=100000, height=100000 则溢出
    int *buf = (int *)malloc(size);   // 分配过小
    memcpy(buf, data, width*height);  // 缓冲区溢出
}
```

**危险模式3：long 转 int 作为数组索引**
```c
int get_item(long index, int items[256]) {
    int idx = (int)index;             // 超大 index 被截断
    return items[idx];                // 越界访问
}

long large_idx = 1e18;
get_item(large_idx, array);
```

**危险模式4：网络协议字段的窄类型截断**
```c
struct msg {
    int32_t checksum;
};

void process_msg(uint64_t full_hash) {
    struct msg m;
    m.checksum = (int32_t)full_hash;  // 高 32 位丢弃，校验和错误
    if (verify_checksum(&m)) {        // 基于截断值验证
        process_data();
    }
}
```

**危险模式5：文件大小截断导致缓冲区溢出**
```c
void read_file(FILE *f) {
    struct stat st;
    fstat(fileno(f), &st);
    int size = (int)st.st_size;       // 在 64 位系统上 st_size 为 off_t(long)
    char buf[size];                   // VLA 大小失真
    read(fileno(f), buf, st.st_size); // 越界
}
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- 强制转换 `(int)`、`(short)`、`(char)`、`(uint32_t)` 作用于 `long`、`long long`、`size_t`、`uint64_t`、`off_t`
- `int x = ...` 赋值右侧为宽类型（隐式转换）
- 算术运算的窄类型转换：`int result = (int)(a * b)`、`short sum = (short)(val1 + val2)`
- 数组索引、大小参数、循环条件的窄类型转换
- 从外部输入（strtol、read、recv、stat）的宽值转换为窄类型
- 转换后立即用于：`malloc`、`memcpy`、数组索引、循环边界

**快速定位保护机制 [L2-L3]**
- 转换前是否检查范围：`if (len > INT_MAX || len < INT_MIN)`、`if (size < 0)`
- 是否在转换后再验证合理性
- 是否使用安全转换宏或函数（如 `SAFE_CAST_TO_INT()`）
- 是否选用足够宽的类型接收操作结果（始终用 `size_t` 作为大小）
- 编译器警告：`-Wconversion`、`-Woverflow`、`-Warith-conversion` 是否启用

---

## Classify

**研判为真漏洞的特征：**
1. 宽类型无条件直接转换为窄类型，源值范围不受限
2. 源值来自外部输入（用户、网络、文件系统），转换后未再验证
3. 转换后的窄类型值用于关键操作：内存分配、数组索引、大小参数、循环条件、校验计算
4. 算术运算（乘法、加法）可能溢出，溢出结果转换为窄类型
5. 多步转换链中，中间过程窄类型已失真，最后操作基于失真值做安全决策

**误报/代码异味的特征：**
- 源值确实在目标类型范围内（如 unsigned char → int，永不溢出）
- 虽为宽类型但来源已明确有界（如循环变量 for(int i=0; i<100; i++)）
- 转换仅用于统计、显示、日志等非关键路径
- 转换前明确检查了值范围再使用
- 使用了项目内定义的安全转换宏

---

## Low risk

**以下场景可评为低风险：**

1. **源值范围已验证**
   - 转换前明确检查：`if (len > 0 && len <= INT_MAX)` 或类似范围验证
   - 源值来自明确有界的计算（如 for 循环计数器 0~99）
   - 源值为编译期常数或字面量

2. **目标类型足以容纳实际值**
   - 源类型虽宽但转换后用途不敏感（如转为 char 仅用于日志显示）
   - 实际业务场景中值不会超出目标类型范围
   - 使用中间类型中转再验证（如先转 long，范围检查后再转 int）

3. **已有明确保护机制**
   - 使用安全转换函数或项目内定义的转换宏，内部已实现溢出检查
   - 采用饱和截断策略（超大值自动截为 INT_MAX）
   - 编译器启用 `-fsanitize=implicit-conversion` 等运行时检查

4. **非关键场景**
   - 转换用于缓存、性能计数、统计等非安全决策的操作
   - 即使值失真也不影响功能正确性或安全性
   - 错误处理完整，即使计算失真也有回退路径

