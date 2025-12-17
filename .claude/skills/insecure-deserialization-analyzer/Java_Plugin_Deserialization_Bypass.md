# Java 插件反序列化绕过

**漏洞概述**  
常出现在插件系统、热加载框架、OSGi 容器、动态扩展机制中，攻击者通过构造恶意插件配置或类加载器序列化数据，绕过沙箱限制或类白名单，实现远程代码执行。

---

## Details

### 典型代码示例

**场景1：URLClassLoader 插件加载配合反序列化**
```java
// 危险：从外部URL加载插件配合反序列化
public class PluginLoader {
    public void loadPlugin(String pluginUrl, byte[] config) throws Exception {
        URL[] urls = {new URL(pluginUrl)};
        URLClassLoader loader = new URLClassLoader(urls);
        
        // 使用自定义类加载器反序列化配置
        ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(config)) {
            @Override
            protected Class<?> resolveClass(ObjectStreamClass desc) throws IOException, ClassNotFoundException {
                return Class.forName(desc.getName(), false, loader); // 绕过默认类加载器
            }
        };
        Object pluginConfig = ois.readObject();
    }
}
```

**场景2：OSGi 插件配置反序列化**
```java
// 危险：OSGi Bundle 配置通过反序列化加载
public class BundleConfigLoader {
    public void loadBundleConfig(InputStream input) throws Exception {
        ObjectInputStream ois = new ObjectInputStream(input);
        BundleConfig config = (BundleConfig) ois.readObject();
        
        // 配置中包含类名，动态加载
        Bundle bundle = bundleContext.installBundle(config.getBundleLocation());
        bundle.start();
    }
}
```

**场景3：Spring 插件热加载配合 RMI**
```java
// 危险：插件通过 RMI 传输配合反序列化
@Service
public class HotDeployService {
    private RemoteInvocationSerializingExporter exporter;
    
    public void deployPlugin(String pluginName) throws Exception {
        // RMI 通信默认使用 Java 序列化
        RemoteService service = (RemoteService) registry.lookup(pluginName);
        Object pluginData = service.getPluginData(); // 反序列化触发点
    }
}
```

**场景4：自定义类加载器配合 readObject**
```java
// 危险：插件类加载器允许任意类实例化
public class PluginClassLoader extends ClassLoader {
    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        byte[] classData = loadClassData(name);
        return defineClass(name, classData, 0, classData.length);
    }
}

public void loadPluginWithCustomLoader(byte[] serializedData) throws Exception {
    PluginClassLoader loader = new PluginClassLoader();
    ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(serializedData)) {
        @Override
        protected Class<?> resolveClass(ObjectStreamClass desc) throws IOException, ClassNotFoundException {
            return loader.loadClass(desc.getName()); // 自定义类加载器绕过白名单
        }
    };
    Object plugin = ois.readObject();
}
```

**场景5：插件仓库缓存反序列化**
```java
// 危险：从 Redis/Hazelcast 加载插件缓存
public class PluginCacheManager {
    public Plugin getPlugin(String pluginId) throws Exception {
        byte[] cachedData = redisTemplate.execute((RedisCallback<byte[]>) 
            connection -> connection.get(pluginId.getBytes()));
        
        if (cachedData != null) {
            ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(cachedData));
            return (Plugin) ois.readObject(); // 缓存数据可能被污染
        }
        return null;
    }
}
```

**场景6：JMX MBean 插件动态注册**
```java
// 危险：通过 JMX 注册插件 MBean
public class PluginMBeanServer {
    public void registerPluginMBean(byte[] mbeanData) throws Exception {
        ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(mbeanData));
        Object mbean = ois.readObject();
        
        // 动态注册 MBean
        MBeanServer server = ManagementFactory.getPlatformMBeanServer();
        ObjectName name = new ObjectName("plugins:type=" + mbean.getClass().getSimpleName());
        server.registerMBean(mbean, name);
    }
}
```

**场景7：JNDI 插件查找配合反序列化**
```java
// 危险：插件配置通过 JNDI 查找
public class JNDIPluginLoader {
    public void loadPlugin(String jndiName) throws Exception {
        Context ctx = new InitialContext();
        Object plugin = ctx.lookup(jndiName); // JNDI 注入可触发反序列化
        
        // 插件配置可能包含恶意序列化对象
        if (plugin instanceof Reference) {
            Reference ref = (Reference) plugin;
            ObjectFactory factory = (ObjectFactory) Class.forName(ref.getFactoryClassName()).newInstance();
            factory.getObjectInstance(ref, null, null, null);
        }
    }
}
```

**场景8：插件注册表动态注册**
```java
// 危险：插件注册表使用反序列化
public class PluginRegistry implements Serializable {
    private Map<String, Plugin> plugins = new HashMap<>();
    
    private void readObject(ObjectInputStream ois) throws Exception {
        ois.defaultReadObject();
        // 自定义 readObject 可能执行危险操作
        for (Plugin plugin : plugins.values()) {
            plugin.initialize(); // 可能触发命令执行
        }
    }
}
```

---

### 快速定位核心操作的技巧

**L0: 快速跳过**
- 代码中无插件系统相关关键词（`plugin`、`Plugin`、`ClassLoader`、`Bundle`、`hotdeploy`）
- 反序列化仅处理基础配置类型（`String`、`Integer`、`Boolean`）且无动态类加载

**L1: 关键词扫描**
- `URLClassLoader`、`PluginClassLoader`、自定义 `ClassLoader`
- `ObjectInputStream.resolveClass()`、`resolveProxyClass()` 重写
- `Class.forName()` + 可控类名
- `BundleContext.installBundle()`、`Bundle.start()`（OSGi）
- `Context.lookup()` + `Reference`、`ReferenceableFactory`（JNDI）
- `RemoteInvocationSerializingExporter`、`RmiServiceExporter`
- `MBeanServer.registerMBean()`、`createMBean()`
- 插件相关缓存操作：`pluginCache`、`PluginRegistry`

**L2: 跳读定位**
- 检查插件加载函数（`loadPlugin`、`deployPlugin`、`installPlugin`）
- 关注自定义类加载器与反序列化的组合使用
- 查看 `readObject()` 方法是否在插件相关类中被重写
- 检查 JNDI 查找的资源名称是否可控
- 确认插件配置数据流向（网络、文件、缓存、数据库）

**L3: 逐行追踪**
- 追踪 `ObjectInputStream` 使用的类加载器来源（是否可被绕过）
- 检查 `resolveClass()` 实现是否限制可加载的类
- 验证插件数据来源是否外部可控（HTTP body、文件上传、MQ 消息）
- 确认缓存数据完整性（Redis/Hazelcast 数据是否可被篡改）
- 检查 JNDI 连接 URL 是否可控（`ldap://`、`rmi://` 注入）
- 分析插件初始化流程中的危险操作（`Runtime.exec`、`ProcessBuilder`）

**L4: 跨模块追踪**
- 识别插件系统架构（OSGi、Spring Plugin、自定义插件框架）
- 追踪类加载器层次结构（父类加载器是否安全）
- 检查插件白名单机制（是否存在、如何绕过）
- 分析插件隔离机制（ClassLoader 隔离、SecurityManager 限制）
- 验证 JNDI/RMI 配置（`com.sun.jndi.rmi.object.trustURLCodebase` 等）
- 检查依赖库中的 Gadget Chain（是否可通过插件类加载器触发）
- 追踪插件间通信机制（是否使用反序列化）

---

### 快速定位保护机制的技巧

**L0: 快速跳过**
- 插件系统完全禁用或使用签名验证机制
- 不使用 Java 原生序列化，采用 JSON/Protobuf

**L1: 关键词扫描防护措施**
- `ObjectInputFilter`、`setObjectInputFilter()`
- `resolveClass()` 中的类白名单检查
- 插件签名验证：`Signature.verify()`、`CodeSigner`
- `SecurityManager`、`AccessController.doPrivileged()`
- `ProtectionDomain`、`Permissions` 配置
- 类加载器白名单：`allowedClassLoaders`
- JNDI 防护：`trustURLCodebase=false`

**L2: 跳读检查白名单机制**
```java
// 白名单示例
@Override
protected Class<?> resolveClass(ObjectStreamClass desc) throws IOException, ClassNotFoundException {
    String className = desc.getName();
    if (!allowedPluginClasses.contains(className)) {
        throw new InvalidClassException("Unauthorized plugin class: " + className);
    }
    return super.resolveClass(desc);
}

// 类加载器限制
if (!(classLoader instanceof TrustedPluginClassLoader)) {
    throw new SecurityException("Untrusted plugin class loader");
}
```

**L3: 逐行分析防护强度**
- 白名单是否完整（是否遗漏接口、抽象类、内部类）
- 类加载器检查是否可绕过（通过代理、反射、`Unsafe`）
- 签名验证时机（是否在类加载前验证）
- 插件隔离是否有效（`SecurityManager` 策略是否严格）
- JNDI 防护配置（`com.sun.jndi.ldap.object.trustURLCodebase`）
- 异常处理是否正确（验证失败是否继续加载）

**L4: 跨模块验证全局防护**
- JVM 启动参数：`-Djdk.serialFilter`、`-Djava.security.manager`、`-Dcom.sun.jndi.rmi.object.trustURLCodebase=false`
- OSGi 安全配置：`ConditionalPermissionAdmin`、Bundle 权限
- Spring Security 配置：RMI 服务暴露限制
- 容器隔离：Docker/Kubernetes 安全策略、AppArmor/SELinux
- 网络隔离：插件加载服务是否仅内网访问
- 代码签名：插件 JAR 是否需要有效签名（`jarsigner`）
- 插件仓库访问控制：HTTP 认证、TLS 双向认证

---

## Classify

### 真实漏洞的判定标准
1. **外部可控性**：插件配置/数据来源可被攻击者控制（HTTP API、文件上传、消息队列、JNDI URL、RMI 连接、缓存数据）
2. **类加载器绕过**：使用自定义类加载器配合反序列化，且 `resolveClass()` 缺少类白名单验证或白名单可被绕过
3. **缺少签名验证**：插件 JAR 或序列化数据未进行签名验证，或验证逻辑存在缺陷（时序问题、证书链校验不完整）
4. **JNDI 注入风险**：使用 `Context.lookup()` 且资源名称可控，未设置 `trustURLCodebase=false` 或使用危险的 JNDI 协议（`ldap://`、`rmi://`）
5. **Gadget Chain 可用**：项目依赖中存在可通过插件类加载器触发的利用链（Commons Collections、Spring、C3P0、ROME）
6. **隔离机制失效**：缺少 `SecurityManager` 或策略配置过于宽松，插件可执行敏感操作（文件访问、网络连接、命令执行）
7. **缓存污染**：插件配置从可被篡改的缓存（Redis、Hazelcast）加载且无完整性校验

### 误报的典型特征
1. **可信数据源**：插件仅从可信源加载（编译时嵌入、本地管理员可写目录、经签名验证的官方仓库、内部 mTLS 服务）
2. **强签名验证**：使用 `jarsigner` 或自定义签名方案验证插件 JAR，密钥通过 HSM/KMS 管理，验证失败立即拒绝加载
3. **严格类白名单**：`resolveClass()` 中实现完整的类白名单（包括包名前缀、接口限制），且白名单由安全团队维护
4. **不使用 Java 序列化**：插件配置采用 JSON/YAML/Protobuf 等安全格式，不涉及 `ObjectInputStream`
5. **安全的类加载器**：仅使用 JDK 标准类加载器或经过安全审计的框架（如 Spring Boot 的 `LaunchedURLClassLoader`）
6. **强隔离环境**：插件运行在独立进程/容器中，配置严格的 `SecurityManager` 策略、SELinux/AppArmor 规则
7. **已修复的 JNDI 配置**：JDK 版本 ≥ 8u191/11.0.1 且显式设置 `trustURLCodebase=false`
8. **死代码或测试代码**：插件加载逻辑在测试类、已弃用模块或永远不会执行的分支中

### 代码异味的识别
1. **弱签名验证**：仅验证插件 JAR 的 MD5/SHA1 哈希值而非数字签名，或签名密钥硬编码在代码中
2. **不完整的类白名单**：白名单仅限制部分包名，但允许子包或接口实现，可能通过代理类绕过
3. **依赖过时的框架**：使用旧版本的 OSGi（Equinox 3.x）、Spring RMI 未禁用反序列化
4. **混合使用序列化方案**：部分插件使用安全方案（JSON），部分仍使用 Java 序列化
5. **缓存数据未保护**：插件配置缓存在 Redis/Memcached 但无 HMAC/签名验证
6. **JNDI 配置不明确**：未显式设置 `trustURLCodebase`，依赖 JDK 默认配置
7. **SecurityManager 配置宽松**：启用了 `SecurityManager` 但策略允许 `AllPermission` 或过多权限
8. **插件热加载缺少审计**：支持运行时热加载但无操作日志、无审批流程
9. **类加载器层次混乱**：多层类加载器嵌套但隔离边界不清晰

---

## Low Risk

### 低风险场景的评判依据

**完善的代码签名机制**
- 插件 JAR 使用 X.509 证书签名，证书链经过完整验证（根 CA 可信、证书未过期、CRL/OCSP 检查）
- 签名验证在类加载前执行（`CodeSigner`、`JarVerifier`），失败时立即拒绝加载并记录日志
- 私钥通过 HSM（硬件安全模块）或 KMS（密钥管理服务）管理，签名流程有审计记录

**严格的类加载隔离**
- 每个插件使用独立的 `ClassLoader` 实例，配置严格的委派模型（父类加载器仅包含 JDK 核心类）
- 实现完整的类白名单（仅允许插件 API 接口、基础类型、经审计的工具类）
- 使用 `SecurityManager` 配置细粒度权限（`FilePermission`、`SocketPermission`、`RuntimePermission` 限制）

**安全的序列化方案**
- 不使用 Java 原生序列化，采用 JSON（Jackson/Gson）、YAML、Protobuf 等安全格式
- 配置严格的反序列化策略（`JsonTypeInfo.Id.NAME` 白名单、`@JsonTypeInfo` 限制）
- 插件配置使用 Schema 验证（JSON Schema、XSD），拒绝不符合规范的输入

**强隔离运行环境**
- 插件运行在独立进程或容器中（Docker/Kubernetes），配置严格的 seccomp profile、AppArmor/SELinux 策略
- 禁用危险系统调用（`execve`、`ptrace`、`mount`、`unshare`）
- 网络隔离（仅允许访问特定内部服务）、文件系统只读挂载（除临时目录外）

**完整的数据保护**
- 插件配置使用 HMAC-SHA256 或 Ed25519 签名，密钥通过 Vault/KMS 动态获取且定期轮换
- 传输层使用 TLS 1.3 配合证书锁定（Certificate Pinning）
- 缓存数据加密存储（AES-256-GCM），密钥独立管理

**可信数据源**
- 插件仅从官方仓库加载，仓库需要双因素认证（2FA）且有完整操作审计
- 插件上传需要代码审查（Code Review）和安全扫描（SAST/DAST）
- 使用内网私有仓库，仅管理员通过跳板机访问

**监控与响应机制**
- 部署 RASP（Runtime Application Self-Protection）监控异常类加载、反序列化操作
- 插件加载失败触发告警（Sentry/PagerDuty），自动隔离受影响实例
- 日志记录所有插件操作（加载、卸载、初始化、方法调用），日志不可篡改（写入 SIEM）

**业务场景限制**
- 插件系统仅用于内部工具，需要硬件 Token 或 mTLS 证书认证
- 插件加载需要双人审批（Four-Eyes Principle），有明确的变更管理流程
- 系统设计为只读查询（无状态变更、无命令执行、无敏感数据访问）

**迁移计划明确**
- 代码已标记为 `@Deprecated`，有明确的迁移到微服务架构或 Serverless 的 Roadmap
- 插件系统使用率低（监控显示流量 <5%），仅用于向后兼容旧客户端
- 通过 Feature Flag 限制仅测试环境启用，生产环境已禁用

**注意**：Java 插件反序列化绕过风险极高，即使评为低风险，仍应推动团队：① 优先使用代码签名 + 类白名单；② 迁移到 JSON/Protobuf 等安全序列化方案；③ 启用 `SecurityManager` 和容器隔离；④ 部署 RASP 监控异常行为。务必全局搜索所有自定义 `ClassLoader`、`resolveClass()` 重写、JNDI 查找、RMI 服务，逐一评估数据源可信度和防护机制有效性。