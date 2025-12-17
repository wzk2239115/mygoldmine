# Java｜非线程安全集合竞态

## Details

### 漏洞成因
在 Spring、Servlet 等多线程环境中，单例 Bean 或 `static` 字段经常持有 `HashMap`、`ArrayList`、`SimpleDateFormat` 等非线程安全对象。如果多个线程同时写入或遍历这些集合，可能导致元素丢失、链表环路、`ConcurrentModificationException` 或死循环。常见场景包括：请求缓存、会话表、定时任务共享集合、静态工具类维护状态。开发者常误以为 JVM 会序列化访问，或仅在部分路径加锁。

### 代码示例

**易受攻击示例：**
```java
@Service
public class SessionRegistry {
    private static final Map<String, SessionInfo> SESSIONS = new HashMap<>();

    public void addSession(String user, SessionInfo info) {
        SESSIONS.put(user, info); // 多线程写入无锁
    }

    public List<SessionInfo> list() {
        return new ArrayList<>(SESSIONS.values());
    }
}
```

**安全示例（使用并发集合）：**
```java
private static final Map<String, SessionInfo> SESSIONS = new ConcurrentHashMap<>();

public void addSession(String user, SessionInfo info) {
    SESSIONS.put(user, info);
}

public List<SessionInfo> list() {
    return new ArrayList<>(SESSIONS.values());
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `new HashMap`, `new ArrayList`, `static`, `@Service`, `Collections.singletonMap`, `SimpleDateFormat`.

**定位步骤：**
1. 搜索集合初始化位置，判断是否在单例或静态上下文。
2. 跳读（L2）寻找写操作 `put/remove/add` 是否位于多线程环境（Controller、任务、Listener）。
3. 识别是否有遍历与写同时发生的代码。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `Collections.synchronizedMap/List`、`ConcurrentHashMap`、`CopyOnWriteArrayList`。
- 显式 `synchronized` 块、`ReentrantLock`。
- `ThreadLocal` 将状态隔离到线程级。

**定位技巧：**
1. 若集合只在构造器填充而后只读，可记录说明。
2. 对简单 `synchronized` 块，逐行读（L3）确认锁对象是否唯一。
3. 跨模块追踪（L4）需要查看集合是否在不同 Bean/线程间传递。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 集合完全受并发集合/锁保护 | **L0（快速跳过）** | 无风险 |
| 大部分路径同步但存在少量未覆盖 | **L2（跳读）** | 需确认 |
| 无任何同步措施 | **L3（逐行读）** | 高风险 |
| 集合跨多个模块使用 | **L4（跨模块追踪）** | 全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
1. 多线程对集合执行写操作且无同步。
2. 可复现数据错乱、`ConcurrentModificationException`、死循环。
3. 集合包含重要状态（如会话、权限、库存）。

#### 误报
1. 集合仅在单线程上下文使用（如单线程任务）。
2. 所有写操作均在 `synchronized` 方法或并发集合下。
3. 集合只在启动阶段构建，运行时只读。

#### 代码异味
1. 部分路径加锁，另一些直接访问。
2. 依赖应用服务器单线程假设。
3. 缺乏注释说明线程安全策略。

## Low risk

### 低风险评级场景

#### 1. 启动后只读
- 场景：集合在初始化阶段填充，运行期不会修改。
- 评估：可标低风险，但需注释约束。

#### 2. 存储非关键缓存
- 场景：集合只缓存可丢失数据，有自动重建。
- 评估：影响有限，可降级但要监控。

#### 3. 正在迁移并发集合
- 场景：已有改造计划改用 `ConcurrentHashMap`。
- 评估：记录为低风险并跟踪进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 启动后只读 | 无运行期写入 | 中 |
| 非关键缓存 | 出错可接受 | 低 |
| 重构计划明确 | 可暂缓 | 低 |

