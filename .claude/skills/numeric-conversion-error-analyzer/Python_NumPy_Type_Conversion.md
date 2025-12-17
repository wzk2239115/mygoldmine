# Python_NumPy_Type_Conversion

**漏洞类型**: NumPy 数组类型转换，数组元素、形状参数、数据类型转换中的精度丢失和溢出

**Python**

Python 中 NumPy 数值类型转换错误常见于数组初始化、元素存储、操作参数转换等场景。NumPy 数组有固定的元素类型（int32、int64、float32、float64 等），超出类型范围的值会发生截断、溢出或精度丢失。字符串转数值时、大整数传递、浮点精度不足、形状和索引参数转整等都可能引发安全问题。

---

## Details

### 代码示例

**危险模式1：字符串数组转整型数组，大数溢出**
```python
import numpy as np

def parse_user_ids(user_id_strings):
    # 用户输入的 ID 字符串列表，可能很大
    user_ids = np.array(user_id_strings, dtype=np.int32)  # 转 int32
    return user_ids

# 大于 2^31-1 的 ID 被截断
ids = parse_user_ids(['1000000000', '2147483648'])  # 溢出
```

**危险模式2：浮点数组转整数组，精度丢失作为数组索引**
```python
import numpy as np

def extract_by_indices(data_array, indices_float):
    # 浮点索引转整，精度丢失
    indices = np.array(indices_float, dtype=np.int32)
    # "3.9" → 3.9f → 3（精度丢失）
    return data_array[indices]

data = np.array([10, 20, 30, 40, 50])
result = extract_by_indices(data, [0.5, 1.7, 3.9])  # 索引错误
```

**危险模式3：NumPy 数组形状参数转换溢出**
```python
import numpy as np

def create_matrix_from_user(rows_str, cols_str):
    rows = int(rows_str)
    cols = int(cols_str)
    # 大数作为形状参数，可能分配过大内存
    matrix = np.zeros((rows, cols), dtype=np.float32)
    return matrix

create_matrix_from_user('2147483647', '2147483647')  # 内存溢出
```

**危险模式4：混合精度数组操作，累积误差**
```python
import numpy as np

def process_sensor_data(float32_array):
    # float32 精度有限，多次操作累积误差
    result = float32_array.astype(np.float32)  # 精度丢失
    result += 0.1  # 浮点误差
    result *= 10
    scaled = result.astype(np.int32)  # 转整时误差被放大
    return scaled

data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
scaled = process_sensor_data(data)  # 结果与预期不符
```

**危险模式5：大整数转浮点数组，精度超限**
```python
import numpy as np

def store_transaction_ids(tx_ids_list):
    # 大整数 ID 转 float32，精度不足（float32 只有 24 bit 有效位）
    tx_array = np.array(tx_ids_list, dtype=np.float32)
    # 数值 > 2^24 会丢失精度
    return tx_array

ids = store_transaction_ids([16777216, 16777217])  # 精度丢失
```

**危险模式6：Unicode/字符串解析后转数值，编码问题**
```python
import numpy as np

def parse_binary_string_array(binary_strings):
    # 字符串 "0xff" 转整型，但未明确指定进制
    values = np.array([int(s) for s in binary_strings], dtype=np.uint8)
    # "0xff" 作为十进制 int 后转 uint8 (0-255) 溢出
    return values

values = parse_binary_string_array(['0xff', '0x100'])  # 溢出
```

**危险模式7：C 扩展传递 NumPy 数组，类型不匹配**
```python
import numpy as np
from ctypes import c_int32

def call_c_function_with_array(large_numbers):
    # Python int 列表转 int32 数组，超范围溢出
    arr = np.array(large_numbers, dtype=np.int32)
    # 调用 C 函数，传递溢出的数据
    result = external_c_lib.process(arr)
    return result

numbers = [2**31, 2**31 + 100]  # 溢出 int32
call_c_function_with_array(numbers)
```

**危险模式8：dtype 隐式转换，逻辑错误**
```python
import numpy as np

def validate_permissions(permission_array):
    # 浮点权限数组转整，精度丢失
    perms = np.array([2.9, 3.1], dtype=np.int8)  # 2, 3

    if np.all(perms >= 3):  # 检查权限级别
        grant_admin_access()  # 被精度问题绕过

    return perms

perms = validate_permissions([2.99, 3.01])  # 精度丢失导致绕过
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]**:
- NumPy 数组创建：`np.array(..., dtype=np.int32/int64/float32/uint8)`
- 字符串转数值数组：`np.array([int(s) for s in strings], dtype=...)`
- 数据类型转换：`.astype(np.int32)`, `.astype(np.float32)`, `.astype(np.uint8)`
- 数组形状参数：`np.zeros((rows, cols))`, `np.reshape(array, (new_shape))`
- 数组索引/切片：`array[indices]`, `array[int(float_index)]`
- 数值范围操作：`np.clip()`, `np.round()` 前后的类型转换
- 浮点数组数学运算：`float32_array + 0.1`, `result *= 10` 后转整
- C 扩展调用传递数组：`external_lib.process(np_array)`

**快速定位保护机制 [L2-L3]**:
- 是否检查源值是否在目标类型范围内：`if np.all(array >= np.iinfo(np.int32).min) and np.all(array <= np.iinfo(np.int32).max)`
- 是否明确指定 dtype 而非隐式推断：`dtype=np.int32` 而非依赖自动推断
- 是否在 astype() 前进行范围验证：`if value in valid_range: result = array.astype(np.int32)`
- 是否使用 `np.clip()` 约束范围：`np.clip(array, MIN, MAX).astype(np.int32)`
- 是否检查浮点特殊值（inf、nan）：`np.isinf()`, `np.isnan()`
- 是否验证数组形状参数不会导致内存溢出：`if rows * cols < MAX_ELEMENTS`
- 字符串解析是否明确指定进制：`int(s, 16)` 而非 `int(s)`
- 是否在 C 扩展接口进行二次类型检查

---

## Classify

**研判为真漏洞的特征：**

1. **字符串数组转固定宽度整型，无范围检查**：大于目标类型最大值的字符串被截断，用于关键计算（ID、权限、大小参数）

2. **浮点数组转整型数组用于索引或权限判断**：精度丢失导致索引越界或权限逻辑错误

3. **数组形状参数来自外部输入，无溢出验证**：超大形状导致内存溢出或 OOM

4. **混合精度操作后转整，累积浮点误差**：float32 运算累积误差后转 int32，误差被放大导致逻辑错误

5. **大整数转浮点数组，精度超出浮点范围**：> 2^24（float32）或 > 2^53（float64）的值转浮点数组后精度丢失

6. **dtype 隐式转换用于权限/安全判断**：未明确指定目标类型，自动推断导致意外溢出

7. **字符串进制解析未明确指定进制**：`int("0xff")` 作十进制处理，转 uint8 溢出

8. **跨模块传递 NumPy 数组，接收端类型假设不一致**：发送端 int64，接收端期望 int32，导致截断

**误报/代码异味的特征：**

- 转换前明确验证范围：`assert np.all(array >= np.iinfo(np.int32).min) and np.all(array <= np.iinfo(np.int32).max)`
- 使用 `np.clip()` 显式约束范围后再转换
- dtype 明确指定且验证源值在范围内
- 浮点数组操作后使用 `np.round()` 并验证舍入误差
- 字符串解析明确指定进制：`int(s, 16)`
- 数组形状参数验证不溢出：`if rows < MAX and cols < MAX`
- 来自内部生成的数据（不涉及用户输入），范围已控制
- 转换结果用于展示/日志，未用于逻辑判断

---

## Low risk

**以下场景可评为低风险：**

1. **完整的范围验证**
   - 转换前检查源值在目标类型范围：`np.iinfo(np.int32).min <= value <= np.iinfo(np.int32).max`
   - 使用 `np.clip()` 约束范围：`clipped = np.clip(array, MIN, MAX)`
   - astype() 前进行断言检查：`assert np.all(array == array.astype(np.int32).astype(array.dtype))`

2. **明确的类型处理**
   - dtype 参数明确指定而非隐式推断
   - 字符串进制解析明确指定进制：`int(hex_str, 16)` 而非 `int(hex_str)`
   - 浮点特殊值（inf、nan）已检查处理：`if not np.isfinite(array).all()`

3. **内部生成的数据**
   - 数据来自内部代码生成，不涉及用户输入
   - 数值范围在源端已控制和验证
   - 如：转换内部生成的配置值或常量

4. **非关键操作**
   - 转换结果仅用于展示、统计、日志，未用于逻辑判断
   - 数值用于缓存键而非关键计算
   - dtype 转换用于性能优化但原值范围已验证

5. **形状参数的安全处理**
   - 数组形状来自内部配置或常量：`shape = (1024, 1024)`
   - 来自用户输入的形状参数经过范围验证：`if rows < MAX_DIM and cols < MAX_DIM`
   - 明确计算总元素数并检查溢出：`if rows * cols > MAX_ELEMENTS: raise ValueError()`

6. **C 扩展接口的类型安全**
   - 传递给 C 函数的 NumPy 数组在接口层进行类型检查
   - 使用类型化的数组子类或 ctypes 包装确保一致性
   - C 扩展的参数文档明确指定 dtype 要求



