# Java 缓存场景不安全反序列化

**漏洞概述**  
缓存系统为提升性能常将 Java 对象序列化后存储，在恢复对象时若直接反序列化外部可控的缓存数据，可触发 Gadget Chain 实现 RCE。常见于 Redis、Memcached、Ehcache、Caffeine、Guava Cache 及 Spring Cache 抽象层。

---

## Details

### 典型代码示例

**Redis JdkSerializationRedisSerializer（Spring Data Redis）**
```java
// 危险：默认使用 Java 序列化，直接从 Redis 读取反序列化
@Bean
public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory factory) {
    RedisTemplate<String, Object> template = new RedisTemplate<>();
    template.setConnectionFactory(factory);
    template.setValueSerializer(new JdkSerializationRedisSerializer()); // 触发点
    return template;
}

// 使用时从 Redis 获取数据会自动反序列化
Object userObj = redisTemplate.opsForValue().get("user:1001");
```

**Jedis 原生客户端反序列化**
```java
// 危险：手动反序列化 Redis byte[] 数据
byte[] cachedData = jedis.get("session:xxx".getBytes());
ByteArrayInputStream bis = new ByteArrayInputStream(cachedData);
ObjectInputStream ois = new ObjectInputStream(bis);
Object session = ois.readObject(); // 触发点
```

**Memcached XMemcached 客户端**
```java
// 危险：XMemcached 默认使用 SerializingTranscoder
MemcachedClient client = new XMemcachedClient("127.0.0.1", 11211);
Object data = client.get("cache_key"); // 内部调用 ObjectInputStream
```

**Ehcache 持久化恢复**
```java
// 危险：DiskStore 从磁盘恢复缓存时反序列化
<ehcache>
    <diskStore path="/var/cache/ehcache"/>
    <cache name="userCache" maxEntriesLocalDisk="10000">
        <persistence strategy="localTempSwap"/> <!-- 触发点：重启恢复 -->
    </cache>
</ehcache>
```

**Spring Cache + Caffeine**
```java
// 危险：自定义序列化器使用 Java 序列化
@Bean
public CacheManager cacheManager() {
    CaffeineCacheManager manager = new CaffeineCacheManager();
    manager.setCaffeine(Caffeine.newBuilder().recordStats());
    // 若配置持久化或分布式扩展时使用 Java 序列化
    return manager;
}
```

**Hazelcast IMDG 分布式缓存**
```java
// 危险：Hazelcast 默认支持 Java 序列化
Config config = new Config();
config.getSerializationConfig().addSerializerConfig(
    new SerializerConfig().setTypeClass(MyClass.class)
                          .setImplementation(new ObjectStreamSerializer()) // 触发点
);
IMap<String, Object> map = hazelcastInstance.getMap("cache");
Object obj = map.get("key");
```

**Guava Cache LoadingCache 外部加载**
```java
// 危险：从外部存储加载序列化数据填充缓存
LoadingCache<String, Object> cache = CacheBuilder.newBuilder()
    .build(new CacheLoader<String, Object>() {
        public Object load(String key) throws Exception {
            byte[] data = externalStorage.get(key);
            return deserialize(data); // 触发点：若 externalStorage 被污染
        }
    });
```

**Redisson 分布式缓存**
```java
// 危险：Redisson 默认使用 FstCodec 或可配置 Java 序列化
Config config = new Config();
config.setCodec(new SerializationCodec()); // 使用 Java 序列化
RedissonClient redisson = Redisson.create(config);
RMap<String, Object> map = redisson.getMap("cache");
Object obj = map.get("key"); // 自动反序列化
```

---

### 快速定位核心操作的技巧

**L1: 关键词扫描**
- `JdkSerializationRedisSerializer`、`SerializationCodec`
- `ObjectInputStream`、`readObject()` 配合 `jedis.get`、`memcached.get`
- `SerializingTranscoder`（XMemcached）
- `ObjectStreamSerializer`（Hazelcast）
- `DiskStore`、`persistence`（Ehcache 配置）
- `setValueSerializer`、`setDefaultSerializer`

**L2: 跳读识别缓存框架**
- 依赖导入：`spring-data-redis`、`jedis`、`lettuce-core`、`xmemcached`、`ehcache`、`hazelcast`、`redisson`
- 配置文件：`application.yml` 中 `spring.cache.type`、`spring.redis.serializer`
- 注解：`@Cacheable`、`@CachePut`、`@EnableCaching`
- Bean 定义：`RedisTemplate`、`CacheManager`、`MemcachedClient`

**L3: 逐行追踪数据流向**
- 缓存数据来源：确认缓存 key 是否可被外部控制（HTTP 参数、Cookie、JWT claims）
- 缓存服务器访问权限：Redis/Memcached 是否暴露公网或弱密码
- 缓存穿透场景：恶意 key 触发从被污染的后端加载数据
- 序列化器配置：检查 `setValueSerializer()` 参数是否为 Java 序列化
- 缓存更新逻辑：是否允许用户提交数据直接写入缓存

**L4: 跨模块追踪 Gadget Chain**
- 项目依赖中的危险库：Commons Collections、Spring、C3P0、Commons BeanUtils
- 自定义缓存加载器：`CacheLoader.load()` 实现中的反序列化逻辑
- 缓存监听器：`CacheEntryListener` 中是否触发反序列化
- 集群同步：分布式缓存节点间同步数据时的序列化方式
- 持久化策略：Ehcache/Caffeine 磁盘持久化或 AOF/RDB 恢复时的反序列化

---

### 快速定位保护机制的技巧

**L1: 关键词扫描防护措施**
- `GenericJackson2JsonRedisSerializer`、`Jackson2JsonRedisSerializer`（使用 JSON 替代 Java 序列化）
- `StringRedisSerializer`（仅存储字符串）
- `ProtobufSerializer`、`KryoRedisSerializer`
- `ObjectInputFilter`、`setObjectInputFilter()`
- Redis 认证：`requirepass`、ACL 配置
- 网络隔离：`bind 127.0.0.1`

**L2: 跳读检查序列化器选择**
```java
// 安全：使用 JSON 序列化
template.setValueSerializer(new GenericJackson2JsonRedisSerializer());

// 安全：使用 Protocol Buffers
template.setValueSerializer(new ProtobufSerializer());

// 安全：仅允许特定类型
RedisSerializer<User> userSerializer = new TypedJacksonSerializer<>(User.class);
```

**L3: 逐行分析防护强度**
- Jackson 配置：检查是否禁用 `enableDefaultTyping()`（避免多态反序列化漏洞）
- Redis 访问控制：`redis.conf` 中 `requirepass`、`rename-command` 禁用危险命令（`FLUSHALL`、`CONFIG`）
- 缓存 key 白名单：是否验证 key 格式，防止任意 key 读写
- 缓存数据签名：是否对序列化数据进行 HMAC 验证
- 异常处理：反序列化失败是否清理缓存并告警

**L4: 跨模块验证全局防护**
- 基础设施层：Redis 是否部署在隔离网络，需 VPN 或堡垒机访问
- 监控告警：是否监控异常反序列化错误（`ClassNotFoundException`、`InvalidClassException`）
- 容器安全：缓存服务是否运行在受限容器中（禁止 `CAP_SYS_ADMIN`）
- Spring Security：是否限制 `@Cacheable` 方法仅授权用户访问
- 配置审计：检查 CI/CD 是否扫描配置中的 `JdkSerializationRedisSerializer`

---

## Classify

### 真实漏洞的判定标准
1. **缓存可控性**：攻击者可写入或污染缓存（Redis 无密码、弱密码、SSRF 写入、缓存投毒）
2. **序列化方式危险**：使用 Java 原生序列化且无白名单过滤
3. **Gadget 可用**：依赖中存在可利用的反序列化链（Commons Collections 等）
4. **数据流可达**：缓存读取操作在正常业务流程中被触发，非测试代码

### 误报的典型特征
1. **内网隔离**：Redis/Memcached 仅监听 localhost，且宿主机无其他 RCE 漏洞
2. **强认证**：Redis 配置复杂密码+ACL，Memcached 配置 SASL 认证
3. **只读缓存**：应用仅从缓存读取自身写入的数据，无外部数据源
4. **安全序列化**：使用 JSON、Protobuf 等安全序列化方式，或仅缓存基础类型（String、Integer）
5. **白名单防护**：实现了严格的类白名单且在 `resolveClass()` 阶段验证

### 代码异味的识别
1. **过度缓存**：缓存不必要的复杂对象，可简化为基础类型
2. **缓存 TTL 过长**：长期存储序列化对象增加攻击窗口
3. **默认配置**：使用框架默认序列化器未显式配置安全选项
4. **缓存穿透未防护**：恶意 key 可触发从不可信源加载数据
5. **混合序列化**：部分缓存用 JSON，部分用 Java 序列化，管理混乱

---

## Low Risk

### 低风险场景的评判依据

**使用安全序列化格式**
- 全局配置使用 `GenericJackson2JsonRedisSerializer` 且禁用 `enableDefaultTyping()`
- 使用 `ProtobufSerializer` 或 `KryoRedisSerializer`（配置白名单）
- 仅缓存 String、Integer 等基础类型，不缓存复杂对象

**网络与认证隔离**
- Redis/Memcached 仅绑定 127.0.0.1 或内网 IP，防火墙规则严格
- 配置强密码（16 位以上随机字符）且定期轮换
- 启用 Redis 6.0+ ACL 限制命令和 key 访问权限
- 使用 mTLS 加密客户端与服务器通信

**数据完整性保护**
- 序列化数据带 HMAC 签名，反序列化前验证签名有效性
- 密钥存储在 KMS（Key Management Service）而非配置文件
- 缓存数据加密存储（Redis 6.0+ TLS，或应用层 AES 加密）

**最小化攻击面**
- 缓存仅用于存储会话 ID、令牌等标识符，不存储完整对象
- 业务逻辑重新从数据库查询对象，缓存仅用于判断存在性
- 禁用 Ehcache 磁盘持久化，仅使用内存缓存
- 定期自动清理缓存，TTL 设置合理（如 15 分钟）

**运行环境限制**
- 应用运行在容器中且配置 seccomp profile 限制系统调用
- 启用 SecurityManager 且策略禁止反射调用敏感类
- Redis 以非 root 用户运行且文件权限最小化
- 监控系统检测异常反序列化错误并自动隔离实例

**业务特性限制**
- 缓存仅用于只读查询加速，不存储用户提交的数据
- 缓存 miss 时从数据库加载且查询参数化，无 SQL 注入风险
- 应用处于维护模式且计划迁移至 Redis JSON 模块或安全序列化方案
- 代码审计确认依赖中不存在可用的反序列化 Gadget Chain