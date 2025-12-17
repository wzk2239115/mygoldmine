# C#｜XmlReader/DataSet 未禁用 DTD 处理

## Details

### 漏洞成因
.NET 的 `XmlReader`, `XDocument.Load`, `DataSet.ReadXml`, `XmlSerializer` 等 API 会基于 `XmlReaderSettings` 解析 XML。若未设置 `DtdProcessing = Prohibit` 并禁用 `XmlResolver`，攻击者可通过 XXE 获取敏感文件或发起 SSRF。

### 代码示例

**易受攻击的代码：**
```csharp
using var reader = XmlReader.Create(stream);
var doc = XDocument.Load(reader); // 默认允许 DOCTYPE
```

**安全示例：**
```csharp
var settings = new XmlReaderSettings {
    DtdProcessing = DtdProcessing.Prohibit,
    XmlResolver = null
};
using var reader = XmlReader.Create(stream, settings);
var doc = XDocument.Load(reader);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `XmlReader.Create`, `XDocument.Load`, `DataSet.ReadXml`, `XmlSerializer`, `XmlTextReader`。

**定位步骤：**
1. 搜索 XmlReaderSettings 创建或 `XmlReader.Create` 使用；
2. 跳读（L2）确认是否设置 `DtdProcessing` 和 `XmlResolver`；
3. 检查是否解析用户上传或网络响应。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 全局封装安全的 `XmlReaderSettings`；
- 使用 `XmlSecureResolver` 限制访问；
- 解析前移除 DOCTYPE 并做 schema 验证；
- 将 XML 转换为 JSON/对象前进行白名单检查。

**定位技巧：**
- 逐行读（L3）跨项目确认所有入口使用同一安全设置；
- 跨模块追踪（L4）工具库是否被外部组件调用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| XmlReaderSettings 统一禁用 DTD/Resolver | **L0（快速跳过）** | 风险低 |
| 个别入口缺少设置 | **L2（跳读）** | 快速补齐 |
| 默认加载用户 XML | **L3（逐行读）** | 高风险 |
| 工具库被多个项目引用 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. XmlReader 默认配置解析用户 XML；
2. `DtdProcessing` 未禁用、`XmlResolver` 未置空；
3. 可构造 payload 访问敏感资源或 SSRF。

#### 误报
1. XML 来源受信且可证明不可被篡改；
2. 解析仅在离线工具或测试环境运行；
3. 解析前已经对 XML 进行严格正则清洗（仍建议禁用）。

#### 代码异味
1. Mixed 使用旧 `XmlTextReader`（已弃用）；
2. 缺乏错误处理，默认捕获异常后继续执行；
3. 在数据层自动调用 `ReadXml` 未审查配置。

## Low risk

### 低风险评级场景

#### 1. 内网系统解析固定 XML
- 攻击面小，可暂降级。

#### 2. 输入源受签名保护
- 风险较低，但建议仍禁用实体。

#### 3. 已计划统一封装 `XmlReader` 工具
- 明确计划，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内网系统 | 攻击面小 | 中 |
| 签名保护 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
