# JavaScript_Array_Length_Overflow

**漏洞类型**: 数组长度计算溢出，使用用户输入创建数组或设置数组长度时未验证

**JavaScript/TypeScript**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`new Array(userInput)`、`arr.length = size`、`Array.from({ length: count })`、`Buffer.alloc(userSize)`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描数组构造函数 `new Array()`、`Array.from()`、`Buffer.alloc()`，以及数组 length 属性赋值。关注长度参数来自用户输入、计算结果或外部数据的情况。检查是否有乘法运算计算数组大小。

- **保护机制定位技巧** (L2: 跳读)：查找长度上限验证（`if (size > MAX_ARRAY_LENGTH)`、`if (size < 0)`），使用安全的默认值，或限制用户输入范围。检查是否对计算结果进行溢出检查。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：数组长度来自不受信任的源，无上限检查，可能导致内存耗尽（DoS）或负数长度
- **误报**：长度有明确上限（如 `Math.min(size, 1000)`）、来自已验证的配置、仅用于测试
- **代码异味**：动态计算数组长度，需确认计算过程是否安全

## Low risk

- 数组长度为常量或有明确上限（如 1000、10000）
- 使用 `Math.min(size, MAX_SIZE)` 限制长度
- 长度来自可信配置且经过验证
- 有异常处理捕获 RangeError
- 使用流式处理或分页代替大数组

## Audit Techniques

### 代码审计专业技巧

**1. 溢出边界检测**
- 寻找数组长度与数字计算的关联：`arr.length * multiplier`、`size + offset`
- 注意 JavaScript 数组最大长度 `2^32 - 1`，Buffer 在 Node.js 中最大 2GB
- 检查负数场景：`new Array(-1)` 会抛出 RangeError，但某些框架可能不当处理

**2. 多层级参数跟踪**
- 参数来自 HTTP 请求体 → URL 参数 → Cookie 中间件处理，需逐层追踪
- 标记可疑传递链：`req.body.count → processArray(count) → new Array(count)`
- 关键词追踪：`parseInt()`、`Number.parseFloat()`、JSON 解析后的数字类型转换

**3. 隐藏的乘法操作识别**
```javascript
// 高危：乘法未验证
const size = width * height * channels;  // 用户控制 width/height
Buffer.alloc(size);

// 安全：乘法前验证
if (width > 10000 || height > 10000) throw Error();
const size = width * height;  // 已验证边界
```

### 真实漏洞 vs 误报区分

**实际漏洞案例**
- `express-multipart` 历史版本：未验证表单字段数量，`fields * max_field_length` 导致内存溢出
- 图片处理库：`width * height * 4` 计算像素缓冲区大小，用户上传超大尺寸图片
- CSV 解析：行数 × 列数计算内存分配，恶意 CSV 文件触发 DoS
- **特征**：乘法参与，用户完全控制，无数值校验或校验逻辑缺陷

**常见误报**
- `new Array(3)` 创建固定 3 元素数组（代码写死）→ **误报**
- `new Array(config.maxSize)` 且 config 来自环境变量 → **通常安全**
- 循环内 `new Array(1)` 累积创建小数组 → **需评估循环次数上限**
- `Array(Object.keys(safeObj).length)` 构造大小数组 → **对象大小受控则安全**

**关键判断点**
| 特征 | 风险等级 | 判断依据 |
|------|--------|--------|
| 用户输入直接作为数组长度 | **高** | 无任何数值限制 |
| 有 `if (size > 10000)` 检查 | **低** | 显式上限已设置 |
| 数学计算 `a * b * c` 无验证 | **高** | 溢出可能性大 |
| `Math.min(userInput, 1000)` | **低** | min 函数保证上界 |
| 异常捕获但继续执行 | **中** | 需确认异常后逻辑 |

### 审计中的陷阱

**1. 类型转换陷阱**
- `parseInt("999999999999")` 返回 `999999999999`（JS 中为安全整数范围外）
- `size | 0` 按位 OR 截断为 32 位有符号整数，超过时变负数
- **技巧**：追踪数值来源到类型转换函数，验证转换前的输入范围

**2. 框架默认行为**
- `Express` 某些版本默认 `limit: '100kb'`，但自定义中间件可能移除限制
- `formidable` 的 `maxFileSize` 与文件数量独立计算
- **技巧**：检查中间件链顺序和全局配置覆盖

**3. 计算顺序问题**
```javascript
// 陷阱：计算顺序导致中间溢出
const total = (a + b) * c;  // 先加可能溢出

// 正确：交换计算顺序
const total = a * c + b * c;  // 但仍需验证
```

**4. 条件分支遗漏**
- 仅在主路径检查，异常路径未检查（如 catch 块中重试分配）
- 多个构造方式（`new Array()` vs `Array.from()` vs 数组字面量扩展）的不一致处理

### 审计清单

- [ ] 定位所有数组构造与 length 赋值操作
- [ ] 追踪长度参数源头（用户输入、计算、外部 API）
- [ ] 检查参数验证逻辑（范围、类型、负数）
- [ ] 验证乘法运算是否有提前检查
- [ ] 评估异常处理是否安全（RangeError、OutOfMemory）
- [ ] 检查是否有时间/空间复杂度文档或限制说明
- [ ] 测试边界值（0、-1、MAX_SAFE_INTEGER、Infinity）

