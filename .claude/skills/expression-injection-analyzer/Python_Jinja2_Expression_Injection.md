# Python Jinja2 模板表达式注入

**漏洞成因**：Jinja2 是 Python 中流行的模板引擎，支持在模板中使用表达式（`{{ }}`）和语句（`{% %}`）。当应用将用户输入直接嵌入模板内容或使用用户输入作为模板字符串时，攻击者可构造恶意表达式访问对象属性、调用方法、导入模块、执行系统命令等，导致服务器端模板注入（SSTI）和远程代码执行。常见于动态页面生成、邮件模板、报表生成等场景。

---

## Details

**代码示例**：
```python
# 危险：将用户输入作为模板内容渲染
from jinja2 import Template

user_input = request.args.get('name')
template = Template("Hello " + user_input)  # 危险：用户输入直接拼接到模板
output = template.render()

# 危险示例：使用 Template.from_string() 渲染用户输入
from jinja2 import Environment
env = Environment()
template_str = request.form.get('template')
template = env.from_string(template_str)  # 危险：用户提供的模板内容
output = template.render(user=current_user)

# 攻击载荷示例
# {{ config }}  # 访问 Flask 配置对象
# {{ ''.__class__.__mro__[1].__subclasses__() }}  # 列出所有子类
# {{ request.application.__globals__.__builtins__.__import__('os').popen('calc').read() }}
# {% for c in [].__class__.__base__.__subclasses__() %}{% if c.__name__ == 'catch_warnings' %}{{ c()._module.__builtins__['__import__']('os').system('calc') }}{% endif %}{% endfor %}

# 危险：在模板变量中使用用户输入
template = Template("<h1>{{ user_title }}</h1>")
output = template.render(user_title=user_input)  # 如果启用自动转义则相对安全

# 较安全：使用自动转义模式
from jinja2 import Environment, select_autoescape
env = Environment(autoescape=select_autoescape(['html', 'xml']))
template = env.get_template('page.html')
output = template.render(name=user_input)  # 用户输入会被 HTML 转义

# 较安全：使用沙箱环境
from jinja2.sandbox import SandboxedEnvironment
env = SandboxedEnvironment()
template = env.from_string(template_str)
output = template.render()  # 限制危险函数和属性访问

# 较安全：仅使用预定义模板，用户仅能提供数据
template = env.get_template('user_profile.html')  # 模板文件由开发者控制
output = template.render(name=user_input, age=user_age)  # 用户仅能提供数据值
```

**快速定位核心操作**：
- 关键词：`Template(`、`from_string`、`render()`、`Environment()`、`{{ }}`、`{% %}`
- 查找 Jinja2 模板的创建和渲染位置
- 追踪模板字符串的来源，判断是否包含用户输入
- 检查是否使用 `Template()` 或 `from_string()` 动态创建模板
- 关注模板渲染上下文中传递的对象（如 `config`、`request`、`app`）
- 搜索依赖：`jinja2`、`flask`（Flask 默认使用 Jinja2）

**快速定位保护机制**：
- 是否使用了 `SandboxedEnvironment` 而非普通 `Environment`
- 是否启用了自动转义：`autoescape=True` 或 `select_autoescape()`
- 模板字符串是否来自可信的文件而非用户输入
- 是否限制了模板上下文中可访问的对象和函数
- 是否自定义了过滤器和测试函数以限制危险操作
- Jinja2 版本是否为最新稳定版（修复了某些绕过技巧）
- 是否禁用了危险的过滤器和函数（如 `attr`、`getitem`）

**审计等级**：**L2-L3**
- **L2**：跳读模板创建和渲染代码，识别动态模板的使用
- **L3**：逐行验证模板字符串来源和环境配置，确认安全措施

---

## Classify

**确认为漏洞**：
- 使用 `Template()` 或 `from_string()` 渲染用户输入的模板字符串
- 未使用 `SandboxedEnvironment` 或沙箱配置不当
- 模板上下文中包含敏感对象（如 Flask 的 `config`、`request.application`）
- 未启用自动转义或转义可被绕过
- 可通过对象继承链访问 `__builtins__` 并执行系统命令

**误报**：
- 使用 `SandboxedEnvironment` 且配置正确
- 模板字符串来自可信的文件系统，用户仅能提供数据值
- 启用了严格的自动转义且模板不包含用户可控的表达式语法
- 模板上下文仅包含必要的数据对象，不包含危险的全局对象

**代码异味**：
- 大量使用动态模板生成，增加 SSTI 风险
- 通过字符串拼接构造模板内容
- 模板上下文中传递了过多的对象和函数
- 缺乏对模板渲染操作的审计日志

---

## Low Risk

以下情况可评为低风险：
- **沙箱环境**：使用 `SandboxedEnvironment` 且未注册危险的过滤器和函数
- **预定义模板**：仅使用文件系统中的模板，用户仅能提供数据值
- **自动转义**：启用严格的自动转义且验证了无法注入模板语法
- **受限上下文**：模板上下文仅包含必要的数据对象，不包含 `config`、`app` 等敏感对象
- **输入验证**：对用户输入进行严格验证，确保不包含模板语法字符（`{`、`}`、`%`）
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有模板渲染操作均记录日志并监控异常模式

**注意**：Jinja2 SSTI 是 Python Web 应用的高危漏洞，攻击者可通过对象继承链绕过沙箱限制，必须严格控制模板内容的来源。
