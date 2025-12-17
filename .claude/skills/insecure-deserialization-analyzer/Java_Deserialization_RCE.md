# Java Deserialization RCE

**漏洞概述**  
常出现在远程通信、缓存恢复、配置加载或插件热加载等业务逻辑实现中，攻击者通过构造恶意序列化数据触发 Gadget Chain 实现 RCE。

---

## Details

### 典型代码示例

**基础 ObjectInputStream 反序列化**
```java
// 危险：直接反序列化外部输入
ObjectInputStream ois = new ObjectInputStream(socket.getInputStream());
Object obj = ois.readObject();  // 触发点
```

**Spring RMI 反序列化**
```java
// 危险：RMI 服务端默认使用 Java 序列化
@Bean
RemoteInvocationSerializingExporter exporter() {
    return new RemoteInvocationSerializingExporter();
}
```

**Apache Commons Collections 利用链**
```java
// 危险类：存在 readObject 的危险 Gadget
import org.apache.commons.collections.functors.InvokerTransformer;
import org.apache.commons.collections.map.LazyMap;
```

**Redis/Memcached 缓存反序列化**
```java
// 危险：缓存数据未验证直接反序列化
byte[] data = jedis.get(key.getBytes());
Object obj = deserialize(data);
```

**JMX MBean 反序列化**
```java
// 危险：JMX 连接处理器使用反序列化
JMXConnectorServer server = JMXConnectorServerFactory.newJMXConnectorServer(url, env, mbs);
```

---

### 快速定位核心操作的技巧

**L1: 关键词扫描**
- `ObjectInputStream.readObject()`、`readUnshared()`
- `XMLDecoder.readObject()`
- `XStream.fromXML()`
- `Yaml.load()`（SnakeYAML）
- `Hessian2Input.readObject()`
- `Kryo.readClassAndObject()`

**L2: 跳读识别反序列化框架**
- 包导入：`java.io.ObjectInputStream`、`org.apache.commons.collections`
- 接口实现：`implements Serializable`、`Externalizable`
- 方法签名：`private void readObject(ObjectInputStream)`

**L3: 逐行追踪数据流向**
- 反序列化入口的数据来源：`InputStream`、`byte[]`、`String`
- 数据是否来自外部可控源：HTTP body、Socket、文件上传、消息队列
- 检查 `readObject()` 前是否有数据验证

**L4: 跨模块追踪 Gadget Chain**
- 识别项目依赖中的已知危险库版本（Commons Collections 3.1-3.2.1、Spring 4.x 等）
- 追踪自定义 `readObject()` 方法中的危险操作：反射调用、命令执行、动态类加载
- 检查 JNDI 引用：`lookup()`、`Reference`、`ReferenceableFactory`

---

### 快速定位保护机制的技巧

**L1: 关键词扫描防护措施**
- `ObjectInputFilter`、`setObjectInputFilter()`（JDK 9+）
- `ValidatingObjectInputStream`（Apache Commons IO）
- `SerialKiller`、`NotSoSerial` 等第三方库
- `resolveClass()` 方法重写
- `SecurityManager` 配置

**L2: 跳读检查白名单/黑名单**
```java
// 白名单示例
if (!allowedClasses.contains(className)) {
    throw new InvalidClassException("Unauthorized deserialization");
}

// 黑名单示例（易绕过，不可靠）
if (className.contains("commons.collections")) {
    throw new InvalidClassException();
}
```

**L3: 逐行分析防护强度**
- 白名单是否完整：检查是否遗漏危险类或允许子类
- 黑名单是否可绕过：使用类代理、接口实现绕过
- 过滤器时机：是否在 `readObject()` 之前执行
- 异常处理：是否正确中断反序列化流程

**L4: 跨模块验证全局防护**
- JVM 启动参数：`-Djdk.serialFilter`、`-Djava.security.manager`
- 配置文件：`jre/lib/security/java.security` 中的 `jdk.serialFilter`
- 框架级防护：Spring Security、Shiro 等的反序列化配置
- 网络隔离：反序列化服务是否仅内网访问

---

## Classify

### 真实漏洞的判定标准
1. **外部可控性**：反序列化的数据来源可被攻击者控制（HTTP、Socket、MQ、文件上传）
2. **无有效防护**：缺少白名单验证或白名单可绕过
3. **Gadget 可用**：项目依赖中存在已知利用链，或自定义类中存在危险的 `readObject()` 实现
4. **执行路径可达**：代码逻辑确保反序列化操作会被执行，非死代码

### 误报的典型特征
1. **内部数据源**：仅反序列化可信内部系统生成的数据（如本地配置文件、数据库存储的自身序列化数据）
2. **不可达路径**：反序列化代码在测试代码、已弃用模块或永远不会执行的分支中
3. **强白名单防护**：实现了严格的类白名单且仅允许基础类型或不可利用的类
4. **版本已修复**：依赖库版本已升级至修复版本（如 Commons Collections 3.2.2+、JDK 8u121+）

### 代码异味的识别
1. **弱黑名单**：仅使用黑名单过滤而非白名单，易被绕过但当前环境无可用 Gadget
2. **部分防护**：有防护措施但覆盖不全，仅在部分反序列化入口实施
3. **反序列化必要性存疑**：功能可通过 JSON 等更安全的序列化方式替代
4. **依赖风险**：项目中存在危险库但当前代码未直接触发反序列化

---

## Low Risk

### 低风险场景的评判依据

**完善的白名单机制**
- 实现了严格的类白名单且仅包含 Java 基础类型、不可变对象或经审计的安全自定义类
- 白名单在 `resolveClass()` 阶段执行，早于对象构造
- 白名单配置由安全团队维护且有变更审计流程

**网络隔离与访问控制**
- 反序列化服务仅监听 localhost 或内网地址且有严格的网络 ACL
- 需要通过强认证（如双向 TLS、Kerberos）才能访问
- 日志完整记录所有反序列化操作及来源

**数据完整性保护**
- 序列化数据使用 HMAC 或数字签名验证，攻击者无法伪造
- 密钥管理安全，未硬编码或泄露
- 签名验证在反序列化之前执行且失败时立即中断

**受限执行环境**
- 应用运行在沙箱或容器中，启用了 SecurityManager 且配置严格策略
- 操作系统层面限制：SELinux、AppArmor 强制访问控制
- 无敏感数据访问权限，即使 RCE 也难以造成实质危害

**仅反序列化安全类型**
- 仅反序列化基础类型包装类（`String`、`Integer`、`Boolean` 等）
- 不使用任何存在 `readObject()` 方法的第三方库类
- 自定义类未实现危险的反序列化逻辑

**业务场景限制**
- 反序列化仅用于内部进程间通信（如本地缓存恢复）
- 数据源完全由系统自身控制，无外部交互路径
- 功能处于维护模式，计划迁移至安全方案