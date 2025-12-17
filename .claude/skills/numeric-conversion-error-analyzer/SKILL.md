---
name: numeric-conversion-error-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证数值类型转换缺陷（CWE-681）；重点关注检测在不同数值类型（整型、浮点、无符号/有符号、不同位宽）之间进行强制转换或隐式转换时，因未校验范围、精度或符号而导致溢出、截断、符号反转、精度丢失等问题，包括跨语言边界（如 Java Native Interface、Python C 扩展、RPC 序列化）以及算术运算后的立即转换、数组索引计算、内存分配大小计算、协议字段解包等场景，从而引发后续缓冲区溢出、逻辑绕过、拒绝服务、越界读写或资金计算错误等连锁安全风险；利用按编程语言组织的参考资料目录中的参考指南定位高危转换路径，并提供修复建议（边界检查、饱和转换、安全封装类、静态断言、编译器告警加固等）。
---

## 通用数值类型转换错误漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：有符号/无符号转换（符号位被解释为数值、负数转无符号导致巨大正数）、不同位宽转换（窄类型到宽类型符号扩展、宽类型到窄类型截断）、整型与浮点转换（浮点转整型精度丢失、整型转浮点精度限制）、跨语言边界转换（JNI类型转换、Python C扩展、RPC序列化、FFI调用）、算术运算后立即转换（运算结果未验证直接转换、中间值溢出）、数组索引计算转换（索引值类型转换、边界检查绕过）、内存分配大小计算转换（分配大小类型转换、整数溢出）、协议字段解包转换（网络协议解析、字节序转换、字段类型转换）、精度丢失（浮点精度、大整数精度、货币计算精度）

**数值类型转换错误漏洞（Numeric Conversion Error, CWE-681）**

**Attention**  
当项目中涉及不同数值类型之间的转换操作时，需重点审计强制转换或隐式转换是否可能导致溢出、截断、符号反转、精度丢失等问题。此类漏洞通常出现在有符号/无符号类型转换、不同位宽类型转换（如 int 转 short、long 转 int）、整型与浮点类型转换、跨语言边界转换（JNI、C扩展、RPC）、算术运算后的立即转换、数组索引计算、内存分配大小计算、协议字段解包等场景中，常见于数值处理、内存管理、缓冲区操作、网络协议解析、跨语言接口、业务逻辑计算等模块。

**Early exit**  
若项目完全不涉及任何数值类型转换操作（如纯字符串处理、纯逻辑判断无数值计算）、或所有类型转换均经过严格的边界检查、范围验证和精度保护，且不存在跨语言边界调用，则可快速退出对该漏洞类型的审计。

**Cases**

**C/C++**
有符号/无符号转换，负数转换为无符号类型时符号位被解释为数值，详见：[C_Signed_Unsigned_Conversion.md](C_Signed_Unsigned_Conversion.md) | 遇到范围检查、类型验证保护机制，详见：[bypassTricks.md#有符号无符号转换绕过](bypassTricks.md#1-有符号无符号转换绕过)
窄类型到宽类型转换，短整型扩展为长整型时的符号扩展问题，详见：[C_Narrow_To_Wide_Conversion.md](C_Narrow_To_Wide_Conversion.md) | 遇到符号扩展验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
宽类型到窄类型转换，长整型截断为短整型时的溢出和截断，详见：[C_Wide_To_Narrow_Conversion.md](C_Wide_To_Narrow_Conversion.md) | 遇到超出范围检查保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
浮点与整型转换，浮点数转整型时的精度丢失和截断，详见：[C_Float_To_Integer_Conversion.md](C_Float_To_Integer_Conversion.md) | 遇到精度检查、范围验证保护机制，详见：[bypassTricks.md#浮点与整型转换绕过](bypassTricks.md#3-浮点与整型转换绕过)
指针与整数转换，指针与整数类型之间的不安全转换，详见：[C_Pointer_Integer_Conversion.md](C_Pointer_Integer_Conversion.md) | 遇到指针有效性验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#23-指针和整数转换)
内存分配大小转换，malloc/calloc/realloc 使用转换后的值作为分配大小，详见：[C_Memory_Allocation_Conversion.md](C_Memory_Allocation_Conversion.md) | 遇到乘法溢出检查保护机制，详见：[bypassTricks.md#内存分配大小转换](bypassTricks.md#6-内存分配大小转换)
数组索引转换，数组索引计算中的类型转换问题，详见：[C_Array_Index_Conversion.md](C_Array_Index_Conversion.md) | 遇到索引范围验证、负数检查保护机制，详见：[bypassTricks.md#数组索引转换绕过](bypassTricks.md#5-数组索引转换绕过)
协议字段解包转换，网络协议解析中的字节序和类型转换，详见：[C_Protocol_Field_Conversion.md](C_Protocol_Field_Conversion.md) | 遇到字节序转换、范围验证保护机制，详见：[bypassTricks.md#协议字段解包转换](bypassTricks.md#7-协议字段解包转换)
绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

**Java**
有符号/无符号转换，Java 中无无符号类型但通过位运算模拟时的转换问题，详见：[Java_Signed_Unsigned_Conversion.md](Java_Signed_Unsigned_Conversion.md) | 遇到范围检查、类型验证保护机制，详见：[bypassTricks.md#有符号无符号转换绕过](bypassTricks.md#1-有符号无符号转换绕过)
窄类型到宽类型转换，byte/short 扩展为 int/long 时的符号扩展，详见：[Java_Narrow_To_Wide_Conversion.md](Java_Narrow_To_Wide_Conversion.md) | 遇到符号扩展验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
宽类型到窄类型转换，int/long 强制转换为 byte/short 时的截断，详见：[Java_Wide_To_Narrow_Conversion.md](Java_Wide_To_Narrow_Conversion.md) | 遇到超出范围检查保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
浮点与整型转换，double/float 转 int/long 时的精度丢失，详见：[Java_Float_To_Integer_Conversion.md](Java_Float_To_Integer_Conversion.md) | 遇到精度检查、范围验证保护机制，详见：[bypassTricks.md#浮点与整型转换绕过](bypassTricks.md#3-浮点与整型转换绕过)
JNI 类型转换，Java Native Interface 调用中的类型转换问题，详见：[Java_JNI_Type_Conversion.md](Java_JNI_Type_Conversion.md) | 遇到边界检查、类型映射保护机制，详见：[bypassTricks.md#跨语言边界转换绕过](bypassTricks.md#4-跨语言边界转换绕过)
数组索引转换，数组索引计算中的类型转换和边界检查，详见：[Java_Array_Index_Conversion.md](Java_Array_Index_Conversion.md) | 遇到索引范围验证、负数检查保护机制，详见：[bypassTricks.md#数组索引转换绕过](bypassTricks.md#5-数组索引转换绕过)
集合大小转换，集合操作中的类型转换问题，详见：[Java_Collection_Size_Conversion.md](Java_Collection_Size_Conversion.md) | 遇到乘法溢出检查保护机制，详见：[bypassTricks.md#内存分配大小转换](bypassTricks.md#6-内存分配大小转换)
协议字段解包转换，网络协议解析中的类型转换，详见：[Java_Protocol_Field_Conversion.md](Java_Protocol_Field_Conversion.md) | 遇到字节序转换、范围验证保护机制，详见：[bypassTricks.md#协议字段解包转换](bypassTricks.md#7-协议字段解包转换)
绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

**Python**
整型与浮点转换，int 与 float 之间的转换精度问题，详见：[Python_Integer_Float_Conversion.md](Python_Integer_Float_Conversion.md) | 遇到精度检查、范围验证保护机制，详见：[bypassTricks.md#浮点与整型转换绕过](bypassTricks.md#3-浮点与整型转换绕过)
大整数转换，Python 大整数转换为 C 扩展类型时的溢出，详见：[Python_BigInt_Conversion.md](Python_BigInt_Conversion.md) | 遇到范围检查、精度验证保护机制，详见：[bypassTricks.md#精度丢失和大整数](bypassTricks.md#8-精度丢失和大整数)
C 扩展类型转换，Python C 扩展中的类型转换问题，详见：[Python_C_Extension_Conversion.md](Python_C_Extension_Conversion.md) | 遇到边界检查、类型映射保护机制，详见：[bypassTricks.md#跨语言边界转换绕过](bypassTricks.md#4-跨语言边界转换绕过)
NumPy 数组类型转换，NumPy 数组类型转换中的精度丢失和溢出，详见：[Python_NumPy_Type_Conversion.md](Python_NumPy_Type_Conversion.md) | 遇到精度检查保护机制，详见：[bypassTricks.md#精度丢失和大整数](bypassTricks.md#8-精度丢失和大整数)
字符串到数字转换，字符串解析为数字时的类型转换问题，详见：[Python_String_To_Number_Conversion.md](Python_String_To_Number_Conversion.md) | 遇到类型验证、显式转换保护机制，详见：[bypassTricks.md#类型混淆和隐式转换](bypassTricks.md#9-类型混淆和隐式转换)
数组索引转换，列表和数组索引中的类型转换，详见：[Python_Array_Index_Conversion.md](Python_Array_Index_Conversion.md) | 遇到索引范围验证、负数检查保护机制，详见：[bypassTricks.md#数组索引转换绕过](bypassTricks.md#5-数组索引转换绕过)
协议字段解包转换，struct 模块解析中的类型转换，详见：[Python_Protocol_Field_Conversion.md](Python_Protocol_Field_Conversion.md) | 遇到字节序转换、范围验证保护机制，详见：[bypassTricks.md#协议字段解包转换](bypassTricks.md#7-协议字段解包转换)
RPC 序列化转换，RPC 调用中的类型序列化和反序列化，详见：[Python_RPC_Serialization_Conversion.md](Python_RPC_Serialization_Conversion.md) | 遇到边界检查、类型映射保护机制，详见：[bypassTricks.md#跨语言边界转换绕过](bypassTricks.md#4-跨语言边界转换绕过)
绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

**Go**
有符号/无符号转换，int 与 uint 之间的转换问题，详见：[Go_Signed_Unsigned_Conversion.md](Go_Signed_Unsigned_Conversion.md) | 遇到范围检查、类型验证保护机制，详见：[bypassTricks.md#有符号无符号转换绕过](bypassTricks.md#1-有符号无符号转换绕过)
不同位宽转换，int8/int16/int32/int64 之间的转换，详见：[Go_Different_Width_Conversion.md](Go_Different_Width_Conversion.md) | 遇到位宽检查、溢出验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
浮点与整型转换，float32/float64 与整数类型之间的转换，详见：[Go_Float_Integer_Conversion.md](Go_Float_Integer_Conversion.md) | 遇到精度检查、范围验证保护机制，详见：[bypassTricks.md#浮点与整型转换绕过](bypassTricks.md#3-浮点与整型转换绕过)
切片容量转换，切片容量计算中的类型转换，详见：[Go_Slice_Capacity_Conversion.md](Go_Slice_Capacity_Conversion.md) | 遇到乘法溢出检查保护机制，详见：[bypassTricks.md#内存分配大小转换](bypassTricks.md#6-内存分配大小转换)
数组索引转换，数组和切片索引中的类型转换，详见：[Go_Array_Index_Conversion.md](Go_Array_Index_Conversion.md) | 遇到索引范围验证、负数检查保护机制，详见：[bypassTricks.md#数组索引转换绕过](bypassTricks.md#5-数组索引转换绕过)
unsafe 包类型转换，unsafe.Pointer 和类型转换的安全问题，详见：[Go_Unsafe_Type_Conversion.md](Go_Unsafe_Type_Conversion.md) | 遇到指针有效性验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#23-指针和整数转换)
CGO 类型转换，CGO 调用中的类型转换问题，详见：[Go_CGO_Type_Conversion.md](Go_CGO_Type_Conversion.md) | 遇到边界检查、类型映射保护机制，详见：[bypassTricks.md#跨语言边界转换绕过](bypassTricks.md#4-跨语言边界转换绕过)
协议字段解包转换，binary 包解析中的类型转换，详见：[Go_Protocol_Field_Conversion.md](Go_Protocol_Field_Conversion.md) | 遇到字节序转换、范围验证保护机制，详见：[bypassTricks.md#协议字段解包转换](bypassTricks.md#7-协议字段解包转换)
绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

**PHP**
整型与浮点转换，int 与 float 之间的转换精度问题，详见：[PHP_Integer_Float_Conversion.md](PHP_Integer_Float_Conversion.md) | 遇到精度检查、范围验证保护机制，详见：[bypassTricks.md#浮点与整型转换绕过](bypassTricks.md#3-浮点与整型转换绕过)
字符串到数字转换，字符串到整型/浮点型的自动转换，详见：[PHP_String_To_Number_Conversion.md](PHP_String_To_Number_Conversion.md) | 遇到类型验证、显式转换保护机制，详见：[bypassTricks.md#类型混淆和隐式转换](bypassTricks.md#9-类型混淆和隐式转换)
数组键类型转换，数组键的类型转换和比较问题，详见：[PHP_Array_Key_Conversion.md](PHP_Array_Key_Conversion.md) | 遇到类型验证保护机制，详见：[bypassTricks.md#类型混淆和隐式转换](bypassTricks.md#9-类型混淆和隐式转换)
大整数转换，大整数在不同系统上的转换行为差异，详见：[PHP_BigInt_Conversion.md](PHP_BigInt_Conversion.md) | 遇到范围检查、精度验证保护机制，详见：[bypassTricks.md#精度丢失和大整数](bypassTricks.md#8-精度丢失和大整数)
类型强制转换，显式类型转换 (int)、(float) 的安全问题，详见：[PHP_Explicit_Type_Casting.md](PHP_Explicit_Type_Casting.md) | 遇到类型验证保护机制，详见：[bypassTricks.md#类型混淆和隐式转换](bypassTricks.md#9-类型混淆和隐式转换)
数组索引转换，数组索引计算中的类型转换，详见：[PHP_Array_Index_Conversion.md](PHP_Array_Index_Conversion.md) | 遇到索引范围验证、负数检查保护机制，详见：[bypassTricks.md#数组索引转换绕过](bypassTricks.md#5-数组索引转换绕过)
协议字段解包转换，网络协议解析中的类型转换，详见：[PHP_Protocol_Field_Conversion.md](PHP_Protocol_Field_Conversion.md) | 遇到字节序转换、范围验证保护机制，详见：[bypassTricks.md#协议字段解包转换](bypassTricks.md#7-协议字段解包转换)
扩展模块类型转换，PHP 扩展中的类型转换问题，详见：[PHP_Extension_Type_Conversion.md](PHP_Extension_Type_Conversion.md) | 遇到边界检查、类型映射保护机制，详见：[bypassTricks.md#跨语言边界转换绕过](bypassTricks.md#4-跨语言边界转换绕过)
绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

**JavaScript/TypeScript**
字符串到数字转换，parseInt、Number、parseFloat 的转换问题，详见：[JavaScript_String_To_Number_Conversion.md](JavaScript_String_To_Number_Conversion.md) | 遇到类型验证、显式转换保护机制，详见：[bypassTricks.md#类型混淆和隐式转换](bypassTricks.md#9-类型混淆和隐式转换)
位运算类型转换，位运算导致的 32 位整数转换，详见：[JavaScript_Bitwise_Type_Conversion.md](JavaScript_Bitwise_Type_Conversion.md) | 遇到位宽检查保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
TypedArray 类型转换，TypedArray 之间的类型转换问题，详见：[JavaScript_TypedArray_Conversion.md](JavaScript_TypedArray_Conversion.md) | 遇到类型验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
BigInt 转换，BigInt 与 Number 之间的转换问题，详见：[JavaScript_BigInt_Conversion.md](JavaScript_BigInt_Conversion.md) | 遇到范围检查、精度验证保护机制，详见：[bypassTricks.md#精度丢失和大整数](bypassTricks.md#8-精度丢失和大整数)
浮点精度转换，浮点数精度丢失和转换问题，详见：[JavaScript_Float_Precision_Conversion.md](JavaScript_Float_Precision_Conversion.md) | 遇到精度检查保护机制，详见：[bypassTricks.md#浮点与整型转换绕过](bypassTricks.md#3-浮点与整型转换绕过)
数组索引转换，数组索引计算中的类型转换，详见：[JavaScript_Array_Index_Conversion.md](JavaScript_Array_Index_Conversion.md) | 遇到索引范围验证、负数检查保护机制，详见：[bypassTricks.md#数组索引转换绕过](bypassTricks.md#5-数组索引转换绕过)
协议字段解包转换，ArrayBuffer 和 DataView 中的类型转换，详见：[JavaScript_Protocol_Field_Conversion.md](JavaScript_Protocol_Field_Conversion.md) | 遇到字节序转换、范围验证保护机制，详见：[bypassTricks.md#协议字段解包转换](bypassTricks.md#7-协议字段解包转换)
WebAssembly 类型转换，WebAssembly 接口中的类型转换，详见：[JavaScript_WebAssembly_Type_Conversion.md](JavaScript_WebAssembly_Type_Conversion.md) | 遇到边界检查、类型映射保护机制，详见：[bypassTricks.md#跨语言边界转换绕过](bypassTricks.md#4-跨语言边界转换绕过)
绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

**Rust**
有符号/无符号转换，i8/i16/i32/i64 与 u8/u16/u32/u64 之间的转换，详见：[Rust_Signed_Unsigned_Conversion.md](Rust_Signed_Unsigned_Conversion.md) | 遇到范围检查、类型验证保护机制，详见：[bypassTricks.md#有符号无符号转换绕过](bypassTricks.md#1-有符号无符号转换绕过)
不同位宽转换，不同位宽整数类型之间的转换，详见：[Rust_Different_Width_Conversion.md](Rust_Different_Width_Conversion.md) | 遇到位宽检查、溢出验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
浮点与整型转换，f32/f64 与整数类型之间的转换，详见：[Rust_Float_Integer_Conversion.md](Rust_Float_Integer_Conversion.md) | 遇到精度检查、范围验证保护机制，详见：[bypassTricks.md#浮点与整型转换绕过](bypassTricks.md#3-浮点与整型转换绕过)
as 关键字转换，as 关键字进行类型转换时的截断和溢出，详见：[Rust_As_Type_Casting.md](Rust_As_Type_Casting.md) | 遇到溢出验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#2-不同位宽转换绕过)
数组索引转换，数组和切片索引中的类型转换，详见：[Rust_Array_Index_Conversion.md](Rust_Array_Index_Conversion.md) | 遇到索引范围验证、负数检查保护机制，详见：[bypassTricks.md#数组索引转换绕过](bypassTricks.md#5-数组索引转换绕过)
unsafe 代码类型转换，unsafe 块中的类型转换安全问题，详见：[Rust_Unsafe_Type_Conversion.md](Rust_Unsafe_Type_Conversion.md) | 遇到指针有效性验证保护机制，详见：[bypassTricks.md#不同位宽转换绕过](bypassTricks.md#23-指针和整数转换)
FFI 类型转换，FFI 调用中的类型转换问题，详见：[Rust_FFI_Type_Conversion.md](Rust_FFI_Type_Conversion.md) | 遇到边界检查、类型映射保护机制，详见：[bypassTricks.md#跨语言边界转换绕过](bypassTricks.md#4-跨语言边界转换绕过)
协议字段解包转换，网络协议解析中的类型转换，详见：[Rust_Protocol_Field_Conversion.md](Rust_Protocol_Field_Conversion.md) | 遇到字节序转换、范围验证保护机制，详见：[bypassTricks.md#协议字段解包转换](bypassTricks.md#7-协议字段解包转换)
绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-numeric-error-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板


