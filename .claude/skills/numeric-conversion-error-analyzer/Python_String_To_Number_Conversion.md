# Python_String_To_Number_Conversion

**漏洞类型**: 字符串到数字转换错误，字符串解析为数字时的精度丢失、截断、溢出、格式歧义

**漏洞成因**

Python 字符串到数字的转换存在以下风险：
- 字符串输入经 `int()`、`float()` 转换后，浮点精度丢失或舍入误差
- JSON/RPC 反序列化中大整数被转换为浮点数，导致精度丢失
- 字符串格式化（十进制、十六进制、八进制）解析错误或歧义
- C 扩展调用中 Python 整数溢出到 C int/long，导致截断
- NumPy 数组中字符串到数值类型的隐式转换超出类型范围
- 用户输入验证不足，负数、特殊值（inf、nan）的转换误解
- 浮点数舍入误差在后续计算中放大，用于索引或内存操作

---

## Details

### 代码示例

**危险模式1：字符串浮点转整作为数组索引**
```python
def process_index(user_input):
    index = int(float(user_input))  # "3.9" → 3.9 → 3
    array = [1, 2, 3, 4, 5]
    return array[index]             # 精度丢失，索引错误

process_index("3.9")  # 越界或错误访问
```

**危险模式2：JSON 大整数精度丢失**
```python
import json

def parse_large_number(json_str):
    data = json.loads(json_str)
    # 超大整数在 JSON 中被转为浮点数再转整数
    large_int = int(data['value'])  # "12345678901234567890" → float → int 精度丢失
    # 用于内存分配或数组大小
    buffer = bytearray(large_int)   # 可能申请过小或过大的内存
    return buffer

parse_large_number('{"value": 12345678901234567890}')
```

**危险模式3：字符串进制解析的歧义**
```python
def parse_number(hex_string):
    # 用户输入 "0x10" 可能被误解为十六进制或十进制
    value = int(hex_string)          # 无进制标志，默认十进制
    if value > 100:
        grant_admin()                # "0x10" 作为十进制是 16，不>100；作为十六进制是 256，>100
    return value

parse_number("0x10")  # 进制歧义导致权限逻辑错误
```

**危险模式4：浮点特殊值的转换**
```python
def handle_measurement(string_value):
    value = float(string_value)
    size = int(value)                # inf → 很大数, nan → 0 或异常
    memory = bytearray(size)         # 申请内存过大导致 OOM，或过小越界
    return memory

handle_measurement("inf")   # 可能申请无限大内存
handle_measurement("nan")   # NaN 转 int 可能为 0
```

**危险模式5：NumPy 隐式类型转换溢出**
```python
import numpy as np

def create_array_from_strings(string_list):
    # 字符串列表转 NumPy 数组，类型推断可能不同
    arr = np.array(string_list, dtype=np.int32)  # 大数转 int32 溢出
    return arr

create_array_from_strings(["1000000000", "2000000000"])  # 溢出
```

**危险模式6：C 扩展中的整数溢出**
```python
def call_c_function(large_number):
    # Python 的无限精度整数传给 C 函数期望 C long
    from ctypes import c_long
    result = my_c_lib.process(c_long(large_number))  # 隐式转换溢出
    return result

call_c_function(2**63 + 1000)  # 超出 c_long 范围
```

**危险模式7：舍入误差放大**
```python
def calculate_buffer_size(percentage_str):
    percentage = float(percentage_str)  # "33.33" → 浮点舍入误差
    size = int(100 * percentage)        # 99.99 vs 100.0 的差异
    buffer = bytearray(size)
    return buffer

calculate_buffer_size("33.33")  # 多次计算导致误差放大
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `int()`、`float()`、`complex()` 作用于字符串或用户输入
- `json.loads()` 返回值直接转换为 int/float，无范围验证
- NumPy 数组转换：`np.array(..., dtype=np.int32/int64/float32)`
- C 扩展调用：`ctypes.c_long()`、`ctypes.c_int()` 包装大数值
- `eval()`、`ast.literal_eval()` 解析字符串为数值
- 字符串格式包含进制前缀 `0x`、`0o`、`0b` 但未明确指定进制
- 浮点数转整：`int(float(string))`、`int(string, 16)`、`int(string, 8)`

**快速定位保护机制 [L2-L3]**
- 转换前是否检查字符串格式：`if not string.isdigit()`, `re.match()`
- 是否验证转换结果范围：`if value >= MIN_INT and value <= MAX_INT`
- 是否检查浮点特殊值：`math.isnan()`、`math.isinf()`、`math.isfinite()`
- 是否明确指定进制：`int(hex_str, 16)` 而非 `int(hex_str)`
- 是否对 JSON 大整数特殊处理（使用 `decimal.Decimal` 或字符串保留）
- NumPy 数组转换是否验证源值在目标类型范围内
- C 扩展调用是否在绑定层验证范围

---

## Classify

**研判为真漏洞的特征：**
1. 字符串直接经 `int(float(...))` 转换后作为数组索引或内存大小，无范围检查
2. JSON 反序列化的大整数未特殊处理，直接转为 int/float 导致精度丢失用于关键计算
3. 浮点字符串转整用于权限判断或数值比较，精度丢失导致逻辑错误
4. 未检查特殊值（inf、nan、-inf），直接转整作为内存操作参数
5. 字符串格式歧义（进制前缀未明确处理），导致值误解
6. 跨模块传递的转换结果未再验证，接收端无边界检查
7. C 扩展或 NumPy 操作中大数值隐式转换溢出，导致逻辑错误

**误报/代码异味的特征：**
- 字符串来自内部代码生成，格式和范围已在源端控制
- 转换前明确验证了格式和范围：`if value.isdigit() and int(value) < MAX`
- 浮点值来自内部计算且范围已限制，转整后再验证
- 使用 `decimal.Decimal` 保留精度，避免浮点转整
- 明确指定进制：`int(hex_str, 16)`，消除歧义
- JSON 反序列化使用 `parse_float=decimal.Decimal` 保留精度
- C 扩展调用前明确检查范围，使用 Python 类型而非 C 原生类型
- 已启用静态类型检查（mypy）或运行时类型验证

---

## Low risk

**以下场景可评为低风险：**

1. **完整的格式和范围验证**
   - 转换前显式验证：`if string.isdigit() and int(string) <= sys.maxsize`
   - 使用 `re.match()` 验证格式，明确指定进制
   - 超出范围时有明确处理（抛异常或返回错误值）

2. **使用安全的转换方法**
   - 采用 `decimal.Decimal(string)` 保留精度，避免浮点转整
   - 使用 `ast.literal_eval()` 而非 `eval()`，格式已验证
   - JSON 反序列化使用 `parse_float=decimal.Decimal` 或自定义处理大整数

3. **内部生成的字符串转换**
   - 字符串来自内部代码生成（不从用户输入），格式和值在源端已控制
   - 如：`str(internal_value)` 再转回相同类型
   - 错误不影响安全（仅显示或统计）

4. **验证后的类型转换**
   - 浮点值在转整前已验证在整型范围内：`if value >= MIN_INT and value <= MAX_INT`
   - NumPy 数组转换前检查所有元素在目标类型范围内
   - 使用 `np.clip()` 或 `np.round()` 等方法约束值域

5. **明确的进制处理**
   - JSON 中数值类型明确分离（string vs number），格式已验证
   - 字符串进制前缀已明确处理，无歧义解析

