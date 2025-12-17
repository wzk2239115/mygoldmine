# Go JSON Unmarshal 配合反射的 RCE

---

## Details

**典型危险代码示例：**

```go
// 场景1：配置文件动态加载配合反射
func loadPluginConfig(filename string) error {
    data, _ := ioutil.ReadFile(filename)
    var config map[string]interface{}
    json.Unmarshal(data, &config) // 解析为 interface{}
    
    // 通过 type 字段动态创建对象
    typeName := config["type"].(string)
    typ := reflect.TypeOf((*Plugin)(nil)).Elem()
    for i := 0; i < typ.NumMethod(); i++ {
        if typ.Method(i).Name == typeName {
            // 反射调用方法，可能触发任意代码
            reflect.ValueOf(plugin).MethodByName(typeName).Call(nil)
        }
    }
    return nil
}

// 场景2：gRPC 消息处理配合 mapstructure
type Request struct {
    Action  string                 `json:"action"`
    Params  map[string]interface{} `json:"params"`
}

func handleRequest(jsonData []byte) {
    var req Request
    json.Unmarshal(jsonData, &req)
    
    // 根据 action 动态执行
    if handler, ok := handlers[req.Action]; ok {
        // 使用 mapstructure 将 params 映射到结构体
        var params interface{}
        mapstructure.Decode(req.Params, &params)
        reflect.ValueOf(handler).Call([]reflect.Value{reflect.ValueOf(params)})
    }
}

// 场景3：插件系统动态类型实例化
func loadPlugin(pluginData []byte) interface{} {
    var meta map[string]interface{}
    json.Unmarshal(pluginData, &meta)
    
    // 通过类型名动态创建实例
    typeName := meta["plugin_type"].(string)
    typ, _ := typeRegistry[typeName] // 全局类型注册表
    instance := reflect.New(typ).Interface()
    
    // 将 JSON 数据映射到实例
    json.Unmarshal(pluginData, instance)
    
    // 调用 Init 方法（可能触发恶意代码）
    reflect.ValueOf(instance).MethodByName("Init").Call(nil)
    return instance
}

// 场景4：HTTP API 动态路由配合反射
func dynamicHandler(w http.ResponseWriter, r *http.Request) {
    var payload map[string]interface{}
    json.NewDecoder(r.Body).Decode(&payload)
    
    // 从 payload 提取 controller 和 method
    controller := payload["controller"].(string)
    method := payload["method"].(string)
    args := payload["args"].([]interface{})
    
    // 反射调用
    ctrl := controllers[controller]
    m := reflect.ValueOf(ctrl).MethodByName(method)
    
    var params []reflect.Value
    for _, arg := range args {
        params = append(params, reflect.ValueOf(arg))
    }
    m.Call(params) // 危险：未验证方法名和参数类型
}

// 场景5：配置热加载配合类型转换
type Config struct {
    Handlers map[string]interface{} `json:"handlers"`
}

func reloadConfig(data []byte) {
    var cfg Config
    json.Unmarshal(data, &cfg)
    
    for name, handler := range cfg.Handlers {
        // 尝试类型断言并调用
        if h, ok := handler.(map[string]interface{}); ok {
            className := h["class"].(string)
            typ := reflect.TypeOf(registeredTypes[className])
            instance := reflect.New(typ).Elem()
            
            // 使用反射设置字段值
            for key, val := range h {
                field := instance.FieldByName(key)
                if field.IsValid() && field.CanSet() {
                    field.Set(reflect.ValueOf(val))
                }
            }
            
            // 调用 Execute 方法
            instance.MethodByName("Execute").Call(nil)
        }
    }
}

// 场景6：WebSocket 消息分发配合动态调用
func handleWebSocketMessage(conn *websocket.Conn, msg []byte) {
    var envelope map[string]interface{}
    json.Unmarshal(msg, &envelope)
    
    eventType := envelope["type"].(string)
    payload := envelope["payload"]
    
    // 通过事件类型动态分发
    if handlerFunc, exists := eventHandlers[eventType]; exists {
        // 使用 mapstructure 解码 payload
        var eventData interface{}
        mapstructure.Decode(payload, &eventData)
        
        // 反射调用处理函数
        funcValue := reflect.ValueOf(handlerFunc)
        funcValue.Call([]reflect.Value{
            reflect.ValueOf(conn),
            reflect.ValueOf(eventData),
        })
    }
}
```

**快速定位核心操作（审计等级标注）：**

- **L1 - 关键词扫描：** 全局搜索 `json.Unmarshal`、`json.NewDecoder`、`mapstructure.Decode`、`reflect.ValueOf`、`MethodByName`、`Call`、`map[string]interface{}`、`interface{}`、`reflect.New`
- **L2 - 跳读定位：** 检查 `Unmarshal` 的目标类型是否包含 `interface{}`、`map[string]interface{}`、`[]interface{}`，重点关注后续是否有反射调用（`MethodByName`、`Call`、`FieldByName`、`Set`）
- **L3 - 逐行审计：** 追踪数据流向，确认 JSON 输入来源（HTTP Body、WebSocket、配置文件、数据库、消息队列、环境变量），检查反射调用的方法名、参数是否可被外部控制
- **L4 - 跨模块追踪：** 检查全局类型注册表（`typeRegistry`、`handlers`）的来源、`mapstructure` 的 `DecodeHook` 配置、自定义 `json.Unmarshaler` 实现、`reflect.MakeFunc` 的使用、是否存在可利用的 Gadget（如执行系统命令的结构体方法）

**快速定位保护机制（审计等级标注）：**

- **L1 - 关键词扫描：** 查找 `json.UnmarshalTypeError`、类型断言 `.(Type)`、`reflect.Kind()` 检查、方法白名单、`mapstructure.DecodeHook`
- **L2 - 跳读验证：** 检查是否使用具体结构体类型而非 `interface{}` 进行解码、是否存在 `struct tag` 验证（如 `validate:"required"`）、是否限制可反序列化的字段集合
- **L3 - 逐行确认：** 验证类型断言是否检查 `ok` 返回值、反射调用前是否校验方法存在性（`Method.IsValid()`）、是否限制可调用方法的白名单、参数类型是否验证、是否检查 `CanSet()`/`CanAddr()`
- **L4 - 架构层防护：** 检查 JSON Schema 验证、数据签名校验（HMAC/JWT）、沙箱隔离（gVisor/Firecracker）、进程权限降级、seccomp/AppArmor 限制、是否使用代码生成工具（如 `easyjson`）避免反射、是否采用明确类型映射替代动态分发

---

## Classify

**真实漏洞研判标准：**
- JSON 数据源可被攻击者控制（HTTP 请求、WebSocket、用户上传文件、外部 API、数据库中的用户内容）
- 使用 `interface{}`、`map[string]interface{}` 或包含 `interface{}` 字段的结构体进行 `Unmarshal`，缺乏类型白名单
- 反序列化后使用反射动态调用方法（`MethodByName`、`Call`），且方法名或参数可被外部数据控制
- 存在全局类型注册机制或处理器映射表（`handlers`、`typeRegistry`），攻击者可通过构造特定 JSON 触发危险类型实例化
- 调用链中存在可利用的 Gadget（如 `os/exec.Command`、`plugin.Open`、文件操作、SQL 执行、模板渲染）
- 使用 `mapstructure` 等第三方库进行动态类型映射，未配置 `DecodeHook` 或类型限制

**误报判定依据：**
- JSON 数据完全来自可信源（硬编码、编译时嵌入、仅本地管理员可写文件）且传输路径有完整性保护
- 使用明确的具体结构体类型进行解码（如 `var config AppConfig`），结构体所有字段均为具体类型（无 `interface{}`、函数类型、通道）
- 解码前进行了 JSON Schema 严格验证或使用 JWT 签名校验（RS256/ES256 且密钥安全管理）
- 反射调用前存在严格的方法白名单检查（硬编码允许的方法列表，使用 `switch-case` 而非动态字符串匹配）
- 使用 `json:"-"` 标签明确排除敏感字段、所有导出字段均有明确类型、使用自定义 `UnmarshalJSON` 进行类型校验
- 解码后对象仅用于只读数据访问（日志、指标），不触发任何方法调用或状态变更

**代码异味识别：**
- 为了"灵活性"使用 `interface{}` 或 `map[string]interface{}` 但未评估安全风险（开发者认为 JSON 足够安全）
- 数据源为半可信（Redis/数据库存储的序列化数据，可能通过其他漏洞污染）
- 使用 `mapstructure.Decode` 进行松散类型转换但未配置 `ErrorUnused`、`WeaklyTypedInput` 等安全选项
- 反射调用逻辑分散在多个包中，难以统一审计和防护
- 动态路由或插件系统依赖字符串匹配（`handlers[name]`）但未限制可访问的处理器集合
- 通过 `reflect.MakeFunc` 或 `reflect.MakeChan` 创建动态函数/通道
- 在 `init()` 函数中注册大量类型到全局映射表，缺乏访问控制
- 使用 `encoding/json` 的 `UseNumber` 选项但未验证数值范围，可能导致整数溢出
- 配置文件支持"热加载"但未限制加载来源或频率
- 错误处理不当（`json.Unmarshal` 错误被忽略，继续使用零值对象）

---

## Low risk

**应降低风险评级的场景：**

1. **环境强隔离：** 反序列化操作运行在独立容器中且配置了严格 seccomp profile（禁止 `execve`、`ptrace`、`socket` 系统调用）、使用 gVisor/Kata Containers 运行时隔离、或在 AWS Lambda/Cloud Run 无状态函数环境中执行且无出站网络权限

2. **攻击面极小：** 仅在内部管理工具中使用（需验证管理界面无认证绕过或 CSRF）、需要硬件 token/mTLS 证书认证且有完整操作审计（Audit Log 不可篡改）、或仅在构建/CI 流程中处理受版本控制的配置文件

3. **技术栈限制：** 完全使用具体类型且通过 `go vet`/`staticcheck` 自定义规则强制禁止 `interface{}` 用于外部输入、使用代码生成工具（`easyjson`、`ffjson`）替代标准库反射、或采用 Protocol Buffers/FlatBuffers 等强类型序列化方案

4. **签名+加密双重保护：** JSON 数据使用 JWS（RFC 7515）签名且验证 `alg` 头防止算法降级攻击、传输层使用 TLS 1.3 配合证书锁定、密钥通过 Vault/KMS 动态获取且定期轮换（TTL < 24h）

5. **监控与响应：** 部署 eBPF/Falco 规则监控异常系统调用（`execve`、`connect` 到非预期 IP）、反序列化失败率超过阈值触发熔断（Circuit Breaker）、或使用 RASP（Runtime Application Self-Protection）拦截危险反射调用

6. **业务逻辑限制：** 反射调用结果仅用于只读查询或统计聚合（不修改状态）、存在人工审核流程（如配置变更需双人确认）、或攻击成功后因网络隔离（VPC/Security Group）无法横向移动或外传数据

7. **协议替代方案在途：** 代码已标记为 `// TODO: migrate to protobuf` 并有明确 roadmap（已分配工程资源和截止日期）、仅用于向后兼容旧客户端且 feature flag 控制流量占比 <5%、或已通过 `build tag` 仅在特定环境编译启用

**注意：** Go 的 `encoding/json` 配合反射虽然灵活，但用于处理不可信输入时极易引入漏洞。即使评为低风险，仍应推动团队采用：① 使用具体类型替代 `interface{}`；② 使用 JSON Schema 验证；③ 限制反射调用的方法白名单；④ 迁移到 Protocol Buffers/gRPC。务必全局搜索 `json.Unmarshal` + `reflect.` 的组合并逐一评估数据源可信度与调用链安全性。