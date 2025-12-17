# PHP｜DOMDocument 未禁用外部实体

## Details

### 漏洞成因
`DOMDocument`、`DOMXPath` 等解析器默认允许 DTD 和外部实体。当加载用户提供的 XML 时，如果未禁用 `DOMDocument::resolveExternals`、`substituteEntities` 或设置相关 libxml 标志，就可被 XXE 利用。

### 代码示例

**易受攻击的代码：**
```php
$dom = new DOMDocument();
$dom->loadXML($xml); // 默认解析外部实体
$name = $dom->getElementsByTagName('name')->item(0)->textContent;
```

**安全示例：**
```php
$dom = new DOMDocument();
$dom->resolveExternals = false;
$dom->substituteEntities = false;
$dom->loadXML($xml, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING);
$name = $dom->getElementsByTagName('name')->item(0)->textContent;
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `DOMDocument`, `load`, `loadXML`, `loadHTML`, `DOMXPath`, `simplexml_import_dom`。

**定位步骤：**
1. 搜索 DOMDocument 实例化代码；
2. 跳读（L2）确认是否禁用外部实体并设置 `LIBXML_NONET`；
3. 检查是否通过 XPath 查询访问数据。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 显式设置 `resolveExternals=false`, `substituteEntities=false`; 
- 使用 `libxml_disable_entity_loader`; 
- 采用 `libxml_set_external_entity_loader` 自定义安全加载器；
- 在入口处对 XML 做 schema 验证。

**定位技巧：**
- 逐行读（L3）确保所有 DOMDocument 实例都进行了安全设置；
- 跨模块追踪（L4）工具函数是否被多处复用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| DOMDocument 统一禁用实体 | **L0（快速跳过）** | 风险低 |
| 部分实例缺少配置 | **L2（跳读）** | 快速修补 |
| 默认 loadXML 处理外部输入 | **L3（逐行读）** | 高风险 |
| DOMDocument 在多个模块中复用 | **L4（跨模块追踪）** | 需完整排查 |

## Classify

### 研判标准

#### 确认漏洞
1. DOMDocument 默认解析用户 XML；
2. 未禁用外部实体；
3. 可构造 payload 访问敏感资源。

#### 误报
1. XML 源完全可信（签名校验）；
2. XML 仅包含常量结构，由后端生成；
3. 在解析前即删除 DOCTYPE 并验证（需强证明）。

#### 代码异味
1. 混合使用 `libxml_disable_entity_loader` 与 DOM 属性，逻辑不清晰；
2. 同一函数既处理可信又处理不可信输入；
3. 没有错误处理，忽略解析异常。

## Low risk

### 低风险评级场景

#### 1. 功能仅供内部用户使用
- 攻击面小，可暂列低风险。

#### 2. 解析的 XML 经过离线签名验证
- 风险较低，但建议仍禁用实体。

#### 3. 已计划统一封装安全 DOM 工具
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部使用 | 攻击面小 | 中 |
| 离线签名 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
