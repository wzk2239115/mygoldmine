# Go｜xml.Unmarshal 直接解析用户输入

## Details

### 漏洞成因
`xml.Unmarshal` 会内部创建 Decoder 并解析实体。若直接对用户可控的 XML 字节调用 `xml.Unmarshal`，未清空实体映射，就会暴露 XXE 漏洞。尽管 Go 1.6+ 默认禁止网络访问，但仍可利用文件 URI 或本地实体读取敏感文件。

### 代码示例

**易受攻击的代码：**
```go
type Config struct {
    Name string `xml:"name"`
}

func loadConfig(body []byte) (*Config, error) {
    var cfg Config
    if err := xml.Unmarshal(body, &cfg); err != nil {
        return nil, err
    }
    return &cfg, nil
}
```

**安全示例：**
```go
func loadConfig(body []byte) (*Config, error) {
    decoder := xml.NewDecoder(bytes.NewReader(body))
    decoder.Strict = true
    decoder.Entity = map[string]string{}
    var cfg Config
    if err := decoder.Decode(&cfg); err != nil {
        return nil, err
    }
    return &cfg, nil
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xml.Unmarshal`, `xml.UnmarshalIndent`, `xml.Decoder`, `xml.NewDecoder`。

**定位步骤：**
1. 搜索 `xml.Unmarshal` 调用；
2. 跳读（L2）确认输入是否来自外部；
3. 检查是否改为自定义 Decoder。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 用自定义 Decoder 并清空 Entity；
- 前置 schema 校验或白名单；
- 在接收层拒绝包含 `<!DOCTYPE>` 的 XML；
- 使用第三方安全库或转换为 JSON。

**定位技巧：**
- 逐行读（L3）确保所有 Unmarshal 调用都替换；
- 跨模块追踪（L4）工具函数是否被多个服务引用。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 不使用 `xml.Unmarshal` 处理外部输入 | **L0（快速跳过）** | 风险低 |
| 个别 Unmarshal 用于用户数据 | **L2（跳读）** | 需替换 |
| 广泛对外部 XML 直接 Unmarshal | **L3（逐行读）** | 高风险 |
| 公共库中使用 Unmarshal | **L4（跨模块追踪）** | 需彻底梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. 直接对用户 XML 调用 `xml.Unmarshal`；
2. 未禁用实体映射；
3. 可通过 payload 访问敏感资源。

#### 误报
1. 输入为内部生成的固定模板；
2. 数据先经过 JSON 化/白名单转换；
3. 使用 `omitempty` 仅解析简单字段无外部实体风险（仍推荐安全配置）。

#### 代码异味
1. Fn 同时用于内部与外部输入；
2. 忽略 `decoder.Strict`；
3. 依赖字符串替换剥离 DOCTYPE。

## Low risk

### 低风险评级场景

#### 1. 内部服务调用
- 攻击面小，可暂降级。

#### 2. 仅处理小型配置并有人工审核
- 风险较低，但建议安全解析。

#### 3. 正在统一封装 XML 解析
- 明确计划，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部调用 | 攻击面小 | 中 |
| 人工审核 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
