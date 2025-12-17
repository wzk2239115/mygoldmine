# Java｜缓存失效竞态

## Details

### 漏洞成因
在“数据库写-缓存删/写”流程中，如果没有使用分布式锁、版本号或原子脚本，当多个请求几乎同时到来时，就可能出现经典的“缓存穿透”竞态：请求 A 删除缓存后尚未写入新值，请求 B 读取到旧数据并重新写回，导致脏数据覆盖。另一个常见问题是采用“延迟双删”或定时任务刷新缓存，但没有确保事务、消息队列顺序一致，缓存与数据库出现短暂不一致甚至长期错误。

### 代码示例

**易受攻击示例：**
```java
@Service
public class UserService {
    @Autowired private RedisTemplate<String, User> redisTemplate;
    @Autowired private UserRepository userRepository;

    public void updateProfile(Long userId, UserProfile profile) {
        userRepository.updateProfile(userId, profile);  // 更新数据库
        redisTemplate.delete(cacheKey(userId));         // 删除缓存
        // 此处无锁，其他请求可能读到旧值并重新写入缓存
    }

    public User findById(Long userId) {
        User cached = redisTemplate.opsForValue().get(cacheKey(userId));
        if (cached != null) {
            return cached;
        }
        User user = userRepository.findById(userId);
        redisTemplate.opsForValue().set(cacheKey(userId), user);
        return user;
    }
}
```

**改进示例：**
```java
public void updateProfile(Long userId, UserProfile profile) {
    userRepository.updateProfile(userId, profile);
    redisTemplate.execute((RedisCallback<Object>) conn ->
        conn.set(cacheKey(userId).getBytes(), serialize(profile),
                 Expiration.seconds(3600),
                 RedisStringCommands.SetOption.XX)); // 使用版本字段/原子脚本
}

public User findById(Long userId) {
    return cacheManager.get(cacheName).get(userId, () -> {
        // 加入分布式锁或请求合并
        try (Lock lock = lockManager.lock(cacheKey(userId))) {
            return userRepository.findById(userId);
        }
    });
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `@Cacheable`, `@CacheEvict`, `redisTemplate`, `CacheManager`, `invalidate`, `delete`, `removeCache`, `RedisCallback`, `Lua`。

**定位步骤：**
1. 搜索写数据库同时操作缓存的代码路径；
2. 跳读（L2）确认删除缓存与写入缓存的顺序；
3. 识别是否存在多个实例或异步任务同时刷新缓存。

#### 保护机制定位（审计等级：L2-L4）
**检查是否存在：**
- 分布式锁（Redisson、Etcd、Zookeeper）；
- 乐观锁/版本号（`WHERE version = ?` + 增量）；
- 原子脚本（Lua `check-and-set`）；
- Cache Aside 模式中请求合并（singleflight、Promise 缓存）；
- 事务与缓存放在同一消息队列中保证顺序。

**定位技巧：**
- 逐行读（L3）更新流程：DB 写 → 缓存删 → 缓存写，确认是否存在空窗；
- 若有多个服务节点，跨模块追踪（L4）分布式锁或消息广播是否覆盖所有节点；
- 检查是否仅依赖 TTL/延迟双删作为补偿。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 Lua/事务脚本保障原子性 | **L0（快速跳过）** | 可直接通过 |
| 使用分布式锁或版本号 | **L2（跳读）** | 快速确认是否正确配置 |
| 简单删缓存 + 写缓存无保护 | **L3（逐行读）** | 高风险，需要深入审计 |
| 多服务实例无统一锁策略 | **L4（跨模块追踪）** | 需全链路梳理 |

## Classify

### 研判标准

#### 确认漏洞
1. 读写缓存存在空窗期，且可通过并发请求复现旧值覆盖；
2. 缺乏分布式锁、Lua 原子脚本或版本控制；
3. 数据属于关键业务（订单、库存、权限等）。

#### 误报
1. 缓存只做只读加速，并通过版本字段或消息广播确保一致；
2. 已实现原子的 compare-and-set，并对并发写失败做重试；
3. 使用 “先写数据库 → 发布更新消息 → 消费端按顺序刷新缓存” 的可靠机制。

#### 代码异味
1. 依赖短 TTL、延迟双删或定时任务纠正；
2. 仅在应用层加 `synchronized`，忽略多实例部署；
3. 写缓存缺少超时、失败重试或降级策略。

## Low risk

### 低风险评级场景

#### 1. 非关键数据缓存
- 场景：缓存项仅用于统计或排行榜，偶发不一致可接受；
- 评估：可降级为低风险，但需记录预期影响。

#### 2. 具备快速自愈机制
- 场景：存在监控与重放任务，发现错写后能自动修复；
- 评估：风险降低，但仍建议优化缓存策略。

#### 3. 即将引入统一缓存框架
- 场景：已有明确计划引入 Redisson、Canal 或 CDC 系统；
- 评估：短期可标低风险，但需要跟踪改造进度。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 缓存仅辅助展示 | 影响范围小 | 低 |
| 有自愈/重放能力 | 可快速恢复 | 低 |
| 改造计划明确 | 短期缓解 | 中 |

