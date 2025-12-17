# Python 动态导入本地文件包含

## Details

### 漏洞成因

Python 应用使用 `__import__()`、`importlib.import_module()`、`importlib.util.spec_from_file_location()`、`exec()`、`eval()` 等动态加载模块或执行代码时，若直接将用户输入作为模块名或代码内容，攻击者可加载任意 Python 模块或执行恶意代码。此漏洞常见于插件系统、动态命令加载、配置管理、脚本执行框架等场景。

### 代码示例

**易受攻击的代码（动态模块加载）：**
```python
from importlib import import_module
from flask import Flask, request

app = Flask(__name__)

@app.route('/load/<module_name>')
def load_module(module_name):
    # module_name = "os" 可加载 os 模块
    module = import_module(module_name)
    return str(dir(module))
```

**插件系统：**
```python
def load_plugin(plugin_name):
    # plugin_name = "../../../etc/passwd" 可能导致导入失败，但会探测文件系统
    plugin = __import__(f"plugins.{plugin_name}", fromlist=[plugin_name])
    plugin.execute()
```

**配置执行：**
```python
def execute_handler(handler_path):
    # handler_path = "os.system"
    parts = handler_path.split('.')
    module = __import__(parts[0], fromlist=[parts[1]])
    return getattr(module, parts[1])()
```

**代码执行（高危）：**
```python
def execute_code(code_file):
    # code_file = "../../../etc/passwd" - 读取任意文件并执行
    with open(f"scripts/{code_file}", 'r') as f:
        code = f.read()
    exec(code)  # 执行任意代码
```

**importlib 文件加载：**
```python
import importlib.util

def load_script(script_path):
    # script_path = "../../evil.py"
    spec = importlib.util.spec_from_file_location("module", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L3）

**关键词扫描：**
- 动态导入：`__import__()`, `import_module()`, `importlib`
- 代码执行：`exec()`, `eval()`, `compile()`
- 文件模块加载：`spec_from_file_location()`, `module_from_spec()`
- 输入源：`request.args`, `request.GET`, `request.POST`, `sys.argv`, 数据库查询结果

**定位步骤：**
1. 搜索 `__import__`、`import_module`、`exec`、`eval` 等函数调用。
2. 检查这些调用的参数是否包含变量，特别是来自外部输入的变量。
3. 追踪变量的来源：HTTP 参数、命令行、文件、数据库。
4. 确认是否有过滤或验证逻辑。

#### 保护机制定位（审计等级：L2-L4）

**检查是否存在：**
- **白名单验证：** 允许导入的模块列表
- **路径规范化：** 对文件路径使用 `realpath()` 检查
- **禁止 eval/exec：** 避免直接执行用户输入的代码
- **沙箱隔离：** 使用受限的全局命名空间执行代码
- **模块限制：** 限制可导入的模块（如禁止 `os`, `subprocess`）

**定位技巧：**
- 确认白名单是否完整，是否包含所有被调用的模块。
- 检查是否过滤了危险模块（`os`, `subprocess`, `sys`, `__import__`）。
- 验证 `exec()/eval()` 时是否限制了全局和本地命名空间。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单映射 + 模块索引 | **L0（快速跳过）** | 用户输入仅为键值 |
| 白名单验证 + 模块限制 | **L1（快速扫描）** | 验证白名单完整性 |
| 直接 import_module 用户输入 | **L3（逐行读）** | 极高风险 |
| exec/eval 用户代码 | **L4（跨模块追踪）** | 远程代码执行 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **用户可控的模块名或代码** 用于动态导入或执行。
2. **缺乏白名单验证**，允许导入任意模块。
3. **能够加载或执行恶意代码**，导致 RCE。

#### 误报

可视为误报的情况：
1. **输入仅用于索引白名单字典**，返回固定模块。
2. **限制导入的模块列表**（如 `allowedModules = ['json', 'csv']`）。
3. **使用受限的 exec/eval 命名空间**，禁止访问危险函数。

#### 代码异味

需记录的潜在问题：
1. **字符串过滤而非白名单**（如 `module.replace('os', '')` 可被绕过）。
2. **白名单不完整**，允许导入包含危险函数的模块。
3. **全局命名空间执行**，`exec(code, globals())` 可访问所有模块。
4. **错误处理泄露信息**，异常消息显示模块加载路径。

## Low risk

### 低风险评级场景

#### 1. 严格的白名单 + 模块限制

- **场景：** 只允许导入预定义的安全模块列表（如 `json`, `csv`），禁止系统模块。
- **风险评估：** 防护有效，但需定期审查白名单。

#### 2. 受限命名空间执行

- **场景：** 使用 `exec(code, {'__builtins__': {}})` 限制 Python 内置函数访问。
- **风险评估：** 提升安全性，但仍需白名单验证源代码。

#### 3. 受控后台操作

- **场景：** 功能仅对管理员开放，需要多重认证。
- **风险评估：** 攻击面小，但管理员账号泄露仍会导致 RCE。

#### 4. 本地开发环境

- **场景：** 脚本仅在本地开发环境运行，不在生产部署。
- **风险评估：** 生产风险为零，但开发环境应有最小权限。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 严格的模块白名单 | 限制导入范围 | 低 |
| 受限命名空间 + 白名单 | 双重防御 | 低 |
| 管理员限定 | 攻击面小 | 中 |
| 仅开发环境 | 生产无风险 | 低 |
