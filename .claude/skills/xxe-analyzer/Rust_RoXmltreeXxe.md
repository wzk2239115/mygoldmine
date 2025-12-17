# Rust｜roxmltree 解析不可信 XML 导致 XXE

## Details

### 漏洞成因
`roxmltree` 是只读的 XML 树解析库，但默认会保留 DOCTYPE 声明。若在解析前未检测并拒绝 DOCTYPE，攻击者可构造实体实现 XXE（虽然 roxmltree 不解析实体，但 DOCTYPE 可被下游逻辑滥用或触发 DoS）。

### 代码示例

**易受攻击的代码：**
```rust
use roxmltree::Document;

fn parse(xml: &str) -> roxmltree::Document {
    Document::parse(xml).expect("invalid xml")
}
```

**安全示例：**
```rust
use roxmltree::Document;

fn parse(xml: &str) -> Result<Document, &'static str> {
    if xml.contains("<!DOCTYPE") {
        return Err("DOCTYPE not allowed");
    }
    Document::parse(xml).map_err(|_| "invalid xml")
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `roxmltree::Document::parse`, `::parse_with_options`, `doctype`, `DTD`。

**定位步骤：**
1. 搜索 roxmltree 的 parse 调用；
2. 跳读（L2）确认是否检查 DOCTYPE；
3. 检查 XML 来源是否可控。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 在解析前检测并拒绝 DOCTYPE；
- 使用 `Document::parse_with_options` 并禁用 `Pi`/`DocType`; 
- 对 XML 内容执行 schema 验证；
- 将不可信 XML 转换为更安全格式。

**定位技巧：**
- 逐行读（L3）确保所有 parse 调用前进行检查；
- 跨模块追踪（L4）工具函数是否被不同服务复用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 解析前统一过滤 DOCTYPE | **L0（快速跳过）** | 风险低 |
| 部分入口缺少过滤 | **L2（跳读）** | 需补齐 |
| 直接对外部输入调用 parse | **L3（逐行读）** | 高风险 |
| 函数被多个模块调用 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. roxmltree 解析用户可控 XML；
2. 未拒绝 DOCTYPE；
3. 可构造 payload 触发 DoS 或下游 XXE。

#### 误报
1. XML 来源固定且受控；
2. 解析前进行严格白名单过滤；
3. 应用使用 roxmltree 仅处理内部模板。

#### 代码异味
1. parse 调用分散，缺乏统一检查；
2. 依赖字符串替换移除部分关键字；
3. 未对解析错误做日志记录。

## Low risk

### 低风险评级场景

#### 1. 内部系统处理可信 XML
- 攻击面小，可暂降级。

#### 2. 使用 Schema 验证限制结构
- 风险降低，但仍建议拒绝 DOCTYPE。

#### 3. 已计划迁移到承载安全选项的库
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部来源 | 攻击面小 | 中 |
| Schema 验证 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
