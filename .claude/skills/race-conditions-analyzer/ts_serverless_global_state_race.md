# TypeScript｜Serverless 全局状态竞态

## Details

### 漏洞成因
在 Serverless（AWS Lambda、Cloudflare Workers、Vercel Edge、Deno Deploy）环境中，函数实例在冷启动后会复用同一全局作用域。若在全局定义 `Map`、`Array`、缓存对象，并在请求处理中修改它们，就会在同一实例的并发请求之间产生竞态，导致状态覆盖、脏数据或安全策略失效。部分平台默认开启并发执行（例如 Lambda 的 `eventLoopWaitMode`），开发者若未考虑到复用，就会踩坑。

### 代码示例

**易受攻击示例：**
```ts
let cache: Record<string, User> = {};

export const handler = async (event) => {
  const userId = event.queryStringParameters.id;
  if (!cache[userId]) {
    cache[userId] = await fetchUser(userId); // 并发请求共享 cache
  }
  return { statusCode: 200, body: JSON.stringify(cache[userId]) };
};
```

**安全示例：**
```ts
export const handler = withLock(async (event) => {
  const userId = event.queryStringParameters.id;
  return await cacheClient.getOrLoad(userId, () => fetchUser(userId));
});

// 或将状态存储在外部（Redis、DynamoDB）并避免在全局变量中写入
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `let cache =`, `global`, `Map`, `LRU`, `coldStart`, `module exports`, `context`。

**定位步骤：**
1. 搜索函数外部的可变全局变量；
2. 跳读（L2）判断请求处理中是否修改这些变量；
3. 检查是否依赖 `coldStart` 标记或假设每次请求独立实例。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 将状态存储到外部持久化服务（Redis、DynamoDB）；
- 使用分布式锁、租约或乐观锁；
- 每次请求复制全局状态到局部变量；
- 限制函数并发（`reservedConcurrency`）并保证幂等。

**定位技巧：**
- 逐行读（L3）确认更新是否在 `await` 间隙发生；
- 查看是否有 `async-lock` 等互斥库；
- 跨模块追踪（L4）多个函数是否共享同一全局模块。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 状态完全外部化或只读 | **L0（快速跳过）** | 风险低 |
| 部分变量外部化 | **L2（跳读）** | 确认剩余部分 |
| 全局可变状态直接共享 | **L3（逐行读）** | 高风险 |
| 多函数导入同一模块状态 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 全局变量在请求处理中被修改且函数允许并发；
2. 无互斥或外部存储，导致数据覆盖；
3. 数据属敏感配置、权限、缓存。

#### 误报
1. 状态只读或每次请求重新初始化；
2. 函数配置为并发度 1（保留并发，事件循环关闭）；
3. 状态仅用于调试或与业务无关。

#### 代码异味
1. 依赖 `coldStart` 标志重置，但失败时不处理；
2. 使用 `global` 缓存并尝试手动控制并发，但缺少验证；
3. 未考虑多区域/多实例同步。

## Low risk

### 低风险评级场景

#### 1. 缓存仅用于性能
- 场景：缓存失效只影响延迟，不影响功能；
- 评估：可降级，但需记录。

#### 2. 有外部监控/自愈
- 场景：异常数据会被周边服务覆盖；
- 评估：风险较低。

#### 3. 即将迁移到外部缓存或锁方案
- 场景：明确计划引入 Redis、Edge KV 等；
- 评估：可标低风险，跟踪进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键缓存 | 影响有限 | 低 |
| 自愈机制 | 可恢复 | 低 |
| 改造计划明确 | 可暂缓 | 中 |

