# C_Memory_Allocation_User_Input

**漏洞类型**: 基于用户输入的内存分配，malloc/calloc/realloc 使用未验证的用户输入作为分配大小

**C/C++**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

e.g. "对应代码示例xxxxx，（快速定位到核心操作的技巧）,（快速定位到保护机制的技巧）"

注意：Details中必须包含这三部分，且后两部分需要在标注审计等级，（L0:快速跳过）（L1:关键词扫描）（L2:跳读）（L3:逐行读）（L4:跨模块追踪）

## Classify

如何研判并归类为漏洞/误报/代码异味（这部分仅进行理论指导无须示例）

## Details

**代码示例**：`malloc(user_size)`、`calloc(rows, cols)` 其中 `rows/cols` 来自用户输入、`realloc(ptr, newSize)` 中新大小的计算

- **核心操作定位技巧** (L1: 关键词扫描)：扫描内存分配函数 `malloc`、`calloc`、`realloc`、`new/new[]`（C++），检查参数是否直接来自用户输入或外部数据源。重点关注乘法运算（`malloc(width * height)`）。

- **保护机制定位技巧** (L3: 逐行读)：查找分配前的大小验证（`if (size > MAX_ALLOC)` 或 `if (width > MAX_WIDTH || height > MAX_HEIGHT)`）、检查乘法溢出、分配后的 NULL 检查、或使用安全分配包装函数。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：无大小验证，参数直接来自用户输入，可导致内存耗尽或缓冲溢出
- **误报**：大小为常量、明确验证过范围、或内存量受系统资源限制
- **代码异味**：涉及乘法但无溢出检查，需分析操作数来源

## Low risk

- 分配大小为编译期常量
- 明确的上界检查（`if (size > 1024 * 1024)`）
- 使用安全分配库（如 Rust 的 vec! 或 C++ 的 std::vector）
- 分配大小来自已验证的业务逻辑（如分页大小）
- 检查 `malloc` 返回值后使用

## Audit Techniques

### 真实漏洞的特征

1. **乘法溢出链**：`malloc(rows * cols * sizeof(struct))`，三个及以上操作数参与乘法，其中至少两个来自用户输入，未显式溢出检查
   - 实际案例：图片库中 `malloc(width * height * 3)` 处理 JPEG 尺寸，攻击者传入 65536*65536 导致分配 0 字节
   - 特征：溢出后 malloc 返回非NULL指针，但分配空间严重不足，后续写入触发堆溢出

2. **类型转换隐患**：`malloc((int)user_input * sizeof(long))`，int溢出但被强制转换为 size_t（无符号）
   - 实际案例：OpenSSL 中 `s->s3->tmp.key_block_length = (int)(EVP_MD_size(...))` 的乘法结果为负，转换为超大 size_t
   - 特征：符号扩展导致分配超大内存，虽然失败但可被误认为是拒绝服务而非内存破坏

3. **二阶段验证缺失**：验证单个参数范围，但未检查组合乘积
   - 实际案例：`if (width < 10000 && height < 10000) malloc(width * height)`，实际可分配 100MB（足够触发溢出）
   - 特征：单个参数验证充分，但乘积未再次验证

### 常见误报场景

1. **固定倍数系数**：`malloc(user_count * 16)` 其中 user_count 来自已验证的数据库查询结果
   - 判断标准：追溯输入源头，如果最终来自数据库的 COUNT(*) 或已验证的业务逻辑，则为误报

2. **隐式验证**：`malloc(size)` 前有 `size = min(size, MAX_SIZE)` 或通过函数返回值自身有范围保证
   - 实际例：`size = read_varint()`，varint 编码本身限制了最大值
   - 判断标准：追踪数据流，确认约束是否被完全应用

3. **运行时资源限制**：系统内存耗尽时 malloc 自动失败，物理约束而非代码约束
   - 但切勿放过：只要代码未检查 malloc 返回值就使用，仍为漏洞

4. **二级指针或结构体大小**：`malloc(sizeof(node_t) * count)` 其中 sizeof 编译期固定
   - 常见误判：认为 sizeof 变量，需确认是否真的涉及用户定义的动态大小类型

### 审计快速判别流程

**Step 1** (L1-关键词扫描 5秒): 定位 `malloc`、`calloc`、`realloc`、`new` 相关调用，标记参数来源（用户输入/常量/全局变量）

**Step 2** (L2-跳读 10秒): 向上追踪参数来源，5 行以内是否有 `if/switch` 范围检查，观察有无 `*`、`+`、`<<` 等可能溢出的操作

**Step 3** (L3-逐行读 30秒):
- 若涉及乘法：逐项检查溢出可能性，验证是否存在显式溢出检查或范围约束
- 若为 calloc：特别检查行列参数是否独立验证
- 若为 realloc：新大小计算逻辑是否安全，是否重复检查

**Step 4** (L4-跨模块追踪): 对可疑点进行符号执行或构造 POC，确认溢出是否真实可触发

### 实战区分案例

| 代码段 | 判断 | 理由 |
|--------|------|------|
| `malloc(read_int() * sizeof(T))` | **漏洞** | read_int() 无范围检查，直接参与乘法 |
| `malloc(min(user_size, 1<<20))` | **误报** | 隐式上界，不可能超过 1MB |
| `malloc(db_count * sizeof(record_t))` | **误报** | db_count 来自已验证的查询，数据库本身有行数限制 |
| `malloc(width * height)` 其中 width/height < 1000 检查存在 | **L2 跳读** | 单个参数验证，需检查乘积是否 < 某常数上界 |
| `calloc(rows, sizeof(...))` 其中 rows = url_param | **漏洞** | calloc 两参直接来自用户，无验证 |
| `new char[config->size]` | **L3 逐行读** | 需追踪 config 的初始化来源和有效期 |

### 审计陷阱与防护建议

**陷阱1：malloc 返回值检查**
- 常见误判：看到 `if (ptr != NULL) { ... }` 就认为安全，实际上这只验证了分配本身，不能防止溢出前的漏洞
- 正确做法：分配前验证大小，分配后验证返回值，两者都需要

**陷阱2：sizeof 混淆**
- 常见误判：`malloc(sizeof(array))` 以为大小是常数，但 array 可能是指针而非数组
- 防护技巧：查看 typedef 和声明，确认 sizeof 作用的是否为变长类型

**陷阱3：溢出检查不完整**
- 常见实现：`if (size > MAX) return error;` 但乘法发生在检查之后，检查变成形同虚设
- 正确做法：在参与乘法前逐项检查，或使用安全乘法宏

**陷阱4：多层函数调用**
- 常见漏判：`malloc(calc_size(user_input))`，跳过了 calc_size 内部的溢出可能
- 防护技巧：递归追踪函数内部，特别关注其中的乘法和类型转换

### 溢出检查的有效性判断

有效的检查方式（可信赖）：
- `if (size > MAX_SIZE || size == 0) return -1;` 然后才执行 malloc
- `if (width > MAX_WIDTH || height > MAX_HEIGHT) ...` 且乘积未再增长
- 安全乘法宏：`if (safe_mul(a, b, &result)) malloc(result);`
- 类型强制转换前检查：`unsigned long sz = (unsigned long)width * height; if (sz > MAX) ...`

无效的检查方式（不能信赖）：
- 只检查单项而不检查乘积：`if (a < 1000 && b < 1000)` 而不检查 `a*b < LIMIT`
- 检查在乘法之后：先 `size = a * b`，再 `if (size < 0)`（有符号溢出时检查已失效）
- 仅检查 malloc 返回值：`ptr = malloc(size); if (!ptr) return;`（无法防止分配前溢出）
- 在 typedef 隐藏的数值操作中：`malloc(ELEMENT_COUNT * ELEMENT_SIZE)`，两个宏都来自用户

### 现场检视要点

1. **第一眼识别**：看到 `malloc/calloc/new[]` 立即标记，不要跳过任何内存分配操作
2. **参数追踪**：在参数处右键跳转到定义，不要止于当前函数作用域
3. **乘法检测**：特别关注 `*`、`<<` 操作，以及隐含的乘法（如 `sizeof` 与变量的组合）
4. **边界交叉**：跨越 if/else、for/while 时，检查变量可能的取值范围变化
5. **NULL 检查**：存在但不充分，分配前验证才是关键

### 高危模式速查表

| 模式 | 风险等级 | 原因 | 审计建议 |
|------|--------|------|--------|
| `malloc(a * b)` 无检查 | **严重** | 直接乘法溢出 | L1 快速定位，必须分析 a/b 来源 |
| `malloc(a * b * c)` | **严重** | 三项乘法更易溢出 | L3 逐项检查范围 |
| `calloc(a, b)` a/b 来自用户 | **严重** | calloc 内部乘法隐式 | 特别关注参数来源 |
| `malloc(size << bits)` | **高** | 位移也是乘法 | 检查 bits 是否可控 |
| `malloc(a + b + offset)` | **中** | 加法也可溢出但概率小 | 检查是否有上界合并 |
| `malloc(CONST * user_count)` | **中-低** | 常数系数 | 追踪 user_count 源头 |
| `new[] T[size]` T 为大结构体 | **中** | 隐式乘法 | 分析 sizeof(T) 是否可变 |

