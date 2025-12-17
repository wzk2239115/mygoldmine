# Python C 扩展类型转换

**漏洞类型**: Python C 扩展中的数值类型转换问题

**概述**: Python 与 C 扩展交互时，整数、浮点数、指针等类型的转换可能导致溢出、精度丢失、缓冲区溢出等漏洞。Python 3 的无限精度整数与 C 的固定宽度类型（int、long、size_t 等）交互时特别容易出现问题。

---

## Details

### 核心风险场景

**整数溢出于 C 扩展边界**
```c
// PyArg_ParseTuple 中的类型转换
int value;
PyArg_ParseTuple(args, "i", &value);  // "i" = int (32位)，超出范围溢出
```
**快速定位核心操作**: `PyArg_ParseTuple` / `PyArg_VaParse` / `PyLong_AsLong` / `PyLong_AsVoidPtr` 等转换函数，以及 `ctypes` / `numpy` 中的类型指定符

**快速定位保护机制** [L1:关键词扫描]：检查是否存在 `PyErr_Occurred()` 调用验证转换结果，是否进行范围校验（如 `if (value < 0 || value > MAX_SAFE_VALUE)`）

---

### 常见转换危险函数

| 函数 | 风险 | 审计等级 |
|------|------|--------|
| `PyLong_AsLong()` | 超出 [-2^31, 2^31-1] 溢出，无返回值验证漏报 | L1 |
| `PyLong_AsUnsignedLong()` | 超出 [0, 2^32-1] 溢出，负数自动转换 | L1 |
| `PyLong_AsLongLong()` | 超出 64 位范围溢出 | L1 |
| `PyLong_AsVoidPtr()` | 指针类型转换，可导致地址空间利用 | L2 |
| `PyArg_ParseTuple("i")` | 受限整数宽度，应检查 "n" 替代 | L1 |

---

### 典型漏洞模式

**模式 1: 无符号转换漏洞**
```c
unsigned int size;
PyArg_ParseTuple(args, "I", &size);  // "I" = unsigned int
// 若 Python 传入负数，在某些实现中被解释为大正数，导致越界
```

**模式 2: 指针大小假设**
```c
Py_ssize_t index;
PyArg_ParseTuple(args, "n", &index);  // "n" = Py_ssize_t，平台相关宽度
char *buffer = malloc(index);  // index 溢出或负数导致小缓冲区
```

**模式 3: 隐式精度丢失**
```python
import ctypes
# Python 大整数隐式转换为 C int，不会抛出异常
large_num = 2**40
c_func.argtypes = [ctypes.c_int]
c_func(large_num)  # 静默溢出，无异常
```

---

### 审计要点 [L2:跳读]

1. **定位 PyArg_ParseTuple 调用**: 检查类型格式符
   - "i" / "I" / "l" / "L" = 有符号/无符号 int/long，易溢出
   - "n" = Py_ssize_t，更安全但仍需范围校验
   - "O" = Python 对象，通常需要手工转换

2. **追踪转换后的值使用** [L3:逐行读]:
   - 作为数组索引/大小？检查负数/越界
   - 用于指针运算？检查整数溢出导致指针越界
   - 参与位运算？检查宽度不匹配

3. **检查错误处理** [L3:逐行读]：
   - 转换函数后是否调用 `PyErr_Occurred()` 或检查返回值
   - 缺失则溢出/错误被静默忽略

---

## Classify

**漏洞判定**：
- 存在 `PyArg_ParseTuple` 等转换函数，转换结果直接用于缓冲区操作、循环限制、指针运算，**且无范围校验或错误检查** → **漏洞**
- 涉及 `PyLong_AsVoidPtr()` 或指针相关转换，未验证指针有效性 → **漏洞**

**误报判定**：
- 转换结果仅作为计算参数，无缓冲区/指针操作 → **误报**
- 虽有转换函数但值来自可信源（硬编码常量） → **误报**

**代码异味判定**：
- 存在 `PyErr_Occurred()` 检查但处理不当（如仅 print 而非返回错误） → **异味**
- 使用 `PyArg_ParseTuple` 但无文档说明范围限制 → **异味**
- NumPy 操作中未显式指定 dtype，依赖隐式转换 → **异味**

---

## Low risk

**低风险场景**：

1. **转换结果范围已在上层 Python 代码校验**
   - 如 Python 端已用 `assert 0 <= value < 2**32` 限制，C 端接收后无需再校验
   - 但需确认 Python 侧校验逻辑确实被执行（非死代码）

2. **转换至 Py_ssize_t 且直接用于 Python API**
   - `PyList_GetItem(list, index)` 中的 index 为 Py_ssize_t，Python 内部已处理范围校验
   - 前提：index 确实来自 `PyArg_ParseTuple("n", &index)` 而非其他转换

3. **转换后立即边界检查**
   ```c
   unsigned int count;
   PyArg_ParseTuple(args, "I", &count);
   if (count > MAX_ALLOWED) return error;  // 显式检查
   ```

4. **使用安全转换函数（如 NumPy 类型系统）**
   - NumPy 的 `np.array(..., dtype=np.int32)` 确保精确宽度，隐式转换受控

5. **仅做只读操作**
   - 转换值仅用于查询、计数而非分配、索引 → **低风险**

