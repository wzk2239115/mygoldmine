# Python_Integer_Arithmetic_Overflow

**漏洞类型**: 整数运算溢出，Python 2 中整数运算可能溢出，Python 3 整数无限精度但仍需关注内存分配

**Python**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`result = a + b`、`size = width * height`、`np.zeros(user_input * 1000)`、使用 ctypes 时的整数运算

- **核心操作定位技巧** (L1: 关键词扫描)：Python 3 整数无限精度，重点扫描将整数传递给 C 扩展、NumPy、ctypes 的场景。检查算术运算结果用于内存分配（`np.array`、`bytearray`、`ctypes.create_string_buffer`）或索引操作的情况。

- **保护机制定位技巧** (L2: 跳读)：查找大小上限检查（`if size > MAX_SIZE`、`if result < 0`），使用 `sys.maxsize` 进行范围限制，或使用 decimal 模块进行精确计算。检查与 C 扩展交互时的类型验证。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：大整数传给 C 扩展/NumPy 导致内存分配失败或截断，影响程序稳定性或安全性
- **误报**：纯 Python 整数运算（自动处理大数）、有明确上限检查、仅用于日志
- **代码异味**：整数运算结果传给外部库，需评估是否会超出目标类型范围

## Low risk

- 纯 Python 整数运算（不涉及 C 扩展或 NumPy）
- 操作数有明确上限（如 `min(value, sys.maxsize)`）
- 使用 decimal.Decimal 进行精确计算
- 传给 C 扩展前进行范围验证
- 结果仅用于逻辑判断或日志

## 审计专业技巧

### 快速识别关键上下文

1. **内存分配场景** - 最危险
   - `np.zeros(size)` / `np.ones(size)` - 大小参数直接来自运算
   - `bytearray(count)` / `bytes(count)` - count 未验证
   - `ctypes.create_string_buffer(size)` - size 溢出导致分配失败
   - `PIL.Image.new((width, height))` - 面积计算未防护

2. **索引操作场景** - 中等风险
   - 数组索引：`arr[calculated_index]` - 溢出导致越界
   - 字符串切片：`data[start:start+length]` - 负数或超界问题
   - 循环范围：`range(size1 * size2)` - 生成巨大迭代器

3. **C扩展交互场景** - 需深度检查
   - Pillow、Cython 扩展调用前的算术
   - 调用 `struct.pack(fmt, value)` - 值超范围
   - Socket/网络编程中的长度计算

### 真实漏洞与误报区分经验

| 特征 | 真实漏洞 | 误报特征 |
|------|--------|--------|
| **输入源** | 用户控制的参数直接参与运算 | 常量或内部生成值 |
| **运算类型** | 乘法/指数（扩大）、位移（左移） | 加法且有合理上界 |
| **结果用途** | 内存分配/大小参数 | 业务逻辑/日志输出 |
| **防护检查** | 无任何验证 | `if result > limit`、`min()` 限制 |
| **溢出后果** | DoS、内存耗尽、段错误 | 计算不准确但无安全影响 |

### 典型案例分析

**真实漏洞案例**：
```python
# 危险：用户输入直接用于内存分配
def create_image(width, height):
    size = width * height  # 整数乘法溢出
    return np.zeros((size, 3))  # 分配超大内存

# 调用：width=100000, height=100000 → size 溢出
```

**误报案例**：
```python
# 安全：常量间的计算，结果受限
def calculate_hash():
    MAX_BITS = 256
    HASH_SIZE = 2 << MAX_BITS  # 常量运算，不取决于输入
    return hashlib.sha256(b"data")

# 安全：有明确检查
def resize_image(user_width, user_height):
    MAX_DIM = 10000
    w = min(user_width, MAX_DIM)
    h = min(user_height, MAX_DIM)
    # 即使 w*h 溢出，结果不超过 100M 像素
```

### 审计检查清单

- [ ] 追踪整数运算的所有输入源，标记用户控制的参数
- [ ] 扫描运算结果的直接用途（内存/索引/循环）
- [ ] 确认运算前是否有 `if`/`min`/`max` 限制
- [ ] 检查是否涉及 C 扩展（import numpy/PIL/struct）
- [ ] 验证 C 扩展文档对参数范围的要求
- [ ] 测试边界值：`sys.maxsize`、`2**31-1`、`2**63-1`
- [ ] 检查错误处理（MemoryError、OverflowError 是否捕获）

### 常见绕过误报的手法

- 隐式类型转换：`len(data) * user_multiplier` - 长度溢出
- 多步运算：`a = x * y; b = a + z` - 中间结果溢出
- 循环累加：`total = 0; for i in range(user_n): total += item_size` - 累加溢出
- 动态代码生成：`exec("x = " + str(big_number))` - 间接整数运算

