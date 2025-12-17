# Python｜xml.sax 解析器允许外部实体

## Details

### 漏洞成因
`xml.sax` 解析器在默认设置下会解析外部实体。若使用 `xml.sax.make_parser()` 解析外部来源的 XML 而未禁用相关特性，攻击者可以通过 DTD 声明访问本地文件或发起 SSRF。

### 代码示例

**易受攻击的代码：**
```python
import xml.sax

class ItemHandler(xml.sax.ContentHandler):
    def startElement(self, name, attrs):
        pass

def parse_xml(data: bytes):
    parser = xml.sax.make_parser()  # 默认允许实体
    parser.setContentHandler(ItemHandler())
    xml.sax.parseString(data, ItemHandler())
```

**安全示例：**
```python
import xml.sax

def secure_parser() -> xml.sax.xmlreader.XMLReader:
    parser = xml.sax.make_parser()
    parser.setFeature("http://xml.org/sax/features/external-general-entities", False)
    parser.setFeature("http://xml.org/sax/features/external-parameter-entities", False)
    parser.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", False)
    return parser

def parse_xml(data: bytes):
    parser = secure_parser()
    parser.setContentHandler(ItemHandler())
    parser.parse(io.BytesIO(data))
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xml.sax`, `make_parser`, `parse`, `parseString`, `setFeature`。

**定位步骤：**
1. 搜索 `xml.sax` 的使用；
2. 跳读（L2）确认是否调用 `setFeature` 禁用实体；
3. 检查数据来源是否可控。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 自定义工厂函数封装安全配置；
- 使用 defusedxml.sax；
- 限制上传文件类型/大小；
- 在解析前执行白名单过滤。

**定位技巧：**
- 逐行读（L3）确保 parser 在所有入口均应用安全特性；
- 跨模块追踪（L4）公共解析函数是否被多个服务调用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用安全 parser 或 defusedxml | **L0（快速跳过）** | 风险低 |
| 部分 parser 缺少安全设置 | **L2（跳读）** | 需补齐 |
| 默认 parser 解析外部 XML | **L3（逐行读）** | 高风险 |
| 工具类被广泛复用 | **L4（跨模块追踪）** | 需彻底排查 |

## Classify

### 研判标准

#### 确认漏洞
1. xml.sax 默认配置解析用户 XML；
2. 未禁用实体或外部 DTD；
3. 可利用 payload 访问敏感资源。

#### 误报
1. 输入仅来自可信内部系统；
2. 在解析前移除 DOCTYPE 并验证；
3. 业务仅处理常量模板。

#### 代码异味
1. 解析器封装但无文档说明安全保障；
2. 混合使用 defusedxml 与原生 sax；
3. 对异常采取静默忽略。

## Low risk

### 低风险评级场景

#### 1. 功能仅内网使用
- 攻击面小，可暂降级。

#### 2. XML 文件经人工/系统签名校验
- 风险较低，但仍建议禁用实体。

#### 3. 已计划迁移到 defusedxml.sax
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内网场景 | 攻击面小 | 中 |
| 签名校验 | 影响有限 | 低 |
| 改造计划 | 可暂缓 | 低 |
