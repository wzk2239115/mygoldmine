# Python 配置解析器表达式注入

**漏洞成因**：Python 的配置解析器（如 `configparser`、`yaml.load`、`pickle.load`）在解析配置文件时可能执行动态代码或表达式。当应用加载用户可控的配置文件或配置内容时，攻击者可构造恶意配置注入 Python 代码、导入危险模块、执行系统命令等，导致远程代码执行。常见于配置文件加载、序列化数据反序列化、动态配置管理等场景。

---

## Details

**代码示例**：
```python
# 危险：使用 yaml.load() 加载用户可控的配置文件
import yaml

config_content = request.files['config'].read()
config = yaml.load(config_content)  # 危险：默认使用 FullLoader，可执行 Python 代码

# 攻击载荷示例（YAML）
# !!python/object/apply:os.system ['calc']
# !!python/object/new:os.system ['calc']
# !!python/object/apply:subprocess.Popen [['calc']]

# 危险：使用 pickle.load() 反序列化用户数据
import pickle

serialized_data = request.POST.get('data')
obj = pickle.loads(serialized_data)  # 危险：pickle 可执行任意代码

# 攻击载荷示例（Pickle）
# import pickle, os
# class RCE:
#     def __reduce__(self):
#         return (os.system, ('calc',))
# pickle.dumps(RCE())

# 危险：使用 eval() 解析配置值
import configparser
config = configparser.ConfigParser()
config.read('app.conf')
value = eval(config.get('section', 'expression'))  # 危险：配置值被当作代码执行

# 危险：使用 exec() 执行配置文件内容
with open('user_config.py') as f:
    exec(f.read())  # 危险：配置文件作为 Python 代码执行

# 较安全：使用 yaml.safe_load() 仅加载标准 YAML 类型
import yaml
config_content = request.files['config'].read()
config = yaml.safe_load(config_content)  # 仅支持标准 YAML 类型，不执行代码

# 较安全：使用 json.load() 加载 JSON 配置
import json
config_content = request.files['config'].read()
config = json.loads(config_content)  # JSON 不支持代码执行

# 较安全：避免使用 pickle，使用 JSON 或其他安全的序列化格式
import json
data = json.dumps(obj)  # 序列化
obj = json.loads(data)  # 反序列化，安全

# 较安全：使用 configparser 但不使用 eval() 解析值
import configparser
config = configparser.ConfigParser()
config.read('app.conf')
value = config.get('section', 'key')  # 直接获取字符串值，不执行代码
```

**快速定位核心操作**：
- 关键词：`yaml.load`、`pickle.load`、`pickle.loads`、`eval(config`、`exec(`、`configparser`、`__reduce__`
- 查找配置文件加载和反序列化操作
- 追踪配置文件或数据的来源，判断是否可被用户控制
- 检查 YAML 加载器的类型：`Loader`、`FullLoader`（危险）或 `SafeLoader`（安全）
- 关注 `pickle` 模块的使用，任何反序列化都可能执行代码
- 搜索 `eval()` 或 `exec()` 对配置值的处理

**快速定位保护机制**：
- 是否使用 `yaml.safe_load()` 而非 `yaml.load()`
- 是否避免使用 `pickle` 进行反序列化，改用 JSON 或其他安全格式
- 配置文件是否仅从可信的文件系统路径加载
- 是否对配置文件内容进行验证和签名检查
- 是否避免使用 `eval()` 或 `exec()` 解析配置值
- 是否限制了配置文件的上传和修改权限
- Python 版本和库版本是否为最新稳定版

**审计等级**：**L2-L3**
- **L2**：跳读配置加载代码，识别危险的加载器和反序列化函数
- **L3**：逐行验证配置来源和加载方式，确认安全措施

---

## Classify

**确认为漏洞**：
- 使用 `yaml.load()` 加载用户可控的配置文件（未指定 `Loader` 或使用 `FullLoader`）
- 使用 `pickle.load()` 或 `pickle.loads()` 反序列化用户可控的数据
- 使用 `eval()` 或 `exec()` 执行配置文件中的值或内容
- 配置文件路径或内容可被用户篡改
- 可通过 YAML 标签或 Pickle 协议执行任意 Python 代码

**误报**：
- 使用 `yaml.safe_load()` 加载配置文件
- 配置文件来自可信的文件系统路径且权限受限
- 使用 JSON 或其他安全的序列化格式
- 配置文件经过数字签名验证，确保未被篡改
- 避免使用 `eval()` 或 `exec()` 解析配置值

**代码异味**：
- 使用 `pickle` 进行数据序列化和反序列化
- 配置文件路径或名称由用户输入决定
- 使用 `eval()` 解析配置值，即使当前配置文件可信
- 缺乏对配置文件的完整性验证

---

## Low Risk

以下情况可评为低风险：
- **安全加载器**：使用 `yaml.safe_load()` 或 `json.load()` 加载配置
- **可信来源**：配置文件仅从可信的文件系统路径加载且权限受限
- **避免 Pickle**：不使用 `pickle` 进行反序列化，改用 JSON 或 Protocol Buffers
- **签名验证**：配置文件经过数字签名验证，确保未被篡改
- **内网应用**：应用仅在内网部署，配置文件由管理员维护
- **最小权限**：应用进程以最小权限运行，限制文件和系统访问
- **日志监控**：所有配置文件加载操作均记录日志并监控异常模式

**注意**：YAML 和 Pickle 的反序列化漏洞危害极高，可直接导致 RCE，强烈建议使用 `yaml.safe_load()` 和避免使用 `pickle`。
