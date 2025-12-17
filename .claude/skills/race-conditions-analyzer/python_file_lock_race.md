# Python｜文件写入锁竞态

## Details

### 漏洞成因
当多个线程或进程同时写入同一文件（缓存、配置、日志）时，如果没有使用文件锁（`fcntl.flock`、`portalocker`、`msvcrt.locking`）或原子替换策略，就会出现写入交错、文件被截断、配置被覆盖等竞态问题。典型案例包括：多进程 Celery worker 写缓存文件、Web 请求与 CLI 脚本共享临时文件、使用 `NamedTemporaryFile(delete=False)` 但未独占访问。

### 代码示例

**易受攻击示例：**
```python
def update_cache(payload: dict):
    with open("/tmp/cache.json", "w") as f:     # 无锁
        json.dump(payload, f)                    # 多进程竞争导致文件损坏
```

**安全示例：**
```python
import fcntl

def update_cache(payload: dict):
    with open("/tmp/cache.json", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

# 或采用原子替换
with open("/tmp/cache.json.tmp", "w") as tmp:
    json.dump(payload, tmp)
os.replace("/tmp/cache.json.tmp", "/tmp/cache.json")
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `open(`, `write(`, `file_put_contents`, `NamedTemporaryFile`, `tempfile`, `json.dump`, `yaml.dump`。

**定位步骤：**
1. 搜索写文件操作，确认文件路径是否固定或来自配置；
2. 跳读（L2）判断是否使用 `fcntl.flock`、`portalocker.Lock`、`filelock.FileLock`；
3. 确认是否在写前删除原文件、是否依赖随机文件名。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `fcntl.flock`、`portalocker`、`filelock` 等锁；
- 原子替换（写临时文件后使用 `os.replace`）；
- 目录级别隔离（每个进程单独目录）；
- 借助数据库/Redis 记录写入锁。

**定位技巧：**
- 逐行读（L3）确认写入是否在锁保护下，异常分支是否释放锁；
- 如果使用 `O_EXCL` 等标志，确认是否处理失败重试；
- 跨模块追踪（L4）多程序共享同一路径时，确保所有路径都加锁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用文件锁或原子替换 | **L0（快速跳过）** | 基本安全 |
| 部分路径加锁 | **L2（跳读）** | 确认遗漏 |
| 完全无锁写共享文件 | **L3（逐行读）** | 高风险 |
| 多进程多语言共享文件 | **L4（跨模块追踪）** | 全链路检查 |

## Classify

### 研判标准

#### 确认漏洞
1. 多线程/进程写同一文件且无锁；
2. 可复现文件损坏、数据交错或权限绕过；
3. 文件内容影响系统行为（配置、令牌、缓存）。

#### 误报
1. 写入操作具有互斥锁或使用原子替换；
2. 每次写入使用唯一文件名，不会冲突；
3. 文件仅在单线程上下文操作。

#### 代码异味
1. 依赖临时文件后 `rename` 但仍保持同一文件句柄；
2. 只在部分平台加锁，缺乏跨平台方案；
3. 写入失败未处理，可能残留半完成文件。

## Low risk

### 低风险评级场景

#### 1. 文件为非关键调试日志
- 场景：写入错乱只影响调试信息；
- 评估：可标低风险，但需监控磁盘空间。

#### 2. 写入频率极低
- 场景：只有部署脚本或人工操作才会触发；
- 评估：短期影响小，但需注明操作规程。

#### 3. 即将迁移到集中存储
- 场景：计划使用数据库、对象存储或配置中心；
- 评估：可作为低风险记录，跟踪改造。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键日志 | 影响有限 | 低 |
| 极低写入频率 | 攻击面小 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

