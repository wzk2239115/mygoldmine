# Rust｜quick-xml 未禁用 DTD 处理

## Details

### 漏洞成因
`quick-xml` 是常用的高性能 XML 解析库。默认情况下允许读取 `<!DOCTYPE>` 并处理实体。若解析用户输入的 XML 而未禁用 DTD 或限制实体，攻击者可利用 XXE 读取服务器文件或请求内网资源。

### 代码示例

**易受攻击的代码：**
```rust
use quick_xml::Reader;
use quick_xml::events::Event;

fn parse(xml: &str) {
    let mut reader = Reader::from_str(xml);
    reader.trim_text(true);
    let mut buf = Vec::new();
    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Eof) => break,
            Ok(_) => buf.clear(),
            Err(e) => panic!("Error: {}", e),
        }
    }
}
```

**安全示例：**
```rust
use quick_xml::Reader;
use quick_xml::events::Event;

fn parse(xml: &str) -> Result<(), quick_xml::Error> {
    if xml.contains("<!DOCTYPE") {
        return Err(quick_xml::Error::UnexpectedToken("DOCTYPE not allowed".into()));
    }
    let mut reader = Reader::from_str(xml);
    reader.expand_empty_elements(true);
    reader.trim_text(true);
    reader.check_end_names(true);
    let mut buf = Vec::new();
    while matches!(reader.read_event_into(&mut buf)?, Event::Eof) == false {
        buf.clear();
    }
    Ok(())
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `quick_xml::Reader`, `from_reader`, `from_str`, `read_event`, `to_owned()`。

**定位步骤：**
1. 搜索 quick-xml Reader/Writer 的创建；
2. 跳读（L2）确认是否检查 DOCTYPE 或自定义实体；
3. 检查是否对输入做白名单过滤。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 解析前过滤/拒绝 `<!DOCTYPE>`；
- 使用 `entities` 配置为空 map（0.30+ 支持）；
- 在业务层使用 schema 验证或转换为安全格式；
- 解析逻辑运行在隔离容器。

**定位技巧：**
- 逐行读（L3）确保所有 parse 调用都进行 DOCTYPE 检查；
- 跨模块追踪（L4）公共解析函数是否在多服务中复用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 统一检查 DOCTYPE 并禁用实体 | **L0（快速跳过）** | 风险低 |
| 少量入口缺少检查 | **L2（跳读）** | 需补齐 |
| 默认 quick-xml 处理用户数据 | **L3（逐行读）** | 高风险 |
| 解析函数被多组件共享 | **L4（跨模块追踪）** | 需彻底梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. quick-xml 默认解析外部 XML；
2. 未禁用 DOCTYPE/实体；
3. 可利用 payload 访问敏感资源。

#### 误报
1. 数据源完全可信、不可被篡改；
2. 解析前强制 schema 验证并拒绝 DOCTYPE；
3. 仅用于内部工具，不接收外部输入。

#### 代码异味
1. 依赖字符串替换 `<DOCTYPE>`；
2. Reader 在多个线程共享，缺乏隔离；
3. 缺少错误处理和日志记录。

## Low risk

### 低风险评级场景

#### 1. 内部系统解析可信 XML
- 攻击面小，可暂降级。

#### 2. 有额外网关过滤
- 虽降低风险，但仍建议本地检查。

#### 3. 已计划升级到支持禁用实体的版本
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部数据源 | 攻击面小 | 中 |
| 网关过滤 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
