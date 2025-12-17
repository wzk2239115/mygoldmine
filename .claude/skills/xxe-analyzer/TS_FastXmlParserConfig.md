# TypeScript｜fast-xml-parser 配置不当导致 XXE

## Details

### 漏洞成因
`fast-xml-parser`、`@fast-csv/xml` 等 Node.js/TypeScript XML 解析库可通过配置控制 DTD/实体处理。若使用默认配置解析用户输入，未禁用 `processEntities` 或 `ignoreAttributes`, `allowBooleanAttributes` 等选项，攻击者可注入实体并触发 XXE/SSRF。

### 代码示例

**易受攻击的代码：**
```ts
import { XMLParser } from 'fast-xml-parser';

const parser = new XMLParser(); // 默认配置
export function parseXml(body: string) {
  return parser.parse(body);
}
```

**安全示例：**
```ts
import { XMLParser } from 'fast-xml-parser';

const parser = new XMLParser({
  ignoreAttributes: false,
  allowBooleanAttributes: true,
  processEntities: false,
  stopNodes: ['*'],
});

export function parseXml(body: string) {
  if (/<!DOCTYPE/i.test(body)) {
    throw new Error('DOCTYPE not allowed');
  }
  return parser.parse(body);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `new XMLParser`, `fast-xml-parser`, `processEntities`, `DTD`, `parse(xml)`。

**定位步骤：**
1. 搜索创建 parser 的代码；
2. 跳读（L2）确认配置是否禁用实体；
3. 检查调用方是否对输入进行校验。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `processEntities: false`, `ignoreAttributes` 合理配置；
- 解析前过滤 `<!DOCTYPE>`；
- 在 API 层定义 schema/白名单；
- 将解析逻辑放置在隔离服务中。

**定位技巧：**
- 逐行读（L3）确保 parser 实例在所有入口都使用安全配置；
- 跨模块追踪（L4）公共解析器是否被不同服务复用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| parser 统一禁用实体并校验 DOCTYPE | **L0（快速跳过）** | 风险低 |
| 部分 parser 漏配 `processEntities` | **L2（跳读）** | 快速修补 |
| 默认配置解析外部 XML | **L3（逐行读）** | 高风险 |
| parser 工具在多服务间共享 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. fast-xml-parser 默认配置解析用户 XML；
2. 未禁用实体或过滤 DOCTYPE；
3. 可构造 payload 访问敏感资源。

#### 误报
1. 输入来自可信后端并经过签名；
2. 解析前已有 schema 验证限制实体；
3. 功能仅在内网使用。

#### 代码异味
1. parser 配置散落在多个文件；
2. 仅通过正则去除 `<!DOCTYPE>`；
3. 复用 parser 实例处理多种来源的 XML。

## Low risk

### 低风险评级场景

#### 1. 内网系统解析
- 攻击面小，可暂降级。

#### 2. XML 输入经过网关过滤
- 风险较低，但建议仍禁用实体。

#### 3. 已计划统一封装解析器
- 明确时间表，暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内网系统 | 攻击面小 | 中 |
| 网关过滤 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
