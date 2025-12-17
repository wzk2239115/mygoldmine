# Python｜asyncio 缓存窗口竞态

## Details

### 漏洞成因
在 `asyncio` 场景下，多协程并发刷新同一缓存键时，如果没有互斥锁或原子操作，协程 A 删缓存后等待 IO，协程 B 读取旧缓存并写回，从而覆盖新值。常见于基于 `aioredis`、`asyncio.gather`、`FastAPI` 的缓存刷新逻辑，尤其是“先删缓存，后写库”的流程或缓存穿透补偿逻辑。

### 代码示例

**易受攻击示例：**
```python
cache = aioredis.from_url("redis://")

async def refresh_user(uid: int):
    await cache.delete(key(uid))             # 删除旧缓存
    data = await fetch_from_db(uid)          # IO 间隙
    await cache.set(key(uid), serialize(data))

async def get_user(uid: int):
    value = await cache.get(key(uid))
    if value:
        return deserialize(value)
    data = await refresh_user(uid)           # 多协程并发调用
    return data
```

**安全示例：**
```python
locks = defaultdict(asyncio.Lock)

async def refresh_user(uid: int):
    async with locks[uid]:                   # 协程级互斥
        data = await fetch_from_db(uid)
        await cache.set(key(uid), serialize(data), ex=600)
        return data

async def get_user(uid: int):
    value = await cache.get(key(uid))
    if value:
        return deserialize(value)
    return await refresh_user(uid)
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `async def refresh`, `await cache.delete`, `cache.set`, `asyncio.gather`, `Redis`, `singleflight`。

**定位步骤：**
1. 搜索删除缓存或刷新缓存的协程；
2. 跳读（L2）判断是否存在 `asyncio.Lock`、`aioredis.lock` 等互斥；
3. 检查 `await` 之间的状态变化是否受保护。

#### 保护机制定位（审计等级：L2-L4）
**检查是否存在：**
- per-key `asyncio.Lock`、`aioredis.lock`、`asyncio.Semaphore`；
- 使用 Redis `SETNX`、`GETSET`、Lua 脚本进行 compare-and-set；
- 请求合并（singleflight）策略；
- 缓存刷新失败时的重试、幂等控制。

**定位技巧：**
- 逐行读（L3）刷新流程：删除 → 查询 → 写入，确认是否存在空窗；
- 若多个服务实例刷新同一键，跨模块追踪（L4）分布式锁是否覆盖所有实例；
- 检查是否仅依赖随机延迟或 TTL 作为补偿。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用锁/分布式互斥或原子脚本 | **L0（快速跳过）** | 风险低 |
| 部分路径加锁 | **L2（跳读）** | 需确认遗漏 |
| 完全无锁、删写缓存分离 | **L3（逐行读）** | 高风险 |
| 多实例刷新无统一策略 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 多协程/实例可同时刷新并写回旧值；
2. 缺乏互斥、版本号或原子操作；
3. 数据为核心业务（配置、限流、订单等）。

#### 误报
1. 使用 per-key 锁或 Redis 分布式锁保证串行；
2. 刷新过程采用 `SETNX`+版本字段确保幂等；
3. 缓存仅做只读副本，原始数据仍以数据库为准且有并发控制。

#### 代码异味
1. 依赖随机 sleep、延迟双删；
2. 锁实现仅限本进程，实际部署多实例；
3. 缺乏失败回滚与监控。

## Low risk

### 低风险评级场景

#### 1. 非关键缓存
- 场景：缓存仅用于性能提升，偶发旧值影响小；
- 评估：可降级，但需标记并监控。

#### 2. 自愈或幂等保障
- 场景：存在幂等令牌、重放队列，错误能自动修复；
- 评估：风险降低，可视为低风险。

#### 3. 即将引入统一锁方案
- 场景：团队计划使用 singleflight、Redisson 等；
- 评估：短期可降级，但需跟踪进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 缓存非核心 | 影响可控 | 低 |
| 幂等/自愈存在 | 错误可恢复 | 低 |
| 改造计划明确 | 临时缓解 | 中 |

