# Python_Array_Index_Conversion

**漏洞类型**: 数组索引转换错误，列表/数组/NumPy 索引中的类型转换导致越界或误访问

**漏洞成因**

Python 中数组索引涉及类型转换时，存在以下风险：
- 浮点数直接转整用作列表/NumPy 数组索引，精度丢失导致越界
- NumPy 数组索引从浮点转整，高维数组索引计算错误
- 用户输入经转换后直接作为索引，无边界检查
- 负数索引在转换中误解（Python 支持负索引，但不支持浮点索引）
- 布尔索引与整数索引混淆导致逻辑错误
- 大整数截断后作为索引，访问错误位置
- NumPy 高级索引中类型转换导致的形状不匹配

---

## Details

### 代码示例

**危险模式1：浮点直接转整作为列表索引**
```python
def accessList(user_index):
    data = [10, 20, 30, 40, 50]
    idx = int(float(user_index))  # "3.9" → 3.9 → 3
    return data[idx]               # 精度丢失，访问错误元素

accessList("3.9")  # 返回 40，但可能期望 50
```

**危险模式2：NumPy 数组索引越界**
```python
import numpy as np

def processNumpyArray(index_str):
    arr = np.array([1, 2, 3, 4, 5])
    idx = int(float(index_str))  # 转换精度丢失
    if idx > 0:
        return arr[idx]           # 可能超出数组范围
    return None

processNumpyArray("5.1")  # int(float("5.1")) = 5，但数组只有 5 元素，IndexError
```

**危险模式3：高维 NumPy 数组的多重索引转换**
```python
import numpy as np

def accessMatrixElement(row_str, col_str):
    matrix = np.arange(20).reshape((4, 5))
    row = int(float(row_str))    # "1.9" → 1
    col = int(float(col_str))    # "2.9" → 2
    return matrix[row, col]      # 精度丢失，访问错误元素

accessMatrixElement("1.9", "2.9")  # 返回 7，但可能期望 8
```

**危险模式4：用户输入索引无边界检查**
```python
def getUserElement(user_idx):
    data = [1, 2, 3, 4, 5]
    idx = int(user_idx)  # 用户可能输入超出范围的数值
    return data[idx]     # 负数索引或越界

getUserElement("10")   # IndexError
getUserElement("-10")  # IndexError（虽然 Python 支持负索引，但 -10 超出范围）
```

**危险模式5：布尔索引与整数索引混淆**
```python
import numpy as np

def maskOrIndex(arr, selector):
    data = np.array([10, 20, 30, 40, 50])
    if isinstance(selector, (list, np.ndarray)):
        # 布尔掩码
        return data[selector]
    else:
        # 整数索引
        idx = int(selector)
        return data[idx]

# 如果 selector 是浮点数的列表，转换后可能产生错误的掩码
maskOrIndex([1.5, 2.7], None)  # 浮点转整：[1, 2]，得到不同的元素
```

**危险模式6：负数索引的符号问题**
```python
def handleNegativeIndex(index_val):
    data = [10, 20, 30, 40, 50]
    # 用户输入 -1 期望访问最后一个元素
    idx = int(float(index_val))  # "-1.5" → -1.5 → -1（截断符号）
    return data[idx]              # 返回 50，符号正确
    # 但如果转换中产生符号误解，结果可能错误

handleNegativeIndex("-1.5")
```

**危险模式7：大整数截断导致索引错误**
```python
def processLargeIndex(index_str):
    data = list(range(100))
    # 来自 JSON/API 的大数值
    large_idx = int(float(index_str))  # "123.45" → 123，但在其他语境可能超出范围
    if large_idx < len(data):
        return data[large_idx]
    return None

# 如果在分布式系统中，long 值被截断为 int 后作为索引
processLargeIndex("99999999999999.99")  # 精度丢失，值变为其他数字
```

**危险模式8：NumPy 高级索引的类型转换**
```python
import numpy as np

def advancedIndexing(indices_str_list):
    arr = np.arange(10)
    # 字符串列表转 NumPy 数组，再用于索引
    indices = np.array([int(float(x)) for x in indices_str_list])
    return arr[indices]  # 精度丢失，访问错误元素

advancedIndexing(["1.9", "3.7", "5.2"])  # [1, 3, 5] 而非 [2, 4, 5]
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `int(float(...))` 或 `int(...)` 直接作用于索引变量
- 列表/数组访问：`list[int(idx)]`、`arr[int(idx)]`、`numpy_arr[int(idx)]`
- 用户输入经 `int()`、`float()` 转换直接作为索引，未验证
- NumPy 多维索引中有类型转换：`matrix[int(r), int(c)]`
- NumPy 布尔掩码前有类型转换导致掩码值改变
- 索引来自 `json.loads()`、API 返回、数据库查询后直接转换
- 循环计数器或计算结果的类型转换用作索引

**快速定位保护机制 [L2-L3]**
- 索引是否在使用前验证范围：`if 0 <= idx < len(array)`
- 转换前是否验证源值有限：`if math.isfinite(val) and val >= 0 and val < len(array)`
- 是否使用 NumPy 索引安全方法：`np.clip(idx, 0, len(arr)-1)`
- 是否通过异常处理捕获 IndexError：`try: ... except IndexError`
- 是否使用 NumPy 的整数索引而非浮点：`arr[np.asarray(idx, dtype=int)]`
- 是否对多维索引的每个维度分别验证
- 是否启用运行时检查或类型提示验证

---

## Classify

**研判为真漏洞的特征：**
1. 浮点数直接转整无检查，用作列表/NumPy 数组索引
2. 用户输入经转换后直接作为索引，无范围验证
3. 大整数或精度丢失的转换结果用作索引，访问错误元素
4. NumPy 多维索引的任何维度有未验证的类型转换
5. 跨模块传递的索引参数未在使用处再验证
6. 布尔掩码与整数索引混淆，类型转换导致选择错误元素

**误报/代码异味的特征：**
- 索引来自内部循环计数器或明确限制范围的计算
- 索引使用前有显式范围检查：`if 0 <= idx < len(array)`
- 使用 `numpy` 的安全索引方法（如 `np.take()` 等）
- 转换源已验证为整数或明确范围内的浮点
- 使用异常处理完整捕获 IndexError 或 ValueError
- 索引仅来自内部常量或配置文件

---

## Low risk

**以下场景可评为低风险：**

1. **完整的范围验证**
   - 索引转换前验证：`if 0 <= idx < len(array)`
   - 浮点值验证有限且范围内：`if math.isfinite(val) and 0 <= int(val) < len(arr)`
   - NumPy 多维索引每个维度都验证

2. **内部受控的索引来源**
   - 索引来自循环计数器或 `range()` 等内置函数
   - 如：`for i in range(len(array)): process(array[i])`
   - 索引范围由代码逻辑保证，无外部输入

3. **异常处理**
   - 索引访问被 `try-except IndexError` 包围
   - 超出范围时有明确的错误处理和日志

4. **使用安全的 NumPy 方法**
   - 使用 `np.take(arr, indices, mode='clip')` 自动截断越界索引
   - 使用 `np.asarray(idx, dtype=int)` 明确转换为整数
   - 使用 NumPy 的索引验证函数

5. **已验证的转换**
   - 转换源已通过 `isinstance()` 验证为数值类型
   - 浮点值已通过 `math.isfinite()` 验证

