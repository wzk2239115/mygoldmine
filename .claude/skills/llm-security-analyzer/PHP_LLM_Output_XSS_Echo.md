# **PHP LLM Output XSS Echo**

当 PHP 应用直接 echo 或输出 LLM 结果到 HTML 页面而未进行转义，攻击者可以通过提示注入导致 XSS 漏洞。

## Details

**代码示例位置识别技巧（L1: 关键词扫描）**
- 搜索直接输出：`echo $llmOutput`、`echo $response`、`<?= $variable ?>`
- 查找转义函数：缺失的 `htmlspecialchars()`、`htmlentities()`
- 搜索模板引擎：`Blade`、`Twig` 的 autoescape 配置
- 查找 LLM 数据处理：`$response->text`、`$result`
- 定位输出上下文：HTML body vs HTML attribute

**核心操作保护机制（L2: 跳读）**
- 检查是否使用了 `htmlspecialchars()` 或 `htmlentities()`
- 验证模板引擎的 autoescape 配置
- 查看是否有内容安全策略（CSP）
- 检查输出编码设置
- 查看是否分离了 HTML 和纯文本输出

**快速定位到具体漏洞（L3: 逐行读）**
- 追踪 LLM 输出的所有输出点
- 检查是否使用了转义函数
- 审查 echo 语句
- 查看模板中的变量使用
- 检查不同上下文的处理

**数据流追踪（L4: 跨模块追踪）**
- 追踪从 LLM API 到 HTML 输出的路径
- 检查所有输出点

## Classify

**确认为漏洞的特征：**
1. 直接 echo LLM 输出
2. 未使用 htmlspecialchars()
3. 模板 autoescape 禁用
4. 在 HTML 属性中输出
5. 无 CSP 保护

**误报场景：**
1. 使用 htmlspecialchars() 或 htmlentities()
2. 模板 autoescape 启用
3. 有 CSP 头
4. 输出仅用于文本
5. 框架自动处理转义

**代码异味（需要深入审查）**
1. 混合 echo 和转义
2. 条件性转义
3. 自定义转义函数
4. 动态 HTML 生成

## Low risk

**评级为低风险的场景：**
1. 所有输出都使用 htmlspecialchars() 或 htmlentities()
2. 模板引擎 autoescape 启用
3. 有 CSP 头限制脚本
4. 输出仅用于文本内容
5. 使用现代框架和安全实践
