# Python Django 模板表达式注入

**漏洞成因**：Django 模板引擎支持在模板中使用变量（`{{ }}`）、标签（`{% %}`）和过滤器。虽然 Django 模板的表达式能力相对受限，但当应用将用户输入作为模板内容进行渲染时，攻击者仍可能通过模板语法访问敏感对象属性、调用方法、遍历数据结构等，导致信息泄露或服务器端模板注入（SSTI）。常见于动态页面生成、自定义模板、邮件模板等场景。

---

## Details

**代码示例**：
```python
# 危险：使用 Template() 渲染用户输入的模板字符串
from django.template import Template, Context

user_input = request.GET.get('template')
template = Template(user_input)  # 危险：用户提供的模板内容
context = Context({'user': request.user})
output = template.render(context)

# 危险示例：使用 Engine.from_string() 渲染用户输入
from django.template import engines
template_str = request.POST.get('content')
template = engines['django'].from_string(template_str)  # 危险：动态模板
output = template.render({'data': user_data})

# 攻击载荷示例（Django 模板相对受限）
# {{ request.META }}  # 访问请求元数据
# {{ settings.SECRET_KEY }}  # 访问 Django 设置（如果在上下文中）
# {% debug %}  # 显示调试信息
# {{ user.is_superuser }}  # 访问用户对象属性
# {% for item in request.user.groups.all %}{{ item }}{% endfor %}  # 遍历关联对象

# 危险：在模板中使用用户输入但未转义
# 在模板文件中: <div>{{ user_content|safe }}</div>  # safe 过滤器禁用自动转义

# 较安全：使用预定义模板文件，用户仅能提供数据
from django.shortcuts import render
return render(request, 'user_profile.html', {'name': user_input})  # 模板文件由开发者控制

# 较安全：使用模板变量时依赖自动转义
# Django 默认启用自动转义，用户输入会被 HTML 转义
template = Template("<h1>{{ title }}</h1>")
context = Context({'title': user_input})
output = template.render(context)  # 用户输入被自动转义

# 较安全：限制上下文处理器，避免传递敏感对象
# 不要在 TEMPLATES['OPTIONS']['context_processors'] 中暴露敏感数据
```

**快速定位核心操作**：
- 关键词：`Template(`、`from_string`、`render()`、`Context()`、`{{ }}`、`{% %}`、`|safe`
- 查找 Django 模板的动态创建位置：`Template(user_input)`
- 追踪模板字符串的来源，判断是否包含用户输入
- 检查模板渲染上下文中传递的对象（如 `request`、`settings`、`user`）
- 关注 `|safe` 过滤器的使用，可能禁用自动转义
- 搜索 `engines['django'].from_string()` 的使用
- 检查自定义模板标签和过滤器的实现

**快速定位保护机制**：
- 模板字符串是否来自可信的文件系统而非用户输入
- 是否依赖 Django 的自动转义功能（默认启用）
- 是否避免使用 `|safe` 过滤器处理用户输入
- 模板上下文是否限制了敏感对象的传递
- 是否禁用了 `{% debug %}` 标签（生产环境应禁用 `DEBUG=False`）
- 是否自定义了安全的模板标签和过滤器
- Django 版本是否为最新稳定版（修复了某些安全问题）

**审计等级**：**L2-L3**
- **L2**：跳读模板创建代码，识别动态模板的使用
- **L3**：逐行验证模板字符串来源和上下文配置，确认安全措施

---

## Classify

**确认为漏洞**：
- 使用 `Template()` 或 `from_string()` 渲染用户输入的模板字符串
- 模板上下文中包含敏感对象（如 `settings`、`request.META`）
- 使用 `|safe` 过滤器处理用户输入，禁用自动转义
- 可通过模板语法访问敏感信息或执行危险操作
- 自定义模板标签或过滤器存在安全漏洞

**误报**：
- 模板字符串来自可信的文件系统，用户仅能提供数据值
- 依赖 Django 的自动转义功能且未使用 `|safe` 处理用户输入
- 模板上下文仅包含必要的数据对象，不包含敏感的全局对象
- 生产环境中禁用了 `DEBUG` 模式（`DEBUG=False`）

**代码异味**：
- 大量使用动态模板生成，增加 SSTI 风险
- 通过字符串拼接构造模板内容
- 模板上下文中传递了过多的对象
- 过度使用 `|safe` 过滤器禁用自动转义

---

## Low Risk

以下情况可评为低风险：
- **预定义模板**：仅使用文件系统中的模板文件，用户仅能提供数据值
- **自动转义**：依赖 Django 的默认自动转义功能且未使用 `|safe`
- **受限上下文**：模板上下文仅包含必要的数据对象，不包含 `settings`、`request` 等敏感对象
- **生产模式**：生产环境中禁用了 `DEBUG` 模式（`DEBUG=False`）
- **输入验证**：对用户输入进行严格验证，确保不包含模板语法字符
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有动态模板渲染操作均记录日志并监控异常模式

**注意**：Django 模板引擎相比 Jinja2 表达式能力更受限，但仍需避免将用户输入作为模板内容，应始终使用预定义模板文件。
