# JavaScript_Integer_Arithmetic_Overflow

**漏洞类型**: 整数运算溢出，JavaScript 使用双精度浮点数，但仍需关注位运算和大整数处理

**JavaScript/TypeScript**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

**代码示例**：`result = a + b`、`size = width * height`、`index = base + offset`、位运算 `value | 0`、`value >>> 0`

- **核心操作定位技巧** (L1: 关键词扫描)：扫描算术操作符 `+`、`-`、`*`，特别是乘法运算和位运算符（`|`、`>>`、`<<`、`>>>`）。JavaScript 位运算会将操作数转为 32 位有符号整数。关注涉及数组索引、内存操作、循环边界的计算。

- **保护机制定位技巧** (L2: 跳读)：查找安全整数检查（`Number.isSafeInteger(result)`、`Math.abs(value) <= Number.MAX_SAFE_INTEGER`），使用 BigInt 进行大数运算，或对操作数进行范围验证。检查是否避免位运算对大数的隐式转换。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：运算结果超出安全整数范围（±2^53 - 1）或位运算导致32位截断，结果参与关键业务逻辑
- **误报**：操作数在安全范围内、使用 Number.isSafeInteger 检查、仅用于非关键计算
- **代码异味**：大数运算未使用 BigInt，需评估是否会超出精度

## Low risk

- 操作数为常量或明确在安全整数范围内
- 使用 Number.isSafeInteger() 验证运算结果
- 使用 BigInt 进行大整数运算
- 位运算仅用于32位整数场景（如颜色值、标志位）
- 运算结果仅用于日志或显示

---

## Audit Skills（审计专业技巧）

### 关键字搜索策略

1. **运算符精准定位**：优先搜索 `*`、`<<`、`**`（幂运算）、`+` 在循环或数组访问前的位置
2. **隐式转换风险点**：检查 `parseInt()`、`Number()`、`Math.floor()` 后是否直接用于位运算或数组索引
3. **类型混淆场景**：字符串到数字的转换路径，特别是 JSON 解析、HTTP 参数、数据库查询结果
4. **流敏感分析**：追踪外部输入（用户输入、API 响应、文件内容）到整数运算的完整数据流

### 真实漏洞特征识别

**高危信号**：
- 不经验证的用户输入直接参与乘法：`arr[user_index * stride]`
- 位运算后用于内存操作：`(offset << 2) | 0` 作为数组下标
- 大数乘法无范围检查：`rowCount * colCount` 分配二维数组
- BigInt 与普通 Number 混用：`BigInt(a) + b`（类型错误，但可能绕过检查）

**真实案例对标**：
```javascript
// 漏洞：用户可控宽度和高度，乘法可能溢出
const size = width * height;  // width=50000, height=50000 -> Number.MAX_SAFE_INTEGER
const buffer = new ArrayBuffer(size);

// 漏洞：位运算截断后用于索引
const idx = (input << 2) >>> 0;  // 负数左移后可能溢出
if (idx < data.length) access(data[idx]);

// 漏洞：字符串到整数的隐式链路
const offset = parseInt(req.headers['x-offset']) * rowSize;  // 无上界检查
```

### 误报排查清单

| 场景 | 判断标准 | 示例 |
|------|---------|------|
| 位标志位操作 | 操作数 < 2^31，仅用于标志存储 | `flags \|= (1 << 5)` ✓ |
| 颜色值计算 | RGB 各分量 <= 255，结果用于 CSS | `(r << 16) \| (g << 8) \| b` ✓ |
| 循环计数 | 初值和增量明确，最大值 < 2^53 | `for(let i=0; i<1000; i++)` ✓ |
| 时间戳操作 | 使用 Date.now()，范围已知 | `Date.now() * 1000` 注意精度 ⚠ |
| 概率计算 | 结果仅用于概率比较 | `Math.random() * 100 \| 0` ✓ |
| 常量预计算 | 编译期可确定，无动态输入 | `const MAX = 2 ** 30; const x = 100 * MAX` ✓ |

### 审计工作流

1. **第一阶段（快速定位）**：
   - 使用 regex `[\+\-\*].*[\(\[]|Number\(|parseInt\(` 定位运算密集区
   - 跳读相邻 5 行，识别是否涉及数组、Buffer、ArrayBuffer

2. **第二阶段（源头溯源）**：
   - 为疑似操作数标记：用户输入、配置参数、外部数据？
   - 追踪 3 跳内是否有验证（bounds check、Math.min/max、if 条件）

3. **第三阶段（上下文评估）**：
   - 检查运算结果的使用：内存分配 > 索引操作 > 显示 > 日志
   - 评估攻击可行性：是否可控、是否有利用价值

### 常见漏报与误杀

**易漏过的场景**：
- 链式运算中的中间溢出：`(a + b) * c`，虽然结果可能安全，但 `a+b` 已溢出
- BigInt 边界条件：`n > Number.MAX_SAFE_INTEGER ? BigInt(n) : n` 逻辑错误
- 框架隐式转换：某些模板引擎、ORM 中的类型强制转换
- 异步上下文中的竞态：多次调用累加导致溢出（罕见但存在）

**易误杀的场景**：
- 归一化操作：`Math.floor(value)` 后范围已知
- 防御性编程：`Math.min(input, MAX_VALUE) * factor`
- 单位转换：`ms / 1000` 不会溢出（反向操作）
- 校验和计算：`hash = (hash * 31 + char.code) >>> 0` 属于设计习惯

### 工具与自动化

- **静态分析工具**：ESLint 插件 `eslint-plugin-security` 可检测某些模式
- **运行时验证**：Chrome DevTools 中设置条件断点 `Number.isSafeInteger(suspiciousVar)`
- **数据流图谱**：对于复杂路径，绘制简单的控制流，标记所有转换点

### 审计场景库

**金融系统中的整数溢出**：
- 金额乘以汇率：`amount * exchangeRate` 需要 BigInt 或精确十进制库
- 利息计算：`principal * rate * (1 + rate) ** periods` 指数增长风险高
- 分账计算：多方分成相加需验证不超过总额

**数据处理中的溢出**：
- 分页查询：`(page - 1) * pageSize + pageSize` 当 page 很大时溢出
- 数据库偏移量：`OFFSET offset * limit` 整数溢出导致查询异常
- 文件切片：`chunkSize * chunkCount` 超大文件处理

**位运算陷阱**：
- UUID 生成中的位操作需确保操作数在 32 位范围内
- 权限位标志：`1 << privilegeLevel` 当 level > 31 时行为未定义
- 哈希分布：`hashCode & (buckets.length - 1)` 需确保 buckets 长度为 2 的幂

### 审计跳过原则

不需要深入审计的场景（快速pass）：
1. 使用类型检查库（TypeScript 严格模式）的项目
2. 完整覆盖 BigInt 的大数运算代码
3. 明确的业务域（如 Node.js 内置库中的微妙优化）
4. 已有 SAST 工具报告且经过验证的代码

### 审计笔记模板

审计时保持记录格式便于复查：

```
[文件] src/utils/calc.js:42
[函数] calculateIndex()
[操作] const idx = row * cols + offset
[源头] row、cols 来自用户输入（HTTP 参数）
[风险] 无验证，可构造 row=70000, cols=40000 导致溢出
[判定] ★★★ 高危 - 直接用于数组索引
[建议] 添加范围检查或使用 BigInt

[文件] src/color.js:15
[操作] (r << 16) | (g << 8) | b
[源头] r、g、b 来自用户输入
[风险] RGB 通常 0-255 范围，此处需验证
[判定] ★ 低风险 - 假设输入验证正确
[备注] 需交叉检查 RGB 输入验证函数
```

