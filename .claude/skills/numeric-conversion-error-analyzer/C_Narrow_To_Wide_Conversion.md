# C_Narrow_To_Wide_Conversion

**漏洞类型**: 窄类型到宽类型转换，短整型扩展为长整型时的符号扩展问题

**C/C++**

窄类型（short、int、char等）转换为宽类型（long、long long等）时，如果源类型是有符号的，会进行符号扩展。负数在转换后仍保持负值，导致在需要非负数的业务逻辑（如内存分配、数组索引、缓冲区长度计算）中引发缓冲区溢出、整数下溢等安全问题。

---

## Details

### 代码示例

**易受攻击的代码模式**:
```c
// 1. 有符号 int 转换到 long，用于内存分配
int size = read_size_from_user(); // 可能返回负数
long alloc_size = size; // 符号扩展：-1 变为 0xFFFFFFFFFFFFFFFF
void *buffer = malloc(alloc_size); // 分配巨大内存或失败

// 2. short 转换到 int 用于数组索引
short index = read_index(); // 可能为 -1
int arr_index = index; // 符号扩展
char *data = "abcdefg";
char c = data[arr_index]; // 访问错误地址

// 3. signed char 转换到 unsigned int
signed char val = read_byte(); // 可能为 -1
unsigned int size = val; // 符号扩展：-1 = 0xFFFFFFFF
memcpy(dest, src, size); // 拷贝巨大数据量

// 4. 多级转换导致符号混乱
short s = -100;
long l = s; // 符号扩展为 -100
size_t sz = l; // 有符号转无符号，负数变巨大正数
malloc(sz); // 分配巨大内存

// 5. 数据验证后再转换
int len = atoi(input); // 假设已验证 > 0
if (len > 0 && len < 1000) { // 验证通过
    long buffer_size = len; // 在条件内看似安全
}
// 但如果在验证前存在 sign extension，可能导致问题

// 6. 结构体中的转换
struct Packet {
    short length; // 网络字节序，可能是负数
} pkt;
unsigned long total = pkt.length; // 符号扩展后变成巨大数值
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 类型转换涉及: `short`, `char`, `int` 转换为 `long`, `long long`, `size_t`, `unsigned int`
- 内存操作: `malloc()`, `calloc()`, `realloc()`, `memcpy()`, `memset()`, `buffer[index]`
- 用户输入来源: `read()`, `recv()`, `fread()`, `atoi()`, `strtol()`, 网络包解析
- 关键词: `cast`, `(long)`, `(unsigned int)`, `(size_t)`, 显式或隐式转换
- 跨字节序处理: `ntohs()`, `ntohl()`, `htons()`, 网络字节序转换后未验证

**L2 跳读定位**:
- 追踪用户输入从读取到转换的路径
- 寻找窄类型变量（short, char, int）向宽类型（long, size_t, unsigned int）的赋值
- 重点关注: 转换后直接用于内存分配、数组索引、长度参数
- 检查转换前是否存在有效范围检查
- 注意隐式转换（如函数参数传递）可能导致的类型升级

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 范围检查: 转换前对值进行验证，如 `if (val < 0 || val > MAX)`
- 负数判断: 显式检查 `if (val < 0)` 并拒绝处理
- 类型使用: 从源头使用无符号类型（`unsigned short`, `uint32_t`）避免符号扩展
- 安全转换: 使用饱和算法或检查转换后的值有效性

**L3 逐行分析**:
- 转换点分析:
  - 确认源类型是否有符号（`signed char`, `short`, `int`）
  - 确认转换后的类型范围是否扩展（窄到宽）
  - 验证转换前是否已进行范围验证
- 验证逻辑检查:
  - 范围检查使用的边界值是否包含负数处理（应排除负值）
  - 是否在类型转换发生前进行检查，而非转换后
  - 检查是否使用了错误的类型进行比较（如与 unsigned 比较的 signed 值）
- 隐式转换陷阱:
  - 函数参数类型匹配（`malloc(size_t)` 但传入 `int`）
  - 赋值时的隐式转换（`size_t sz = signed_var;`）
  - 算术运算中的自动类型提升

**L4 跨模块追踪**:
- 追踪读取数据的源函数实现（`read()`, `recv()`, `parse_packet()`）
- 验证网络字节序转换函数的返回值范围
- 检查上游模块是否有输入验证，下游是否重复验证
- 追踪宏定义和类型别名，确认实际类型而非名字假象
- 检查编译器警告级别（`-Wconversion`, `-Wsign-conversion`）是否启用

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 窄的有符号类型直接转换为宽类型，用于内存分配或长度计算，且转换前无有效的负数检查
- 转换后的值可被攻击者通过输入直接控制为负数，经符号扩展后变成巨大正数
- 转换后的值用于缓冲区操作（memcpy, strcpy 等）、数组索引或内存分配，可导致溢出
- 存在明显的有符号/无符号混用，如 `ssize_t` 与 `size_t` 混淆导致的逻辑错误
- 网络协议解析时，未验证转换后的值在合理范围内就直接使用

**误报判定**:
- 源类型本身就是无符号（`unsigned int`, `uint32_t`），不存在符号扩展问题
- 转换前存在严格的范围检查，确保值在 `[0, MAX_SAFE_VALUE]` 范围内
- 转换后的值仅用于只读操作（如日志记录）或无关键业务逻辑
- 数据来源受信任且严格验证（如内部算法输出而非用户输入）
- 宽类型的使用仅用于外部表示，核心业务逻辑在转换前已完成

**代码异味**:
- 存在多级类型转换（`signed char` → `int` → `long`），每级可能引入新的转换问题
- 使用了显式强制转换而非隐式转换，且转换前无检查（表明开发者知道有风险但未处理）
- 混用不同宽度的类型进行算术运算，隐式类型提升可能导致符号变化
- 对同一值进行不同类型的多次使用，不同代码路径对类型的假设不一致

---

## Low risk

### 低风险场景

**源类型控制**:
- 从源头使用无符号整数类型（`unsigned short`, `uint32_t`, `size_t`），完全避免符号扩展
- 数据来源是可信的内部系统模块或硬编码值，不经过用户输入

**验证防护**:
- 在任何转换前显式检查值是否为负：`if (value < 0) { return error; }`
- 使用饱和转换或检查函数，确保转换结果在预期范围内
- 转换后的值再次验证其上界，如 `if (converted > MAX_SAFE_SIZE) { return error; }`

**使用场景隔离**:
- 转换后的值仅用于比较、日志或只读查询，不用于内存分配或数组索引
- 转换后的值在进入关键代码路径前经过再次验证
- 类型转换仅用于外部 API 兼容，核心业务逻辑在转换前完成

**编译和工具防护**:
- 启用编译器严格警告（`-Wconversion`, `-Wsign-conversion`），所有警告均被修复
- 使用静态分析工具（Clang Static Analyzer, Coverity）检测类型转换问题
- 运行时使用 AddressSanitizer 或 UBSan 检测溢出和未定义行为

**设计层防护**:
- API 设计明确指定返回值范围（如注释说明返回值总是非负）
- 使用类型系统强制要求（如定义 `SafeSize` 类型别名强制进行验证）
- 缓冲区操作使用安全 API（C++ std::vector, std::string）避免手动内存管理
