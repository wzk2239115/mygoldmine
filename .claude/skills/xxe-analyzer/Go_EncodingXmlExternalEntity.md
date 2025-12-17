# Go｜encoding/xml Decoder 未禁用外部实体

## Details

### 漏洞成因
Go 标准库 `encoding/xml` 的 `Decoder` 默认允许外部实体。当使用 `xml.NewDecoder` 解析用户输入的 XML（尤其是通过 `Decode`、`Token` 迭代的方式）而未禁用实体时，攻击者可以触发 XXE。

### 代码示例

**易受攻击的代码：**
```go
func parseConfig(r io.Reader) (*Config, error) {
    decoder := xml.NewDecoder(r)
    var cfg Config
    if err := decoder.Decode(&cfg); err != nil {
        return nil, err
    }
    return &cfg, nil
}
```

**安全示例：**
```go
func parseConfig(r io.Reader) (*Config, error) {
    decoder := xml.NewDecoder(r)
    decoder.Strict = true
    decoder.Entity = map[string]string{} // 清空实体映射
    var cfg Config
    if err := decoder.Decode(&cfg); err != nil {
        return nil, err
    }
    return &cfg, nil
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xml.NewDecoder`, `decoder.Decode`, `decoder.Token`, `Unmarshal`, `encoding/xml`。

**定位步骤：**
1. 搜索 `xml.NewDecoder` 使用点；
2. 跳读（L2）确认是否设置 `decoder.Entity`；
3. 检查输入是否来自用户、网络或文件上传。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 将 `decoder.Entity` 置为空 map；
- 使用第三方库（`github.com/beevik/etree` 安全配置等）；
- 对 XML 进行 schema/白名单校验；
- 将 XML 转换为 Go struct 前先在受控环境解析。

**定位技巧：**
- 逐行读（L3）确认每个 Decoder 都应用安全设置；
- 跨模块追踪（L4）辅助函数是否复用不安全 Decoder。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Decoder 统一清空实体 | **L0（快速跳过）** | 风险低 |
| 个别 Decoder 遗漏设置 | **L2（跳读）** | 快速补齐 |
| 大量 Decoder 默认解析用户 XML | **L3（逐行读）** | 高风险 |
| Decoder 工具被多包共享 | **L4（跨模块追踪）** | 需完整梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. `xml.NewDecoder` 解析用户输入；
2. 未禁用外部实体；
3. 可构造 payload 读取本地文件或 SSRF。

#### 误报
1. 输入来自受控来源；
2. XML 在进入系统前已净化；
3. 仅用作内部工具。

#### 代码异味
1. 解析器封装在工具包，缺少安全说明；
2. 使用 `decoder.Strict = false`；
3. 解析结果直接用于文件写入/命令执行。

## Low risk

### 低风险评级场景

#### 1. XML 来自内部可信系统
- 攻击面小，可暂降级。

#### 2. 功能仅用于调试或离线转换
- 影响有限，但仍建议安全配置。

#### 3. 已计划统一封装安全 Decoder
- 明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部来源 | 攻击面小 | 中 |
| 离线工具 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
