# Python eval/exec 函数用户输入注入

**漏洞成因**：Python 的 `eval()` 和 `exec()` 函数可执行字符串形式的 Python 代码。当应用将用户输入或外部数据直接传递给这些函数时，攻击者可构造恶意代码执行任意操作，如导入危险模块（`os`、`subprocess`）、读写文件、执行系统命令、访问敏感对象等，导致远程代码执行。常见于动态表达式求值、公式计算器、配置解析、脚本执行等场景。

---

## Details

**代码示例**：
```python
# 危险：直接使用 eval() 执行用户输入
user_input = request.GET.get('expr')
result = eval(user_input)  # 危险：用户可注入任意 Python 代码

# 危险：使用 exec() 执行用户输入
user_code = request.POST.get('code')
exec(user_code)  # 危险：用户可执行任意 Python 语句

# 危险示例：带有全局和局部命名空间
user_expr = request.args.get('expression')
context = {'x': 10, 'y': 20}
result = eval(user_expr, globals(), context)  # 攻击者可访问全局对象

# 攻击载荷示例
# __import__('os').system('calc')
# __import__('subprocess').run(['calc'])
# open('/etc/passwd').read()
# [c for c in [].__class__.__bases__[0].__subclasses__() if c.__name__ == 'Popen'][0](['calc'])

# 危险：即使限制了命名空间，仍可通过内置对象访问危险功能
eval(user_input, {'__builtins__': {}})  # 可被绕过

# 较安全：使用 ast.literal_eval() 仅允许字面量表达式
import ast
user_input = request.GET.get('data')
try:
    data = ast.literal_eval(user_input)  # 仅支持字面量：字符串、数字、元组、列表、字典等
except (ValueError, SyntaxError):
    raise Exception("Invalid input")

# 较安全：使用安全的表达式求值库
from simpleeval import simple_eval
result = simple_eval(user_input, names={'x': 10, 'y': 20})  # 限制可用的函数和变量

# 较安全：表达式白名单验证
import re
if not re.match(r'^[\d\s+\-*/()]+$', user_input):
    raise Exception("Invalid expression")
result = eval(user_input)  # 仅允许数学表达式
```

**快速定位核心操作**：
- 关键词：`eval(`、`exec(`、`compile(`、`__import__`、`globals()`、`locals()`
- 查找 `eval()` 和 `exec()` 函数的调用位置
- 追踪这些函数的参数来源，判断是否包含用户输入
- 检查是否传递了 `globals()` 或 `locals()` 参数
- 关注动态代码执行场景：计算器、表达式求值、配置加载
- 搜索 `compile()` 函数的使用，也可能存在代码注入风险

**快速定位保护机制**：
- 是否使用了 `ast.literal_eval()` 而非 `eval()`
- 是否使用了安全的表达式求值库（如 `simpleeval`、`RestrictedPython`）
- 是否限制了 `eval()` 的命名空间参数（`globals`、`locals`）
- 是否对用户输入进行了白名单验证或语法检查
- 是否禁用了 `__builtins__`：`eval(expr, {'__builtins__': {}})`（注意：可被绕过）
- 是否使用了沙箱环境或容器隔离
- Python 版本是否较新（某些版本修复了绕过技巧）

**审计等级**：**L1-L3**
- **L1**：关键词扫描，快速识别 `eval(` 和 `exec(` 的使用
- **L2**：跳读函数调用上下文，判断参数来源
- **L3**：逐行验证是否存在输入验证和命名空间限制

---

## Classify

**确认为漏洞**：
- 直接使用 `eval()` 或 `exec()` 执行用户输入的字符串
- 用户输入未经任何验证或过滤
- 即使限制了 `__builtins__`，仍可通过对象继承链绕过
- 可通过 `__import__`、`__subclasses__` 等机制访问危险模块

**误报**：
- 使用 `ast.literal_eval()` 仅解析字面量数据
- 使用安全的表达式求值库且配置正确
- 用户输入经过严格的白名单验证，仅允许安全的数学表达式
- 代码字符串为硬编码常量或来自可信的配置文件

**代码异味**：
- 使用 `eval()` 或 `exec()` 处理动态逻辑，即使当前输入不可控
- 通过字符串拼接构造代码，易引入注入风险
- 限制了 `__builtins__` 但未充分验证绕过风险
- 缺乏代码执行的审计日志

---

## Low Risk

以下情况可评为低风险：
- **使用 ast.literal_eval**：仅解析 Python 字面量，不执行代码
- **安全求值库**：使用 `simpleeval` 或 `RestrictedPython` 且配置严格
- **表达式白名单**：用户输入必须匹配预定义的安全模式（如纯数学表达式）
- **严格命名空间**：禁用 `__builtins__` 且验证了无法通过对象继承链绕过
- **沙箱隔离**：代码执行在受限的容器或虚拟机中
- **内网应用**：应用仅在内网部署，用户为可信的内部员工
- **日志监控**：所有 `eval()`/`exec()` 调用均记录日志并实时监控异常模式

**注意**：Python 的 `eval()` 和 `exec()` 极其危险，几乎所有限制都存在绕过可能，强烈建议使用 `ast.literal_eval()` 或安全的替代方案。
