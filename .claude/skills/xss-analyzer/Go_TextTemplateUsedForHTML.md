# Go｜使用 text/template 渲染 HTML 导致 XSS

## 基本信息

- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 15-30分钟（单个漏洞点）
- **先决知识：** Go 标准库（text/template vs html/template）、模板语法、自动转义
- **复杂度评估：**
  - 简单场景（单个模板文件）：15-20分钟
  - 复杂场景（多个模板、自定义函数）：30-45分钟

## 🚀 30秒快速清单

- [ ] 代码是否使用了 `text/template` 而不是 `html/template` 来渲染 HTML？
- [ ] 模板中是否输出了用户输入或外部数据？
- [ ] 是否定义了自定义模板函数且这些函数没有进行 HTML 转义？
- [ ] 应用是否使用了 `html/template` 但禁用了自动转义？
- [ ] 是否存在在 Go 代码中预先编码后再传入模板的情况？

**判断：** 如果第 1-2 个问题打勾且第 4 未被实现，需要进行 L3+ 深度分析

## Details

### 漏洞成因
Go 中 `html/template` 自动对数据进行上下文敏感转义，而 `text/template` 不会。当开发者误用 `text/template` 渲染 HTML 页面，或将用户输入直接写入响应，就会导致 XSS。

### 代码示例

**易受攻击的代码：**
```go
tmpl := template.New("result") // text/template
tmpl, _ = tmpl.Parse(`<p>{{.Query}}</p>`)
tmpl.Execute(w, map[string]string{"Query": r.FormValue("q")})
```

**安全示例：**
```go
htmlTmpl := template.Must(htmltemplate.New("result").Parse(`<p>{{.Query}}</p>`))
htmlTmpl.Execute(w, struct{ Query string }{r.FormValue("q")})
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `template.New`, `template.Parse`, `Execute`, `ExecuteTemplate`, `fmt.Fprintf`。

**定位步骤：**
1. 搜索 `text/template` 使用场景；
2. 跳读（L2）确认模板输出是否为 HTML 响应；
3. 检查是否错误地使用 `fmt.Fprintf`、`w.Write` 拼接用户输入。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 使用 `html/template`; 
- 输出前调用 `template.HTMLEscapeString`;
- 响应改为 JSON，并由前端安全渲染；
- 统一的渲染函数封装。

**定位技巧：**
- 逐行读（L3）确认模板变量来源；
- 跨模块追踪（L4）对同一模板的复用是否使用不同 package。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全部使用 `html/template` | **L0（快速跳过）** | 风险低 |
| 少数页面误用 `text/template` | **L2（跳读）** | 快速修补 |
| 不使用模板而直接拼接 HTML | **L3（逐行读）** | 高风险 |
| 模板由多个包共享 | **L4（跨模块追踪）** | 需完整分析 |

## Classify

### 研判标准

#### 确认漏洞
1. HTML 响应由 `text/template` 渲染或手工拼接；
2. 插入用户可控数据；
3. 能构造 payload 执行脚本。

#### 误报
1. 输出为纯文本/JSON；
2. 数据来自常量或经过编码；
3. 页面仅内部调试使用且不可外部访问。

#### 代码异味
1. 在模板中使用 `{{.}}` 输出未处理字符串；
2. 使用 `template.Must(template.New(...))` 但未引入 html/template；
3. 渲染函数散落各处，缺少统一封装。

## Low risk

### 低风险评级场景

#### 1. 内部调试页面
- 攻击面小，可暂降级。

#### 2. 输出仅展现低敏数据
- 虽风险低，但仍建议改用 html/template。

#### 3. 已计划切换到 html/template
- 有明确时间表，暂降级并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部页面 | 攻击面小 | 中 |
| 低敏数据 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
