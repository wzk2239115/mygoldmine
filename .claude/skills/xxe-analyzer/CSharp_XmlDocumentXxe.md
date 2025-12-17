# C#｜XmlDocument 未禁用 XmlResolver

## Details

### 漏洞成因
.NET 中 `XmlDocument` 默认的 `XmlResolver` 允许解析外部实体。若在 Web API、WCF、桌面程序中加载用户提供的 XML 而不将 `XmlResolver` 设为 `null`，就会触发 XXE。

### 代码示例

**易受攻击的代码：**
```csharp
var doc = new XmlDocument();
doc.LoadXml(xmlString); // 默认 XmlResolver 允许外部实体
var name = doc.SelectSingleNode("/user/name").InnerText;
```

**安全示例：**
```csharp
var settings = new XmlReaderSettings {
    DtdProcessing = DtdProcessing.Prohibit,
    XmlResolver = null
};
using var reader = XmlReader.Create(new StringReader(xmlString), settings);
var doc = new XmlDocument { XmlResolver = null };
doc.Load(reader);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `XmlDocument`, `LoadXml`, `Load`, `XmlResolver`, `XmlReaderSettings`。

**定位步骤：**
1. 搜索 XmlDocument 实例化代码；
2. 跳读（L2）确认是否设置 `XmlResolver = null`；
3. 检查是否使用 `XmlReader` 并配置 `DtdProcessing`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `XmlResolver = null`；
- `XmlReaderSettings` 设置 `DtdProcessing = Prohibit/Ignore`；
- 使用 `System.Xml.XmlSecureResolver` 限制访问；
- 接口层过滤 DOCTYPE。

**定位技巧：**
- 逐行读（L3）确保所有入口均使用安全设置；
- 跨模块追踪（L4）公共解析器被多个组件调用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| XmlDocument/XmlReader 都禁用实体 | **L0（快速跳过）** | 风险低 |
| 部分入口遗漏配置 | **L2（跳读）** | 需补齐 |
| 默认 LoadXml 处理用户输入 | **L3（逐行读）** | 高风险 |
| 解析器封装被全局复用 | **L4（跨模块追踪）** | 需彻底排查 |

## Classify

### 研判标准

#### 确认漏洞
1. XmlDocument 默认解析用户 XML；
2. XmlResolver 未置空；
3. 可构造 payload 访问敏感资源。

#### 误报
1. XML 来源于可信签名；
2. 功能仅在离线工具使用；
3. 外部网关过滤 DOCTYPE。

#### 代码异味
1. 混用安全和不安全配置；
2. 注释提醒 TODO 未实现；
3. 异常处理吞掉解析错误。

## Low risk

### 低风险评级场景

#### 1. 内部接口解析可信 XML
- 攻击面小，可暂降级。

#### 2. 输入经过签名/加密校验
- 风险较低，但建议仍禁用实体。

#### 3. 已计划统一封装 XmlDocument 工具
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部接口 | 攻击面小 | 中 |
| 签名校验 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
