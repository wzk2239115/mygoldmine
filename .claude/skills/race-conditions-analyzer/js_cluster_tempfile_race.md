# JavaScript｜Cluster 临时文件竞态

## Details

### 漏洞成因
Node.js 在 `cluster`、`fork` 或 `worker_threads` 模式下，会有多个进程/线程共享同一临时文件、锁文件或配置文件。如果没有使用文件锁、唯一文件名或 IPC 协调，就可能出现写入交错、文件被覆盖、JSON 损坏等竞态问题。常见于：多 worker 写缓存、进程间通过文件传递状态、脚手架命令生成临时文件。

### 代码示例

**易受攻击示例：**
```js
const fs = require('fs');
const cluster = require('cluster');

if (cluster.isMaster) {
  for (let i = 0; i < 4; i++) {
    cluster.fork();
  }
} else {
  fs.writeFileSync('/tmp/shared.json', JSON.stringify({ pid: process.pid }));
}
```

**安全示例：**
```js
const lockfile = require('proper-lockfile');
async function writeShared(data) {
  await lockfile.lock('/tmp/shared.json');
  try {
    await fs.promises.writeFile('/tmp/shared.json', JSON.stringify(data));
  } finally {
    await lockfile.unlock('/tmp/shared.json');
  }
}

// 或使用唯一文件名
const tmpPath = path.join(os.tmpdir(), `shared-${process.pid}.json`);
await fs.promises.writeFile(tmpPath, JSON.stringify(data));
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `cluster`, `fork`, `worker`, `fs.writeFile`, `tmp`, `os.tmpdir`, `lockfile`。

**定位步骤：**
1. 搜索共享文件路径（`/tmp/`, `.lock`, `.json` 等）；
2. 跳读（L2）判断是否生成唯一文件名或使用锁；
3. 检查是否有 IPC（`process.send`, `worker_threads` port）协调写入。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 文件锁库：`proper-lockfile`, `lockfile`, `fs-ext`；
- 唯一文件名（包含 `process.pid`、`cluster.worker.id`）；
- 改用 IPC/Redis/数据库共享状态；
- 在 master 进程集中写文件。

**定位技巧：**
- 逐行读（L3）确认锁是否在 finally 中释放；
- 处理异常时是否保留临时文件导致覆盖；
- 跨模块追踪（L4）多个服务实例是否共用同一路径。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用文件锁或唯一文件名 | **L0（快速跳过）** | 风险低 |
| 部分路径加锁 | **L2（跳读）** | 确认遗漏 |
| 多 worker 无锁写共享文件 | **L3（逐行读）** | 高风险 |
| 多服务共用文件且无协调 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 多 worker 同写共享文件且无锁/唯一名；
2. 可复现文件损坏、配置丢失或权限绕过；
3. 文件影响核心逻辑（配置、令牌、缓存）。

#### 误报
1. 每个 worker 写入独立文件或通过 master 汇总；
2. 使用锁库确保互斥并妥善处理异常；
3. 状态存储在 Redis/数据库而非本地文件。

#### 代码异味
1. 依赖 Node 单线程假设，忽略 cluster 多进程；
2. 使用 `fs.writeFileSync` 无锁；
3. 临时文件未清理，可能造成覆盖。

## Low risk

### 低风险评级场景

#### 1. 文件仅存储非关键日志
- 场景：写入错乱只影响调试输出；
- 评估：可标低风险，但需监控磁盘。

#### 2. 写入频率极低
- 场景：仅在部署或维护脚本中执行；
- 评估：风险较小，但需记录操作流程。

#### 3. 正在迁移到集中存储
- 场景：计划改用 IPC、Redis 或对象存储；
- 评估：可降级，跟踪改造进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键日志 | 影响有限 | 低 |
| 低频操作 | 风险小 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

