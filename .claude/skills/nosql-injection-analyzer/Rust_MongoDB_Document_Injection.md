# Rust MongoDB Document Injection

## Details

**漏洞成因**：Rust 的 MongoDB 驱动（mongodb crate）提供类型安全的接口，但使用 `bson` 库进行文档操作时，若通过 `from_reader()`、`from_slice()` 等方法反序列化用户输入，攻击者可构造恶意 BSON 文档注入查询。特别是在使用 `Document::get_str()` 等动态访问时。

**代码审计焦点**：
- 是否使用 `bson::from_reader()`、`bson::from_slice()` 反序列化用户输入
- `Document` 对象的构造是否通过用户输入
- 是否使用了 `serde_json::from_str()` 转换用户输入
- 查询过滤器是否通过 `doc!` 宏或 `bson!` 宏构造

**核心定位技巧**：
- **(L1: 关键词扫描)** 搜索 `from_reader`、`from_slice`、`doc!`、`bson!` 等关键字
- **(L2: 跳读)** 检查这些方法的参数是否来自用户输入或网络数据
- **(L3: 逐行读)** 追踪 Document 对象的构造和使用，确认是否进行了验证
- **(L4: 跨模块追踪)** 检查是否通过多个函数进行 Document 转换

**保护机制识别**：
- **(L1: 关键词扫描)** 检查是否使用了 Rust 的类型系统（struct + serde）
- **(L2: 跳读)** 验证反序列化是否使用了类型检查
- **(L3: 逐行读)** 确认是否使用了 MongoDB 驱动的高级 API（Collection::find）
- **(L4: 跨模块追踪)** 检查是否使用了验证库（validator crate）

## Classify

**漏洞研判**：
1. 若直接反序列化用户输入为 Document → 漏洞
2. 若 Document 的键由用户输入构造 → 漏洞
3. 若通过动态访问（如 `doc.get_str(key)`，其中 key 由用户控制）→ 漏洞

**误报风险**：
1. 使用 struct + serde 进行类型安全反序列化 → 低风险
2. Document 的键为常量且值通过类型检查 → 低风险
3. 使用 MongoDB 驱动的高级 typed API → 低风险

## Low risk

- 使用 struct + serde 进行类型安全反序列化
- Document 的键使用常量或枚举
- 值通过 Rust 类型系统限制
- 使用 MongoDB 驱动的 typed Collection API
- 验证库验证所有用户输入

