# Go 动态插件加载本地文件包含

## Details

### 漏洞成因

Go 应用使用 `plugin.Open()` 动态加载编译的 Go 插件（`.so` 文件）时，若插件路径由用户输入控制且未做白名单验证，攻击者可加载任意编译的恶意插件实现远程代码执行。此漏洞常见于模块化应用框架、插件系统、动态功能加载等场景。与脚本语言不同，Go 插件加载的风险在于加载恶意的 `.so` 文件会直接执行其中的代码。

### 代码示例

**易受攻击的代码（动态插件加载）：**
```go
package main

import (
	"net/http"
	"plugin"
)

func loadPlugin(w http.ResponseWriter, r *http.Request) {
	pluginName := r.URL.Query().Get("plugin")  // plugin=../../evil.so
	pluginPath := "plugins/" + pluginName + ".so"

	p, err := plugin.Open(pluginPath)
	if err != nil {
		http.Error(w, "Plugin not found", 404)
		return
	}

	// 加载插件中的函数
	symb, err := p.Lookup("Execute")
	if err != nil {
		http.Error(w, "Function not found", 404)
		return
	}

	execute := symb.(func())
	execute()  // 执行插件代码
}
```

**无验证的插件路径：**
```go
import "plugin"

func InitializePlugin(pluginPath string) error {
	// pluginPath = "../../../lib/evil.so"
	p, err := plugin.Open(pluginPath)
	if err != nil {
		return err
	}

	symb, _ := p.Lookup("Init")
	init := symb.(func() error)
	return init()
}
```

**配置文件指定插件路径：**
```go
import (
	"encoding/json"
	"plugin"
)

type Config struct {
	PluginPath string `json:"plugin_path"`
}

func LoadConfiguredPlugin(configData []byte) error {
	var cfg Config
	json.Unmarshal(configData, &cfg)

	// cfg.PluginPath = "../../evil.so"
	p, err := plugin.Open(cfg.PluginPath)
	if err != nil {
		return err
	}

	symb, _ := p.Lookup("Run")
	run := symb.(func() error)
	return run()
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L3）

**关键词扫描：**
- 插件操作：`plugin.Open()`, `p.Lookup()`, `plugin.Symbol`
- 动态加载：任何涉及 `plugin.Open()` 的代码
- 路径构造：`filepath.Join()`, 字符串拼接 + `plugin.Open()`
- 配置加载：`json.Unmarshal()`, `yaml.Unmarshal()` 中的路径字段
- 输入源：`r.URL.Query()`, `r.FormValue()`, 配置文件, 数据库

**定位步骤：**
1. 搜索 `plugin.Open()` 调用。
2. 检查 `plugin.Open()` 的参数是否包含变量。
3. 追踪变量的来源：HTTP 请求、配置文件、数据库。
4. 确认是否有白名单验证或路径检查。

#### 保护机制定位（审计等级：L2-L4）

**检查是否存在：**
- **白名单验证：** 允许加载的插件列表（必需）
- **路径规范化：** `filepath.Clean()`, `filepath.Abs()` 规范化路径
- **前缀校验：** 规范化后检查 `strings.HasPrefix()` 固定目录
- **符号链接检查：** `os.Lstat()` 检测符号链接
- **文件权限检查：** 确保插件文件仅由管理员可写

**定位技巧：**
- 白名单是必需的，仅依赖路径规范化不够安全。
- 验证 `filepath.Join()` 的参数顺序，用户输入为绝对路径会覆盖。
- 检查符号链接是否被检查，`os.Lstat()` 可检测链接。
- 验证加载插件的时机和权限，确保只有授权操作可加载。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单 + 固定扩展名 | **L0（快速跳过）** | 用户输入仅为键值 |
| 白名单 + 路径规范化 | **L1（快速扫描）** | 验证白名单完整性 |
| 直接拼接用户输入 | **L3（逐行读）** | 极高风险 |
| 无验证的插件加载 | **L4（跨模块追踪）** | 远程代码执行 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **插件路径由用户输入控制**。
2. **缺乏白名单验证**，允许加载任意路径的插件。
3. **能够加载恶意插件导致代码执行**。

#### 误报

可视为误报的情况：
1. **插件名称仅用于索引白名单数组**，返回固定插件。
2. **路径经过规范化并检查前缀，且白名单完整**。
3. **插件仅由管理员上传，路径不受外部输入影响**。

#### 代码异味

需记录的潜在问题：
1. **字符串过滤而非白名单**（如 `strings.ReplaceAll(path, "..", "")` 可被绕过）。
2. **白名单不完整或来自可写的配置文件**。
3. **符号链接未检查**，可指向任意 `.so` 文件。
4. **插件文件权限过宽**，普通用户可修改插件文件。
5. **错误处理泄露信息**，异常消息显示加载路径。

## Low risk

### 低风险评级场景

#### 1. 严格的白名单 + 固定扩展名

- **场景：** 只允许加载预定义插件列表，且强制 `.so` 扩展名。
- **风险评估：** 防护有效，但需定期审查白名单，确保插件文件权限正确。

#### 2. 受限加载目录 + 路径规范化

- **场景：** 插件只能从固定目录加载，使用 `filepath.Clean()` + `strings.HasPrefix()` 验证。
- **风险评估：** 防护层次清晰，但需验证规范化逻辑。

#### 3. 受控后台操作

- **场景：** 插件加载功能仅对管理员开放，需要多重认证。
- **风险评估：** 攻击面小，但管理员账号泄露仍会导致 RCE。

#### 4. 本地开发环境

- **场景：** 插件系统仅在本地开发环境使用，不在生产部署。
- **风险评估：** 生产风险为零，但开发环境应有最小权限。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 严格的插件白名单 | 限制加载范围 | 低 |
| 路径规范化 + 符号链接检查 | 深度防御 | 低 |
| 管理员限定 | 攻击面小 | 中 |
| 仅开发环境 | 生产无风险 | 低 |
