# Python Pickle RCE

## Details

### 典型代码示例

```python
# 危险：直接反序列化外部数据
import pickle
data = request.get_data()
obj = pickle.loads(data)  # RCE 入口

# 危险：从不可信文件加载
with open(user_file, 'rb') as f:
    obj = pickle.load(f)

# 危险：任务队列
from celery import Celery
app = Celery(serializer='pickle')  # 默认配置风险

# 危险：Redis/Memcached 缓存
cache_data = redis.get(key)
obj = pickle.loads(cache_data)

# 危险：自定义 __reduce__
class Exploit:
    def __reduce__(self):
        return (os.system, ('whoami',))
```

### 快速定位核心操作 **【审计等级 L1-L2】**

**关键函数（L1-关键词扫描）：**
- `pickle.loads()` / `pickle.load()`
- `pickle.Unpickler().load()`
- `marshal.loads()` / `marshal.load()`
- `shelve.open()` / `shelve.DbfilenameShelf()`
- `dill.loads()` / `cloudpickle.loads()`
- `pandas.read_pickle()`
- `torch.load()` (PyTorch 模型加载)
- `joblib.load()` (sklearn 持久化)
- `yaml.load()` (不安全模式)

**数据流追踪（L2-跳读）：**
1. 搜索关键词后，向上追溯数据来源（函数参数、HTTP 请求、文件路径、队列消息）
2. 检查数据是否跨越信任边界（外部输入、用户上传、网络接收）
3. 关注配置项：`serializer='pickle'`、`protocol=`、`fix_imports=`

**框架特定位置（L2-跳读）：**
- **Celery**：检查 `CELERY_TASK_SERIALIZER`、`CELERY_ACCEPT_CONTENT` 配置
- **Django**：搜索 `SESSION_SERIALIZER`、缓存后端配置
- **Flask**：查看 `session.serializer`、Redis 扩展
- **RPC 框架**：检查 `RPyC`、`Pyro4` 序列化配置

### 快速定位保护机制 **【审计等级 L2-L3】**

**白名单检查（L2-跳读）：**
```python
# 查找是否存在类白名单
class SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "allowed_module" and name in ["SafeClass"]:
            return getattr(sys.modules[module], name)
        raise pickle.UnpicklingError("Forbidden")
```

**签名验证（L2-跳读）：**
```python
# 搜索 hmac/signature 相关代码
import hmac
# 是否在反序列化前验证完整性
if hmac.compare_digest(expected, actual):
    pickle.loads(data)
```

**网络隔离（L3-逐行读）：**
- 检查是否仅在内网服务间传输
- 是否存在认证/授权机制
- 是否限制只能处理本地生成的序列化数据

**替代方案（L2-跳读）：**
- 搜索是否使用 `json.loads()`、`msgpack.unpackb()` 等安全替代
- 检查是否有迁移计划（代码注释、TODO）

**审计优先级：**
- L4：跨模块追踪 → 数据源头完全不可控（Web 直接输入、公开 API）
- L3：逐行读 → 存在保护但实现可疑（自定义白名单逻辑复杂）
- L2：跳读 → 中间件/框架默认配置（Celery、Django Session）
- L1：关键词扫描 → 快速发现潜在风险点

## Classify

### 漏洞（True Positive）判定条件
1. **数据来源不可信**：外部用户输入、HTTP 请求体、用户上传文件、公开 API 参数
2. **无有效保护**：未实现类白名单、无签名验证、无网络隔离
3. **可达性确认**：代码路径可触发（非测试代码、非废弃分支）
4. **影响范围**：能够执行任意代码或系统命令

### 误报（False Positive）判定条件
1. **数据完全可信**：仅反序列化程序自身生成的数据（同进程内生成并立即使用）
2. **强完整性保护**：使用密钥签名（HMAC-SHA256）且密钥管理安全
3. **网络隔离**：仅在完全可信的内部服务间传输（非用户可达）
4. **代码不可达**：测试代码、已废弃功能、条件永远不满足的分支

### 代码异味（Code Smell）判定条件
1. **使用 pickle 但数据受限**：白名单实现合理但未来可能扩展
2. **历史遗留**：代码注释表明计划迁移到 JSON/MessagePack
3. **过度信任**：依赖"内部使用"假设但未强制技术限制
4. **配置风险**：框架默认启用 pickle 但当前场景未暴露

### 研判技巧
- **向上追溯 3 层**：函数参数 ← HTTP 路由 ← 中间件 ← 用户输入
- **横向关联**：同一数据源的其他反序列化点（批量审计）
- **时序分析**：序列化和反序列化是否在同一生命周期（会话劫持风险）
- **权限边界**：低权限用户能否构造恶意序列化数据

## Low Risk

### 低风险场景判定

**完全内部生成消费：**
- 序列化数据由程序自身生成，立即在同一进程/可信环境中反序列化
- 典型例子：内存缓存、临时文件（权限 600）、进程间通信（Unix Socket）

**强签名保护：**
- 使用 HMAC-SHA256/SHA512 签名，密钥通过安全方式管理（环境变量、密钥服务）
- 签名验证在反序列化前，使用 `hmac.compare_digest()` 防时序攻击
- 注意：签名仅保证完整性，不防止重放攻击（需结合时间戳/nonce）

**网络物理隔离：**
- 仅在完全隔离的内网传输（无互联网出口、VLAN 隔离）
- 服务间通信需双向 TLS 认证（mTLS）
- 用户无任何途径接触序列化数据（包括间接操控）

**严格类白名单：**
- 实现 `find_class()` 白名单且仅允许纯数据类（无 `__reduce__`、`__setstate__` 等魔术方法）
- 白名单类代码可控、定期审计、不引入危险依赖
- 配合沙箱环境（容器、seccomp）

**框架安全配置：**
- Celery 使用 `serializer='json'` 或 `msgpack`（明确禁用 pickle）
- Django `SESSION_SERIALIZER` 设置为 `JSONSerializer`
- 定期审计配置文件防止回退

**降级评估：**
- 即使判定为低风险，也应标注为"技术债"并推动迁移
- 优先级低于直接可利用漏洞，但高于一般代码优化
- 建议在代码注释中说明风险已知且已评估
