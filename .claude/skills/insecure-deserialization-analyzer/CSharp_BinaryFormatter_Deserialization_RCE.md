# C# BinaryFormatter 反序列化 RCE

---

## Details

**典型危险代码示例：**

```csharp
// 场景1：从网络流直接反序列化
BinaryFormatter formatter = new BinaryFormatter();
object obj = formatter.Deserialize(networkStream);

// 场景2：从缓存恢复对象
byte[] cachedData = Cache.Get("userObject");
MemoryStream ms = new MemoryStream(cachedData);
object userObj = formatter.Deserialize(ms);

// 场景3：WCF 自定义序列化
[ServiceBehavior]
public class MyService {
    public void ProcessData(byte[] data) {
        var formatter = new BinaryFormatter();
        var obj = formatter.Deserialize(new MemoryStream(data));
    }
}

// 场景4：配置文件反序列化
var config = formatter.Deserialize(File.OpenRead("app.config"));
```

**快速定位核心操作（审计等级标注）：**

- **L1 - 关键词扫描：** 全局搜索 `BinaryFormatter`、`Deserialize`、`NetDataContractSerializer`、`LosFormatter`、`ObjectStateFormatter`、`SoapFormatter` 关键词
- **L2 - 跳读定位：** 检查 Deserialize 调用点，重点关注数据源是否来自外部（Request、Session、Cookie、File、Database、Cache、Network）
- **L3 - 逐行审计：** 追踪数据流向，确认反序列化输入是否经过 `using` 语句块内、是否存在类型检查（`is`/`as` 运算符）、是否在 `try-catch` 后仍使用对象
- **L4 - 跨模块追踪：** 追踪 WCF binding 配置、ASP.NET 的 `web.config` 中 `<system.runtime.serialization>` 节点、中间件管道中的自定义 `ISerializationSurrogateSelector` 实现

**快速定位保护机制（审计等级标注）：**

- **L1 - 关键词扫描：** 查找 `SerializationBinder`、`ISerializationSurrogateSelector`、`TypeFilterLevel`、`[Serializable]` 白名单限制
- **L2 - 跳读验证：** 检查是否存在自定义 `Binder` 并覆盖 `BindToType` 方法进行类型白名单校验
- **L3 - 逐行确认：** 验证 `Binder` 实现逻辑是否可被绕过（如仅检查命名空间前缀、正则不严谨、允许泛型展开）
- **L4 - 架构层防护：** 检查 AppDomain 隔离配置、CAS（Code Access Security）策略、进程权限降级、网络隔离策略

---

## Classify

**真实漏洞研判标准：**
- 反序列化数据源可被攻击者完全控制（如 HTTP Body、Query 参数、Cookie、上传文件）
- 使用 `BinaryFormatter` 或其他不安全序列化器且无有效的类型白名单限制
- 应用依赖的程序集中存在可利用的 Gadget 链（如 System.dll、System.Windows.Forms.dll）
- 反序列化操作在高权限上下文中执行（如 SYSTEM、Administrator、应用程序池身份）

**误报判定依据：**
- 数据源完全来自内部信任源（硬编码、编译时嵌入资源、管理员专用配置文件）且访问路径受严格权限控制
- 使用了 `SerializationBinder` 并实现了严格的类型白名单（仅允许明确的业务类型，拒绝 System.* 命名空间）
- 反序列化前对数据进行了 HMAC 签名校验且密钥安全存储（需确认签名算法强度、密钥轮换机制）
- 运行环境已完全移除可利用程序集（需通过依赖分析工具验证）

**代码异味识别：**
- 使用不安全序列化器但数据源为半可信（如数据库中的业务数据，理论上可通过其他漏洞污染）
- 存在类型过滤但实现不严谨（如仅黑名单模式、可通过泛型或嵌套类型绕过）
- 依赖外部配置文件控制序列化行为（配置文件本身可能被篡改）
- 在异常处理后继续使用反序列化对象（可能触发 finalizer 攻击）

---

## Low risk

**应降低风险评级的场景：**

1. **环境隔离充分：** 反序列化操作运行在受限沙箱环境（如 Azure Functions Consumption Plan、AWS Lambda）、容器环境配置了 seccomp/AppArmor 严格限制系统调用、或使用独立低权限服务账户且无网络出站权限

2. **攻击面极小：** 仅在内部管理后台使用（需验证后台本身无其他高危漏洞）、需经过多因素认证且有完整审计日志、或仅在本地工具/脚本中处理受信任文件

3. **技术栈限制：** 目标环境为 .NET Core 3.0+ 且已全局禁用 BinaryFormatter（检查 `AppContext` 开关）、或应用完全基于 Blazor WebAssembly 运行在客户端、或使用了 IL 重写工具移除所有不安全序列化器

4. **监控补偿到位：** 存在实时行为监控（如 EDR 拦截 `csc.exe`/`powershell.exe` 异常调用）、反序列化操作触发告警并联动自动熔断、或业务逻辑设计使得 RCE 后无法进一步横向移动或数据泄露

5. **临时性使用：** 代码明确标记为待废弃（如注释说明迁移计划、存在对应 Issue 跟踪）、仅在过渡期间处理历史遗留数据、且已设置访问频率限制和有效期

**注意：** 即使符合以上条件，仍应建议团队进行安全重构，低风险评级不等于可忽略。