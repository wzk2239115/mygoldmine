# Java_Integer_Arithmetic_Overflow

**漏洞类型**: 整数运算溢出，加减乘运算结果超出 int 或 long 类型范围

**Java**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

e.g. "对应代码示例xxxxx，（快速定位到核心操作的技巧）,（快速定位到保护机制的技巧）"

注意：Details中必须包含这三部分，且后两部分需要在标注审计等级，（L0:快速跳过）（L1:关键词扫描）（L2:跳读）（L3:逐行读）（L4:跨模块追踪）

## Classify

如何研判并归类为漏洞/误报/代码异味（这部分仅进行理论指导无须示例）

## Details

**代码示例**：`result = a + b`、`product = width * height`、`offset = base + userInput`，其中操作数类型为 int/long

- **核心操作定位技巧** (L1: 关键词扫描)：扫描算术操作符 `+`、`-`、`*`，特别是乘法。检查操作数类型（int vs long）、以及操作数来源（用户输入、计算结果、API 返回值）。关注涉及内存/数组操作的计算。

- **保护机制定位技巧** (L2: 跳读)：查找溢出检查（如 `if (a > Integer.MAX_VALUE - b)`、`if (Math.multiplyExact() throws ArithmeticException`），使用 `Math.addExact/subtractExact/multiplyExact()` 等溢出感知方法、或转为 long 进行中间计算。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：无溢出检查，操作数来自不受信任的源，结果参与关键业务逻辑
- **误报**：操作数为常量或明确范围内、使用溢出检查方法、仅用于日志
- **代码异味**：类型混合，需评估溢出影响

## Audit Tips & Real Cases

### 审计手法进阶

**1. 数据流溯源** (L4: 跨模块追踪)
- 追踪操作数来源：用户输入 → HTTP 参数、JSON、CSV、数据库查询结果
- 检查中间层过滤：API 限制、业务规则约束、范围校验
- 关键：即使单个操作看似安全，组合操作可能溢出 (如 a*b+c)
- 示例：`int result = width * height + offset;` 需同时校验三个操作

**2. 上下文分析** (L2-L3)
- **关键操作**：内存分配 (`new byte[size]`)、数组访问 (`arr[index]`)、缓冲区操作
- **非关键操作**：日志记录的计数、UI 展示的数值
- **字节操作陷阱**：`byte b = someInt & 0xFF;` 隐式转换，需校验 someInt 范围

**3. 真实漏洞特征**

| 特征 | 示例 | 审计判断 |
|------|------|--------|
| 乘法无界 | `buffer = new byte[rows * cols];` | 高危：用户控制 rows/cols，无大小限制 |
| 加法溢出转负 | `offset = start + len; if(offset < 0) DoS` | 高危：利用溢出导致负数，绕过边界检查 |
| 连续操作堆积 | `sum = a + b + c + d;` a,b,c,d 均来自输入 | 中危：多次加法累积溢出风险 |
| 类型混合 | `int idx = (int)largeValue;` 未校验 | 高危：截断导致意外的小值 |
| 右移掩码 | `int val = input >> 16;` 负数输入 | 中危：算术右移导致符号扩展 |

**4. 常见误报陷阱**

- ✗ 误判：`int x = 100 * 200;` 未检测到是常量 → 需验证编译期常量
- ✗ 误判：`Math.min(a, Integer.MAX_VALUE)` 后的加法 → 需追踪返回值范围
- ✗ 误判：`if (a < Integer.MAX_VALUE) b = a + 1;` 条件遗漏等值情况 → `a == Integer.MAX_VALUE` 也溢出
- ✓ 正判：`int safe = Math.toIntExact(longValue);` 检查异常捕获，验证是否有兜底逻辑

**5. 微妙的真实漏洞**

```
// 案例 1: 位移隐形溢出（常被漏检）
public int decodePacketSize(int encodedSize) {
    return (encodedSize << 2);  // 乘以 4，无检查
}
// 漏洞：encodedSize > 536870911 时溢出，allocate 时 buffer 大小错误

// 案例 2: 条件检查绕过
public byte[] buildBuffer(int width, int height) {
    if (width > 1000 || height > 1000) throw new Exception;
    return new byte[width * height];  // 漏洞：1000*1000=1000000 < Integer.MAX，但 × 数据类型可能为负
}

// 案例 3: 无符号与有符号混淆
public void parseLength(byte[] data) {
    int len = data[0] & 0xFF;      // 0-255
    int len2 = data[1] << 8;       // -32768 ~ 32512（负数风险）
    int total = len + len2;        // 符号位不同的加法
}
```

**6. 审计效率优化**

- 优先级排序：`new byte[]` `new int[]` → 乘法操作 → 条件分支中的加减
- 快速排除：已使用 `Math.*Exact()` 或 `Objects.requireNonNull()` 验证的操作
- 二次检验：找到溢出点后，验证：(1) 来源是否真正不可控 (2) 异常处理是否充分 (3) 结果使用场景

**7. 真实vs误报对比**

| 场景 | 代码 | 判断 | 理由 |
|------|------|------|------|
| 真实漏洞 | `new byte[userSize * 2];` 无校验 | **HIGH** | 用户可输入 Integer.MAX_VALUE，导致负数 |
| 误报 | `new byte[FIXED_SIZE * 2];` 常量 | **PASS** | 编译期常量，不会溢出 |
| 真实漏洞 | `int result = a * b; if(result < 0) error;` | **HIGH** | 溢出后转负不是检查，漏洞仍存在 |
| 误报 | `long result = (long)a * b;` 转 long | **PASS** | 中间结果用 long 存储，不会信息丧失 |
| 边界漏洞 | `if (size <= Integer.MAX_VALUE) arr[size];` | **HIGH** | 等号遗漏，size==Integer.MAX_VALUE 时溢出 |
| 代码异味 | `int hash = a ^ b ^ c;` 无逻辑 | **INFO** | 位运算无溢出风险，但应验证是否本意 |

**8. 跨越常见的审计陷阱**

- **陷阱1：符号位混淆**
  - `byte b = -1;` 与 `int i = b & 0xFF;` 后 i=255（无符号解读）vs 传递给有符号参数时 i=-1（符号扩展）
  - 审计时需追踪最终使用场景

- **陷阱2：API 返回范围未知**
  - `List.size()` 返回 int，无法超过 Integer.MAX_VALUE（安全）
  - 但数据库查询 `.getLong()` 可能无界，需追踪源头

- **陷阱3：条件检查的微妙缺陷**
  - `if (a + b > threshold) { alloc(a + b); }` → 漏洞：a+b 可能先溢出变负
  - 正确做法：先用 `Math.addExact()` 检查，再判断大小

- **陷阱4：数据类型自动转换**
  - `int[] arr = new int[1 + 2147483647];` 自动溢出
  - `int[] arr = new int[1L + 2147483647];` 编译错误（更安全）

**9. 实战审计Checklist**

- [ ] 定位所有整数算术操作（+、-、*、<<、>>）
- [ ] 确认操作数类型（int/long/byte/short）和来源（常量/参数/返回值/数据库）
- [ ] 检查溢出防护：(1) 明确的范围校验 (2) Math.*Exact() 调用 (3) 中间值用 long 存储
- [ ] 追踪结果使用场景：数组分配/内存操作 (高危) vs 日志/计数 (低危)
- [ ] 验证条件判断是否完整（特别是边界值 Integer.MAX_VALUE/-Integer.MIN_VALUE）
- [ ] 检查异常处理：Math.*Exact() 抛出异常时是否有 catch 和降级方案
- [ ] 审视复合操作：`a * b + c` 需逐个检查，不能只看最终结果

**10. 审计报告关键指标**

- **高危判断**：用户输入 + 乘法/位移 + 内存分配，无检查
- **中危判断**：条件检查不严密（等号遗漏、转换后再检查）、多步累积溢出
- **低危判断**：明确上界的操作、已用防护方法、非关键场景
- **需求澄清**：未知来源的返回值范围、跨系统数据流、业务规则不明确

## Low risk

- 操作数均为编译期常量或已验证值
- 使用 `Math.addExact/subtractExact/multiplyExact()` 等方法
- 转为 long 进行中间计算后再转回 int（确保无信息丧失）
- 操作仅用于格式化、时间戳等非关键场景
- 使用 BigInteger 进行精确计算

