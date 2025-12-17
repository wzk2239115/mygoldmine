# JavaScript｜Promise 缓存刷新竞态

## Details

### 漏洞成因
在 Node.js/前端 BFF 中，常看到“读取缓存 → 无则发起异步请求 → 写回缓存”的逻辑。如果多个请求几乎同时触发刷新，Promise 未去重，旧值可能在稍后写回覆盖新值，或重复请求后端导致放大流量。常见于 `axios`、`fetch` 请求、`Promise.all` 并发刷新、使用 `if (!cache[key])` 判断。

### 代码示例

**易受攻击示例：**
```js
const cache = new Map();

async function getUser(id) {
  if (cache.has(id)) {
    return cache.get(id);
  }
  const data = await fetchUser(id);   // 并发请求同时触发
  cache.set(id, data);                // 最后一个写入者可能是旧值
  return data;
}
```

**安全示例：**
```js
const inflight = new Map();
const cache = new Map();

async function getUser(id) {
  if (cache.has(id)) return cache.get(id);
  if (inflight.has(id)) return inflight.get(id);

  const promise = fetchUser(id)
    .then(data => {
      cache.set(id, data);
      inflight.delete(id);
      return data;
    })
    .catch(err => {
      inflight.delete(id);
      throw err;
    });
  inflight.set(id, promise);
  return promise;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `if (!cache`, `Promise.all`, `refreshCache`, `fetch`, `axios`, `getOrSet`。

**定位步骤：**
1. 搜索缓存读取/写入逻辑；
2. 跳读（L2）判断是否存在 `inflight` 去重、互斥锁；
3. 检查 `finally` 中是否清除状态。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- In-flight map、防抖/节流、SingleFlight；
- 分布式锁或 Redis `SETNX`；
- `cacheEntry.promise` 结构；
- 原子写入（`SET` 时校验版本）。

**定位技巧：**
- 逐行读（L3）确认写缓存的顺序是否保证最新值；
- 检查错误路径是否清理 in-flight 状态；
- 跨模块追踪（L4）多实例部署时是否有共享锁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 inflight 去重或锁 | **L0（快速跳过）** | 风险低 |
| 部分路径处理 inflight | **L2（跳读）** | 确认覆盖 |
| 无任何互斥/去重 | **L3（逐行读）** | 高风险 |
| 多实例共享缓存无锁 | **L4（跨模块追踪）** | 全链路审计 |

## Classify

### 研判标准

#### 确认漏洞
1. 多请求刷新同一键会重复请求后端或写回旧值；
2. 缺乏互斥、去重或版本控制；
3. 影响核心数据（权限、定价、配置）。

#### 误报
1. 使用 inflight map/SingleFlight 确保同一键只请求一次；
2. 缓存刷新放在单线程 worker 中统一处理；
3. 缓存只做只读副本，更新通过事件驱动且具备版本校验。

#### 代码异味
1. 依赖客户端重试或随机延迟；
2. 清理 inflight 状态不完整，异常时残留 Promise；
3. 使用全局 `await lock()` 但锁粒度过大导致性能问题。

## Low risk

### 低风险评级场景

#### 1. 缓存非关键
- 场景：数据仅影响性能（如推荐列表），错误不会破坏功能；
- 评估：可降级，但需记录。

#### 2. 有自愈机制
- 场景：后台定时任务重新拉取，或下游具备幂等；
- 评估：风险降低。

#### 3. 改造计划明确
- 场景：准备引入 inflight map、分布式锁；
- 评估：可标低风险，跟踪执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键缓存 | 影响可控 | 低 |
| 自愈/幂等 | 可恢复 | 低 |
| 改造计划明确 | 临时缓解 | 中 |

