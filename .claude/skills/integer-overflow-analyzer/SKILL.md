---
name: integer-overflow-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证整数溢出漏洞；重点关注检测数值运算、内存分配、类型转换、循环控制等场景中，整数运算结果超出数据类型的表示范围，导致缓冲区溢出、逻辑绕过、拒绝服务等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用整数溢出漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：危险操作类型（算术运算溢出、乘法溢出、加法溢出、减法下溢）、内存分配和缓冲区操作（基于用户输入的内存分配、缓冲区大小计算、数组索引越界）、业务逻辑和安全检查（计数器溢出、边界检查绕过、权限验证绕过、金额计算溢出）、类型转换和比较（有符号/无符号转换、类型提升、比较操作溢出）、流程控制和循环（循环边界条件、循环计数器溢出、迭代次数未限制）、常量溢出（编译时常量溢出、硬编码值溢出）、位操作和移位（左移溢出、右移符号扩展、位运算溢出）

**整数溢出漏洞（Integer Overflow）**

**Attention**  
当项目中涉及整数运算、内存分配、数组索引、循环控制、类型转换等操作时，需重点审计整数运算结果是否可能超出数据类型的表示范围。此类漏洞通常出现在算术运算（加减乘除）、内存分配大小计算、数组索引计算、循环计数器、类型转换（有符号/无符号、窄类型到宽类型）、位操作和移位等场景中，常见于数值处理、内存管理、缓冲区操作、业务逻辑计算、安全验证等模块。

**Early exit**  
若项目完全不涉及任何整数运算、内存分配、数组操作、循环控制等数值计算逻辑（如纯静态内容服务、纯配置驱动无计算逻辑），或所有数值计算均在安全的数值范围内且经过严格验证，则可快速退出对该漏洞类型的审计。

**Cases**

**C/C++**
算术运算溢出，包括加法、减法、乘法运算结果超出数据类型表示范围，详见：[C_Arithmetic_Overflow.md](C_Arithmetic_Overflow.md)
→ 遇到溢出检查保护（如 `if (a > INT_MAX - b)`），参考 [bypassTricks.md § 1](bypassTricks.md#1-算术运算溢出绕过)

基于用户输入的内存分配，malloc/calloc/realloc 使用未验证的用户输入作为分配大小，详见：[C_Memory_Allocation_User_Input.md](C_Memory_Allocation_User_Input.md)
→ 遇到分配大小检查保护（如 `if (size > MAX_ALLOC)`），参考 [bypassTricks.md § 2](bypassTricks.md#2-内存分配绕过)

数组索引越界，使用用户输入或计算结果作为数组索引时未检查边界，详见：[C_Array_Index_Out_Of_Bounds.md](C_Array_Index_Out_Of_Bounds.md)
→ 遇到边界检查保护（如 `if (index >= length)`），参考 [bypassTricks.md § 2.2](bypassTricks.md#22-数组越界利用)

有符号/无符号类型转换导致的溢出，有符号整数转换为无符号时符号位被解释为数值，详见：[C_Signed_Unsigned_Conversion.md](C_Signed_Unsigned_Conversion.md)
→ 遇到类型转换验证保护（如 `if (signed_value < 0)`），参考 [bypassTricks.md § 3](bypassTricks.md#3-类型转换溢出绕过)

循环计数器溢出，循环边界条件计算不当导致无限循环或提前退出，详见：[C_Loop_Counter_Overflow.md](C_Loop_Counter_Overflow.md)
→ 遇到循环边界检查保护（如 `i < count && i != INT_MAX`），参考 [bypassTricks.md § 4](bypassTricks.md#4-循环边界绕过)

常量溢出，编译时常量或硬编码值超出数据类型范围，详见：[C_Constant_Overflow.md](C_Constant_Overflow.md)
→ 遇到编译时常量验证，参考 [bypassTricks.md § 1](bypassTricks.md#1-算术运算溢出绕过)

位操作和移位溢出，左移操作导致符号位改变或超出范围，详见：[C_Bitwise_Shift_Overflow.md](C_Bitwise_Shift_Overflow.md)
→ 遇到移位量检查保护（如 `if (shift >= 32)`），参考 [bypassTricks.md § 6](bypassTricks.md#6-位操作溢出绕过)

**Java**
整数运算溢出，加减乘运算结果超出 int 或 long 类型范围，详见：[Java_Integer_Arithmetic_Overflow.md](Java_Integer_Arithmetic_Overflow.md)
→ 遇到 Math.addExact/multiplyExact 等保护，参考 [bypassTricks.md § 7.1](bypassTricks.md#71-integer-溢出)

数组长度计算溢出，使用用户输入或计算结果创建数组时未验证长度，详见：[Java_Array_Length_Overflow.md](Java_Array_Length_Overflow.md)
→ 遇到数组长度检查保护，参考 [bypassTricks.md § 2 & § 7.1](bypassTricks.md#71-integer-溢出)

类型转换导致的溢出，窄类型向宽类型转换时的符号扩展问题，详见：[Java_Type_Casting_Overflow.md](Java_Type_Casting_Overflow.md)
→ 遇到类型转换验证保护，参考 [bypassTricks.md § 3 & § 7.1](bypassTricks.md#71-integer-溢出)

业务逻辑中的计数器溢出，积分、金额等业务计数器未检查溢出，详见：[Java_Business_Counter_Overflow.md](Java_Business_Counter_Overflow.md)
→ 遇到业务数值检查保护（如使用 BigInteger/BigDecimal），参考 [bypassTricks.md § 5 & § 7.1](bypassTricks.md#71-integer-溢出)

循环边界条件计算不当，for/while 循环中使用可能导致溢出的表达式，详见：[Java_Loop_Boundary_Overflow.md](Java_Loop_Boundary_Overflow.md)
→ 遇到循环边界检查保护，参考 [bypassTricks.md § 4](bypassTricks.md#4-循环边界绕过)

集合大小计算溢出，ArrayList、HashMap 等集合的大小计算或扩容逻辑存在溢出风险，详见：[Java_Collection_Size_Overflow.md](Java_Collection_Size_Overflow.md)
→ 遇到集合容量验证保护，参考 [bypassTricks.md § 7.1](bypassTricks.md#71-integer-溢出)

位操作溢出，移位或位运算结果超出类型范围，详见：[Java_Bitwise_Operation_Overflow.md](Java_Bitwise_Operation_Overflow.md)
→ 遇到位操作验证保护，参考 [bypassTricks.md § 6](bypassTricks.md#6-位操作溢出绕过)

**Python**
整数运算溢出，Python 2 中整数运算可能溢出，Python 3 整数无限精度但仍需关注内存分配，详见：[Python_Integer_Arithmetic_Overflow.md](Python_Integer_Arithmetic_Overflow.md)
→ 遇到大整数长度检查保护（如 `len(str(big_int)) > MAX_DIGITS`），参考 [bypassTricks.md § 7.2](bypassTricks.md#72-大整数操作)

数组或列表大小计算溢出，使用 NumPy 数组或其他扩展时基于用户输入创建数组，详见：[Python_Array_Size_Overflow.md](Python_Array_Size_Overflow.md)
→ 遇到数组大小验证保护，参考 [bypassTricks.md § 2 & § 7.2](bypassTricks.md#72-大整数操作)

类型转换溢出，将大整数转换为 C 扩展或特定类型时的溢出，详见：[Python_Type_Conversion_Overflow.md](Python_Type_Conversion_Overflow.md)
→ 遇到 ctypes/numpy 类型转换验证保护，参考 [bypassTricks.md § 7.2](bypassTricks.md#72-大整数操作)

业务逻辑计数器溢出，金额计算、积分累计等业务逻辑未检查溢出，详见：[Python_Business_Logic_Overflow.md](Python_Business_Logic_Overflow.md)
→ 遇到业务数值检查保护，参考 [bypassTricks.md § 5](bypassTricks.md#5-业务逻辑溢出绕过)

循环边界计算问题，range() 函数参数或循环条件使用用户输入，详见：[Python_Loop_Boundary_Issue.md](Python_Loop_Boundary_Issue.md)
→ 遇到循环边界检查保护，参考 [bypassTricks.md § 4](bypassTricks.md#4-循环边界绕过)

缓冲区操作溢出，使用 ctypes 或 C 扩展时缓冲区大小计算不当，详见：[Python_Buffer_Operation_Overflow.md](Python_Buffer_Operation_Overflow.md)
→ 遇到缓冲区大小验证保护，参考 [bypassTricks.md § 2.3](bypassTricks.md#23-缓冲区大小计算绕过)

位运算溢出，使用位操作或移位时的溢出风险，详见：[Python_Bitwise_Operation_Overflow.md](Python_Bitwise_Operation_Overflow.md)
→ 遇到位操作验证保护，参考 [bypassTricks.md § 6](bypassTricks.md#6-位操作溢出绕过)

**Go**
整数运算溢出，Go 中整数溢出是未定义行为，需检查溢出检测机制，详见：[Go_Integer_Arithmetic_Overflow.md](Go_Integer_Arithmetic_Overflow.md)
→ 遇到手动溢出检查保护，参考 [bypassTricks.md § 1](bypassTricks.md#1-算术运算溢出绕过)

切片容量计算溢出，make() 函数创建切片时使用用户输入作为容量参数，详见：[Go_Slice_Capacity_Overflow.md](Go_Slice_Capacity_Overflow.md)
→ 遇到容量大小检查保护，参考 [bypassTricks.md § 2](bypassTricks.md#2-内存分配绕过)

类型转换溢出，不同整数类型之间的转换可能导致溢出或截断，详见：[Go_Type_Conversion_Overflow.md](Go_Type_Conversion_Overflow.md)
→ 遇到类型转换验证保护，参考 [bypassTricks.md § 3](bypassTricks.md#3-类型转换溢出绕过)

数组索引越界，使用计算结果作为数组或切片索引时未检查边界，详见：[Go_Array_Index_Out_Of_Bounds.md](Go_Array_Index_Out_Of_Bounds.md)
→ 遇到索引边界检查保护，参考 [bypassTricks.md § 2.2](bypassTricks.md#22-数组越界利用)

循环边界条件问题，for 循环中使用可能导致溢出的表达式或条件，详见：[Go_Loop_Boundary_Issue.md](Go_Loop_Boundary_Issue.md)
→ 遇到循环边界检查保护，参考 [bypassTricks.md § 4](bypassTricks.md#4-循环边界绕过)

内存分配溢出，unsafe 包或 CGO 调用中的内存分配大小计算，详见：[Go_Memory_Allocation_Overflow.md](Go_Memory_Allocation_Overflow.md)
→ 遇到 unsafe 内存分配大小检查保护，参考 [bypassTricks.md § 2](bypassTricks.md#2-内存分配绕过)

位操作溢出，左移或位运算结果超出类型范围，详见：[Go_Bitwise_Operation_Overflow.md](Go_Bitwise_Operation_Overflow.md)
→ 遇到位操作验证保护，参考 [bypassTricks.md § 6](bypassTricks.md#6-位操作溢出绕过)

**PHP**
整数运算溢出，PHP 整数溢出在 64 位系统上较少，但 32 位系统或大整数处理需关注，详见：[PHP_Integer_Arithmetic_Overflow.md](PHP_Integer_Arithmetic_Overflow.md)
→ 遇到整数范围检查保护，参考 [bypassTricks.md § 1](bypassTricks.md#1-算术运算溢出绕过)

数组长度计算溢出，使用用户输入创建数组或字符串时长度计算不当，详见：[PHP_Array_Length_Overflow.md](PHP_Array_Length_Overflow.md)
→ 遇到数组长度验证保护，参考 [bypassTricks.md § 2](bypassTricks.md#2-内存分配绕过)

类型转换溢出，字符串到整数转换、浮点数到整数转换时的溢出，详见：[PHP_Type_Conversion_Overflow.md](PHP_Type_Conversion_Overflow.md)
→ 遇到类型转换验证保护（如 is_numeric 检查），参考 [bypassTricks.md § 3](bypassTricks.md#3-类型转换溢出绕过)

业务逻辑计数器溢出，金额、积分等业务数值计算未检查溢出，详见：[PHP_Business_Counter_Overflow.md](PHP_Business_Counter_Overflow.md)
→ 遇到业务数值检查保护，参考 [bypassTricks.md § 5](bypassTricks.md#5-业务逻辑溢出绕过)

循环边界计算问题，for/while 循环中使用用户输入或计算结果作为边界条件，详见：[PHP_Loop_Boundary_Issue.md](PHP_Loop_Boundary_Issue.md)
→ 遇到循环边界检查保护，参考 [bypassTricks.md § 4](bypassTricks.md#4-循环边界绕过)

字符串操作溢出，substr、str_repeat 等函数使用大数值参数，详见：[PHP_String_Operation_Overflow.md](PHP_String_Operation_Overflow.md)
→ 遇到字符串长度验证保护，参考 [bypassTricks.md § 2](bypassTricks.md#2-内存分配绕过)

哈希或加密算法中的整数溢出，自定义加密算法中的数值计算，详见：[PHP_Crypto_Integer_Overflow.md](PHP_Crypto_Integer_Overflow.md)
→ 遇到加密算法数值验证保护，参考 [bypassTricks.md § 1](bypassTricks.md#1-算术运算溢出绕过)

**JavaScript/TypeScript**
整数运算溢出，JavaScript 使用双精度浮点数，但仍需关注位运算和大整数处理，详见：[JavaScript_Integer_Arithmetic_Overflow.md](JavaScript_Integer_Arithmetic_Overflow.md)
→ 遇到 Number.MAX_SAFE_INTEGER 检查保护，参考 [bypassTricks.md § 7.3](bypassTricks.md#73-浮点精度绕过)

TypedArray 溢出，使用 Int8Array、Uint32Array 等类型化数组时的溢出风险，详见：[JavaScript_TypedArray_Overflow.md](JavaScript_TypedArray_Overflow.md)
→ 遇到 TypedArray 边界检查保护，参考 [bypassTricks.md § 7.3](bypassTricks.md#73-浮点精度绕过)

数组长度计算溢出，使用用户输入创建数组或设置数组长度时未验证，详见：[JavaScript_Array_Length_Overflow.md](JavaScript_Array_Length_Overflow.md)
→ 遇到数组长度验证保护，参考 [bypassTricks.md § 2](bypassTricks.md#2-内存分配绕过)

类型转换溢出，字符串到数字转换、位运算时的溢出，详见：[JavaScript_Type_Conversion_Overflow.md](JavaScript_Type_Conversion_Overflow.md)
→ 遇到类型转换验证保护（如 Number.isSafeInteger），参考 [bypassTricks.md § 7.3](bypassTricks.md#73-浮点精度绕过)

业务逻辑计数器溢出，金额计算、积分累计等业务逻辑未检查溢出，详见：[JavaScript_Business_Logic_Overflow.md](JavaScript_Business_Logic_Overflow.md)
→ 遇到业务数值检查保护，参考 [bypassTricks.md § 5](bypassTricks.md#5-业务逻辑溢出绕过)

循环边界条件问题，for/while 循环中使用可能导致溢出的表达式，详见：[JavaScript_Loop_Boundary_Issue.md](JavaScript_Loop_Boundary_Issue.md)
→ 遇到循环边界检查保护，参考 [bypassTricks.md § 4](bypassTricks.md#4-循环边界绕过)

BigInt 操作溢出，使用 BigInt 类型时与普通整数类型转换的溢出风险，详见：[JavaScript_BigInt_Overflow.md](JavaScript_BigInt_Overflow.md)
→ 遇到 BigInt 转换验证保护，参考 [bypassTricks.md § 7.3](bypassTricks.md#73-浮点精度绕过)

**Rust**
整数运算溢出，Rust 默认在调试模式下检查溢出，但发布模式下需使用 checked_* 方法，详见：[Rust_Integer_Arithmetic_Overflow.md](Rust_Integer_Arithmetic_Overflow.md)
→ 遇到 checked_*/saturating_*/wrapping_* 方法保护，参考 [bypassTricks.md § 1](bypassTricks.md#1-算术运算溢出绕过)

Vec 容量计算溢出，Vec::with_capacity() 或 Vec::reserve() 使用用户输入作为容量参数，详见：[Rust_Vec_Capacity_Overflow.md](Rust_Vec_Capacity_Overflow.md)
→ 遇到容量大小检查保护，参考 [bypassTricks.md § 2](bypassTricks.md#2-内存分配绕过)

数组索引越界，使用计算结果作为数组索引时未使用边界检查，详见：[Rust_Array_Index_Out_Of_Bounds.md](Rust_Array_Index_Out_Of_Bounds.md)
→ 遇到 get()/get_mut() 边界检查保护，参考 [bypassTricks.md § 2.2](bypassTricks.md#22-数组越界利用)

类型转换溢出，as 关键字进行类型转换时的截断或溢出，详见：[Rust_Type_Casting_Overflow.md](Rust_Type_Casting_Overflow.md)
→ 遇到 TryFrom/TryInto trait 验证保护，参考 [bypassTricks.md § 3](bypassTricks.md#3-类型转换溢出绕过)

循环边界条件问题，for 循环中使用可能导致溢出的表达式，详见：[Rust_Loop_Boundary_Issue.md](Rust_Loop_Boundary_Issue.md)
→ 遇到循环迭代器边界检查保护，参考 [bypassTricks.md § 4](bypassTricks.md#4-循环边界绕过)

unsafe 代码中的溢出，unsafe 块中直接进行指针算术或内存操作，详见：[Rust_Unsafe_Integer_Overflow.md](Rust_Unsafe_Integer_Overflow.md)
→ 遇到 unsafe 块内的手动检查保护，参考 [bypassTricks.md § 2 & § 3](bypassTricks.md#2-内存分配绕过)

位操作溢出，左移或位运算结果超出类型范围，详见：[Rust_Bitwise_Operation_Overflow.md](Rust_Bitwise_Operation_Overflow.md)
→ 遇到位操作验证保护，参考 [bypassTricks.md § 6](bypassTricks.md#6-位操作溢出绕过)

## 整数溢出绕过技巧与保护机制验证

在进行整数溢出漏洞审计时，特别是验证防护机制的有效性，需要了解常见的绕过技巧。**当遇到以下保护机制时，请查阅 [bypassTricks.md](bypassTricks.md) 中的相应章节**：

### 保护机制绕过索引

#### 1. 算术运算溢出检查保护
**遇到场景**：代码中使用 `if (a > INT_MAX - b)` 等溢出检查、或使用安全库函数（如 `__builtin_add_overflow`、`Math.addExact` 等）
**绕过技巧**：详见 [bypassTricks.md § 1. 算术运算溢出绕过](bypassTricks.md#1-算术运算溢出绕过)
- § 1.1 编译器优化绕过：使用 volatile、浮点中间计算、汇编指令
- § 1.2 符号扩展利用：无符号转换、多步操作分散检查
- § 1.3 乘法溢出绕过：浮点数乘法、负数相乘、位移代替、分解乘法

#### 2. 内存分配大小验证保护
**遇到场景**：malloc/calloc/new 之前检查分配大小、验证 `size > MAX_ALLOC` 或 `count > MAX_COUNT`
**绕过技巧**：详见 [bypassTricks.md § 2. 内存分配绕过](bypassTricks.md#2-内存分配绕过)
- § 2.1 大小计算绕过：无符号溢出返回 0、负数转换为大数值、分解计算累积溢出
- § 2.2 数组越界利用：负索引访问前置内存、整数溢出后环绕、两阶段漏洞
- § 2.3 缓冲区大小计算绕过：格式字符串注入、环绕整数绕过检查、多次累积溢出

#### 3. 类型转换验证保护
**遇到场景**：有符号/无符号转换前检查 `signed_value < 0`、宽类型转窄类型前范围检查
**绕过技巧**：详见 [bypassTricks.md § 3. 类型转换溢出绕过](bypassTricks.md#3-类型转换溢出绕过)
- § 3.1 隐式转换绕过：按位操作直接内存转换、联合体转换、函数指针转换
- § 3.2 窄类型转换绕过：多步转换逐级绕过、浮点中间转换、位掩码提取
- § 3.3 指针转换绕过：整数中间值溢出、intptr_t 有符号溢出、分块转换

#### 4. 循环边界条件检查保护
**遇到场景**：循环条件中检查 `i < count && i != INT_MAX`、指针边界验证 `ptr < buffer + size`
**绕过技巧**：详见 [bypassTricks.md § 4. 循环边界绕过](bypassTricks.md#4-循环边界绕过)
- § 4.1 计数器溢出：无符号计数器环绕、浮点精度导致循环次数偏差、循环内修改计数器、乘法递增溢出
- § 4.2 边界条件绕过：指针算术溢出环绕、ptrdiff_t 负数溢出、条件短路时已溢出、浮点边界精度损失

#### 5. 业务逻辑数值验证保护
**遇到场景**：金额检查 `amount > MAX_AMOUNT`、计数器上限 `count >= MAX_COUNT`、权限级别 `user_level >= ADMIN_LEVEL`
**绕过技巧**：详见 [bypassTricks.md § 5. 业务逻辑溢出绕过](bypassTricks.md#5-业务逻辑溢出绕过)
- § 5.1 金额计算绕过：负数绕过正数上限检查、小数舍入累积误差、货币换算错误、分散充值累积溢出
- § 5.2 计数器溢出：整数溢出重置为负数、多计数器独立绕过、时间窗口边界竞争、分布式计数器总和溢出
- § 5.3 权限检查绕过：负数转换为大无符号值、权限位移位溢出、权限叠加溢出回绕

#### 6. 位操作和移位验证保护
**遇到场景**：移位前检查 `shift >= 32`、位掩码验证 `bits < 32`、使用无符号右移避免符号扩展
**绕过技巧**：详见 [bypassTricks.md § 6. 位操作溢出绕过](bypassTricks.md#6-位操作溢出绕过)
- § 6.1 左移溢出：取模运算溢出、负数移位未定义行为、多步移位累积、浮点转换移位量
- § 6.2 右移符号扩展：强制转换为有符号类型、算术右移提取符号位、循环移位边界未定义
- § 6.3 位掩码溢出：bits >= 32 时未定义行为、长整数掩码在 32 位系统溢出、多步构建掩码溢出、查表越界

#### 7. 特定语言防护机制
**遇到场景**：Java 使用 `BigInteger`、Python 3 无限精度整数、JavaScript `Number.isSafeInteger` 检查
**绕过技巧**：详见 [bypassTricks.md § 7. 特定语言绕过](bypassTricks.md#7-特定语言绕过)
- § 7.1 Java Integer 溢出：long 中间计算再截断、数组长度溢出、集合容量翻倍溢出
- § 7.2 Python 大整数操作：numpy 有限精度数组、ctypes C 类型溢出、分块处理内存溢出
- § 7.3 JavaScript 浮点精度绕过：BigInt 转 Number 精度损失、TypedArray 固定精度溢出、位运算强制 32 位转换

### 防护机制强度评估

参考 [bypassTricks.md § 8. 防护机制检查清单](bypassTricks.md#8-防护机制检查清单)：

| 防护机制 | 绕过难度 | 审计重点 |
|---------|---------|---------|
| 简单范围检查 | 低 | 负数输入、类型转换、多步操作 |
| 溢出检查函数 | 低-中 | 浮点中间计算、位操作替代、编译器优化 |
| 类型验证 | 低-中 | 隐式转换、联合体、指针强转 |
| 指针算术验证 | 中 | 指针溢出环绕、intptr_t 差异 |
| BigInteger / 无限精度 | 中-高 | 内存限制、C 扩展类型转换 |
| 编译器内置检查 | 高 | 优化禁用、汇编直接操作 |

### 审计实施指南

详见 [bypassTricks.md § 9. 审计建议](bypassTricks.md#9-审计建议)：

**高风险信号**：
- 使用简单范围检查而非语言内置溢出检查函数
- 多步整数操作链，任一环节可能溢出
- 频繁类型转换（特别是有符号/无符号、指针/整数）
- 循环条件依赖可溢出的计算结果
- 业务逻辑使用固定精度整数而非 BigInteger/BigDecimal

**验证步骤**：
1. 识别所有整数操作点（算术、类型转换、位操作）
2. 追踪输入源（用户可控数据流）
3. 评估现有防护机制（检查完整性和正确性）
4. **使用 bypassTricks 中的技巧尝试绕过**
5. 分析利用后果（缓冲区溢出、权限绕过、拒绝服务等）
6. 生成标准化漏洞报告

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-integer-overflow-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

