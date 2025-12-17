# Python｜lxml 解析器配置不当导致 XXE

## Details

### 漏洞成因
`lxml` 是功能丰富的 XML 解析库，默认允许外部实体和 DTD。若调用 `lxml.etree.fromstring`、`etree.parse`、`XMLParser` 等处理用户输入的 XML 而未禁用实体，会导致 XXE 攻击。

### 代码示例

**易受攻击的代码：**
```python
from lxml import etree

def load_xml(data: bytes):
    root = etree.fromstring(data)  # 默认允许实体
    return root.xpath('//item/text()')
```

**安全示例：**
```python
from lxml import etree

def load_xml(data: bytes):
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(data, parser=parser)
    return root.xpath('//item/text()')
# 或者使用 defusedxml.lxml
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `lxml`, `etree.fromstring`, `etree.parse`, `XMLParser`, `objectify`。

**定位步骤：**
1. 搜索 `lxml.etree` 的使用；
2. 跳读（L2）确认是否自定义 `XMLParser` 并禁用实体；
3. 检查是否使用 `resolve_entities=True` 等危险配置。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `XMLParser(resolve_entities=False, no_network=True)`；
- 使用 `defusedxml.lxml` 替代；
- 在解析前移除 `<!DOCTYPE>` 声明或进行白名单验证；
- 沙箱执行（多进程隔离）。

**定位技巧：**
- 逐行读（L3）确保 parser 配置应用到所有入口；
- 跨模块追踪（L4）公共函数是否接受外部数据。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用安全 parser 或 defusedxml | **L0（快速跳过）** | 风险低 |
| 部分调用缺少 parser | **L2（跳读）** | 需统一配置 |
| 全部使用默认 fromstring/parse | **L3（逐行读）** | 高风险 |
| lxml 在多个服务共享 | **L4（跨模块追踪）** | 必须全面梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. lxml 解析用户可控 XML；
2. `resolve_entities` 未禁用；
3. 可构造 payload 读取/请求敏感资源。

#### 误报
1. 数据源受信任且无法被外部操控；
2. 解析器经过严格的 schema/白名单过滤；
3. 模块已迁移到 defusedxml。

#### 代码异味
1. parser 配置分散，易遗漏；
2. 依赖字符串替换移除 DOCTYPE；
3. 允许网络访问 (no_network=False)。

## Low risk

### 低风险评级场景

#### 1. 数据仅来自可信内部系统
- 可暂降级，但建议仍启用安全 parser。

#### 2. 插件/脚本仅在受控环境运行
- 风险较小，但需文档化。

#### 3. 已计划统一封装 XML 工具
- 明确时间表，可暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部来源 | 攻击面小 | 中 |
| 受控环境 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
