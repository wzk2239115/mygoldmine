# Python｜ElementTree 默认配置导致 XXE

## Details

### 漏洞成因
`xml.etree.ElementTree` 和 `xml.dom.minidom` 默认允许解析外部实体。若直接调用 `ElementTree.parse` 或 `fromstring` 处理用户提供的 XML，攻击者可通过 `<!DOCTYPE>` 声明访问本地文件或发起 SSRF。

### 代码示例

**易受攻击的代码：**
```python
import xml.etree.ElementTree as ET

def handle_request(body: bytes):
    root = ET.fromstring(body)  # 默认允许外部实体
    return root.findtext('name')
```

**安全示例：**
```python
from defusedxml import ElementTree as DefusedET

def handle_request(body: bytes):
    root = DefusedET.fromstring(body)
    return root.findtext('name')
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xml.etree.ElementTree`, `ET.parse`, `ET.fromstring`, `minidom.parse`, `Document()`。

**定位步骤：**
1. 搜索 ElementTree/minidom 的使用；
2. 跳读（L2）确认输入是否来自请求、文件上传；
3. 检查是否改用 defusedxml 或手动禁用实体。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `defusedxml` 系列库；
- 在 Python 3.11+ 中使用 `xml.etree.ElementTree.XMLParser(target=None, dtd_validation=False)` 并显式禁用；
- 对上传文件执行白名单过滤或转换为 JSON。

**定位技巧：**
- 逐行读（L3）确认所有解析点都替换为安全库；
- 跨模块追踪（L4）通用工具函数是否被导入系统范围内使用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全面使用 defusedxml | **L0（快速跳过）** | 风险极低 |
| 部分使用安全库，部分仍用默认 | **L2（跳读）** | 需统一替换 |
| 广泛使用默认 ElementTree 解析外部数据 | **L3（逐行读）** | 高风险 |
| 工具函数被多服务复用 | **L4（跨模块追踪）** | 需彻底梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. 使用默认 ElementTree 解析用户可控 XML；
2. 未禁用外部实体；
3. 可通过 payload 读取本地文件/SSRF。

#### 误报
1. XML 来自常量或可信后端；
2. 在解析前进行了严格白名单过滤；
3. 环境运行 defusedxml（已替换 import）。

#### 代码异味
1. 在库封装中混用安全与不安全解析器；
2. 依赖 try/except 捕获异常而非禁用实体；
3. 缺乏单元测试覆盖恶意 XML。

## Low risk

### 低风险评级场景

#### 1. 功能仅接受内部系统 XML
- 攻击面小，可暂降级。

#### 2. XML 文件经过人工审核
- 仍建议使用安全库，但风险较低。

#### 3. 正在迁移到 defusedxml
- 明确时间表，可暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部来源 | 攻击面小 | 中 |
| 人工审核 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
