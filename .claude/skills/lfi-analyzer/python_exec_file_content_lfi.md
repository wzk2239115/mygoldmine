# Python 文件内容执行本地文件包含

## Details

### 漏洞成因

Python 应用在读取文件内容后使用 `exec()`、`eval()`、`compile()` 等函数执行时，若文件路径由用户输入控制且未做路径验证，攻击者可读取任意 Python 脚本文件并执行其中的代码，导致远程代码执行。此漏洞常见于脚本加载框架、动态任务执行、配置加载与执行等场景，危害等级极高。

### 代码示例

**易受攻击的代码（文件读取 + exec）：**
```python
import os
from flask import Flask, request

app = Flask(__name__)

@app.route('/exec/<script_name>')
def execute_script(script_name):
    # script_name = "../../etc/passwd"
    script_path = os.path.join('scripts', script_name)
    with open(script_path, 'r') as f:
        code = f.read()
    exec(code)  # 直接执行文件内容
    return "Done"
```

**配置文件执行：**
```python
def load_config(config_file):
    # config_file = "../../app_secret_config.py"
    config_path = f"config/{config_file}.py"
    with open(config_path, 'r') as f:
        config_code = f.read()
    exec(config_code, globals())  # 配置被执行到全局命名空间
```

**动态任务执行：**
```python
from celery import Celery

app = Celery('tasks')

def execute_task(task_file):
    # task_file = "../../malicious.py"
    with open(f"tasks/{task_file}", 'r') as f:
        task_code = f.read()
    exec(task_code)  # 后台任务执行任意代码
```

**eval 执行代码（高危）：**
```python
def evaluate_expression(expr_file):
    # 从文件读取表达式，使用 eval 执行
    with open(f"expressions/{expr_file}", 'r') as f:
        expr = f.read()
    return eval(expr)  # eval 可执行任意 Python 代码
```

**pickle 反序列化（高危）：**
```python
import pickle

def load_serialized_object(obj_file):
    # obj_file = "../../etc/passwd"
    with open(f"objects/{obj_file}", 'rb') as f:
        obj = pickle.load(f)  # pickle 可执行任意代码
    return obj
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L3）

**关键词扫描：**
- 文件执行：`exec()`, `eval()`, `compile()`, `__import__()`
- 序列化：`pickle.load()`, `pickle.loads()`, `dill`, `cloudpickle`
- 文件读取：`open()`, `read()`, `read_text()`, `read_bytes()`
- 路径操作：`os.path.join()`, `Path()`, `.format()`, `f-string`
- 输入源：`request.GET`, `request.POST`, `request.args`, `sys.argv`

**定位步骤：**
1. 搜索 `exec(`、`eval(`、`pickle.load(` 等代码执行或反序列化函数。
2. 检查这些函数前是否有 `open()` 或 `read()` 操作。
3. 追踪文件路径参数的来源，确认是否来自外部输入。
4. 确认是否有路径验证或沙箱隔离。

#### 保护机制定位（审计等级：L2-L4）

**检查是否存在：**
- **白名单验证：** 允许执行的文件列表
- **路径规范化：** 使用 `realpath()` 验证文件路径
- **禁止 exec/eval：** 使用安全的配置加载库（如 `json`, `yaml`）
- **受限命名空间：** `exec(code, {'__builtins__': {}})` 限制访问
- **签名验证：** 对脚本进行数字签名验证
- **避免 pickle：** 使用 JSON 或 YAML 替代不安全的反序列化

**定位技巧：**
- 确认执行代码时是否限制了命名空间（`exec(code, safe_globals)`）。
- 检查是否使用了 `pickle`，这是不安全的反序列化方式。
- 验证是否对文件内容进行了验证（如哈希校验、签名验证）。
- 查看是否可以绕过白名单（如通过路径编码或符号链接）。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单脚本列表 | **L0（快速跳过）** | 用户输入仅为键值 |
| 路径规范化 + 白名单 | **L1（快速扫描）** | 验证防护完整性 |
| 直接执行用户指定文件 | **L3（逐行读）** | 极高风险 |
| 无路径验证的 exec/eval | **L4（跨模块追踪）** | 远程代码执行 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **文件路径由用户输入控制**。
2. **缺乏路径验证或白名单**。
3. **文件内容被 exec/eval 执行或通过 pickle 反序列化**。
4. **执行命名空间包含危险函数**（如 `__import__`, `os.system`）。

#### 误报

可视为误报的情况：
1. **文件名仅用于索引白名单字典**，返回固定脚本。
2. **路径经 `realpath()` 规范化并检查前缀**。
3. **使用 JSON/YAML 代替 pickle 进行数据加载**。
4. **执行命名空间被严格限制，不包含危险函数**。

#### 代码异味

需记录的潜在问题：
1. **使用 pickle 反序列化不可信数据**。
2. **exec/eval 时使用 `globals()` 而非受限命名空间**。
3. **错误处理不当，异常信息泄露文件路径**。
4. **符号链接未检查，可指向任意文件**。
5. **多处执行逻辑，某些地方缺乏防护**。

## Low risk

### 低风险评级场景

#### 1. 严格白名单 + 路径规范化

- **场景：** 白名单列出所有允许执行的脚本，使用 `realpath()` 验证路径。
- **风险评估：** 防护有效，但需定期审查白名单，禁用 pickle。

#### 2. 受限命名空间 + 签名验证

- **场景：** 执行时使用受限的全局命名空间，且脚本经过数字签名验证。
- **风险评估：** 深度防御，但签名验证实现需正确。

#### 3. 完全避免 exec/eval

- **场景：** 使用 JSON/YAML 配置加载，不使用 exec/eval 执行代码。
- **风险评估：** 最安全的方案，建议采用。

#### 4. 受控后台操作

- **场景：** 脚本执行功能仅对管理员开放，需要多重认证。
- **风险评估：** 攻击面小，但管理员账号泄露仍会导致 RCE。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 严格白名单 | 限制执行范围 | 低 |
| 路径规范化 + 签名验证 | 深度防御 | 低 |
| 使用 JSON/YAML | 避免危险 exec | 最低 |
| 管理员限定 | 攻击面小 | 中 |
