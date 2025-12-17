# C｜libxml2 未禁用外部实体

## Details

### 漏洞成因
libxml2 是 C/C++ 常用的 XML 库。若在调用 `xmlReadMemory`, `xmlReadFile`, `xmlParseDoc` 等解析用户输入时未禁用实体加载（`XML_PARSE_NOENT`、`XML_PARSE_DTDLOAD` 等），攻击者可加载外部资源，导致敏感信息泄露或 SSRF。

### 代码示例

**易受攻击的代码：**
```c
xmlDocPtr doc = xmlReadMemory(xml, strlen(xml), "input.xml", NULL, 0); // 默认解析实体
if (doc == NULL) {
    return -1;
}
// 处理 doc
```

**安全示例：**
```c
xmlDisableEntityLoader(1);
xmlSubstituteEntitiesDefault(0);
xmlDocPtr doc = xmlReadMemory(xml, strlen(xml), "input.xml", NULL,
    XML_PARSE_NONET | XML_PARSE_NOERROR | XML_PARSE_NOWARNING);
xmlDisableEntityLoader(0);
if (doc == NULL) {
    return -1;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xmlRead`, `xmlParse`, `xmlDocPtr`, `libxml2`, `xmlParseMemory`。

**定位步骤：**
1. 搜索 libxml2 解析入口；
2. 跳读（L2）确认传入的 flags 是否包含 `XML_PARSE_NONET`、`XML_PARSE_NOENT`；
3. 检查解析输入是否来自用户。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 设置 `XML_PARSE_NONET` 禁止网络访问；
- 使用 `xmlDisableEntityLoader(true)`；
- 统一封装解析函数；
- 通过 schema 白名单验证 XML。

**定位技巧：**
- 逐行读（L3）确认所有调用都使用安全选项；
- 跨模块追踪（L4）库是否在第三方组件中被再次使用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 默认设置禁用网络/实体 | **L0（快速跳过）** | 风险低 |
| 部分调用缺少安全标志 | **L2（跳读）** | 快速修补 |
| 广泛使用默认 xmlRead* | **L3（逐行读）** | 高风险 |
| 库被多个组件复用 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. libxml2 默认解析用户输入；
2. 未禁用外部实体/DTD；
3. 可构造 payload 访问敏感文件或 SSRF。

#### 误报
1. 输入为内部常量或经过签名；
2. 解析仅在离线工具运行；
3. 已启用沙箱隔离（证明充分）。

#### 代码异味
1. 对 flags 取值混乱，注释不明；
2. 将 `XML_PARSE_NOENT` 与 `XML_PARSE_DTDLOAD` 组合；
3. 忽略解析错误继续执行。

## Low risk

### 低风险评级场景

#### 1. 仅在隔离环境运行
- 攻击面小，可暂降级。

#### 2. 数据来源可信且有校验
- 风险较低，但仍建议禁用实体。

#### 3. 已计划升级解析封装
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 隔离环境 | 攻击面小 | 中 |
| 可信来源 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
