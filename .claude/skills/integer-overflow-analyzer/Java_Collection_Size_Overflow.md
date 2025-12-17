# Java_Collection_Size_Overflow

**漏洞类型**: 集合大小计算溢出，ArrayList、HashMap 等集合的大小计算或扩容逻辑存在溢出风险

**Java**

---

专注于这一垂直漏洞类型研判任务，从漏洞成因触发，编写该md文件，包含一下三个小标题，【注意语言精炼，表达简洁，可以作为审计小抄，仅专注于审计，不包含攻击与修复】：

## Details

e.g. "对应代码示例xxxxx，（快速定位到核心操作的技巧）,（快速定位到保护机制的技巧）"

注意：Details中必须包含这三部分，且后两部分需要在标注审计等级，（L0:快速跳过）（L1:关键词扫描）（L2:跳读）（L3:逐行读）（L4:跨模块追踪）

## Classify

如何研判并归类为漏洞/误报/代码异味（这部分仅进行理论指导无须示例）

## Details

**代码示例**：集合大小计算 `list.size() + offset`、容量扩展 `newCapacity = oldCapacity * 2`、自定义扩容逻辑中的乘法运算

- **核心操作定位技巧** (L1: 关键词扫描)：扫描 `.size()`、`.capacity`、乘法运算 `* 2` 或 `* 1.5`、位移运算 `<< 1`。重点关注自定义集合类的扩容方法、以及将 size 作为数组下标或内存分配参数的代码。

- **保护机制定位技巧** (L2: 跳读)：查找溢出检查（`if (newCapacity > Integer.MAX_VALUE)` 或 `if (newCapacity < 0)`）、使用 `Math.min/Math.max` 限制容量、或遵循 JDK 规范（如 ArrayList 的安全扩容实现）的代码。

## Classify

判断是否为漏洞的要点：
- **确定漏洞**：无溢出检查，集合大小直接参与内存分配、数组创建或循环
- **误报**：使用标准库集合（ArrayList、HashMap 等），它们已内置溢出保护
- **代码异味**：自定义集合扩容逻辑缺乏验证，但规模较小或流量可控

## Audit Techniques - 真实漏洞与误报区分

### 1. 运行时行为观察 (L3: 逐行读)
- **真实漏洞迹象**：调用 `new int[size]` 时，size 未经验证且受用户输入控制；方法无返回值检查（如 `ensureCapacity()` 无异常处理）；代码在特定版本 JDK 下表现与标准库不同
- **误报典型表现**：代码虽有乘法运算，但被 `ArrayList.ensureCapacity()` 等标准方法包裹；循环条件或分支限制了实际增长空间；集合大小被限制在常量范围内

### 2. 数据流溯源审计 (L4: 跨模块追踪)
- **高危数据链路**：外部输入 → parse/transform → 集合大小计算 → 内存分配。尤其关注 HTTP 参数、文件读取、网络数据作为集合初始容量时
- **安全数据链路**：配置文件定义 → 编译期常量 → 集合初始化；服务端逻辑计算 → 业务规则限制 → 集合操作

### 3. 真实案例对比

**真实漏洞示例**：
```java
// 无保护的自定义动态数组
int newCapacity = oldCapacity * 2;  // 无检查
Object[] newArray = new Object[newCapacity];  // 可溢出成负数，导致 NegativeArraySizeException
```

**误报示例**：
```java
// ArrayList 源码（JDK 1.8+）已内置保护
int newCapacity = oldCapacity + (oldCapacity >> 1);  // oldCapacity * 1.5
if (newCapacity - MAX_ARRAY_SIZE > 0)
    newCapacity = hugeCapacity(newCapacity);  // 溢出时返回 Integer.MAX_VALUE
```

### 4. 版本与框架依赖 (L2: 跳读)
- **Guava、Apache Commons Collections 等第三方库**：检查版本号，高版本通常已修复溢出风险
- **自定义集合框架**：重点审计非主流库；检查是否跟进 JDK 最新安全实践；关注 GitHub Issues 中的已报告漏洞

### 5. 审计优先级建议
1. **P0 - 立即复现**：用户输入 → `new byte[size]` 或 `list.size() * factor` 无检查
2. **P1 - 深入评估**：自定义集合类且代码逻辑复杂；边界值测试（Integer.MAX_VALUE、Integer.MIN_VALUE 附近）
3. **P2 - 低优先级**：受业务规则制约的容量增长；单元测试已覆盖的代码路径；明确文档化的限制

## Low risk

- 使用 Java 标准库集合类（ArrayList、HashMap、LinkedList 等）
- 集合大小来自本地常量或编译期可验证的数据
- 明确限制集合大小的业务规则（如分页、固定数量限制）
- 使用 `Collections.unmodifiableList()` 等不可变集合的只读操作
- 第三方成熟库（Guava 1.25+、Apache Commons 3.8+ 等）的集合实现

