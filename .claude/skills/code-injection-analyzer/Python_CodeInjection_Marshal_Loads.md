# Python marshal.loads() 反序列化代码注入

**漏洞成因**：使用 `marshal.loads()` 反序列化用户输入的数据，marshal 模块用于序列化 Python 对象（特别是代码对象），攻击者可构造恶意的 marshal 格式数据，在反序列化时执行任意代码或加载恶意代码对象。

---

## Details

**代码示例**：
```python
# 危险：直接反序列化用户输入
import marshal
user_data = request.data  # 来自网络请求的二进制数据
obj = marshal.loads(user_data)

# 危险：从文件读取 marshal 数据
with open(user_file, 'rb') as f:
    data = marshal.load(f)

# 危险：反序列化后立即执行
marshaled = request.form.get('code_obj')
code_obj = marshal.loads(base64.b64decode(marshaled))
exec(code_obj)

# 虚假安全：检查后执行（仍然不安全）
data = marshal.loads(user_data)
if isinstance(data, types.CodeType):
    exec(data)
```

**快速定位核心操作**（L1-L3）：
- 关键词：`marshal.loads(`、`marshal.load(`、`marshal.dumps`、`CodeType`
- 查看数据来源：网络请求、文件、数据库、用户上传
- 检查反序列化后是否立即执行：`exec()`、`eval()`、函数调用
- 追踪数据流：`request.data`、`request.files`、`request.form`

**快速定位保护机制**（L2-L3）：
- 是否存在数据签名验证：HMAC、数字签名等
- 是否进行了 marshal 数据的结构检查：版本号、对象类型白名单
- 是否限制了反序列化对象的类型：仅允许特定类型（如数字、字符串）
- 是否避免了对代码对象的执行：检查 types.CodeType

**审计等级**：**L2-L4**
- **L2**：跳读 marshal 相关调用，确认数据来源
- **L3**：逐行读取反序列化及其参数、防护机制
- **L4**：跨模块追踪用户数据到 marshal 的完整流程，包括执行调用

---

## Classify

**确认为漏洞**：
- 用户可控的数据被直接反序列化（marshal.loads/load）
- 反序列化后的对象被执行（exec、eval、函数调用）
- 无签名校验、类型检查等防护

**误报**：
- marshal 数据来自受信任源（硬编码、服务器内部生成）
- 使用了签名或加密验证，确保数据完整性
- 反序列化后的对象仅用于数据访问，不执行

**代码异味**：
- 使用 marshal 但有部分防护（需评估防护完整性）
- 权限控制依赖前端验证
- 业务可用 pickle、json 等更安全方案替代

---

## Low Risk

以下情况可评为低风险：
- **数据签名校验**：marshal 数据使用 HMAC、数字签名等方式校验
- **权限隔离**：反序列化在最小权限用户下执行
- **内网保护**：仅限管理员、开发者、内网访问
- **类型限制**：反序列化后仅允许特定数据类型，禁止代码对象执行
- **审计监控**：反序列化操作被完整记录、监控
