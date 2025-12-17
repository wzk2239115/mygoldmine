# JavaScript/Node.js Redis分布式限流同步缺陷

**难度:** ★★★★☆ | **审计时间:** 30-40分钟 | **关键词:** 竞态条件、原子性、Lua脚本、主从延迟

## 快速检查清单
- [ ] 使用Lua脚本保证原子性？
- [ ] GET-INCR-EXPIRE完全分离（竞态条件）？
- [ ] MULTI/EXEC期望隔离性但无Lua脚本？
- [ ] Cluster中Hash Tag正确使用？
- [ ] 从从库读取限流数据（主从延迟）？
- [ ] 连接池配置`maxRetriesPerRequest`和`enableOfflineQueue`？
- [ ] 有降级策略（Redis故障时）？
- [ ] 错误处理中是否catch放行？

## 漏洞详解

### 根本原因
分布式限流的核心问题是操作非原子，违反Redis单线程本质。常见缺陷：
- **竞态条件**：GET检查和INCR递增分离，多请求并发读到相同值后全部通过
- **非原子TTL**：INCR和EXPIRE分开，进程崩溃导致键永不过期（内存泄漏）
- **MULTI无隔离**：MULTI/EXEC保证顺序但不防止其他客户端写入中间状态
- **Pipeline非原子**：批量发送≠原子，仍可被其他请求交错执行
- **Cluster跨槽位**：多键操作无Hash Tag导致CROSSSLOT错误或一致性问题
- **主从延迟**：从库读取限流数据时存在毫秒级同步滞后
- **连接耗尽**：连接池配置不当或无降级策略导致服务不可用
- **错误掩盖**：catch中返回true放行，绕过限流防护

### 常见缺陷代码

**缺陷1：竞态条件 - GET-INCR分离**
```javascript
async function buggyRateLimit(key, limit) {
    const current = await redis.get(key);  // T1: 读取值
    // T2: 其他请求也在这里读取相同值！
    if (parseInt(current || 0) >= limit) return false;
    await redis.incr(key);  // T3: 递增
    if (!current) await redis.expire(key, 60);
    return true;
}
// 问题：假设limit=5，count=4，3个并发请求同时读到4，全部通过！
```

**缺陷2：TTL设置非原子**
```javascript
async function buggyExpire(key, limit) {
    const count = await redis.incr(key);
    // 问题：INCR后若进程崩溃，EXPIRE未执行，键永不过期
    if (count === 1) await redis.expire(key, 60);
    return count <= limit;
}
```

**缺陷3：MULTI/EXEC不隔离**
```javascript
// MULTI/EXEC保证顺序但不防止其他客户端修改
const multi = redis.multi();
multi.get(key);  // 读到值A
multi.incr(key); // 其他客户端可能在此期间修改！
await multi.exec();
```

**缺陷4：Pipeline非原子**
```javascript
// 批量发送≠原子操作，仍可被其他请求交错执行
const pipeline = redis.pipeline();
pipeline.get(key);
pipeline.incr(key);
await pipeline.exec();
```

**缺陷5：Cluster跨槽位**
```javascript
// 两个键在不同槽位，Cluster无法事务处理
const userKey = `rate:user:${userId}`;
const ipKey = `rate:ip:${ip}`;
await cluster.multi().incr(userKey).incr(ipKey).exec(); // CROSSSLOT错误！
// 解决：使用Hash Tag → `rate:{${userId}}:user`, `rate:{${userId}}:ip`
```

**缺陷6：主从延迟**
```javascript
await masterRedis.incr(key);  // 写主库
const count = await slaveRedis.get(key);  // 可能读到旧值（同步延迟）
```

**缺陷7：连接池配置不当**
```javascript
const redis = new Redis({
    // 缺少关键配置导致高并发时连接耗尽或命令堆积
    maxRetriesPerRequest: null,  // 应设置为3
    enableOfflineQueue: true     // 应设置为false（不堆积断线期间的命令）
});
```

### 审计检查清单

**高危缺陷**（满足任一立即标记）：
1. `redis.get()` + `redis.incr()` + `redis.expire()` 三步分离 → **竞态条件**
2. 未用Lua脚本但调用超2次Redis命令 → **非原子操作**
3. `INCR(key)` 后独立执行 `EXPIRE(key)` → **键永不过期**（内存泄漏）
4. Cluster中多键操作无Hash Tag → **CROSSSLOT错误或数据不一致**
5. 从从库读取：`readReplica.get(key)` → **主从延迟+旁路检测绕过**
6. `catch(err) { return true }` → **故障放行**
7. 未设置连接池`maxRetriesPerRequest` → **连接堆积**

**代码搜索关键字**（审计时高效查找）：
- `redis.get` + `redis.incr` 在同一函数（间隔<3行）
- `redis.incr` + `redis.expire` 分开
- `redis.multi()` 跨行出现 `exec()` 但无Lua脚本
- `redis.pipeline()` 出现竞态逻辑
- 正则：`rate:.*\${.*?}` 无`{}`标签
- `slaveRedis|readReplica|slave:` 等从库操作
- `catch.*return true`
- 缺少 `maxRetriesPerRequest: null` 或 `3`

**低风险条件**（审计通过标准）：
✓ 核心限流逻辑使用Lua脚本（或单条原子命令）
✓ INCR和EXPIRE必须在脚本内或一条命令
✓ Cluster键采用Hash Tag：`prefix:{userId}:type`
✓ 仅从主库读写（无`readReplica`/`slave`）
✓ 连接池：`{maxRetriesPerRequest: 3, enableOfflineQueue: false}`
✓ 使用成熟库（`rate-limit-flexible`, `redis-rate-limit`等）
✓ 降级策略完整且有测试
✓ 错误捕获后返回`false`（拒绝）而非放行

---

## 安全实现速览

**方案1：Lua脚本（推荐）**
```javascript
const counterScript = `
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window)
end
return {current > limit and 1 or 0, limit - current}
`;
redis.defineCommand('counterLimit', {numberOfKeys: 1, lua: counterScript});

async function rateLimit(key, limit, window) {
    try {
        const [exceeded, remaining] = await redis.counterLimit(key, limit, window);
        return {allowed: exceeded === 0, remaining};
    } catch (err) {
        return {allowed: true, error: true}; // 降级允许
    }
}
```

**方案2：原子命令（简单场景）**
```javascript
// 用SET NX EX替代GET+INCR+EXPIRE
await redis.set(key, 1, 'EX', window, 'NX'); // 首次设置
if (await redis.incr(key) > limit) return false;
```

**方案3：Cluster（Hash Tag）**
```javascript
// 相关键用{userId}标签保证在同一槽位
const userKey = `rate:{${userId}}:user`;
const ipKey = `rate:{${userId}}:ip`;
// 现在可以用MULTI/EXEC处理这两个键
```

**方案4：降级策略**
```javascript
const localCache = new Map();
async function rateLimitWithFallback(key, limit, window) {
    if (!redisHealthy) {
        // Redis故障时用本地限流（宽松）
        return localRateLimit(key, limit * 2, window);
    }
    try {
        return await redis.counterLimit(key, limit, window);
    } catch {
        return localRateLimit(key, limit * 2, window);
    }
}
```

**最佳实践**：
- ✓ 使用`rate-limit-flexible`库（内置Lua脚本）
- ✓ 配置连接池：`{maxRetriesPerRequest: 3, enableOfflineQueue: false}`
- ✓ 仅从主库读写（避免主从延迟）
- ✓ 监控Redis慢查询和连接数
- ✓ 实现熔断和降级（故障自动切换到本地限流）

---

## 修复优先级与审计建议

**修复顺序**（按风险等级）：
1. **P0-立即修复**：竞态条件（GET+INCR+EXPIRE分离）→ 改为Lua脚本
2. **P1-快速修复**：连接池配置缺陷 → 添加`maxRetriesPerRequest: 3, enableOfflineQueue: false`
3. **P2-短期改善**：主从延迟 → 改用主库读或使用Read Preference策略
4. **P3-中期优化**：Cluster问题 → 引入Hash Tag，添加CROSSSLOT错误处理
5. **P4-长期改进**：降级策略、熔断器、监控告警

**现场审计技巧**：
- **快速定位**：搜索`redis.incr`和`redis.expire`相邻行数（间隔<5行即高危）
- **并发测试**：AB压测5个并发请求验证限流边界，若超限则确认竞态
- **延迟验证**：故意关闭从库同步，观察从库读取是否导致限流失效
- **连接监控**：`redis-cli INFO stats` 查看`connected_clients`峰值，超过配置值说明耗尽
- **内存泄漏**：`MEMORY STATS` 观察关键`rate:*`键TTL，若无TTL则确认永不过期问题
- **Cluster验证**：向多键操作发送命令，捕获CROSSSLOT错误日志
- **降级测试**：停止Redis，观察应用是否完全拒绝（无降级）或仍然可用

**日志分析**：
```javascript
// 审计告诉你的危险信号
console.log('  Redis timeout');      // 连接耗尽或堆积
console.log('  CROSSSLOT error');    // Cluster Hash Tag问题
console.log('  Connection limit');   // 连接池已满
// 找这些日志 → 确认对应缺陷
```

**经验小贴士**：
- Lua脚本≠绝对安全，需检查脚本逻辑本身（如`EVAL`注入）
- `SET key value EX sec NX` 仅适合**首次计数**，不适合递增场景
- `enableOfflineQueue: false` 很关键，否则连接断开期间堆积请求
- 主从延迟通常<10ms，但高并发时可能达到秒级，不可忽视
- Cluster Hash Tag要全局统一，混用不同格式会导致分散不均

