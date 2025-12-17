# JavaScript｜文件写入竞态

## Details

### 漏洞成因
Node.js 异步 IO 场景下，若多个 Promise/goroutine（worker）同时对同一文件执行 `fs.writeFile`、`fs.appendFile`、`createWriteStream`，且没有排队或锁，则写入顺序不确定，可能出现日志交错、JSON 被截断、配置覆盖。即使 Node 单线程，若在多实例部署、cluster 模式或使用 `Promise.all` 并发写，同样会发生竞态。

### 代码示例

**易受攻击示例：**
```js
async function writeConfig(config) {
  await fs.promises.writeFile('/tmp/config.json', JSON.stringify(config));
}

Promise.all(users.map(u => writeConfig(u.settings))); // 并发写入
```

**安全示例：**
```js
const { Mutex } = require('async-mutex');
const mutex = new Mutex();

async function writeConfig(config) {
  const release = await mutex.acquire();
  try {
    await fs.promises.writeFile('/tmp/config.json.tmp', JSON.stringify(config));
    await fs.promises.rename('/tmp/config.json.tmp', '/tmp/config.json');
  } finally {
    release();
  }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `fs.writeFile`, `fs.appendFile`, `writeFileSync`, `createWriteStream`, `stream.pipe`。

**定位步骤：**
1. 搜索写文件函数，确认路径是否固定；
2. 跳读（L2）判断是否有锁、队列、互斥；
3. 查看是否使用 `Promise.all`、`map` 并发触发写入。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `async-mutex`, `p-limit`, `bottleneck` 等串行化工具；
- 流式写入 + 背压控制（单写流）；
- 原子替换（写临时文件再 `rename`）；
- 分布式锁或队列。

**定位技巧：**
- 逐行读（L3）确认异常时是否释放锁；
- 检查 `createWriteStream` 是否多次创建导致覆盖；
- 跨模块追踪（L4）当多个服务实例写同一文件时，是否有统一策略。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用互斥/队列或原子替换 | **L0（快速跳过）** | 风险低 |
| 部分路径有锁 | **L2（跳读）** | 确认遗漏 |
| 并发写同一文件无锁 | **L3（逐行读）** | 高风险 |
| 多实例写同一文件无协调 | **L4（跨模块追踪）** | 必须全链路检查 |

## Classify

### 研判标准

#### 确认漏洞
1. 多请求/worker 同时写同一文件；
2. 缺乏互斥锁、队列或原子替换；
3. 文件影响配置、权限、缓存等关键数据。

#### 误报
1. 写入操作串行执行或通过单独 worker 处理；
2. 每次写入使用唯一文件名；
3. 文件仅用于追加日志且日志有后处理。

#### 代码异味
1. 依赖 Node 单线程特性但在 `Promise.all` 中并发写；
2. 使用 `writeFileSync` 阻塞，导致性能问题但仍可能交错；
3. 没有错误处理，写失败静默忽略。

## Low risk

### 低风险评级场景

#### 1. 非关键日志文件
- 场景：写入错乱只影响调试；
- 评估：可降级，但提醒优化。

#### 2. 写入频率极低
- 场景：仅运维脚本或部署时执行；
- 评估：短期影响小，需要记录流程。

#### 3. 改造计划明确
- 场景：将迁移到集中配置服务或数据库；
- 评估：可标低风险，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键日志 | 影响有限 | 低 |
| 低频操作 | 风险小 | 中 |
| 改造计划 | 可暂缓 | 低 |

