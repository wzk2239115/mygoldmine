---
name: insecure-deserialization-analyzer
description: 专业的审计工作流程，通过静态代码分析识别和验证不安全反序列化漏洞；重点关注检测将不可信数据直接反序列化为程序对象时缺乏类型校验和安全限制的问题，涵盖多种编程语言中的反序列化机制（如 Java ObjectInputStream、Python pickle、PHP unserialize、C# BinaryFormatter 等），利用按编程语言组织的参考资料目录中的参考指南识别潜在的远程代码执行、对象注入和逻辑绕过风险。
---

**Attention**  
当项目中存在将不可信数据（如用户输入、网络请求、文件内容等）直接反序列化为程序对象或执行逻辑时，需高度警惕。该漏洞成因在于反序列化过程未进行充分校验或类型限制，导致攻击者可构造恶意序列化数据触发任意代码执行、对象注入、逻辑绕过等后果。此类问题常见于涉及数据持久化、跨服务通信、缓存机制、配置加载或插件扩展等模块。

**Early exit**  
若项目代码中完全未使用任何序列化/反序列化机制（如 JSON/YAML/XML 仅用于纯数据解析且不还原为对象、无 pickle、Marshal、ObjectInputStream、serde 等对象重建行为），且未依赖任何第三方库进行对象反序列化操作，则可快速退出对该漏洞类型的审计。
---

## 通用不安全反序列化漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：反序列化不可信数据源（用户输入/网络数据/缓存数据）、缺乏类型白名单或类型验证、使用已知不安全的反序列化函数、缺乏数据完整性验证（签名/HMAC）、魔术方法或生命周期钩子被滥用、反序列化过程缺乏隔离和限制（沙箱/资源限制）

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的反序列化机制相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
常出现在远程通信、缓存恢复、配置加载或插件热加载等业务逻辑实现中，包括但不限于使用 `ObjectInputStream`、Apache Commons Collections、Spring RMI、JMX 等方式，详见：  
- 使用 ObjectInputStream 反序列化不可信数据导致远程代码执行，详见：[Java_Deserialization_RCE.md](Java_Deserialization_RCE.md)  
- 缓存系统中反序列化恶意对象触发安全漏洞，详见：[Java_Unsafe_Deserialization_in_Cache.md](Java_Unsafe_Deserialization_in_Cache.md)  
- 插件加载过程中反序列化绕过安全检查，详见：[Java_Plugin_Deserialization_Bypass.md](Java_Plugin_Deserialization_Bypass.md)

**Python**  
常出现在任务队列、RPC 调用、配置持久化或 Web 框架中间件中，包括但不限于使用 `pickle`、`marshal`、`shelve` 或自定义 `__reduce__` 方法等方式，详见：  
- 使用 pickle 反序列化不可信数据导致远程代码执行，详见：[Python_Pickle_RCE.md](Python_Pickle_RCE.md)  
- Celery 任务队列中不安全的反序列化配置，详见：[Python_Unsafe_Deserialization_in_Celery.md](Python_Unsafe_Deserialization_in_Celery.md)  
- 使用 marshal.load 处理不可信数据引发安全问题，详见：[Python_Marshal_Load_Vulnerability.md](Python_Marshal_Load_Vulnerability.md)

**PHP**  
常出现在会话管理、缓存反序列化、插件或模块动态加载中，包括但不限于使用 `unserialize()`、`phar` 伪协议、`Session` 自定义处理器等方式，详见：  
- 使用 unserialize 函数处理用户输入构造 POP 链攻击，详见：[PHP_Unserialize_Pop_Chain.md](PHP_Unserialize_Pop_Chain.md)  
- 通过 phar 伪协议触发反序列化漏洞，详见：[PHP_Phar_Deserialization.md](PHP_Phar_Deserialization.md)  
- 会话处理器反序列化导致远程代码执行，详见：[PHP_Session_Deserialization_RCE.md](PHP_Session_Deserialization_RCE.md)

**Go**  
常出现在 gRPC、配置文件加载或插件系统中，包括但不限于使用 `gob`、`encoding/json` 配合反射、`unsafe` 包或第三方库（如 `mapstructure`）进行结构体重建时缺乏类型校验，详见：  
- 使用 gob 编码反序列化不可信数据引发安全问题，详见：[Go_Gob_Deserialization_Vulnerability.md](Go_Gob_Deserialization_Vulnerability.md)  
- JSON 反序列化配合反射机制导致远程代码执行，详见：[Go_JSON_Unmarshal_Reflection_RCE.md](Go_JSON_Unmarshal_Reflection_RCE.md)  
- 插件系统反序列化绕过沙箱安全限制，详见：[Go_Plugin_Deserialization_Sandbox_Bypass.md](Go_Plugin_Deserialization_Sandbox_Bypass.md)

**JavaScript / TypeScript**  
常出现在服务端（如 Node.js）接收客户端序列化对象、插件加载或配置反序列化场景中，包括但不限于使用 `vm.runInContext` 配合 `JSON.parse` 误用、`serialize-javascript` 库缺陷、或自定义反序列化逻辑等方式，详见：  
- 通过 eval 或 Function 构造器反序列化执行恶意代码，详见：[JS_Deserialization_via_Eval.md](JS_Deserialization_via_Eval.md)  
- RPC 通信中不安全的反序列化导致代码注入，详见：[TS_Unsafe_Deserialization_in_RPC.md](TS_Unsafe_Deserialization_in_RPC.md)  
- V8 序列化机制绕过安全沙箱限制，详见：[JS_V8_Serialization_Bypass.md](JS_V8_Serialization_Bypass.md)

**C#**  
常出现在 WCF 通信、ASP.NET ViewState 处理、缓存反序列化或配置加载中，包括但不限于使用 `BinaryFormatter`、`NetDataContractSerializer`、`JavaScriptSerializer` 配合 `TypeNameHandling` 或自定义 `TypeConverter` 等方式，详见：  
- 使用 BinaryFormatter 反序列化不可信数据导致远程代码执行，详见：[CSharp_BinaryFormatter_Deserialization_RCE.md](CSharp_BinaryFormatter_Deserialization_RCE.md)  
- JSON.NET 中不安全的 TypeNameHandling 配置引发类型混淆攻击，详见：[CSharp_JSON_NET_TypeNameHandling_Vulnerability.md](CSharp_JSON_NET_TypeNameHandling_Vulnerability.md)  
- ASP.NET ViewState 反序列化漏洞利用，详见：[CSharp_ViewState_Deserialization_Attack.md](CSharp_ViewState_Deserialization_Attack.md)

**C/C++**  
常出现在自定义二进制协议解析、游戏存档加载、配置反序列化或插件系统中，包括但不限于使用自定义结构体 `memcpy`、`fread` 直接填充对象、或依赖如 `Boost.Serialization` 等库时未验证输入边界与类型，详见：  
- 自定义二进制反序列化过程中缺乏边界检查导致缓冲区溢出，详见：[C_Custom_Binary_Deserialization_Overflow.md](C_Custom_Binary_Deserialization_Overflow.md)  
- Boost.Serialization 库反序列化时类型混淆漏洞，详见：[CPP_Boost_Serialization_Type_Confusion.md](CPP_Boost_Serialization_Type_Confusion.md)  
- 结构体反序列化操作导致释放后使用（UAF）漏洞，详见：[C_Struct_Deserialization_UAF.md](C_Struct_Deserialization_UAF.md)

**Rust**  
常出现在使用 `bincode`、`serde`（如 `ron`/`toml`/`json` 启用 `deserialize_any`）、或自定义 `Deserialize` 实现的网络协议、配置加载中，若未限制反序列化类型或未启用 `#[serde(deny_unknown_fields)]` 等防护，可能导致逻辑绕过或内存安全问题，详见：  
- 使用 bincode 进行任意类型反序列化导致安全风险，详见：[Rust_Bincode_Arbitrary_Deserialization.md](Rust_Bincode_Arbitrary_Deserialization.md)
- Serde 的 deserialize_any 机制导致逻辑绕过漏洞，详见：[Rust_Serde_Deserialize_Any_Logic_Bypass.md](Rust_Serde_Deserialize_Any_Logic_Bypass.md)
- 自定义反序列化实现中的释放后使用（UAF）问题，详见：[Rust_Custom_Deserializer_UAF.md](Rust_Custom_Deserializer_UAF.md)
- 绕过技巧，详见：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-insecure-deserialization-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板

