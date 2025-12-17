---
name: xxe
description: 专业的审计工作流程，通过静态代码分析识别和验证 XXE（XML 外部实体注入）漏洞；重点关注检测不安全的 XML 解析器配置，包括未禁用外部实体、DTD 处理或参数实体，从而导致敏感信息泄露、服务器端请求伪造（SSRF）、拒绝服务攻击等安全问题；利用按编程语言组织的参考资料目录中的参考指南。
---

**Attention**  
当项目中存在对用户可控或外部来源的XML数据进行解析的逻辑时，若解析器未禁用外部实体（External Entity）或未采取安全配置，则可能触发XXE漏洞。此类问题常见于涉及XML数据处理的模块，如API接口接收XML格式请求、导入/导出XML配置文件、SOAP Web服务、文档解析等业务场景。

---

**Early exit**

**在开始审计之前，必须首先运行 XXE 扫描脚本完成初步检索**，快速判断项目是否涉及 XML 解析相关代码。这是审计流程的强制性第一步，不可跳过。

**调用方式：**

```python
# 获取当前工作目录（项目路径）
target_path = get_cwd()

# 运行 XXE 扫描脚本
scan_result = skill_run_command(path="bash", params=["scripts/scan.sh", target_path])
```

若项目代码中完全不涉及XML解析（如未使用任何XML解析库，且所有接口仅处理JSON或其他非XML格式数据），则可快速退出对该漏洞类型的审计。

---

**通用 XXE 漏洞模式（所有项目必审）**

拿到任何涉及 XML 数据处理的应用项目，无论使用何种编程语言，以下 XXE 漏洞模式都必须进行审计。这些问题源于 XML 解析器配置不安全或使用不当，与具体语言实现无关。查看详细说明：[general.md](general.md)

**遇到防护机制时的绕过技巧引用：**
- SOAP/WebService 场景 → 详见 [bypassTricks.md - SOAP和WebService XXE](bypassTricks.md#soap和webservice-xxe)
- 带外数据泄露场景 → 详见 [bypassTricks.md - Out-of-Band (OOB)数据提取](bypassTricks.md#out-of-band-oob数据提取)
- 错误消息泄露场景 → 详见 [bypassTricks.md - 错误信息泄露](bypassTricks.md#错误信息泄露)
- 拒绝服务攻击（Billion Laughs）→ 详见 [bypassTricks.md - 复杂的参数实体链](bypassTricks.md#复杂的参数实体链)
- XML 关键字/内容过滤 → 详见 [bypassTricks.md - XXE过滤绕过](bypassTricks.md#xxe过滤绕过)
- 编码和格式限制 → 详见 [bypassTricks.md - 编码和格式绕过](bypassTricks.md#编码和格式绕过)
- 协议限制（file://、http:// 等）→ 详见 [bypassTricks.md - 协议利用](bypassTricks.md#协议利用)
- http 关键字过滤 → 详见 [bypassTricks.md - http关键字过滤的绕过](bypassTricks.md#http关键字过滤的绕过)
- XML 声明被过滤 → 详见 [bypassTricks.md - XML声明过滤的绕过](bypassTricks.md#xml声明过滤的绕过)
- 无回显/输出受限场景 → 详见 [bypassTricks.md - 嵌套DTD参数实体注入技术](bypassTricks.md#嵌套dtd参数实体注入技术)

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的 XML 解析库实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
- 使用 DocumentBuilderFactory、SAXParserFactory 等解析器时未禁用外部实体功能，详见：[Java_XmlParserUnsafeConfig.md](Java_XmlParserUnsafeConfig.md)  
- SOAP 服务接收 XML 请求但未对解析器进行安全配置，详见：[Java_SoapServiceXxe.md](Java_SoapServiceXxe.md)  
- 在导入/导出功能中解析用户上传的 XML 文件时未禁用 DTD 处理，详见：[Java_XmlImportFeature.md](Java_XmlImportFeature.md)

**Python**  
- 使用 xml.etree.ElementTree 默认配置解析 XML 时未禁用外部实体，详见：[Python_ElementTreeDefaultUnsafe.md](Python_ElementTreeDefaultUnsafe.md)  
- 使用 lxml 库解析用户输入的 XML 数据时配置不当，详见：[Python_LxmlXxe.md](Python_LxmlXxe.md)  
- 使用 xml.sax 解析器处理 XML 时允许外部实体解析，详见：[Python_SaxParserEntity.md](Python_SaxParserEntity.md)

**PHP**  
- 使用 SimpleXML 解析用户输入但未调用 libxml_disable_entity_loader(true)，详见：[PHP_SimpleXmlXxe.md](PHP_SimpleXmlXxe.md)  
- 使用 DOMDocument 加载 XML 时未禁用外部实体或 DTD 处理，详见：[PHP_DomDocumentEntity.md](PHP_DomDocumentEntity.md)  
- 在 XML-RPC 服务中解析 XML 请求时未进行安全配置，详见：[PHP_XmlRpcParse.md](PHP_XmlRpcParse.md)  
- SVG文件处理导致的XXE绕过，详见：[php_svg_xxe_bypass.md](php_svg_xxe_bypass.md)  
- Office文档（DOCX/XLSX/PPTX）解析中的XXE风险，详见：[php_office_document_xxe.md](php_office_document_xxe.md)

**Go**  
- 使用 encoding/xml 包的 Decoder 解析外部 XML 数据时未禁用外部实体，详见：[Go_EncodingXmlExternalEntity.md](Go_EncodingXmlExternalEntity.md)  
- 使用 xml.Unmarshal 直接解析用户可控的 XML 输入而未进行安全配置，详见：[Go_XmlUnmarshalUnsafe.md](Go_XmlUnmarshalUnsafe.md)

**JavaScript / TypeScript (Node.js)**  
- 使用 xml2js 库解析用户提交的 XML 时未禁用外部实体和 DTD 处理，详见：[JS_Xml2jsXxe.md](JS_Xml2jsXxe.md)  
- 使用 fast-xml-parser 等库时未正确配置安全选项禁用外部实体，详见：[TS_FastXmlParserConfig.md](TS_FastXmlParserConfig.md)

**C/C++**  
- 使用 libxml2 库解析 XML 时未禁用外部实体加载器或未设置安全标志，详见：[C_Libxml2ExternalEntity.md](C_Libxml2ExternalEntity.md)  
- 使用 XML 解析函数时未设置 XML_PARSE_NOENT 等选项禁用 DTD 处理，详见：[Cpp_XmlParseNoDtd.md](Cpp_XmlParseNoDtd.md)

**Rust**  
- 使用 roxmltree 库解析不受信任的 XML 数据时未验证 DOCTYPE 声明，详见：[Rust_RoXmltreeXxe.md](Rust_RoXmltreeXxe.md)  
- 使用 quick-xml 库时未禁用 DTD 或外部实体处理功能，详见：[Rust_QuickXmlDtd.md](Rust_QuickXmlDtd.md)

**C# (.NET)**  
- 使用 XmlDocument 加载用户输入的 XML 时未将 XmlResolver 设置为 null，详见：[CSharp_XmlDocumentXxe.md](CSharp_XmlDocumentXxe.md)  
- 使用 XmlReader 或 DataSet.ReadXml 时未禁用 DTD 处理和外部实体解析，详见：[CSharp_XmlReaderSecure.md](CSharp_XmlReaderSecure.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注 XML 数据处理相关的实现：**

- 查阅项目文档，重点关注涉及 XML 数据处理的功能模块说明
- 理解业务领域和核心功能，识别涉及 XML 解析的场景
- 识别关键组件、模块及其关系，特别是 API 接口、数据导入/导出模块、Web 服务模块
- 梳理应用流程（重点：XML 数据接收流程、XML 解析流程、XML 数据处理与返回）
- 识别关键业务功能（接收 XML 格式的 API 请求、导入/导出 XML 配置文件、SOAP Web 服务、文档解析等）
- 理解所用技术栈和框架（Web框架、XML解析库类型和版本，如 DocumentBuilderFactory、lxml、SimpleXML、xml2js 等）
- 查阅配置文件以理解系统行为（XML 解析器配置、外部实体处理配置、DTD 处理设置等）
- 定位 XML 解析器的初始化位置（解析器创建、配置参数设置、安全选项配置）
- 定位 XML 数据的解析位置（解析函数调用、数据来源验证、解析结果处理）
- 识别 XML 数据来源（HTTP 请求体、上传文件、外部接口、用户输入等）

**Early exit（早期退出）：**

**必须先执行前面 Early exit 章节中要求的扫描脚本**，根据扫描结果判断是否继续审计。如果扫描结果显示项目不符合条件（例如完全不涉及 XML 解析、未引入任何 XML 解析库、所有接口仅处理 JSON 等非 XML 格式数据），必须立即退出该漏洞类型的审计，无需继续深入分析。

只有在扫描脚本确认项目中存在 XML 数据处理逻辑并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅 XXE 漏洞的参考指南

XXE 漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用 XXE 漏洞模式（所有项目必审）**

在 **通用 XXE 漏洞模式** 章节中，列举了所有涉及 XML 处理的应用都必须审计的 XXE 问题：
- XML 解析器配置不安全（外部实体未禁用、DTD 处理未禁用、参数实体未禁用）
- 特定业务场景的 XXE（API 接口、文件上传、SVG 处理、Office 文档处理）
- XXE 用于服务器端请求伪造（内网探测、云环境元数据访问）
- XXE 拒绝服务攻击（Billion Laughs、Quadratic Blowup、Slow XXE）
- 特殊格式的 XXE 变种（YAML、JSON-LD、XOP/MTOM）
- 数据泄露技术（带外数据泄露、错误消息泄露）

这些问题与编程语言无关，是 XML 解析器配置和使用方式的通用缺陷，任何处理 XML 的应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言 XML 解析库的特定问题：
- 按编程语言分类（Java、Python、PHP、Go、JavaScript/TypeScript、C/C++、Rust、C#）
- 列出该语言 XML 解析库的典型 XXE 缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用 XXE 漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `xxe_external_entity_enabled.md`、`Java_XmlParserUnsafeConfig.md`、`Python_ElementTreeDefaultUnsafe.md`、`PHP_SimpleXmlXxe.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的漏洞模式，并进行有效的审计和评估。

**遇到防护机制或过滤时**：参考"通用 XXE 漏洞模式"章节中的**绕过技巧引用**列表，根据具体的保护措施类型（如 SOAP 服务、关键字过滤、协议限制等），查看 bypassTricks.md 中对应的绕过方法。

## 审计等级定义

XXE 漏洞审计采用分层的审计等级制度，根据 XML 解析器配置的安全性来指导审计深度。

| 等级 | 名称 | 时间 | 解析器配置特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 安全配置：外部实体已禁用、DTD 处理已禁用、XmlResolver 为 null |
| **L1** | 快速扫描 | 3-5 分钟 | 有配置 + 需确认：需验证所有解析器实例是否都配置了安全选项 |
| **L2** | 跳读 | 5-10 分钟 | 部分配置：部分解析器已配置，需验证覆盖范围和特殊格式处理 |
| **L3** | 逐行读 | 15-30 分钟 | 默认配置或明显缺陷：未禁用外部实体、DTD 处理未禁用 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：多处解析、文件上传、SVG/Office 文档、SOAP 服务 |

### 快速判断流程

**第 1 步：是否存在 XML 解析？**
- 无 XML 解析 → L0 跳过
- 有 XML 解析 → 继续第 2 步

**第 2 步：解析器是否禁用外部实体？**
- 明确禁用（DTD、外部实体、XmlResolver=null） → 继续第 3 步
- 未禁用或默认配置 → **L3+**

**第 3 步：所有解析器实例都配置了吗？**
- 所有实例都配置 → **L0**
- 部分实例配置或需确认 → **L1-L2**
- 多处解析或特殊格式 → **L3-L4**

### 各等级操作指南

**L0**：安全配置
```java
// Java - 禁用外部实体
DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
dbf.setFeature("http://xml.org/sax/features/external-general-entities", false);
dbf.setFeature("http://xml.org/sax/features/external-parameter-entities", false);

// Python - 使用 defusedxml
from defusedxml import ElementTree
ElementTree.parse(xml_file)

// PHP - 禁用实体加载
libxml_disable_entity_loader(true);
```

**L1**：有配置 + 需确认
- 所有解析器实例是否都禁用了外部实体？
- DTD 处理是否已禁用？
- XmlResolver 是否设置为 null？
- 是否使用了安全库（如 defusedxml）？

**L2**：部分配置
- 哪些解析器实例已配置？哪些未配置？
- SVG、Office 文档等特殊格式是否有单独处理？
- 文件上传是否有 MIME 类型验证？
- 是否存在绕过安全配置的代码路径？
- 遇到内容/编码过滤 → 详见 [bypassTricks.md - 编码和格式绕过](bypassTricks.md#编码和格式绕过)

**L3**：默认配置或未配置
```java
// 未禁用外部实体
DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
DocumentBuilder db = dbf.newDocumentBuilder();
db.parse(xmlInput);  // 存在 XXE 风险

// Python - 使用不安全的库
import xml.etree.ElementTree as ET
ET.parse(xml_file)  // 存在 XXE 风险

// PHP - 未禁用实体加载
$xml = simplexml_load_string($xmlInput);  // 存在 XXE 风险
```
完整分析解析器配置和使用流程，追踪数据流，确认 XXE 风险点

**L4**：复杂链路
- 多处 XML 解析：不同模块、不同解析器
- 文件上传：MIME 类型检测、文件内容验证
- SVG 文件处理：图片上传、图标处理
- Office 文档解析：DOCX/XLSX/PPTX 处理
- SOAP 服务：Web 服务接口 → 详见 [bypassTricks.md - SOAP和WebService XXE](bypassTricks.md#soap和webservice-xxe)
- 带外数据泄露：网络请求追踪 → 详见 [bypassTricks.md - Out-of-Band (OOB)数据提取](bypassTricks.md#out-of-band-oob数据提取)
- 遇到协议限制 → 详见 [bypassTricks.md - 协议利用](bypassTricks.md#协议利用)
- 遇到关键字过滤 → 详见 [bypassTricks.md - XXE过滤绕过](bypassTricks.md#xxe过滤绕过)、[http关键字过滤的绕过](bypassTricks.md#http关键字过滤的绕过)、[XML声明过滤的绕过](bypassTricks.md#xml声明过滤的绕过)

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 外部实体已禁用 + DTD 已禁用 | L0 | 无风险 |
| 有配置 + 需确认覆盖范围 | L1 | 验证所有实例 |
| 部分实例配置 | L2 | 验证覆盖范围 + 查看编码绕过 |
| 默认配置未禁用外部实体 | L3 | 高风险 |
| 文件上传或 SOAP 服务 | L4 | 完整追踪 + 查看 SOAP/协议绕过 |
| SVG/Office 文档处理 | L4 | 完整追踪 + 查看编码绕过 |
| 遇到过滤/WAF 保护 | L4 | 查看对应过滤类型的绕过章节 |
```

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的漏洞利用链：入口（不可信输入）→ 处理逻辑 → 危险操作 → 影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护
- 遇到防护机制时，参考上述"通用 XXE 漏洞模式"章节中的**绕过技巧引用**，针对具体保护措施查看对应的绕过方法

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-xxe-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
