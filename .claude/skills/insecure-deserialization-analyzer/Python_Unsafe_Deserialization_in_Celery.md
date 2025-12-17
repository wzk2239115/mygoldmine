# Python Celery 不安全反序列化

Celery 任务队列默认支持多种序列化协议，当使用 `pickle` 时，攻击者可通过构造恶意任务消息触发 RCE，常见于消息队列（Redis/RabbitMQ）、结果后端、任务参数传递等场景。

---

## Details

### 典型代码示例

```python
# 危险配置1：全局启用 pickle 序列化
from celery import Celery
app = Celery('tasks', broker='redis://localhost')
app.conf.task_serializer = 'pickle'  # 危险
app.conf.accept_content = ['pickle', 'json']  # 允许 pickle
app.conf.result_serializer = 'pickle'  # 结果后端也用 pickle

# 危险配置2：旧版配置方式
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_ACCEPT_CONTENT = ['pickle']
CELERY_RESULT_SERIALIZER = 'pickle'

# 危险场景3：混合序列化器
@app.task(serializer='pickle')  # 单个任务指定
def process_data(obj):
    return obj.process()

# 危险场景4：直接反序列化消息体
from kombu.serialization import loads
payload = redis_client.get('celery-task-meta-xxx')
result = loads(payload, content_type='application/x-python-serialize')

# 危险场景5：Canvas/Chain 序列化
from celery import chain
workflow = chain(task1.s(user_input), task2.s())  # user_input 被 pickle 序列化
workflow.apply_async()
```

### 快速定位核心操作 **【审计等级 L1-L3】**

**L1 关键词扫描**：
- 配置文件关键字：`task_serializer`、`accept_content`、`result_serializer`
- 代码关键字：`@app.task(serializer=`、`Celery(`、`apply_async(`
- 旧版配置：`CELERY_TASK_SERIALIZER`、`CELERY_ACCEPT_CONTENT`、`CELERY_RESULT_SERIALIZER`
- 直接操作：`kombu.serialization.loads(`、`register_pickle()`

**L2 跳读配置文件**：
- `celeryconfig.py` / `settings.py` 中的 `task_serializer` 配置
- `broker_url` 和 `result_backend` 类型（Redis/RabbitMQ/Database）
- 检查是否有 `content_type='application/x-python-serialize'` 或 `content_encoding='binary'`
- Django Celery 检查 `CELERY_*` 配置项

**L3 逐行审计数据流**：
- 任务定义装饰器参数：`@app.task(bind=True, serializer='pickle')`
- 任务调用链：`task.apply_async(args=(obj,))` → obj 是否用户可控
- Canvas 复杂工作流：`chain()`、`group()`、`chord()` 传递的参数
- 自定义消息序列化：检查 `kombu.serialization.register()` 注册的自定义序列化器

**框架特定位置（L2-L3）**：
- **消息队列注入点**：直接向 Redis/RabbitMQ 队列写入恶意消息
- **结果后端**：检查 `result_backend` 存储（Redis/Database）是否可被污染
- **Beat 定时任务**：`celerybeat-schedule` 文件是否可写入恶意序列化数据
- **Worker Pool**：prefork/eventlet/gevent 对序列化数据的处理差异

### 快速定位保护机制 **【审计等级 L2-L4】**

**L2 跳读配置安全性**：
```python
# 安全配置：仅允许 JSON/MessagePack
app.conf.task_serializer = 'json'
app.conf.accept_content = ['json', 'msgpack']  # 不含 pickle/yaml
app.conf.result_serializer = 'json'

# 半安全：允许 pickle 但有内容类型限制
app.conf.accept_content = ['application/json']  # 显式白名单
```

**L3 逐行检查任务装饰器**：
```python
# 检查是否所有任务都覆盖为安全序列化器
@app.task(serializer='json', ignore_result=True)  # 安全
def safe_task(data):
    pass

# 危险：部分任务未指定，继承全局配置
@app.task  # 如果全局是 pickle 则危险
def legacy_task(obj):
    pass
```

**L4 跨模块追踪**：
- **中间件层**：检查是否有 `task_prerun`、`task_postrun` 信号处理器验证消息完整性
- **消息签名**：查找 `app.conf.task_serializer_options` 中的签名配置（Celery 不原生支持需自定义）
- **Broker 认证**：Redis/RabbitMQ 访问控制是否限制外部写入
- **Result Backend 隔离**：结果存储是否与其他系统共享（跨应用污染风险）
- **版本兼容性**：Celery < 4.0 默认 `accept_content=['pickle']`，需重点审计

**审计优先级**：
- **L4 跨模块追踪** → 确认 Broker 可被外部访问（公网 Redis、弱密码）
- **L3 逐行读** → `accept_content` 包含 `pickle` 且存在用户可控任务参数
- **L2 跳读** → 全局配置默认 `pickle`，但所有任务入口暂无外部输入
- **L1 关键词扫描** → 快速发现潜在配置风险点
- **L0 快速跳过** → 配置明确为 `json` 且无 `pickle` 相关代码

---

## Classify

### 漏洞（True Positive）判定条件
1. **配置启用 pickle**：`accept_content` 包含 `pickle`/`yaml`/`application/x-python-serialize`
2. **消息队列可达**：Broker（Redis/RabbitMQ）可被攻击者访问（公网暴露、弱密码、SSRF 触达）
3. **无消息签名**：未实现 HMAC 或数字签名验证消息来源
4. **Worker 可触发**：恶意消息能被 Worker 消费并执行反序列化

### 误报（False Positive）判定条件
1. **配置已禁用**：`accept_content` 仅包含 `['json']`、`['msgpack']` 等安全协议
2. **网络完全隔离**：Broker 仅监听 localhost 或 VPC 内网，无跨信任边界通信
3. **消息源可信**：所有任务由内部服务触发，用户无任何途径影响消息内容（包括间接影响）
4. **版本已修复**：Celery >= 4.0 且配置迁移完成（旧配置已清理）

### 代码异味（Code Smell）判定条件
1. **遗留配置**：代码注释表明"计划迁移到 JSON"但未完成
2. **部分加固**：新任务使用 `json`，但历史任务仍指定 `pickle`
3. **隐式依赖**：未显式配置 `accept_content`，依赖框架默认值（版本敏感）
4. **过度信任内网**：认为 Redis 在内网就安全，忽略 SSRF、容器逃逸等风险

### 研判技巧
- **配置审计优先**：先查全局配置，再检查任务级覆盖
- **Broker 可达性测试**：通过 Shodan/Fofa 确认端口暴露情况
- **消息格式分析**：抓取实际队列消息，确认 `content-type` 头
- **版本对比**：Celery 3.x 默认不安全，4.x 改为 `json` 但可降级

---

## Low Risk

### 低风险场景判定

**完全内网隔离：**
- Broker 和 Worker 在物理隔离网络（无互联网网关、VLAN 隔离）
- 访问需双因素认证 + IP 白名单
- 所有消息由内部服务生成，无用户输入传递到任务参数

**强认证+加密传输：**
- Redis/RabbitMQ 配置 TLS + 强密码（非默认账户）
- 使用 Celery 消息签名扩展（自定义中间件）
- Broker 启用 ACL 限制队列写入权限

**只读/展示任务：**
- 任务仅执行数据查询，不触发系统命令或文件操作
- 注意：仍需警惕 `__reduce__` 在对象构造时触发副作用

**历史包袱已计划清理：**
- 存在明确的迁移 Roadmap（Jira/TODO）
- 监控告警覆盖 pickle 使用（审计日志）
- 新代码强制 Lint 规则禁止 `serializer='pickle'`

**沙箱环境限制：**
- Worker 运行在无特权容器（seccomp、AppArmor）
- 无敏感文件访问权限（/etc、/root）
- 网络出口严格限制（仅允许访问内部 API）

### 降级评估
- 即使评为低风险，也应在安全债务清单中跟踪
- 优先级：低于直接 RCE，高于信息泄露
- 建议在下一个大版本重构时彻底迁移到 JSON/MessagePack