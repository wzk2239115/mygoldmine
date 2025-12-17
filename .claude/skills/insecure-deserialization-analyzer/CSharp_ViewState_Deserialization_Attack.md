# C# ASP.NET ViewState 反序列化攻击

---

## Details

**典型危险代码示例：**

```csharp
// 场景1：全局禁用 MAC 验证（web.config）
<pages enableViewStateMac="false" />

// 场景2：页面级禁用 MAC 验证
<%@ Page EnableViewStateMac="false" %>

// 场景3：禁用 ViewState 加密
<pages viewStateEncryptionMode="Never" />

// 场景4：自定义 ViewState 处理
protected override object LoadPageStateFromPersistenceMedium() {
    string viewStateString = Request.Form["__VIEWSTATE"];
    LosFormatter formatter = new LosFormatter();
    return formatter.Deserialize(viewStateString);
}

// 场景5：使用 ObjectStateFormatter 反序列化
ObjectStateFormatter osf = new ObjectStateFormatter();
object obj = osf.Deserialize(Request.Form["__VIEWSTATE"]);

// 场景6：machineKey 配置不当
<machineKey validation="SHA1" 
            validationKey="Auto" 
            decryption="Auto" 
            decryptionKey="AutoGenerate,IsolateApps" />

// 场景7：从外部加载 ViewState
string viewStateData = Cache.Get<string>("vs_" + userId);
var formatter = new LosFormatter();
var state = formatter.Deserialize(Convert.FromBase64String(viewStateData));
```

**快速定位核心操作（审计等级标注）：**

- **L1 - 关键词扫描：** 全局搜索 `enableViewStateMac`、`ViewStateEncryptionMode`、`LosFormatter`、`ObjectStateFormatter`、`LoadPageStateFromPersistenceMedium`、`SavePageStateToPersistenceMedium`、`__VIEWSTATE`
- **L2 - 跳读定位：** 检查 `web.config` 中 `<pages>` 节点的 MAC 和加密配置，扫描 `.aspx` 文件页面指令中的 `EnableViewStateMac` 属性，定位自定义 ViewState 持久化实现
- **L3 - 逐行审计：** 追踪 ViewState 数据流，确认是否从 `Request.Form["__VIEWSTATE"]` 直接反序列化，检查是否绕过内置验证机制，验证 `LosFormatter.Deserialize` 的调用上下文
- **L4 - 跨模块追踪：** 检查 `web.config` 的 `<machineKey>` 配置（验证密钥强度、是否硬编码、是否跨应用共享），追踪 IIS 应用程序池配置、Master Page 中的全局设置、HttpModule 中的 ViewState 拦截逻辑

**快速定位保护机制（审计等级标注）：**

- **L1 - 关键词扫描：** 查找 `enableViewStateMac="true"`、`ViewStateEncryptionMode="Always"`、`RequireViewStateEncryption()`、machineKey 的强验证算法（`HMACSHA256`/`HMACSHA512`）
- **L2 - 跳读验证：** 检查是否全局强制启用 MAC 验证，确认 `machineKey` 使用强随机密钥且未使用 `AutoGenerate,IsolateApps`（每次重启会变化导致兼容性问题），验证是否禁用旧页面访问
- **L3 - 逐行确认：** 验证自定义 ViewState 持久化时是否调用 `Page.RegisterRequiresViewStateEncryption()` 强制加密，检查反序列化前是否验证签名（`MachineKey.Decode`），确认异常处理不会降级到不安全模式
- **L4 - 架构层防护：** 检查 WAF 是否检测异常 ViewState 模式（超长、非标准 Base64、已知 Gadget 特征），验证负载均衡器是否配置会话亲和性（避免 machineKey 不一致），确认是否使用 ASP.NET Core（默认不使用 ViewState）

---

## Classify

**真实漏洞研判标准：**
- `enableViewStateMac` 显式设置为 `false` 或通过代码禁用（`Page.EnableViewStateMac = false`）
- ViewState 加密被禁用且 MAC 验证可被绕过（如使用已知/泄露的 machineKey）
- 使用 `LosFormatter` 或 `ObjectStateFormatter` 直接反序列化外部可控数据且无签名验证
- machineKey 使用默认值、弱密钥、硬编码在公开代码库中、或通过配置文件泄露可被获取
- 应用依赖程序集中存在可利用 Gadget 链（System.Configuration、System.Windows.Data.ObjectDataProvider、System.Diagnostics.Process）

**误报判定依据：**
- `enableViewStateMac` 为 `true`（默认值）且 machineKey 使用强随机密钥并安全存储（Azure Key Vault、加密配置）
- ViewState 强制加密（`ViewStateEncryptionMode="Always"` 且调用 `RegisterRequiresViewStateEncryption()`）
- 使用内置 `Page.LoadPageStateFromPersistenceMedium` 且未被重写，依赖框架自动验证
- machineKey 配置使用 `HMACSHA256`/`HMACSHA512` 验证、`AES` 加密，且密钥长度符合标准（validation 64 字节、decryption 32 字节）
- 应用已迁移至 ASP.NET Core（默认使用数据保护 API 替代 ViewState，基于 DPAPI 或集中密钥管理）

**代码异味识别：**
- 使用 `AutoGenerate,IsolateApps` 的 machineKey（Web Farm 场景下会导致 ViewState 验证失败，开发者可能被迫禁用 MAC）
- ViewState 存储在非标准位置（Session、数据库、Redis）但未经过额外签名验证（可能被其他漏洞污染）
- 在 `LoadViewState` 或 `LoadPageStateFromPersistenceMedium` 中捕获异常后继续执行（可能触发部分反序列化攻击）
- machineKey 在多个应用间共享（扩大攻击面，一个应用的漏洞可利用另一个应用的 machineKey）
- 使用 `SHA1` 验证算法（已过时，建议升级到 SHA256/SHA512）
- ViewState 包含敏感业务逻辑参数（如权限标识、价格信息）但仅依赖客户端完整性（即使有 MAC，也应在服务端重新验证）

---

## Low risk

**应降低风险评级的场景：**

1. **技术栈升级：** 应用已运行在 ASP.NET Core 上（不使用传统 ViewState，采用 antiforgery token 和数据保护 API）、或通过 IIS URL Rewrite 强制拒绝包含 `__VIEWSTATE` 的请求

2. **环境隔离充分：** 应用运行在完全隔离的内网环境（无互联网访问、严格 IP 白名单）、或使用 Azure App Service 且配置了虚拟网络集成和私有端点

3. **密钥管理严格：** machineKey 存储在 Azure Key Vault 或 AWS Secrets Manager、定期自动轮换、并通过 RBAC 限制访问，且使用 HMACSHA512 + AES-256

4. **攻击面最小化：** ViewState 仅在管理后台使用（需经过双因素认证、有完整审计日志）、或页面已设置 `EnableViewState="false"` 仅用于展示无状态信息

5. **监控与补偿：** 部署 RASP 或 WAF 实时检测异常 ViewState 模式（超长、熵值异常、已知 Gadget 特征）、反序列化异常触发自动熔断和告警、存在入侵检测系统监控异常进程创建

6. **Web Farm 配置正确：** 所有服务器使用统一的强 machineKey、通过配置管理工具（Ansible/Chef）集中管理、且定期审计配置一致性

7. **临时遗留代码：** 页面已标记废弃且有明确迁移计划（已分配开发资源）、访问日志显示使用量极低、或已通过 Feature Flag 限制仅测试环境可访问

**注意：** 即使 MAC 验证启用，仍需评估 machineKey 的安全性。若密钥泄露或使用默认值，攻击者可伪造任意 ViewState。建议优先迁移至 ASP.NET Core 或禁用 ViewState 改用无状态设计（Session/Hidden Field）。