---
name: xpath-injection-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证 XPath 注入漏洞；重点关注检测不安全的 XPath 查询构造，即用户可控输入未经适当验证或过滤直接用于构造 XPath 表达式；利用按编程语言组织的参考资料目录中的参考指南。
---

## 通用 XPath 注入漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：XPath 表达式直接拼接（用户输入直接拼接到 XPath 字符串）、谓词注入（WHERE 条件中用户输入未转义）、轴操作符注入（//、/、@ 等轴操作符可控）、函数调用注入（contains()、starts-with()、substring() 等函数参数可控）、逻辑操作符注入（and、or、not 等逻辑操作符可控）、数值比较注入（=、!=、<、> 等比较操作符可控）、字符串拼接注入（concat() 函数中用户输入未转义）、命名空间注入（命名空间前缀可控）、变量绑定注入（XPath 变量绑定中用户输入未验证）、XPath 2.0 函数注入（tokenize()、matches() 等函数参数可控）、XML 数据源注入（XML 文档内容可控）、XSLT 模板注入（XPath 表达式在 XSLT 模板中未转义）

**遇到防护机制时的绕过技巧引用：**
- 引号过滤（单引号、双引号） → 详见 [bypassTricks.md - 引号和分隔符绕过](bypassTricks.md#1-引号和分隔符绕过)
- or/and 逻辑操作符检查 → 详见 [bypassTricks.md - 括号和逻辑运算符绕过](bypassTricks.md#12-括号和逻辑运算符绕过)
- 特殊字符黑名单过滤 → 详见 [bypassTricks.md - XML 实体和字符参考绕过](bypassTricks.md#8-xml-实体和字符参考绕过)
- 函数黑名单（concat、substring 等） → 详见 [bypassTricks.md - 字符串函数绕过](bypassTricks.md#31-字符串函数绕过)
- XPath 轴限制（parent::、ancestor:: 等） → 详见 [bypassTricks.md - 轴和谓词绕过](bypassTricks.md#41-轴和谓词绕过)
- 通配符限制（//、* 禁用） → 详见 [bypassTricks.md - 通配符和递归下降绕过](bypassTricks.md#42-通配符和递归下降绕过)
- 查询长度或复杂度限制 → 详见 [bypassTricks.md - 递归和深度限制绕过](bypassTricks.md#91-递归和深度限制绕过)
- 无回显/盲注场景 → 详见 [bypassTricks.md - 布尔盲注](bypassTricks.md#111-布尔盲注) 和 [时间盲注](bypassTricks.md#112-时间盲注)
- XPath 库特定防护 → 详见 [bypassTricks.md - 特定 XPath 库绕过](bypassTricks.md#10-特定-xpath-库绕过)
- 多步骤/链式过滤 → 详见 [bypassTricks.md - 多步骤注入和链式攻击](bypassTricks.md#12-多步骤注入和链式攻击)

---

**XPath 注入漏洞**

**Attention**  
当项目中使用了 XPath 查询 XML 数据并将用户可控输入未经安全处理直接用于构造 XPath 表达式时，极易引发 XPath 注入漏洞。此类问题通常出现在用户认证（XML 用户数据库）、数据搜索和过滤、XML 配置解析、XSLT 转换、XML 数据验证等涉及 XPath 查询的业务模块中，需重点审计动态构造 XPath 表达式的代码路径。

**Early exit**  
若项目完全未使用 XML 数据查询（如仅使用关系型数据库且无 XML 处理）、或所有 XPath 查询均通过完全参数化方式（使用变量绑定且确保无字符串拼接）、或前端为纯静态页面无后端逻辑，则可快速退出对该漏洞类型的审计。

**Cases**

**Java**
使用 javax.xml.xpath.XPath 时，用户输入直接拼接到 XPath 表达式字符串中，详见：[Java_XPath_String_Concat.md](Java_XPath_String_Concat.md)
使用 dom4j 框架时，XPath 查询中用户输入未转义直接使用，详见：[Java_Dom4j_XPath_Injection.md](Java_Dom4j_XPath_Injection.md)
使用 JDOM 框架时，XPath 表达式构造时用户输入未验证，详见：[Java_JDOM_XPath_Injection.md](Java_JDOM_XPath_Injection.md)
使用 Xalan XPath 引擎时，变量绑定中用户输入未过滤，详见：[Java_Xalan_XPath_Variable_Injection.md](Java_Xalan_XPath_Variable_Injection.md)
Spring 框架中使用 XPath 进行 XML 配置解析时，用户输入直接用于构造表达式，详见：[Java_Spring_XPath_Config_Injection.md](Java_Spring_XPath_Config_Injection.md)

**Python**
使用 lxml.etree.XPath 时，用户输入直接拼接到 XPath 表达式字符串中，详见：[Python_Lxml_XPath_Concat.md](Python_Lxml_XPath_Concat.md)
使用 xml.etree.ElementTree 时，XPath 查询中用户输入未转义，详见：[Python_ElementTree_XPath_Injection.md](Python_ElementTree_XPath_Injection.md)
使用 xpath 库时，表达式构造时用户输入未验证，详见：[Python_XPath_Lib_Injection.md](Python_XPath_Lib_Injection.md)
Django 框架中使用 XPath 进行 XML 数据处理时，用户输入直接用于构造表达式，详见：[Python_Django_XPath_Injection.md](Python_Django_XPath_Injection.md)

**JavaScript (Node.js)**
使用 xpath 库时，用户输入直接拼接到 XPath 表达式字符串中，详见：[NodeJS_XPath_String_Concat.md](NodeJS_XPath_String_Concat.md)
使用 xmldom 和 xpath 组合时，XPath 查询中用户输入未转义，详见：[NodeJS_XmlDom_XPath_Injection.md](NodeJS_XmlDom_XPath_Injection.md)
使用 libxmljs 时，表达式构造时用户输入未验证，详见：[NodeJS_LibXmlJs_XPath_Injection.md](NodeJS_LibXmlJs_XPath_Injection.md)
Express 框架中使用 XPath 进行 XML 数据查询时，用户输入直接用于构造表达式，详见：[NodeJS_Express_XPath_Injection.md](NodeJS_Express_XPath_Injection.md)

**TypeScript**
使用 xpath 库时，类型不安全的 XPath 表达式构造，详见：[TypeScript_XPath_Type_Unsafe.md](TypeScript_XPath_Type_Unsafe.md)
使用 @xmldom/xmldom 和 xpath 组合时，XPath 查询中用户输入未转义，详见：[TypeScript_XmlDom_XPath_Injection.md](TypeScript_XmlDom_XPath_Injection.md)
NestJS 框架中使用 XPath 进行 XML 配置解析时，用户输入直接用于构造表达式，详见：[TypeScript_NestJS_XPath_Injection.md](TypeScript_NestJS_XPath_Injection.md)

**PHP**
使用 DOMXPath 时，用户输入直接拼接到 XPath 表达式字符串中，详见：[PHP_DOMXPath_String_Concat.md](PHP_DOMXPath_String_Concat.md)
使用 SimpleXMLElement 时，XPath 查询中用户输入未转义，详见：[PHP_SimpleXML_XPath_Injection.md](PHP_SimpleXML_XPath_Injection.md)
Laravel 框架中使用 XPath 进行 XML 数据处理时，用户输入直接用于构造表达式，详见：[PHP_Laravel_XPath_Injection.md](PHP_Laravel_XPath_Injection.md)
Symfony 框架中使用 XPath 进行 XML 配置解析时，用户输入未验证，详见：[PHP_Symfony_XPath_Injection.md](PHP_Symfony_XPath_Injection.md)

**Go**
使用 encoding/xml 和 xpath 包时，用户输入直接拼接到 XPath 表达式字符串中，详见：[Go_Xml_XPath_Concat.md](Go_Xml_XPath_Concat.md)
使用 antchfx/xpath 库时，XPath 查询中用户输入未转义，详见：[Go_Antchfx_XPath_Injection.md](Go_Antchfx_XPath_Injection.md)
Gin 框架中使用 XPath 进行 XML 数据查询时，用户输入直接用于构造表达式，详见：[Go_Gin_XPath_Injection.md](Go_Gin_XPath_Injection.md)

**C/C++**
使用 libxml2 库时，用户输入直接拼接到 XPath 表达式字符串中，详见：[C_LibXml2_XPath_Concat.md](C_LibXml2_XPath_Concat.md)
使用 Xalan C++ 时，XPath 查询中用户输入未转义，详见：[C_Xalan_XPath_Injection.md](C_Xalan_XPath_Injection.md)
自定义 XPath 解析器中的注入风险，详见：[C_Custom_XPath_Parser_Injection.md](C_Custom_XPath_Parser_Injection.md)

**Rust**
使用 quick-xml 和 sxd-xpath 组合时，用户输入直接拼接到 XPath 表达式字符串中，详见：[Rust_QuickXml_XPath_Concat.md](Rust_QuickXml_XPath_Concat.md)
使用 xml-rs 和 xpath 库时，XPath 查询中用户输入未转义，详见：[Rust_XmlRs_XPath_Injection.md](Rust_XmlRs_XPath_Injection.md)
自定义 XPath 查询构建器的不安全实现，详见：[Rust_Custom_XPath_Query_Builder.md](Rust_Custom_XPath_Query_Builder.md)

## 审计等级定义

XPath 注入漏洞审计采用分层的审计等级制度，根据 XPath 表达式的构造方式来指导审计深度。

| 等级 | 名称 | 时间 | XPath 构造特征 |
|------|------|------|---------|
| **L0** | 快速跳过 | 1-2 分钟 | 安全构造：使用参数化/变量绑定，无字符串拼接，输入白名单验证 |
| **L1** | 快速扫描 | 3-5 分钟 | 部分参数化但需确认：有变量绑定，需验证是否存在字符串拼接 |
| **L2** | 跳读 | 5-10 分钟 | 混合构造：部分参数化，部分拼接；或输入过滤但规则需验证 |
| **L3** | 逐行读 | 15-30 分钟 | 直接拼接无防护：用户输入直接拼接到 XPath 表达式，特殊字符未转义 |
| **L4** | 跨模块追踪 | 30-60 分钟 | 复杂链路：多处 XPath 查询不一致、动态表达式构造、XML 源可控 |

### 快速判断流程

**第 1 步：XPath 表达式如何构造？**
- 直接拼接用户输入 → **L3+**
- 使用变量绑定/参数化 → 继续第 2 步

**第 2 步：输入是否有过滤或验证？**
- 无任何过滤 → **L2-L3**
- 有白名单验证 → 继续第 3 步

**第 3 步：是否覆盖所有 XPath 查询？**
- 仅部分查询有保护或 XML 源可控 → **L2-L4**
- 所有查询都有一致的保护 → **L0-L1**

### 各等级操作指南

**L0**：安全构造
```javascript
// ✅ 参数化查询（变量绑定）
xpath.select("//user[username=$username]",
  {username: userInput});  // 输入通过变量传递

// ✅ 白名单验证
const allowed = ['admin', 'user', 'guest'];
if (allowed.includes(role)) {
  xpath = `//role[name='${role}']`;  // 安全拼接
}
```

**L1**：部分参数化，快速确认
- 是否对所有用户输入都使用了变量绑定？
- 是否存在未使用参数化的 XPath 查询？
- 是否有混合使用参数化和字符串拼接？

**L2**：混合构造，需核实
- 哪些部分使用了参数化，哪些没有？
- 输入过滤规则是什么（黑名单还是白名单）？
- 是否覆盖了所有特殊字符（`'`、`"` 等）？
- XML 数据源是否可控？

**L3**：直接拼接无防护，深度分析
```javascript
// ❌ 直接拼接，XPath 注入
const username = req.body.username;  // 用户输入
xpath = `//user[username='${username}']`;  // 直接拼接
// 攻击：username = "' or '1'='1"

// ❌ 特殊字符未转义
xpath = "//user[@id='" + userId + "']";  // 未转义

// ❌ 谓词注入
xpath = `//item[contains(description, '${keyword}')]`;  // 无过滤

// ❌ 轴操作符可控
const axis = req.body.axis;  // / 或 //
xpath = axis + "/user";  // 轴可控
```
追踪完整的 XPath 查询构造流程，确认注入点和利用方式

**L4**：复杂链路，完整追踪
- XPath 查询的多处实现：是否都使用了相同的保护方式？
- XML 源的来源：是否可被用户控制？
- 动态表达式构造：是否使用了 concat()、substring() 等函数拼接？
- 变量绑定的正确性：是否确实进行了安全的参数化？

### 审计等级应用

```markdown
| 场景 | 等级 | 说明 |
|------|------|------|
| 参数化查询 + 白名单 | L0 | 无风险 |
| 参数化但需验证 | L1 | 验证覆盖范围 |
| 部分拼接或过滤 | L2 | 验证完整性 |
| 直接拼接无防护 | L3 | 高风险深度分析 |
| 特殊字符未转义 | L3 | 高风险深度分析 |
| 多处实现不一致 | L4 | 完整链路追踪 |
```

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-xpath-injection-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

