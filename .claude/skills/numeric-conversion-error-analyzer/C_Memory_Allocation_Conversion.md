# C_Memory_Allocation_Conversion

**漏洞类型**: 内存分配大小转换，malloc/calloc/realloc 使用转换后的值作为分配大小

**C/C++**

C/C++ 中内存分配函数（malloc、calloc、realloc）的大小参数通常为 `size_t`（无符号）。当使用有符号整数计算分配大小时，若类型转换处理不当，负数会被解释为巨大的正数值，导致分配极小的内存（溢出后截断）或极大的内存（OOM），进而引发缓冲区溢出、堆溢出、信息泄露等安全问题。

---

## Details

### 代码示例

**危险模式1：有符号整数直接传入 malloc**
```c
int size = get_user_size();  // 用户输入可能为负数
char *buffer = malloc(size);  // 负数转 size_t 变成极大数，可能分配失败
if (!buffer) return;
memcpy(buffer, data, actual_size);  // 分配大小与实际写入大小不符
```

**危险模式2：算术运算后的有符号数作为分配大小**
```c
int count = get_count();      // 用户输入
int elem_size = 16;
size_t alloc_size = count * elem_size;  // 有符号溢出后转 size_t
char *arr = malloc(alloc_size);  // 溢出导致分配过小
```

**危险模式3：强制转换有符号数到 size_t**
```c
int offset = parse_offset();   // 可能为负数
char *buf = malloc((size_t)offset + 1024);  // 强制转换负数为巨大 size_t
memset(buf, 0, 1024);
```

**危险模式4：calloc 的计数和大小都来自有符号计算**
```c
int rows = read_int();
int cols = read_int();
int *matrix = (int *)calloc(rows * cols, sizeof(int));  // 乘法溢出
```

**危险模式5：realloc 时大小转换不当**
```c
int new_size = read_size();
char *p = buf;
buf = realloc(buf, (size_t)new_size);  // new_size 为负时，转为巨大数值
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `malloc(`、`calloc(`、`realloc(` 后跟 `int`、`signed` 变量或表达式（未强制转换）
- `*` 运算（行数×列数、大小×计数）作为分配参数，未验证溢出
- `(size_t)` 强制转换作用于有符号源（特别是负数来源）
- 使用 `sizeof` 乘以用户输入的有符号计数：`malloc(count * sizeof(...))`
- `strtol()`、`atoi()` 等解析函数的输出直接用于分配大小

**快速定位保护机制 [L2-L3]**
- 是否在分配前检验：`if (size <= 0 || size > MAX_SIZE)`
- 是否在乘法前检查溢出：`if (count > MAX_SIZE / sizeof(...))`
- 是否使用安全分配函数（`safe_malloc()`、`calloc_safe()` 等）
- 是否明确转换为 `size_t` 前进行范围检查
- 是否检查 malloc 返回值并处理分配失败
- 编译器警告：`-Wconversion`、`-Wsign-conversion` 是否启用

---

## Classify

**研判为真漏洞的特征：**
1. 有符号整数未经验证直接用于分配大小参数（malloc、calloc、realloc）
2. 有符号数运算（乘法、加法）结果可能溢出，溢出后用于分配大小
3. 负数源经强制转换为 `size_t` 后分配内存
4. 多步转换链条中，中间步骤有符号数未检查，最终用于分配
5. 分配大小与实际写入大小来自不同来源，且大小计算未验证

**误报/代码异味的特征：**
- 分配大小为编译期常数或明确的无符号变量
- 虽用有符号计算但明确验证范围在合理值内（如 `if (size > 0 && size < 10000)`）
- 用户输入经过白名单或严格正整数验证后才用于分配
- 对内部固定大小的结构体分配（如 `malloc(sizeof(struct_type))`）
- 虽有转换但上下文表明值确实非负（如循环计数已验证）

---

## Low risk

**以下场景可评为低风险：**

1. **分配大小已明确验证**
   - 分配大小在分配前通过范围检查：`if (size > 0 && size < MAX_ALLOC)`
   - 分配大小来自编译期常数或完全无符号计算链
   - 使用白名单或模式验证确保大小合理

2. **乘法溢出已防护**
   - 乘法前进行溢出检查：`if (count > SIZE_MAX / elem_size)`
   - 使用乘法安全函数（如 `safe_mul()`）
   - 编译器启用 `-fsanitize=signed-integer-overflow` 或类似保护

3. **有符号到无符号转换已验证**
   - 显式转换前进行范围检查：`if (size >= 0) buf = malloc((size_t)size)`
   - 使用宏封装转换逻辑，内部已处理检查
   - 通过静态分析工具（如 Coverity）验证无风险

4. **封装函数已安全**
   - 使用专用安全分配函数（项目内定义的 `safe_malloc()` 等），函数内部已处理验证
   - 第三方库的安全分配函数（如 OpenSSL 的 `OPENSSL_malloc`）

5. **用户输入受限**
   - 分配大小直接来自受限协议字段，已在协议解析层验证范围
   - 用户输入仅用于非关键的缓存大小，分配失败有完整的回退处理

