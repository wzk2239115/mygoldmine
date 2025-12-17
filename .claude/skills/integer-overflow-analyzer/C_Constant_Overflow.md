# C_Constant_Overflow

**漏洞类型**: 常量溢出，编译时常量或硬编码值超出数据类型范围

**C/C++**

---

## Details

**代码示例**：`#define MAX 0x7FFFFFFF + 1`、`const int LIMIT = 2147483648`、`int x = 0xFFFFFFFF;`、`size_t len = 0xFFFFFFFF; malloc(len + 1);`

### 核心操作定位技巧 (L1: 关键词扫描)

- 扫描关键字：`#define`、`const`、`enum`、`static const` 等常量定义位置
- 识别数值格式：十六进制(`0x...`)、八进制(`0...`)、科学计数法(`1e9`)、硬编码十进制数值
- 数值后缀检查：`L`(long)、`UL`(unsigned long)、`LL`(long long)、`ULL`(unsigned long long)、`U`(unsigned)、`F`(float)
- 敏感操作上下文扫描：常量用于 `malloc/calloc/realloc` 大小、数组维度、位运算掩码、类型转换源值
- 数值范围对标：int(±2^31-1)、unsigned int(2^32-1)、long(32位系统2^31-1)、size_t(平台相关)

### 保护机制定位技巧 (L2: 跳读)

- 编译器警告检查：编译命令中是否启用 `-Wall -Wextra -Wconversion -Woverflow`；查看编译日志中的常量溢出警告
- 类型前向声明：检查常量定义前是否有类型显式声明或转换；例如 `(unsigned long)0xFFFFFFFF` 的意图表示
- 三方工具验证：项目是否集成 Clang Static Analyzer、Coverity 等工具，其报告中常量溢出的处理方式
- 代码审查记录：搜索 CHANGELOG/Commit Message 中是否有常量值调整或"intentional overflow"等注释
- 运行时实现：某些溢出常量是否被运行时模块验证或限制（如 mempool 对分配大小的上界检查）

---

## Classify

### 判断维度

**确定真实漏洞**：
1. 常量溢出后的值被直接用于**内存分配**（malloc 参数）、**数组大小**、**缓冲区操作**等敏感上下文
2. 溢出导致的值变为**不合预期**（如负数、超大数）且**无后续检查**
3. 跨模块追踪(L4)发现：常量被外部模块使用，导致对其含义理解错误

示例：`#define BUF_SIZE 0x80000000` 用于 `char buf[BUF_SIZE];` → 真实漏洞（栈溢出或编译失败）

**识别误报**：
1. 常量值本身在类型范围内（检查时用错了数值大小）
2. 溢出是**故意的、已知的**行为（如用于 Hash 函数 `hash = (hash * 31 + c) & 0xFFFFFFFF;`）
3. 常量仅用于**参考/注释用途**，未被代码逻辑使用
4. 类型已正确指定（如 `unsigned long long LARGE = 0x100000000LL;` 在64位系统安全）

示例：`#define SEED 0x9e3779b97f4a7c15` 用于 hash 初始化 → 误报（设计意图）

**代码异味**（需进一步验证）：
1. 常量定义与使用上下文不一致（如定义时后缀为 `U`，但赋值给 `signed int`）
2. 多个平台/编译器条件编译常量，值不统一
3. 常量值恰好接近类型边界（如 `0x7FFFFFFF + 1`），可能是复制粘贴错误

---

## 审计经验与技巧

### 现场审计策略

- **初筛**：在编译阶段直接使用 `-Woverflow -Wconstant-conversion` 编译，获取编译器诊断列表
- **上下文验证**：找到常量定义后，立即 grep 其使用位置，追踪到最终敏感操作（L3/L4 阶段）
- **类型溯源**：对于 `#define` 宏，检查所有包含该头文件的源文件中的实际使用类型
- **版本对比**：在公开 CVE 或补丁中搜索该项目名+常量溢出，快速判断已知风险

### 常见误区

1. **数值大小判断错误**：审计者误算十六进制，如将 `0xFFFFFFFF` 错认为小于 `int` 上限
   - 解决：使用在线计算器或 Python: `0xFFFFFFFF == 4294967295`
2. **忽视平台差异**：在32位和64位系统中，`long` 的大小不同
   - 解决：检查 `#ifdef __LP64__` 或 `#ifdef _WIN32` 条件编译
3. **混淆编译期与运行期**：编译时合法的常量不代表运行时使用安全
   - 解决：追踪常量使用的运行时上下文，如 memcpy 时的边界检查
4. **遗漏隐式转换**：常量可能在赋值或函数调用时被隐式截断
   - 解决：启用 `-Wconversion` 编译选项，观察隐式转换警告

### 真实案例对标

**案例1（真实漏洞）**：
```c
#define CHUNK_SIZE 0xFFFFFFFF
size_t total = CHUNK_SIZE + sizeof(header);  // 溢出为0x100000000+, 截断后变小
malloc(total);  // 分配过小缓冲区 → 堆溢出
```
**审计判断**：常量溢出 + 用于内存计算 + 无检查 = 确定漏洞

**案例2（误报）**：
```c
#define FNV_PRIME 0x01000193
unsigned int hash = FNV_PRIME;  // 类型正确，值在范围内
```
**审计判断**：常量在类型范围内 = 误报

---

## Low risk 指标

- 常量定义中显式使用了合适的类型后缀（UL、ULL、L）
- 编译器无溢出警告（-Wall -Wextra -Woverflow 下）
- 常量仅用于计算、日志输出、格式字符串、条件判断
- 常量使用点存在显式类型检查或上界验证
- 在 Coverity/MISRA 等工具扫描中无标记
- 代码注释明确说明溢出是意图设计（如 "Intentional wrapping for hash"）

