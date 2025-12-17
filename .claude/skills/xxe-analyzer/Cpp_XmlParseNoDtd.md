# C++｜libxml2/其他解析函数未禁用 DTD 处理

## Details

### 漏洞成因
在 C++ 项目中，常通过 libxml2、xerces-c、tinyxml2 等库解析 XML。如果未显式禁用 DTD/外部实体，攻击者可在 XML 中构造恶意实体。C++ 代码中常见通过 `xmlParseDoc`、`xercesc::DOMLSParser` 默认配置解析用户输入。

### 代码示例

**易受攻击的代码：**
```cpp
#include <libxml/parser.h>

xmlDocPtr doc = xmlParseDoc(reinterpret_cast<const xmlChar*>(xml.c_str()));
if (doc == nullptr) {
    throw std::runtime_error("invalid xml");
}
```

**安全示例：**
```cpp
xmlDoValidityCheckingDefaultValue = 0;
xmlSubstituteEntitiesDefault(0);
xmlDisableEntityLoader(1);
xmlDocPtr doc = xmlReadMemory(xml.c_str(), xml.size(), "input.xml", nullptr,
    XML_PARSE_NONET | XML_PARSE_NOERROR | XML_PARSE_NOWARNING);
xmlDisableEntityLoader(0);
if (doc == nullptr) {
    throw std::runtime_error("invalid xml");
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xmlParseDoc`, `xmlReadMemory`, `xercesc`, `tinyxml2`, `RapidXML`, `TiXmlDocument`。

**定位步骤：**
1. 搜索 XML 解析入口；
2. 跳读（L2）确认是否禁用 DTD/实体；
3. 检查解析输入是否来自用户文件、网络消息、RPC。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 对 libxml2 调用 `xmlDisableEntityLoader`、设置选项；
- 对 xerces-c 调用 `parser->setExternalEntityResolver(nullptr)` 并禁用 DTD；
- tinyxml2 默认不解析 DTD，但仍需确保未手工实现实体；
- 在解析前白名单验证或转换为安全格式。

**定位技巧：**
- 逐行读（L3）确保所有解析器实例都应用安全配置；
- 跨模块追踪（L4）辅助函数是否被多个组件使用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 所有解析器禁用 DTD/实体 | **L0（快速跳过）** | 风险低 |
| 部分解析入口未设置 | **L2（跳读）** | 需补齐 |
| 默认配置解析用户 XML | **L3（逐行读）** | 高风险 |
| 多库混合使用难以统一配置 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. 解析器默认允许 DTD/实体；
2. 输入可由攻击者控制；
3. 可构造 payload 访问敏感资源。

#### 误报
1. XML 来源可信且签名验证；
2. 解析仅在脱机工具使用；
3. 外层网关过滤或剥离 DOCTYPE（有证据）。

#### 代码异味
1. 为兼容 legacy 使用 `XML_PARSE_DTDLOAD`; 
2. 忘记恢复全局实体加载器状态；
3. 没有错误处理导致静默失败。

## Low risk

### 低风险评级场景

#### 1. 解析仅在内网环境执行
- 攻击面小，可暂降级。

#### 2. XML 文件经人工审核
- 风险较低，但建议禁用实体。

#### 3. 计划统一封装安全解析器
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内网环境 | 攻击面小 | 中 |
| 人工审核 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
