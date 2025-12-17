# Python yaml.load() 不安全反序列化

**漏洞成因**：使用 `yaml.load()` 不指定 Loader 参数或使用 `FullLoader`/`UnsafeLoader` 来解析用户输入的 YAML 数据，YAML 解析器会执行 YAML 中的 Python 对象标签，攻击者可通过构造恶意 YAML 在解析时执行任意 Python 代码。

---

## Details

**代码示例**：
```python
# 危险：yaml.load() 无 Loader 参数或使用默认 Loader（旧版本）
import yaml
user_yaml = request.form.get('config')
data = yaml.load(user_yaml)

# 危险：使用 FullLoader（仍可执行代码）
config = yaml.load(user_yaml, Loader=yaml.FullLoader)

# 危险：使用 UnsafeLoader
data = yaml.load(user_yaml, Loader=yaml.UnsafeLoader)

# 安全：使用 SafeLoader
safe_data = yaml.load(user_yaml, Loader=yaml.SafeLoader)
# 或更简洁的方式
safe_data = yaml.safe_load(user_yaml)
```

**快速定位核心操作**（L1-L2）：
- 关键词：`yaml.load(`、`yaml.full_load(`、`yaml.unsafe_load(`、`Loader=` 参数
- 查看 YAML 数据来源：用户输入、配置文件、网络请求
- 检查是否指定了 Loader：无 Loader 参数是旧版本的默认危险行为
- 追踪数据流：`request.args`、`request.form`、`request.files`、上传文件

**快速定位保护机制**（L1-L3）：
- 是否使用 `yaml.safe_load()` 或 `yaml.load(..., Loader=yaml.SafeLoader)`
- 是否使用了 `FullLoader`（部分风险）或 `UnsafeLoader`（完全危险）
- 是否存在 YAML 结构白名单：仅允许特定的键、值类型
- 是否对用户数据进行了前置检查或转义

**审计等级**：**L1-L3**
- **L1**：关键词扫描，快速定位 yaml.load 调用
- **L2**：跳读确认 Loader 参数是否安全
- **L3**：逐行读取 YAML 处理逻辑、数据来源、防护机制

---

## Classify

**确认为漏洞**：
- 使用 `yaml.load()` 不指定 Loader 参数（旧版本默认行为）
- 使用 `yaml.load(..., Loader=yaml.FullLoader)` 或 `UnsafeLoader`
- 解析的 YAML 来自用户可控输入

**误报**：
- 使用 `yaml.safe_load()` 或 `yaml.load(..., Loader=yaml.SafeLoader)`
- YAML 数据来自受信任源（硬编码配置、服务器本地文件）
- 用户输入被严格限制在安全的数据结构

**代码异味**：
- 使用 yaml.load 但有部分防护（需评估防护完整性）
- 权限控制依赖前端验证
- 业务可用 json 或 yaml.safe_load 替代

---

## Low Risk

以下情况可评为低风险：
- **正确使用 SafeLoader**：明确指定 `yaml.safe_load()` 或 `Loader=yaml.SafeLoader`
- **权限隔离**：YAML 解析在最小权限用户下执行
- **内网保护**：仅限管理员、内网、可信用户
- **数据白名单**：允许的 YAML 结构被严格限制
- **审计监控**：YAML 解析操作被完整记录、监控
