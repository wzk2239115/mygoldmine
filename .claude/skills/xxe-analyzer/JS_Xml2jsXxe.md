# JavaScript｜xml2js 默认配置导致 XXE

## Details

### 漏洞成因
Node.js 的 `xml2js` 库在默认配置下会解析外部实体和 DOCTYPE。若直接调用 `parseString`/`parseStringPromise` 处理用户提供的 XML，而未禁用 `doctype`、`explicitCharkey` 等危险特性，会暴露 XXE 风险。

### 代码示例

**易受攻击的代码：**
```javascript
const xml2js = require('xml2js');

async function parse(body) {
  const result = await xml2js.parseStringPromise(body); // 默认配置
  return result.order;
}
```

**安全示例：**
```javascript
const parser = new xml2js.Parser({
  explicitCharkey: false,
  explicitRoot: false,
  preserveChildrenOrder: false,
  // 关键配置：禁止 DOCTYPE 与实体
  xmldec: { standalone: true },
  normalizeTags: true,
  validator: function() { return true; }
});

async function parse(body) {
  if (/<!DOCTYPE/i.test(body)) throw new Error('DOCTYPE is not allowed');
  parser.saxParser.entity = {}; // 清空实体映射
  return parser.parseStringPromise(body);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xml2js`, `parseString`, `parseStringPromise`, `new xml2js.Parser`。

**定位步骤：**
1. 搜索 `xml2js` 的使用；
2. 跳读（L2）确认是否传入安全配置或手动校验 DOCTYPE；
3. 检查是否清空 `parser.saxParser.entity`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `fast-xml-parser` 等可配置禁用实体的库；
- 在解析前过滤或拒绝包含 `<!DOCTYPE>` 的请求；
- 通过 schema 校验限制 XML 结构；
- 将解析逻辑置于隔离环境。

**定位技巧：**
- 逐行读（L3）确认 parser 实例复用时是否每次清空实体；
- 跨模块追踪（L4）公共解析模块是否被多个服务使用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 解析前禁用 DOCTYPE/实体 | **L0（快速跳过）** | 风险低 |
| 部分解析器缺少配置 | **L2（跳读）** | 快速补齐 |
| 默认 xml2js 解析用户 XML | **L3（逐行读）** | 高风险 |
| 解析模块多服务共享 | **L4（跨模块追踪）** | 需完整分析 |

## Classify

### 研判标准

#### 确认漏洞
1. xml2js 默认配置解析用户 XML；
2. 未禁用 DOCTYPE/实体；
3. 可通过 payload 访问敏感资源。

#### 误报
1. XML 仅来自内部服务；
2. 在到达解析器前已移除 DOCTYPE；
3. 只用于测试工具不可被外部访问。

#### 代码异味
1. 依赖自定义正则替换 `<ENTITY>`；
2. parser 实例全局复用未清空实体；
3. 缺乏错误处理，异常时仍返回部分结果。

## Low risk

### 低风险评级场景

#### 1. 内部管道解析
- 攻击面小，可暂降级。

#### 2. 请求来源已签名验证
- 风险较低，但仍建议禁用实体。

#### 3. 计划迁移到安全解析器
- 明确时间表，暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部来源 | 攻击面小 | 中 |
| 强认证 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
