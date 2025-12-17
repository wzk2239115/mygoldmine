# Java_Array_Length_Overflow

**漏洞类型**: 数组长度计算溢出，使用用户输入或计算结果创建数组时未验证长度

**Java**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

e.g. "对应代码示例xxxxx，（快速定位到核心操作的技巧）,（快速定位到保护机制的技巧）"

注意：Details中必须包含这三部分，且后两部分需要在标注审计等级，（L0:快速跳过）（L1:关键词扫描）（L2:跳读）（L3:逐行读）（L4:跨模块追踪）

## Classify

如何研判并归类为漏洞/误报/代码异味（这部分仅进行理论指导无须示例）

## Details

**代码示例**：`int[] arr = new int[userSize];`、`new ArrayList(size)` 其中 size 来自用户输入、`Arrays.copyOf(original, newLength)`

- **核心操作定位技巧** (L2: 跳读)：扫描数组创建操作 `new Type[size]`、Collection 初始化 `new ArrayList(size)`，检查 size 参数来源。关注大小计算涉及乘法（`new int[width * height]`）的情况。

- **保护机制定位技巧** (L2: 跳读)：查找创建前的大小验证（`if (size > MAX_ARRAY_SIZE)` 或 `if (size < 0)`），以及对负数/零的处理。Java 会抛出 NegativeArraySizeException，但如果溢出导致正数值可能绕过。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：无大小验证，参数来自用户输入，可导致 OutOfMemoryError 或整数溢出绕过检查
- **误报**：大小为常量、经过验证、或使用标准库自动处理
- **代码异味**：大小计算复杂，需追踪所有可能值

### 真实漏洞与误报的区分经验

#### 真实漏洞特征 (L3: 逐行读)
1. **无界计算**：大小参数直接来自 HTTP 请求、文件读取、网络输入（无中间校验）
   - 示例：`new int[request.getIntParameter("size")]`、`new byte[inputStream.read()]`

2. **隐藏的溢出**：乘法运算 `width * height` 未检查，可能从正数溢出到负数
   - `if (width > 0 && height > 0)` 检查不足，需要检查乘积本身
   - 常见绕过：`Integer.MAX_VALUE / 2 + 1` 与另一个大数相乘导致负数

3. **跳过异常处理**：虽然 JVM 会抛异常，但在循环或批处理中重复触发导致 DoS
   - 审计视角：即使异常被捕获，频繁 OOM 也是漏洞

#### 常见误报情形 (L2: 跳读)
1. **受限的本地计算**：
   - `int size = Math.min(userInput, 1000);` → 受限，低风险
   - `new int[list.size()]` → 容器自管理，低风险

2. **防御式检查被忽视**：
   - `if (size > 0 && size < 1_000_000) { new int[size]; }` → 安全
   - 误报常因未追踪到前置条件

3. **库函数隐式处理**：
   - `Arrays.copyOf(original, newLength)` → 库内部有边界检查
   - `ArrayList` 构造器 → 只预分配，溢出时才动态扩展

#### 审计关键技巧 (L3-L4: 逐行+跨模块)

**技巧1：追踪污点来源** (L4: 跨模块追踪)
- 标记所有用户输入入口点
- 追踪中间变量的每一步变换（乘除、加减、位移）
- 关键问题：在数组创建前，该值经过几次变换都没做溢出检查？

**技巧2：识别虚假防御**
- `if (size > 0)` 只检查负数，不检查上界 → 仍可能 OOM
- `if (size < Integer.MAX_VALUE)` 看似完整，但创建 `new int[size * 4]` 时仍溢出
- 必须检查：`size * stride <= MAX_ARRAY_SIZE`

**技巧3：多维数组陷阱**
- `new int[rows][cols]` 需同时验证两个参数
- `for (int i = 0; i < userRows; i++) arr[i] = new int[userCols];` → 两层都需验证

**技巧4：集合初始化容量陷阱**
- `new HashMap(capacity)` → 如果 capacity 很大，预分配也消耗资源
- `new StringBuilder(size)` → 类似情况

## Low risk

- 数组大小为编译期常量
- 明确的大小检查（`if (size > 1_000_000)`）
- 使用 Collections 框架自动管理大小
- 大小来自本地计算且受业务规则限制
- 使用 `guava` 等库的 `Preconditions.checkArgument(size > 0 && size < MAX)`
- 使用 try-catch 捕获 NegativeArraySizeException 且有 fallback 逻辑

## Medium risk

- 大小计算涉及乘法，仅检查了单个操作数的范围
- 用户输入经过简单边界检查但未覆盖溢出场景
- 在高并发下重复触发 OutOfMemoryError 的风险

## High risk

- 无任何验证的直接用户输入数组大小
- 多步计算后未再检查最终大小
- 大小参数来自不受信任的外部源（API、文件、网络）

