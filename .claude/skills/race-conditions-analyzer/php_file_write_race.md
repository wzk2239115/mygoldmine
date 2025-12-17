# PHP｜文件写入竞态

## Details

### 漏洞成因
在 PHP Web/CLI 场景中，多个请求或任务可能同时调用 `file_put_contents`、`fopen`/`fwrite` 操作同一文件（缓存、配置、日志、上传控制文件）。如果未使用 `LOCK_EX`、`flock` 或临时文件原子替换，就会出现内容交错、文件被截断、配置被覆盖等競態问题，特别是在 NFS/共享存储环境下更难察觉。

### 代码示例

**易受攻击示例：**
```php
function updateCache(array $data): void {
    file_put_contents('/tmp/cache.json', json_encode($data)); // 无锁
}
```

**安全示例：**
```php
function updateCache(array $data): void {
    $fp = fopen('/tmp/cache.json', 'c');
    if (!$fp) {
        throw new RuntimeException('open failed');
    }
    if (!flock($fp, LOCK_EX)) {
        throw new RuntimeException('lock failed');
    }
    ftruncate($fp, 0);
    fwrite($fp, json_encode($data));
    fflush($fp);
    flock($fp, LOCK_UN);
    fclose($fp);
}

// 或写临时文件后 rename
$temp = tempnam(sys_get_temp_dir(), 'cache');
file_put_contents($temp, json_encode($data));
rename($temp, '/tmp/cache.json');
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `file_put_contents`, `fopen`, `fwrite`, `LOCK_EX`, `flock`, `tempnam`, `rename`。

**定位步骤：**
1. 搜索写文件的位置，确认路径是否固定或来自共享目录；
2. 跳读（L2）判断是否传入 `LOCK_EX` 或调用 `flock`；
3. 确认是否存在多处写同一文件（Web + CLI、worker + cron）。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `LOCK_EX` / `flock` / `Semaphore`；
- 原子替换（临时文件 + `rename`）；
- 不同用户/进程写入不同目录；
- 使用缓存/数据库代替本地文件。

**定位技巧：**
- 逐行读（L3）确保无锁路径不会在异常分支中被跳过；
- 如果使用 `rename`，确认写入后才替换且不会泄露临时文件；
- 跨模块追踪（L4）当多个脚本/worker 共用文件时，确认全部采取同步措施。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用锁或临时文件原子替换 | **L0（快速跳过）** | 可直接通过 |
| 部分路径加锁 | **L2（跳读）** | 确认遗漏 |
| 完全无锁写共享文件 | **L3（逐行读）** | 高风险 |
| 多服务共享文件无统一策略 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 多进程/请求写同一文件且无锁；
2. 可复现文件损坏、配置覆盖或权限绕过；
3. 文件内容影响业务逻辑或安全策略。

#### 误报
1. 每次写入使用唯一文件名，不存在冲突；
2. 所有路径都加锁或使用原子 `rename`；
3. 文件仅由单线程/单进程写入。

#### 代码异味
1. 依赖 `LOCK_EX` 但忽略返回值；
2. 临时文件未清理或未检查 `rename` 成功；
3. 共享存储（NFS）下锁机制不可靠却无替代方案。

## Low risk

### 低风险评级场景

#### 1. 文件仅用于非关键日志
- 场景：写入错乱不会影响业务行为；
- 评估：可标低风险，但需监控磁盘容量。

#### 2. 写入频率低且有人工流程
- 场景：配置文件只在部署脚本运行时更新；
- 评估：短期风险小，但应记录操作说明。

#### 3. 正在迁移至集中存储
- 场景：计划使用 Redis、数据库或对象存储；
- 评估：可降级，需跟踪改造任务。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 非关键日志 | 影响有限 | 低 |
| 低频人工操作 | 可控风险 | 中 |
| 改造计划明确 | 可暂缓 | 低 |

