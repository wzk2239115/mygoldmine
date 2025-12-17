# Java｜导入/导出 XML 功能未禁用 DTD

## Details

### 漏洞成因
许多后台或桌面程序允许用户上传 XML 文件以导入配置或数据。若解析器未禁用 DTD 和外部实体，攻击者可在上传的 XML 中嵌入恶意实体，利用服务器读取敏感文件、执行 SSRF 或触发资源耗尽。

### 代码示例

**易受攻击的代码：**
```java
public void importConfig(MultipartFile file) throws Exception {
    DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
    DocumentBuilder builder = factory.newDocumentBuilder();
    Document doc = builder.parse(file.getInputStream());
    // 进一步处理 doc
}
```

**安全示例：**
```java
public void importConfig(MultipartFile file) throws Exception {
    DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
    factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
    factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
    factory.setXIncludeAware(false);
    factory.setExpandEntityReferences(false);
    DocumentBuilder builder = factory.newDocumentBuilder();
    Document doc = builder.parse(new InputSource(file.getInputStream()));
    // 进一步处理 doc
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `import`, `upload`, `MultipartFile`, `parse`, `DocumentBuilder`, `SAXParser`, `Unmarshaller`。

**定位步骤：**
1. 搜索处理文件上传或导入的代码；
2. 跳读（L2）确认解析器是否禁用了外部实体；
3. 检查是否允许用户自定义 XML 模板。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 白名单校验上传文件类型和大小；
- 使用安全配置的解析器（与前两个案例相同）；
- 在导入前执行 Schema 验证或转换为安全格式（JSON）；
- 将解析逻辑放在沙箱或隔离容器中。

**定位技巧：**
- 逐行读（L3）确认所有导入路径都设置了安全特性；
- 跨模块追踪（L4）导入功能是否存在 CLI/任务等其他入口。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 导入功能统一使用安全解析器 | **L0（快速跳过）** | 风险低 |
| 个别导入逻辑遗漏配置 | **L2（跳读）** | 快速补齐 |
| 直接使用默认解析器处理用户文件 | **L3（逐行读）** | 高风险 |
| 导入流程跨多个模块 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. 导入功能解析用户上传的 XML；
2. 未禁用 DOCTYPE/外部实体；
3. 可通过 payload 获取敏感信息或 SSRF。

#### 误报
1. 上传文件仅来自受信任管理员且在离线环境处理；
2. 导入功能仅接收固定模板且在前端验证；
3. 上传后立即转换为纯文本并验证（无 XML 解析）。

#### 代码异味
1. 仅禁用部分特性；
2. 解析器工厂复用导致部分调用仍不安全；
3. 注释提醒“待增加安全配置”未落实。

## Low risk

### 低风险评级场景

#### 1. 功能仅面向内部运维
- 攻击面有限，可暂降级。

#### 2. 上传文件经过离线审核
- 仍建议启用安全配置，但优先级可低。

#### 3. 已计划迁移至结构化格式
- 明确时间表，可暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部运维 | 攻击面小 | 中 |
| 离线审核 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
