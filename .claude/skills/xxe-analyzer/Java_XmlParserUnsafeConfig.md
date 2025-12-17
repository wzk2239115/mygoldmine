# Java｜XML 解析器未禁用外部实体

## Details

### 漏洞成因
Java 默认的 `DocumentBuilderFactory`、`SAXParserFactory`、`TransformerFactory` 等解析器在未显式禁用外部实体（External Entity）和 DTD 处理时，攻击者可以构造包含 `<!DOCTYPE>` 的 XML，读取服务器本地文件、执行 SSRF 或造成 DoS。常见于 REST/SOAP 接口、配置导入、消息解析等场景。

### 代码示例

**易受攻击的代码：**
```java
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
DocumentBuilder builder = factory.newDocumentBuilder();
Document doc = builder.parse(request.getInputStream());
```

**安全示例：**
```java
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
factory.setXIncludeAware(false);
factory.setExpandEntityReferences(false);
DocumentBuilder builder = factory.newDocumentBuilder();
Document doc = builder.parse(new InputSource(request.getInputStream()));
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `DocumentBuilderFactory`, `SAXParserFactory`, `TransformerFactory`, `XMLInputFactory`, `builder.parse`, `factory.newInstance`。

**定位步骤：**
1. 搜索创建 XML 解析器的代码；
2. 跳读（L2）确认是否设置禁用外部实体的特性；
3. 检查解析数据是否来自用户或外部系统。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 设置上述安全特性为 `true/false`；
- 使用安全的 StAX `XMLInputFactory` 并禁用实体；
- 在 Spring/SOAP 配置中启用 `xmlns:sec` 安全选项；
- 通过 Schema 验证或白名单过滤限制 DTD。

**定位技巧：**
- 逐行读（L3）确保所有工厂实例都设置了特性；
- 跨模块追踪（L4）通用工具类、拦截器是否覆盖全部入口。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 统一初始化并禁用外部实体 | **L0（快速跳过）** | 风险低 |
| 某些解析器未设置特性 | **L2（跳读）** | 快速补齐配置 |
| 广泛使用默认配置解析外部 XML | **L3（逐行读）** | 高风险 |
| 解析器在多个模块动态创建 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. 使用默认解析器解析用户可控 XML；
2. 未禁用 DOCTYPE、外部实体；
3. 可构造 XXE payload 读取/请求敏感资源。

#### 误报
1. 解析的 XML 来源受控（内部签名、白名单）且无攻击面；
2. 仅解析固定模板或常量字符串；
3. 中间件/网关已过滤 DOCTYPE（需佐证）。

#### 代码异味
1. 仅部分特性禁用（例如只禁用 general entity）；
2. 使用旧版 JAXP 实现，默认不安全；
3. 工厂实例缓存后在其他场景复用，缺乏注释。

## Low risk

### 低风险评级场景

#### 1. XML 仅来源于可信内部系统
- 攻击面小，但仍建议启用安全特性。

#### 2. 解析用于测试或脱机工具
- 可暂降级，但应标注风险。

#### 3. 正在升级到安全配置
- 有明确时间表，可暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 可信来源 | 攻击面小 | 中 |
| 脱机/测试用途 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
