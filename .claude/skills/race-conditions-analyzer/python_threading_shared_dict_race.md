# Python｜多线程共享字典竞态

## Details

### 漏洞成因
Python 的 `dict`、`list` 在 CPython 下虽然由 GIL 保护字节码级互斥，但一旦线程在 `C` 扩展中释放 GIL（如网络 IO、`time.sleep`、`requests`），多线程同时写入全局字典仍会造成数据竞争、键丢失或 `RuntimeError: dictionary changed size during iteration`。常见于缓存、任务状态表、统计计数器等共享结构，开发者误以为 GIL 足够安全。

### 代码示例

**易受攻击示例：**
```python
cache = {}

def worker(user_id):
    data = fetch_remote(user_id)   # requests 会暂时释放 GIL
    cache[user_id] = data          # 多线程无锁写入

threads = [Thread(target=worker, args=(uid,)) for uid in users]
for t in threads: t.start()
```

**安全示例：**
```python
cache = {}
lock = threading.RLock()

def worker(user_id):
    data = fetch_remote(user_id)
    with lock:
        cache[user_id] = data

# 或使用线程安全容器
from collections import defaultdict
cache = defaultdict(lambda: threading.Lock())
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `threading.Thread`, `ThreadPoolExecutor`, `global`, `shared`, `dict`, `list`, `+=`, `append`。

**定位步骤：**
1. 搜索共享字典或列表定义，确认是否在模块顶层或单例对象中；
2. 跳读（L2）线程函数，看是否包含写操作；
3. 判断是否有 `Lock`、`RLock`、`Condition`、`Queue` 等同步措施。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `threading.Lock`、`RLock`、`Condition`、`Semaphore`；
- `queue.Queue`、`collections.deque(maxlen=...)` 等线程安全容器；
- 在任务内复制数据后再合并（Copy-on-write）；
- 使用 `concurrent.futures` 并只在主线程收集结果。

**定位技巧：**
- 逐行读（L3）确认写操作是否在 `with lock` 块中；
- 关注 `dict.setdefault`、`dict.update`、`list.append`、`+=` 这类复合操作；
- 跨模块追踪（L4）当缓存跨多个文件共享时，确保所有入口都持锁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用锁或线程安全容器 | **L0（快速跳过）** | 直接通过 |
| 大部分路径加锁但存在漏网 | **L2（跳读）** | 快速确认遗漏 |
| 完全无锁写共享字典 | **L3（逐行读）** | 高风险 |
| 缓存跨多个模块共享 | **L4（跨模块追踪）** | 需全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 多线程写共享字典/列表，缺乏锁或安全容器；
2. 可复现键丢失、覆盖、异常（压测或日志）；
3. 缓存数据对业务关键（权限、会话、配置）。

#### 误报
1. 字典仅在单线程使用或线程内局部变量；
2. 使用 `Lock`/`Queue` 正确保护；
3. 使用 `multiprocessing.Manager().dict()` 等多进程安全容器。

#### 代码异味
1. 依赖“当前实现刚好安全”的注释或假设；
2. 写操作封装在函数内但未显式加锁；
3. 使用 `defaultdict` 自动创建对象却缺少锁。

## Low risk

### 低风险评级场景

#### 1. 缓存仅用于统计
- 场景：字典存储非关键指标，偶发错误影响较小；
- 评估：可标低风险，但需监控。

#### 2. 单线程部署假设已确认
- 场景：服务实际部署单线程 worker；
- 评估：短期可降级，但必须记录假设。

#### 3. 即将迁移至并发安全方案
- 场景：计划替换为 `ConcurrentDict` 或外部缓存；
- 评估：可列低风险，需跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键统计 | 影响有限 | 低 |
| 单线程运行 | 攻击面小 | 中 |
| 重构计划明确 | 可暂缓 | 低 |

