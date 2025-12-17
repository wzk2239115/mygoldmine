# Python_Integer_Float_Conversion

**漏洞类型**: 整型与浮点转换，int 与 float 之间的转换精度问题

**Python**

Python 中整数与浮点数的转换涉及精度丢失、四舍五入行为不同、溢出和下溢等问题。浮点数的 IEEE 754 表示导致精度有限，转为整数时可能出现意外截断。Python 3 中整数是无限精度的，但转浮点时会失去精度。这类问题常在金额计算、权限判断、密钥长度、数组索引等安全相关操作中导致漏洞。

---

## Details

### 代码示例与核心操作定位

**危险模式1：浮点金额转整数时的精度丢失**
```python
def process_payment(amount_float):
    # 用户输入或计算的浮点数金额
    amount_cents = int(amount_float * 100)  # 浮点精度丢失

    if amount_cents > 1000000:  # 金额阈值检查
        requires_approval()

    charge(amount_cents)

# 浮点精度问题导致金额计算错误
process_payment(123.455)  # 期望 12345，实际可能 12344 或 12346
```

**危险模式2：比较操作中的浮点精度**
```python
def verify_discount(original_price, discount_rate):
    discounted = original_price * discount_rate  # 浮点运算
    int_discounted = int(discounted)

    # 权限检查依赖于转换结果
    if int_discounted < 1000:
        allow_max_discount()  # 精度丢失导致权限提升

    return int_discounted

verify_discount(1000.1, 0.999999)  # 浮点精度可能通过检查
```

**危险模式3：数组大小或索引的浮点转整**
```python
def allocate_buffer(size_float):
    size = int(size_float)  # 浮点截断
    buffer = bytearray(size)  # 分配内存

    return buffer

# 浮点数被截断，导致分配大小与预期不符
allocate_buffer(1024.9)  # 分配 1024，期望 1025
```

**危险模式4：数组索引的浮点计算**
```python
def access_array(index_float, array):
    index = int(index_float)  # 浮点截断

    # 精度丢失导致访问错误的元素
    return array[index]  # 可能访问错误索引导致越界或逻辑错误

data = [10, 20, 30]
access_array(2.99, data)  # 访问 index 2，期望 index 3
```

**危险模式5：整数超过浮点精度范围**
```python
def verify_transaction(transaction_id_str):
    id_int = int(transaction_id_str)
    id_float = float(id_int)

    # 大整数转浮点后精度丢失
    if id_float == id_int:  # 可能为 False！
        confirm_transaction()

    return id_int

# 64 位大整数精度超出浮点范围 (2^53)
verify_transaction('9007199254740993')  # 精度丢失后比较失败
```

**危险模式6：浮点运算中的累积误差**
```python
def calculate_total(items_array):
    total = 0.0

    for price in items_array:
        total += float(price)  # 浮点加法的累积误差

    total_cents = int(total * 100)  # 误差被放大
    return total_cents

prices = [0.1, 0.2, 0.3]
result = calculate_total(prices)  # 精度问题导致总金额错误
```

**危险模式7：权限计算中的浮点转整**
```python
def calculate_permission_level(score_float):
    level = int(score_float)  # 精度丢失

    permissions = {
        0: 'guest',
        1: 'user',
        2: 'moderator',
        3: 'admin'
    }

    # 字典键访问依赖于转换精度
    return permissions.get(level, 'none')

# 浮点精度导致权限提升
calculate_permission_level(2.99)  # 返回 'moderator'，期望 'user'
```

**危险模式8：密钥导出中的浮点参数**
```python
def derive_key(iteration_count_float, salt):
    iterations = int(iteration_count_float)  # 精度丢失

    # 密钥强度依赖于迭代次数
    key = pbkdf2_hmac('sha256', password, salt, iterations)
    return key

derive_key(100000.5, b'salt')  # 迭代次数被截断为 100000
```

**危险模式9：NumPy 数组类型转换**
```python
import numpy as np

def create_array(size_float):
    size = int(size_float)  # 精度丢失
    # NumPy 数组索引或大小依赖转换
    arr = np.zeros(size, dtype=np.int32)
    return arr

create_array(1024.9)  # 创建 1024 大小数组，期望 1025
```

**危险模式10：struct 打包/解包中的浮点转整**
```python
import struct

def pack_packet(version_float):
    version = int(version_float)  # 精度丢失

    # 协议字段打包依赖于转换
    packet = struct.pack('!H', version)  # 协议版本号
    return packet

pack_packet(1.99)  # 版本号被截断，可能导致协议混乱
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描 [L1]**:
- 浮点到整数转换：`int(float_var)`, `int(a * b)`, `int(result)`
- 浮点运算：`a * b`, `a + b`, `a / b` 后转整数
- 金额相关：`amount * 100`, `price * discount_rate`, `total += price`
- 数组大小参数：`bytearray(int(size))`, `np.zeros(int(count))`
- 数组索引：`array[int(index)]`, `list[int(index)]`
- 权限/阈值比较：`if int(score) > threshold`, `level = int(value)`
- 整数转浮点再比较：`float(int_var) == int_var`, `(float)int == int`
- 密钥/安全参数：`pbkdf2_hmac(..., int(iterations), ...)`, `struct.pack(..., int(field))`
- struct 打包：`struct.pack('!H', int(value))`, `struct.unpack_from(...)` 后转整

**快速定位保护机制 [L2-L3]**:
- 是否在转换前验证精度范围：`if math.isfinite(x) and x >= MIN_INT and x <= MAX_INT`
- 是否使用 `decimal.Decimal` 保持精度：`decimal.Decimal(str(value))`
- 是否进行四舍五入而非直接截断：`round(x, 2)` 后转整
- 是否验证转换后的值与原值是否一致：`int_val == float_val`
- 是否对数值范围进行二次验证：`if MIN <= value <= MAX`
- 金额计算是否使用 Decimal：`from decimal import Decimal`
- 是否避免浮点比较：使用显式精度检查
- 是否检查特殊值：`math.isnan()`, `math.isinf()` 检查

---

## Classify

**研判为真漏洞的特征：**

1. **安全决策依赖浮点转整**：权限判断、金额验证、阈值检查依赖 `int(float_var)` 转换，无精度验证

2. **浮点运算后直接使用**：如 `price * discount` 或 `total += price` 后转整，未进行精度检查

3. **大整数精度超出浮点范围**：超过 2^53 的整数转浮点后精度丢失，用于身份验证或比较

4. **金额计算无法保证精度**：使用浮点做金额运算，未用 Decimal 库

5. **累积浮点误差导致阈值绕过**：循环中浮点加法累积误差后转整，导致最终结果与预期不符

6. **数组索引由浮点计算得出**：浮点计算结果转整作为数组索引，无边界检查导致越界

7. **密钥导出强度削弱**：密钥派生函数的迭代次数、长度等参数由浮点转整导致实际强度不足

8. **协议字段由浮点转整导致混乱**：struct 打包或网络协议字段使用浮点转整，导致协议混乱

**误报/代码异味的特征：**

- 浮点转整前进行完整验证：`if math.isfinite(x) and x == int(x)`
- 使用 Decimal 处理精度敏感操作：`Decimal(str(value))` 保持精度
- 数值来自应用常量或配置，不涉及浮点运算：`ITERATIONS = 100000`
- 转换结果用于展示/日志，未用于逻辑判断或安全决策
- 显式指定四舍五入方式：`round(value, 2)` 后进行明确的阈值检查
- 使用专用金额/货币库处理：`decimal.Decimal`, Money 库
- 函数有类型提示且明确期望整数参数：`def func(count: int):`
- NumPy 数组转换前检查范围：`if 0 <= value < MAX: arr[int(value)]`

---

## Low risk

**以下场景可评为低风险：**

1. **完整的精度验证**
   - 转换前验证浮点精度：`if math.isfinite(x) and x == int(x): value = int(x)`
   - 转换后验证结果：`int_val = int(x); if int_val != x: raise ValueError()`
   - 金额使用四舍五入后验证：`rounded = round(price, 2); if abs(rounded - price) > 0.01: error()`

2. **使用精度保持的工具**
   - Decimal 库处理：`from decimal import Decimal; total = Decimal(str(a)) + Decimal(str(b))`
   - 字符串计算：所有数值保持为字符串格式进行计算或 SQL 参数化
   - Money 库：应用统一使用 Money 对象处理金额

3. **数值来源受控**
   - 浮点数来自应用常量：`DISCOUNT_RATE = 0.9`
   - 来自配置文件的硬编码值
   - 来自数据库且已验证的值
   - 完全内部生成的数据

4. **非安全相关的操作**
   - 浮点转整用于展示、统计、日志：`f"{value:.0f}"`
   - 数值仅用于计数显示，不影响权限或金额逻辑
   - 转换结果用于缓存键而非逻辑判断
   - UI 表示或格式化，未用于后续计算

5. **安全参数的完整验证**
   - 密钥长度为预定义常量：`KEY_LENGTH = 32`
   - 迭代次数来自已验证的配置：从受信配置文件读取后再验证范围
   - PBKDF2 参数完整检查：`if 100000 <= iterations <= 10000000`

6. **类型声明和严格检查**
   - 函数参数有类型提示：`def process(count: int) -> None:`
   - 使用 `isinstance()` 显式类型检查：`assert isinstance(count, int)`
   - 使用 mypy 或其他静态类型检查
   - 数组索引访问前进行范围检查：`if 0 <= index < len(array)`

