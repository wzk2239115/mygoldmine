# Go｜手工拼接 HTML 导致 XSS

## 基本信息

- **难度等级：** ★★☆☆☆ (初级)
- **审时间：** 10-20分钟（单个漏洞点）
- **先决知识：** Go 字符串操作、HTTP 响应、HTML 编码、`html.EscapeString()` 使用
- **复杂度评估：**
  - 简单场景（单点拼接）：10-15分钟
  - 复杂场景（多个拼接点、循环生成）：20-30分钟

## 🚀 30秒快速清单

- [ ] 代码是否使用字符串拼接（+、fmt.Sprintf 等）构造 HTML 响应？
- [ ] 拼接的内容是否包含用户输入或外部变量？
- [ ] 拼接前是否使用了 `html.EscapeString()` 或 `template.HTMLEscape()` 进行编码？
- [ ] 是否使用了 Go 模板替代手工拼接？
- [ ] 是否存在多个地方进行拼接但编码方式不一致？

**判断：** 如果第 1-2 个问题打勾且第 3 个未打勾，需要进行 L2+ 深度分析

## Details

### 漏洞成因
当开发者使用 `fmt.Sprintf`、字符串连接或 `bytes.Buffer` 手工拼接 HTML 响应时，如果直接插入用户输入而未编码，将导致 XSS。该问题常见于轻量服务、告警邮件生成、模板缺失的历史代码。

### 代码示例

**易受攻击的代码：**
```go
func searchHandler(w http.ResponseWriter, r *http.Request) {
    query := r.FormValue("q")
    html := fmt.Sprintf("<h1>Search: %s</h1>", query)
    w.Header().Set("Content-Type", "text/html; charset=utf-8")
    w.Write([]byte(html))
}
```

**安全示例：**
```go
func searchHandler(w http.ResponseWriter, r *http.Request) {
    query := htmltemplate.HTMLEscapeString(r.FormValue("q"))
    w.Header().Set("Content-Type", "text/html; charset=utf-8")
    fmt.Fprintf(w, "<h1>Search: %s</h1>", query)
}
// 或改用 html/template 渲染
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `fmt.Sprintf("<`, `fmt.Fprintf(w`, `bytes.Buffer`, `strings.Builder`, `w.Write([]byte(`。

**定位步骤：**
1. 搜索构造 HTML 的字符串拼接；
2. 跳读（L2）确认变量来源是否可控；
3. 检查是否使用 `html/template` 或 `html.EscapeString`。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `html/template` 或 `html.EscapeString`; 
- 对参数进行类型/长度限制；
- 输出改为 JSON，让前端负责编码；
- 统一的 HTML 渲染工具函数。

**定位技巧：**
- 逐行读（L3）确认每个拼接点是否编码；
- 跨模块追踪（L4）字符串是否传递到邮件、日志等其他渠道。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 html/template 或 HTMLEscape | **L0（快速跳过）** | 风险低 |
| 部分位置遗漏编码 | **L2（跳读）** | 快速修复 |
| 广泛手工拼接 HTML | **L3（逐行读）** | 高风险 |
| 字符串跨模块重用 | **L4（跨模块追踪）** | 需完整分析 |

## Classify

### 研判标准

#### 确认漏洞
1. HTML 通过字符串拼接生成；
2. 插入用户可控内容未编码；
3. 可构造 payload 执行脚本。

#### 误报
1. 内容为常量或已编码；
2. 输出不在浏览器渲染（纯文本邮件、日志）；
3. 页面仅内网调试使用。

#### 代码异味
1. 使用 `fmt.Sprintf` 嵌套模板；
2. 依赖自定义替换 `<`、`>`；
3. 多个函数重复实现相似逻辑，缺乏统一规范。

## Low risk

### 低风险评级场景

#### 1. 输出仅供内网查看
- 攻击面小，可暂降级。

#### 2. 数据为低敏信息
- 即使被注入影响有限，但仍建议编码。

#### 3. 即将迁移到模板渲染
- 有明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部访问 | 攻击面小 | 中 |
| 低敏数据 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
