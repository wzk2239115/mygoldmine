# Go 配置文件表达式注入

**漏洞成因**：Go 应用在加载配置文件时，部分配置解析库（如 YAML 的某些实现）可能支持表达式求值或动态执行功能。当应用加载用户可控的配置文件时，攻击者可构造恶意配置注入代码、执行系统命令或修改应用行为。虽然 Go 标准库的配置解析相对安全，但第三方库和自定义解析逻辑可能存在风险。常见于配置文件加载、环境变量解析、动态配置管理等场景。

---

## Details

**代码示例**：
```go
// 危险：加载用户可控的配置文件
package main
import (
    "gopkg.in/yaml.v2"
    "io/ioutil"
    "net/http"
)

func loadConfig(w http.ResponseWriter, r *http.Request) {
    file, _ := r.FormFile("config")
    configData, _ := ioutil.ReadAll(file)

    var config map[string]interface{}
    yaml.Unmarshal(configData, &config) // 危险：解析用户上传的配置文件
}

// 危险：使用支持表达式的配置库
// 某些 YAML 库可能支持标签或引用，导致代码执行

// 危险：使用 os/exec 执行配置中的命令
import "os/exec"
command := config["command"].(string) // 配置值来自用户输入
cmd := exec.Command("sh", "-c", command) // 危险：执行配置中的命令
cmd.Run()

// 危险：使用 plugin 包动态加载配置中指定的插件
import "plugin"
pluginPath := config["plugin"].(string) // 用户可控的插件路径
p, _ := plugin.Open(pluginPath) // 危险：加载任意插件
symbol, _ := p.Lookup("Execute")
symbol.(func())()

// 较安全：仅从可信路径加载配置文件
configPath := "/etc/myapp/config.yaml" // 硬编码路径
configData, _ := ioutil.ReadFile(configPath)
yaml.Unmarshal(configData, &config)

// 较安全：验证配置文件的签名
if !verifySignature(configData, signature) {
    return errors.New("Invalid config signature")
}

// 较安全：使用 JSON 而非 YAML，避免标签和引用
import "encoding/json"
json.Unmarshal(configData, &config) // JSON 不支持代码执行

// 较安全：对配置值进行类型和范围验证
if command, ok := config["command"].(string); ok {
    if !isAllowedCommand(command) {
        return errors.New("Invalid command")
    }
}
```

**快速定位核心操作**：
- 关键词：`yaml.Unmarshal`、`json.Unmarshal`、`ioutil.ReadFile`、`plugin.Open`、`exec.Command`
- 查找配置文件的加载和解析位置
- 追踪配置文件的来源，判断是否可被用户控制
- 检查是否使用了 YAML 或其他支持复杂特性的格式
- 关注配置值的使用：是否用于命令执行、文件操作、插件加载
- 搜索 `go.mod` 中的配置解析库依赖

**快速定位保护机制**：
- 配置文件是否仅从可信的文件系统路径加载
- 是否对配置文件进行签名验证
- 是否使用 JSON 而非 YAML 等支持复杂特性的格式
- 是否对配置值进行类型和范围验证
- 是否限制了配置文件的上传和修改权限
- 是否避免在配置中直接执行命令或加载插件
- Go 版本和第三方库版本是否为最新稳定版

**审计等级**：**L2-L3**
- **L2**：跳读配置加载代码，识别配置来源和格式
- **L3**：逐行验证配置解析和使用方式，确认安全措施

---

## Classify

**确认为漏洞**：
- 加载用户可控的配置文件（如文件上传）
- 配置文件使用 YAML 且可能支持危险的标签或引用
- 配置值直接用于命令执行、插件加载等危险操作
- 未对配置文件进行签名验证或完整性检查
- 配置解析库存在已知的安全漏洞

**误报**：
- 配置文件仅从可信的文件系统路径加载且权限受限
- 使用 JSON 或其他安全的配置格式
- 对配置值进行了严格的类型和范围验证
- 配置文件经过签名验证，确保未被篡改
- 配置值不用于危险操作（仅用于数据配置）

**代码异味**：
- 配置文件路径或名称由用户输入决定
- 使用 YAML 解析复杂的嵌套结构
- 配置值直接用于系统调用或文件操作
- 缺乏对配置文件的完整性验证

---

## Low Risk

以下情况可评为低风险：
- **可信来源**：配置文件仅从可信的文件系统路径加载且权限受限
- **安全格式**：使用 JSON 或 TOML 等不支持代码执行的格式
- **签名验证**：配置文件经过数字签名验证，确保未被篡改
- **值验证**：对所有配置值进行类型、范围和白名单验证
- **最小权限**：应用进程以最小权限运行，限制文件和系统访问
- **内网应用**：应用仅在内网部署，配置文件由管理员维护
- **日志监控**：所有配置文件加载操作均记录日志并监控异常

**注意**：Go 的配置解析相对安全，但仍需确保配置文件来自可信来源，并对配置值进行验证，避免用于危险操作。
