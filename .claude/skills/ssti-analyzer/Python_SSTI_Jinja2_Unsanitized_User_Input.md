# Python_SSTI_Jinja2_Unsanitized_User_Input

**漏洞类型**: 使用 Jinja2 模板引擎时未对用户输入进行过滤，直接将用户可控内容嵌入模板渲染

---

## Details

### 代码示例

**易受攻击的代码模式**:
```python
# 直接渲染用户输入作为模板内容
from jinja2 import Template
user_input = request.args.get('template')
template = Template(user_input)  # 用户输入直接作为模板代码
result = template.render()

# render_template_string 直接渲染用户输入
from flask import Flask, render_template_string
user_content = request.form['content']
html = render_template_string(user_content)

# 字符串拼接后渲染
template_str = "Hello, " + request.args.get('name')
template = Template(template_str)
output = template.render()

# 使用 jinja2.Environment 加载字符串模板
from jinja2 import Environment
env = Environment()
user_template = request.get_json()['template']
tpl = env.from_string(user_template)  # 直接从用户输入创建模板
rendered = tpl.render()

# Jinja2 文件模板但上下文包含用户可控数据
template = jinja2.Template(open('template.html').read())
user_data = request.json
result = template.render(user_data=user_data)  # 用户可控的变量直接放入上下文
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 模板创建函数: `Template()`, `render_template_string()`, `env.from_string()`, `select_autoescape=False`
- 模板渲染方法: `.render()`, `.render_template()`, `.module.root()`
- 用户输入获取: `request.args.get()`, `request.form[]`, `request.get_json()`, `request.data`, `request.values`
- 输入源: 来自 GET/POST 参数、JSON body、Cookie、Header、URL 路径参数
- 模板文件处理: `get_template()`, `select_template()` 配合用户可控的模板名

**L2 跳读定位**:
- 从用户输入获取点追踪到 `Template()` 或 `render_template_string()` 的参数
- 关注模板内容是否包含完整的 `Template()` 调用或通过字符串拼接传入
- 检查模板变量是否来自用户输入且在模板中直接使用
- 搜索模板渲染调用的上下文参数是否包含用户可控数据

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入白名单验证: `if input in ALLOWED_TEMPLATES:`, `SAFE_KEYWORDS = [...]`
- 模板使用限制: 仅渲染预定义模板文件，不接受用户提交的模板代码
- 转义处理: `Markup()`, `markupsafe.escape()` 对用户输入进行转义
- AutoEscape 启用: `Environment(autoescape=True)` 或 `select_autoescape()`
- Sandbox 沙箱: `SandboxedEnvironment` 限制模板可访问的函数和属性

**L3 逐行分析**:
- 模板创建方式检查:
  - `Template()` vs `get_template('filename')` - 前者接受代码字符串，后者仅加载文件
  - 是否使用 `from_string()` (接受代码字符串) vs `from_file()` (加载文件)
  - 是否在 `Environment` 中配置 `loader=FileSystemLoader()`（限制只能加载文件）
- Autoescape 配置:
  - 检查 `autoescape=True` 是否在 Environment 初始化
  - `select_autoescape()` 是否正确配置用于保护用户输入
  - 是否仅针对 HTML/XML 但不包括 Jinja2 表达式
- 沙箱使用:
  - 是否使用 `SandboxedEnvironment` 替代 `Environment`
  - 是否配置 `globals`, `filters`, `tests` 白名单
  - 是否禁用危险过滤器如 `range()`, `lipsum()`
- 模板变量白名单:
  - 上下文中传递的变量是否经过验证和类型检查
  - 是否存在变量名白名单 `ALLOWED_CONTEXT_VARS`
  - 是否使用 `strict_undefined=True` 防止访问未定义变量

**L4 跨模块追踪**:
- 追踪用户输入从 routes/views → 模板处理 → 渲染的完整数据流
- 检查是否在中间件或装饰器层做了输入验证
- 验证是否有全局的 Jinja2 环境配置文件限制危险操作
- 检查框架配置 (如 Flask/Django) 是否默认启用了 Autoescape
- 追踪模板继承和包含操作，检查 `extends`, `include`, `import` 是否受到用户控制

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接作为 `Template()` 或 `render_template_string()` 的参数
- 模板引擎未启用 Autoescape 且用户可控数据直接渲染
- 使用基础 `Environment()` 而非 `SandboxedEnvironment` 时，允许访问 Python 内置对象
- 模板中可使用 `{{ 7 * 7 }}` 等表达式进行代码执行验证
- 可通过 `{{ self.__init__.__globals__.__builtins__.open('/etc/passwd').read() }}` 等 SSTI payload 访问系统资源

**误报判定**:
- 模板内容完全由后端开发者预定义，用户仅可控模板中的变量值（如 `Hello, {{ name }}`）
- 使用了 `SandboxedEnvironment` 且正确配置了函数/属性白名单，经验证无法访问危险方法
- 启用了严格的 Autoescape，且用户输入仅作为模板变量不参与模板逻辑构造
- 使用 `get_template('filename')` 加载预定义模板文件，用户仅能控制文件名选择（需检查路径遍历）
- 存在完整的输入验证白名单，用户输入被严格限制在允许的模板列表内

**代码异味**:
- 虽然启用了 Autoescape 但仍使用 `{{ user_input | safe }}`，绕过转义保护
- 模板变量名称来自用户输入如 `{{ request.args['var_name'] }}`，可能访问不预期的上下文变量
- 使用黑名单过滤危险字符串如禁用 `__` 或 `class__`，但仍可通过其他编码绕过
- 模板路径参数可由用户控制如 `get_template(user_input + '.html')`，存在目录遍历风险
- 在模板中直接包含未验证的用户输入用于条件判断或循环次数如 `{% for i in range(user_count) %}`
- 使用了过期的 Jinja2 版本，可能存在已知的沙箱逃逸漏洞

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 模板渲染功能仅限管理员或特权用户使用，需要强认证
- 用户提交的模板需经后台审核才能被渲染执行
- 功能被完全隔离在内部系统，非公网可访问

**架构设计防护**:
- 已明确采用 `SandboxedEnvironment` 替代普通 `Environment`
- 模板内容完全预定义在代码中或受信的配置文件，用户仅控制参数值
- 使用了专门的模板编译和渲染微服务，与主应用隔离
- 启用了严格的 Content Security Policy 限制脚本执行

**输入与输出保护**:
- 用户输入被严格白名单验证，仅允许字母数字和特定符号
- 即使用户可控模板名称，也通过 `FileSystemLoader` 限制模板目录访问
- 渲染结果经过二次处理或重新编码后返回，不直接透传原始内容
- 所有用户输入在模板中都被强制当作变量值而非模板代码处理

**监控与运行环保**:
- 部署在完全隔离的容器或虚拟机环境，无系统文件访问权限
- 进程以最小权限用户运行，文件系统权限限制严格
- 有完整的审计日志和异常检测，可及时发现异常模板渲染
- 系统配置禁用了危险函数如 `exec()`, `system()`, 文件操作等
