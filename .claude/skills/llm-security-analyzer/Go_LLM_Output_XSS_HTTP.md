# **Go LLM Output XSS HTTP**

当 Go Web 应用将 LLM 输出直接返回给客户端而未进行 HTML 转义，攻击者可以通过提示注入导致 XSS 漏洞。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索响应发送：`w.Write()`、`fmt.Fprintf()`、`json.NewEncoder()`
- 查找 HTML 设置：`w.Header().Set("Content-Type", "text/html")`
- 搜索转义函数：`html.EscapeString()`、缺失调用
- 查找模板：`template.Execute()`、`html/template`
- 定位 Content-Type：检查响应类型

**核心操作保护机制（L2: 跳读）**
- 检查是否使用了 `html/template` 包
- 验证是否对输出进行了转义
- 查看是否使用了 `html.EscapeString()`
- 检查是否设置了正确的 Content-Type
- 查看是否有 CSP 头

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪输出的构造方式
- 检查是否使用了 template 包
- 审查转义逻辑
- 查看是否有多个输出点
- 检查属性值处理

**数据流追踪（L4: 跨模块追踪）**
- 追踪从 LLM 到客户端的输出路径
- 检查中间处理

## Classify

**确认为漏洞的特征：**
1. 直接写入 LLM 输出到 HTTP 响应
2. Content-Type 为 HTML 但未转义
3. 未使用 html/template
4. 手动拼接 HTML
5. 无 CSP 保护

**误报场景：**
1. 使用 html/template 包自动转义
2. 使用 html.EscapeString()
3. 返回 JSON 由客户端处理
4. 有 CSP 头
5. 仅输出文本

**代码异味（需要深入审查）**
1. 手动 HTML 构造
2. 混合转义方式
3. 动态 HTML 生成
4. 条件转义

## Low risk

**评级为低风险的场景：**
1. 使用 html/template 自动转义
2. 返回 JSON 由现代框架处理
3. 使用 html.EscapeString()
4. 有 CSP 头
5. 仅输出文本内容
