# TypeScript｜共享 Map 互斥缺失

## Details

### 漏洞成因
NestJS、Express 等后端服务往往将全局状态存放在 `Map`、`Set` 或 LRU 缓存中。如果服务是单例（`@Injectable({ scope: Scope.DEFAULT })`），多个请求会并发读写同一实例。当缺乏互斥锁或原子操作时，数据可能被覆盖、状态错乱，尤其是在 `Promise.all`、多实例部署、`cluster` 环境下。此外，TypeScript 编译后仍运行于 Node.js，需考虑多进程部署导致的共享文件或外部缓存竞态。

### 代码示例

**易受攻击示例：**
```ts
@Injectable()
export class SessionService {
  private sessions = new Map<string, Session>();

  upsertSession(key: string, value: Session) {
    this.sessions.set(key, value); // 并发请求无锁
  }

  getSession(key: string) {
    return this.sessions.get(key);
  }
}
```

**安全示例：**
```ts
import { Mutex } from 'async-mutex';

@Injectable()
export class SessionService {
  private sessions = new Map<string, Session>();
  private mutex = new Mutex();

  async upsertSession(key: string, value: Session) {
    const release = await this.mutex.acquire();
    try {
      this.sessions.set(key, value);
    } finally {
      release();
    }
  }
}

// 或使用外部缓存（Redis）或 per-request scope
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `new Map(`, `Map<string`, `@Injectable`, `global`, `cache`, `LRU`, `set`, `delete`。

**定位步骤：**
1. 搜索全局/单例服务中的 Map 声明；
2. 跳读（L2）查看写操作是否受到互斥控制；
3. 判断是否在 `Promise.all` 或事件处理器中同时调用。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 互斥锁库（`async-mutex`, `async-lock`, `p-limit`）；
- 将 Map 作用域限制为请求（`Scope.REQUEST`）或暂存到 Redis；
- 使用 `Map<string, Promise<T>>` 进行 inflight 去重；
- 使用 `cluster`/worker 时，状态集中在主进程或共享存储。

**定位技巧：**
- 逐行读（L3）确认写操作前是否获取锁；
- 注意 `delete`、`clear` 等操作，也需要互斥；
- 跨模块追踪（L4）当服务被其他模块注入时，确保每个入口都遵循锁策略。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| Map 访问封装在锁/外部缓存中 | **L0（快速跳过）** | 风险低 |
| 部分操作加锁 | **L2（跳读）** | 需确认遗漏 |
| 完全无锁写共享 Map | **L3（逐行读）** | 高风险 |
| 多实例共享状态无统一策略 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 多请求并发写 shared Map，缺乏互斥或隔离；
2. 可复现数据覆盖、状态错乱或内存泄漏；
3. Map 保存关键状态（session、令牌、权限）。

#### 误报
1. Map 仅在单请求作用域使用，或是只读结构；
2. 所有写操作都在互斥锁中，或使用 Redis 等集中存储；
3. 状态通过消息队列/事件在主进程集中处理。

#### 代码异味
1. 依赖“Node 单线程”假设，但部署时启用了 cluster/PM2；
2. 锁粒度过大导致性能问题，开发者可能绕过锁；
3. Map 作为导出变量提供给多个模块，缺少封装。

## Low risk

### 低风险评级场景

#### 1. 缓存非关键
- 场景：Map 用于性能缓存，错误影响小；
- 评估：可降级，但需说明限制。

#### 2. 单实例部署且确认不会扩容
- 场景：服务明确只运行单进程；
- 评估：短期风险小，但需文档说明。

#### 3. 已计划迁移到 Redis/锁机制
- 场景：团队准备引入外部缓存或锁；
- 评估：可标低风险，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键缓存 | 影响有限 | 低 |
| 单实例部署 | 无并发 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

