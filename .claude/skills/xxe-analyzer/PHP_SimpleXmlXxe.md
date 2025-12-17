# PHP｜SimpleXML 未禁用外部实体

## Details

### 漏洞成因
在 PHP 中使用 `simplexml_load_string`、`simplexml_load_file` 处理用户可控的 XML 时，如果未禁用外部实体加载，攻击者可通过 `<!DOCTYPE>` 声明触发 XXE，读取服务器文件或发起 SSRF。默认情况下，libxml 会解析外部实体。

### 代码示例

**易受攻击的代码：**
```php
function parseProfile($xml) {
    $data = simplexml_load_string($xml);
    return (string) $data->name;
}
```

**安全示例：**
```php
function parseProfile($xml) {
    $previous = libxml_disable_entity_loader(true);
    $dom = new DOMDocument();
    $dom->loadXML($xml, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING);
    libxml_disable_entity_loader($previous);
    $data = simplexml_import_dom($dom);
    return (string) $data->name;
}
// 或直接改用 simplexml_load_string($xml, 'SimpleXMLElement', LIBXML_NONET)
// 并确保在解析前永久禁用实体加载
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `simplexml_load_string`, `simplexml_load_file`, `SimpleXMLElement`, `libxml_disable_entity_loader`。

**定位步骤：**
1. 搜索 SimpleXML 使用位置；
2. 跳读（L2）确认是否调用 `libxml_disable_entity_loader(true)`；
3. 检查是否设置 `LIBXML_NONET`, `LIBXML_NOENT`, `LIBXML_DTDLOAD` 等标志。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 全局禁用实体加载；
- 使用 `DOMDocument` + 安全配置替换；
- 在上传前对 XML 做白名单过滤；
- 采用 JSON/CSV 等替代格式。

**定位技巧：**
- 逐行读（L3）确保所有入口都恢复 libxml 的原状态；
- 跨模块追踪（L4）公共解析工具是否被多个功能复用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| SimpleXML 全部禁用实体 | **L0（快速跳过）** | 风险低 |
| 个别解析缺少禁用逻辑 | **L2（跳读）** | 快速修补 |
| 广泛使用默认 SimpleXML | **L3（逐行读）** | 高风险 |
| 解析工具被多模块共享 | **L4（跨模块追踪）** | 需完整排查 |

## Classify

### 研判标准

#### 确认漏洞
1. SimpleXML 默认解析用户 XML；
2. 未禁用外部实体或网络访问；
3. 可构造 XXE payload 读取敏感资源。

#### 误报
1. 数据来自可信内部系统；
2. 解析前执行了严格白名单过滤；
3. 功能仅用于内部工具，外部不可访问。

#### 代码异味
1. 忘记恢复 `libxml_disable_entity_loader`; 
2. 使用 `LIBXML_NOENT` 等标志导致实体展开；
3. 注释中提醒“TODO: 添加安全配置”未实现。

## Low risk

### 低风险评级场景

#### 1. 功能仅面向内部管理员
- 攻击面小，可暂降级。

#### 2. 上传文件经过人工审核
- 风险较低，但建议仍禁用实体。

#### 3. 已计划迁移到安全解析方案
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部管理员 | 攻击面小 | 中 |
| 人工审核 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
