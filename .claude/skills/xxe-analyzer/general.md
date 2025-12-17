---
name: general
description: XXE通用漏洞模式快速参考 - 所有涉及XML处理的项目必审
---

# XXE 通用漏洞模式快速参考

任何涉及 XML 数据处理的应用都必须审计以下漏洞模式。

---

## 1. XML 解析器配置不安全

### 外部实体（External Entity）未禁用

**风险**：读取本地文件、SSRF、DoS

**危险代码**
```java
// Java - 未配置防护
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
Document doc = builder.parse(userInput);  // 直接解析
```

**安全做法**
```java
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
factory.setXIncludeAware(false);
factory.setExpandEntityReferences(false);
```

**快速定位**：搜索 `DocumentBuilderFactory.newInstance()`、`xml.etree.ElementTree.parse()`、`DOMDocument->load()`，检查后20行是否有上述防护

---

### DTD 处理未禁用

**风险**：在DTD中定义恶意实体、引用外部DTD、参数实体攻击

**攻击示例**
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<foo>&xxe;</foo>
```

**安全做法**
```java
// Java
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
```

**快速定位**：搜索 `DOCTYPE` 关键字，确保明确禁用了 `disallow-doctype-decl`

---

### 参数实体（Parameter Entity）未禁用

**风险**：绕过基本过滤、高级数据泄露、DoS

**快速定位**：搜索 DTD 中的 `%` 符号或参数实体配置关键字

**安全做法**：禁用参数实体处理
```java
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
```

---

## 2. 特定业务场景

### API 接口接收 XML

**快速定位**：搜索 `Content-Type: application/xml` 或 `@PostMapping`、`@RequestMapping` 配合 XML 解析调用

**审计重点**：确保所有接收 XML 的 API 端点都有完整的 XXE 防护

---

### 文件上传和导入

**快速定位**：搜索文件上传处理函数，检查是否调用了 XML 解析

**审计重点**：
- 上传文件类型检查是否足够
- 解析上传文件时是否有 XXE 防护

---

### SVG 文件处理

**快速定位**：搜索 `.svg` 文件处理、ImageMagick、GD、Pillow 等库的调用

**审计重点**：验证图片处理库的 XXE 防护；检查是否直接调用 XML 解析

---

### Office 文档处理

**快速定位**：搜索 Apache POI (Java)、PHPWord (PHP)、python-docx (Python)、Aspose (C#)

**审计重点**：
- 库版本是否足够新（新版本通常更安全）
- 手动解析 ZIP 时是否有 XXE 防护

---

## 3. XXE 用于 SSRF

### 内网服务探测 / 云元数据服务访问

**风险**：探测内网端口、获取 AWS/GCP/Azure 元数据（IAM 凭证、令牌等）

**攻击示例**
```xml
<!-- AWS 元数据服务 -->
<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/iam/security-credentials/">
```

**审计重点**：如果应用部署在云环境，XXE 防护尤为重要

---

## 4. XXE DoS 攻击

### Billion Laughs / 指数实体扩展

**风险**：嵌套实体导致内存耗尽、CPU 爆炸

**防护**：禁用外部实体和 DTD 处理（最根本）

---

### Quadratic Blowup / 二次方扩展

**风险**：大量参数实体重复引用导致二次方级别内存消耗

**防护**：禁用参数实体处理

---

### Slow XXE / 慢速资源

**风险**：引用超大文件或响应极慢的服务导致应用挂起

**防护**：设置 XML 解析超时限制、限制实体大小

---

## 5. 特殊格式变种

### YAML 解析

**风险**：YAML 解析器不安全配置、锚点和别名 DoS

**安全做法**
```python
import yaml
data = yaml.safe_load(yaml_string)  # 而非 yaml.load()
```

---

### JSON-LD / XOP/MTOM

**审计要点**：检查项目是否使用这些格式，验证相关库的安全配置

---

## 快速检查清单

```
□ 定位所有 XML 解析器（扫描脚本辅助）
□ 验证外部实体是否被禁用
  □ Java: external-general-entities = false
  □ Python: resolve_entities = False
  □ PHP: libxml_disable_entity_loader(true)
□ 验证 DTD 是否被禁用
  □ Java: disallow-doctype-decl = true
□ 验证参数实体是否被禁用
  □ Java: external-parameter-entities = false
□ 定位 API 端点接收 XML 的位置
□ 检查文件上传功能是否涉及 XML 解析
□ 检查 SVG、Office 文档等特殊格式处理
□ 验证防护配置的完整性
```

---

## 使用本文档

1. **扫描阶段**：运行 `scan.sh` 定位 XXE 相关代码
2. **快速参考**：本文档提供漏洞模式概览和代码示例
3. **深度审计**：根据编程语言查看对应的语言特定指南（`Language_*.md`）
