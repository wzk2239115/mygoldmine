# Python Jinja2/Mako 模板路径本地文件包含

## Details

### 漏洞成因

Python Web 框架广泛使用 Jinja2、Mako、Django Templates 等模板引擎。当应用根据用户输入动态加载模板文件时，若缺乏路径规范化和白名单验证，攻击者可利用 `../` 目录遍历或绝对路径读取敏感文件。此漏洞特别危险，因为模板文件会被解析并执行，若内容可控则直接导致 SSTI（服务端模板注入）或代码执行。

### 代码示例

**Jinja2 动态模板加载（易受攻击）：**
```python
from jinja2 import Environment, FileSystemLoader
from flask import Flask, request

app = Flask(__name__)
env = Environment(loader=FileSystemLoader('templates'))

@app.route('/render/<template_name>')
def render(template_name):
    # template_name = "../../etc/passwd" 会尝试加载敏感文件
    template = env.get_template(template_name)
    return template.render()
```

**Mako 模板加载：**
```python
from mako.lookup import TemplateLookup
from flask import Flask, request

app = Flask(__name__)
lookup = TemplateLookup(directories=['templates'])

@app.route('/view/<page>')
def view(page):
    # page = "../config.py"
    template = lookup.get_template(page)
    return template.render()
```

**自定义模板路径拼接：**
```python
from jinja2 import Environment, FileSystemLoader
import os

def load_custom_template(user_dir, template_name):
    # user_dir 由用户提供，template_name = "../../etc/passwd"
    template_dir = os.path.join('custom_templates', user_dir)
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render()
```

**Django 模板 + 用户路径：**
```python
from django.template.loader import get_template
from django.http import HttpResponse

def render_template(request):
    template_name = request.GET.get('template')  # template=../../settings.py
    template = get_template(template_name)
    return HttpResponse(template.render())
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）

**关键词扫描：**
- Jinja2：`Environment()`, `FileSystemLoader()`, `get_template()`, `render()`
- Mako：`TemplateLookup()`, `get_template()`, `render()`
- Django：`get_template()`, `loader.get_template()`, `render_to_string()`
- Jinja2 直接：`Environment(loader=FileSystemLoader())`
- 输入源：`request.GET`, `request.POST`, `request.args`, 数据库查询

**定位步骤：**
1. 搜索模板加载函数（`get_template`、`FileSystemLoader`）与用户输入的共现。
2. 检查 `FileSystemLoader` 配置的模板目录是否由用户控制。
3. 追踪 `get_template()` 的参数来源。
4. 确认是否有路径过滤或白名单验证。

#### 保护机制定位（审计等级：L2-L3）

**检查是否存在：**
- **白名单验证：** 允许加载的模板列表
- **路径规范化：** 使用 `realpath()` 验证最终路径
- **前缀检查：** 确保模板路径在允许的目录内
- **禁用 import/include：** 模板引擎是否禁用了 `{% import %}` 和 `{% include %}`
- **沙箱隔离：** 模板执行上下文的限制

**定位技巧：**
- 确认 `FileSystemLoader` 初始化时的目录是否为常量还是变量。
- 检查是否对 `get_template()` 的参数进行了过滤。
- 验证 Jinja2 的 `autoescape` 和 `trim_blocks` 等安全配置。
- 查看模板文件是否只读，是否需要高权限访问。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单模板列表 | **L0（快速跳过）** | 用户输入仅为键值 |
| 路径规范化 + 前缀校验 | **L2（跳读）** | 确认校验逻辑完备 |
| 直接拼接用户输入 | **L3（逐行读）** | 极高风险 |
| 模板内容可控 + 模板执行 | **L4（跨模块追踪）** | SSTI + RCE |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **用户可控的模板路径** 用于 `get_template()`。
2. **缺乏有效防护**（无路径规范化、白名单、目录限制）。
3. **能够访问敏感文件或模板内容可控**。

#### 误报

可视为误报的情况：
1. **模板名称仅用于索引白名单字典**。
2. **路径经过规范化并检查前缀**。
3. **模板目录由框架/应用固定控制，不受用户输入影响**。

#### 代码异味

需记录的潜在问题：
1. **多个 FileSystemLoader 配置不一致**，某些路由缺乏防护。
2. **模板内容包含用户输入且未转义**，导致 SSTI。
3. **模板引擎未禁用危险函数**（如 `include`、`import`），可被利用。
4. **错误处理泄露路径信息**，`TemplateNotFound` 异常显示尝试的路径。

## Low risk

### 低风险评级场景

#### 1. 白名单模板列表

- **场景：** 只允许加载预定义的模板列表，用户输入仅为键值。
- **风险评估：** 防护有效，但需定期审查白名单。

#### 2. 受限模板目录 + 路径规范化

- **场景：** 使用 `realpath()` 验证路径，确保在允许的目录内，且禁用 `include/import`。
- **风险评估：** 防护层次清晰，但需验证规范化逻辑。

#### 3. 只读静态模板

- **场景：** 模板目录仅包含公开的、预定义的模板文件，无动态内容。
- **风险评估：** 危害有限，但仍可能泄露目录结构。

#### 4. 受控后台操作

- **场景：** 功能仅对管理员开放，需要多重认证。
- **风险评估：** 攻击面小，但管理员账号泄露仍会导致 LFI。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 白名单模板 | 限制加载范围 | 低 |
| 路径规范化 + 前缀检查 | 有效防护 | 低 |
| 禁用 include/import | 深度防御 | 低 |
| 管理员限定 | 攻击面小 | 中 |
