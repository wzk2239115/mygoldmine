# Python Email Template Injection

## Details

Python 邮件系统中使用模板引擎（如 Jinja2、Django Templates、string.Template）渲染邮件内容时，若用户输入直接嵌入模板未经转义，攻击者可注入模板指令。这可能导致敏感信息泄露、服务器端模板注入（SSTI）或邮件内容篡改。

**代码示例与审计要点**

```python
from jinja2 import Template
from django.core.mail import send_mail

# 危险：直接将用户输入拼接到模板字符串
template_str = f"Hello {user_name}, your code is: {{{{ code }}}}"
template = Template(template_str)
body = template.render(code=secret_code)
send_mail('Subject', body, 'from@example.com', [user_email])

# 危险：使用用户输入作为模板内容
template = Template(request.POST.get('email_template'))
body = template.render(context_data)
```

**快速定位核心操作 (L1: 关键词扫描)**
- 搜索 `Template(`、`jinja2.Template`、`django.template.Template`、`string.Template`
- 查找 `render()`、`substitute()`、`format()` 方法
- 定位模板字符串中是否包含用户输入：`f"...{user_input}..."`、字符串拼接
- 检查 `render_to_string()`、`get_template()` 是否使用了动态模板名或内容

**快速定位保护机制 (L2: 跳读)**
- 查找自动转义设置：`autoescape=True`、`{% autoescape on %}`
- 搜索手动转义函数：`escape()`、`markupsafe.escape()`、`html.escape()`
- 检查是否使用沙箱环境：`jinja2.sandbox.SandboxedEnvironment`
- 查看模板是否从文件加载而非用户输入构建

---

## Classify

**理论研判标准**

1. **确认为漏洞的标志**：
   - 用户输入直接拼接到模板字符串中
   - 允许用户提供完整的模板内容
   - 模板渲染时未启用自动转义
   - 可通过输入 `{{7*7}}` 或 `{{config}}` 等测试注入成功
   - 能够访问敏感对象或执行代码

2. **确认为误报的情况**：
   - 模板内容完全静态，从文件系统加载
   - 用户输入仅作为预定义模板的上下文变量传入
   - 使用了沙箱模板环境（SandboxedEnvironment）
   - 所有用户输入都经过严格转义

3. **代码异味判断**：
   - 虽有转义但不完全（仅转义部分特殊字符）
   - 转义在某些代码路径中缺失
   - 使用 `safe` 过滤器或 `mark_safe()` 标记用户输入为安全内容

---

## Low risk

**这些情况应给予低风险评级**

1. **静态模板**：所有邮件模板从文件系统加载，用户输入仅作为上下文数据传入，模板本身不可修改

2. **沙箱环境**：使用 `jinja2.sandbox.SandboxedEnvironment` 限制模板执行能力，禁止访问敏感对象和函数

3. **自动转义**：模板引擎启用了自动 HTML/文本转义，所有变量默认转义

4. **严格白名单**：模板中可用的变量和过滤器经过严格限制，用户输入仅能影响纯文本内容

5. **纯文本邮件**：仅发送纯文本邮件，不使用 HTML 模板，模板注入的影响有限
