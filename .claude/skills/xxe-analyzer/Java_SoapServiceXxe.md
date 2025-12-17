# Java｜SOAP 服务解析器未禁用外部实体

## Details

### 漏洞成因
基于 JAX-WS、Apache CXF、Spring-WS 的 SOAP 服务通常会自动解析请求中的 XML。如果未禁用外部实体或未配置安全的 `SOAPMessageFactory`，攻击者可构造恶意 SOAP 报文，实现文件读取、SSRF 或拒绝服务。

### 代码示例

**易受攻击的代码：**
```java
@WebService
public class OrderService {
    public String process(String requestXml) {
        MessageFactory mf = MessageFactory.newInstance();
        SOAPMessage msg = mf.createMessage(null, new ByteArrayInputStream(requestXml.getBytes(StandardCharsets.UTF_8)));
        // 处理 msg
        return "OK";
    }
}
```

**安全示例：**
```java
MessageFactory mf = MessageFactory.newInstance();
SOAPMessage msg = mf.createMessage();
SOAPPart soapPart = msg.getSOAPPart();
soapPart.setContent(new SAXSource(getSecureXmlReader(), new InputSource(new StringReader(requestXml))));

private XMLReader getSecureXmlReader() throws SAXException {
    SAXParserFactory spf = SAXParserFactory.newInstance();
    spf.setFeature("http://xml.org/sax/features/external-general-entities", false);
    spf.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
    spf.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
    spf.setNamespaceAware(true);
    return spf.newSAXParser().getXMLReader();
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `MessageFactory`, `SOAPMessage`, `SOAPPart`, `SAAJ`, `JAX-WS`, `CXF`。

**定位步骤：**
1. 搜索 SOAP 服务或消息工厂创建代码；
2. 跳读（L2）确认解析器是否使用安全配置；
3. 检查 WSDL/Endpoint 是否允许外部实体。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `javax.xml.XMLConstants.FEATURE_SECURE_PROCESSING`; 
- 在 Spring-WS 中配置 `SaajSoapMessageFactory` 禁用 DTD；
- 网关/ESB 对 SOAP 报文进行 DOCTYPE 过滤；
- 使用 XML firewall 或 schema 验证。

**定位技巧：**
- 逐行读（L3）确保所有 SOAP 端点都应用安全工厂；
- 跨模块追踪（L4）客户端调用是否复用不安全的消息工厂。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全部 SOAP 解析器已禁用外部实体 | **L0（快速跳过）** | 风险低 |
| 部分端点未应用安全配置 | **L2（跳读）** | 需补齐配置 |
| 默认 MessageFactory 直接解析请求 | **L3（逐行读）** | 高风险 |
| 多个服务/客户端共享不安全工厂 | **L4（跨模块追踪）** | 必须彻底梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. SOAP 服务使用默认解析器解析外部请求；
2. 未禁用外部实体或 DTD；
3. 可构造 XXE payload 读取内网资源。

#### 误报
1. SOAP 服务仅接收受信任系统签名的请求；
2. 请求经 API Gateway 过滤 DOCTYPE 并阻断攻击；
3. 报文只在内网传输且无外部攻击面。

#### 代码异味
1. 在客户端和服务端共享 MessageFactory 实例；
2. 依赖旧版 SAAJ 实现缺少安全特性；
3. 文档未说明为何允许外部实体。

## Low risk

### 低风险评级场景

#### 1. 服务仅在隔离网络运行
- 攻击面有限，可暂降级，但仍建议加固。

#### 2. 报文由内部序列化生成
- 风险较低，但需记录假设。

#### 3. 正在引入安全工厂或网关过滤
- 有明确计划，可暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 隔离网络 | 攻击面小 | 中 |
| 内部生成 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
