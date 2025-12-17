# Python pickle 反序列化代码注入

**漏洞成因**：使用 `pickle.loads()` 或 `cPickle.loads()` 反序列化用户输入的数据，pickle 模块会在反序列化过程中调用对象的 `__reduce__()`、`__setstate__()` 等魔法方法，攻击者可构造恶意序列化数据在反序列化时执行任意代码。

---

## Details

**代码示例**：
```python
# 危险：直接反序列化用户输入
import pickle
user_data = request.data  # 来自网络请求的二进制数据
obj = pickle.loads(user_data)

# 危险：cPickle 反序列化（Python 2）
import cPickle
cached = request.cookies.get('cache')
obj = cPickle.loads(base64.b64decode(cached))

# 危险：Pickle 数据可能来自会话、文件、缓存
with open(user_file, 'rb') as f:
    data = pickle.load(f)

# 虚假安全：使用 Unpickler 仍然不安全
import pickle
u = pickle.Unpickler(user_stream)
obj = u.load()
```

**快速定位核心操作**（L1-L2）：
- 关键词：`pickle.loads(`、`pickle.load(`、`cPickle.loads(`、`cPickle.load(`、`Unpickler`
- 查看反序列化的数据来源：网络请求、文件、数据库、缓存
- 检查是否涉及用户可控的数据流：`request.data`、`request.files`、cookies、session
- 追踪使用了 `pickle.load()` 还是 `pickle.loads()`

**快速定位保护机制**（L2-L3）：
- 是否使用 `pickle.loads()` 时指定了 `Unpickler` 的 `find_class` 方法（Python 3）
- 是否使用了替代方案：`json.loads()`、`yaml.safe_load()`、`pickle.restrict_loads()`（仅 Python 3.13+）
- 是否存在数据签名验证：HMAC、数字签名等
- 是否对反序列化的对象类型进行白名单限制

**审计等级**：**L2-L4**
- **L2**：跳读 pickle 相关调用，确认数据来源
- **L3**：逐行读取 loads/load 及其参数来源、白名单校验
- **L4**：跨模块追踪用户数据到 pickle 的完整流程

---

## Classify

**确认为漏洞**：
- 用户可控的数据被直接反序列化（pickle.loads/load）
- 无签名校验、白名单限制等防护
- Python 版本较低（3.8 及以下），pickle 模块无有效限制

**误报**：
- pickle 数据来自受信任源（硬编码序列化对象、内部生成）
- 使用了 `pickle.restrict_loads()` 或自定义 find_class 白名单
- 使用了替代方案（json、yaml.safe_load）

**代码异味**：
- 使用 pickle 但有部分防护（需评估防护完整性）
- 权限控制依赖前端验证
- 业务可用更安全的序列化方案替代

---

## Low Risk

以下情况可评为低风险：
- **数据签名校验**：pickle 数据使用 HMAC、数字签名、加密等方式校验
- **权限隔离**：反序列化在最小权限用户下执行
- **内网保护**：仅限管理员、内网、可信客户端
- **白名单限制**：实现了 find_class 白名单，仅允许特定类反序列化
- **审计监控**：反序列化操作被完整记录、监控
