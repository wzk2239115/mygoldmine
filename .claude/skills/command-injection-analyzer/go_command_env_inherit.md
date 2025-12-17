# Go | exec.Command环境变量继承漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] exec.Command是否继承了父进程的环境变量？
- [ ] 环境变量中是否存在用户可控的值？
- [ ] 是否调用了cmd.Env来清理或设置环境变量？
- [ ] 是否明确删除了危险环境变量（LD_PRELOAD等）？

## Details

### 漏洞成因
Go的exec.Command默认继承父进程的所有环境变量。如果父进程的环境变量（如PATH、LD_PRELOAD等）被攻击者污染，或应用在执行命令前未清理环境变量，可能导致任意代码执行。此问题常见于需要执行外部命令的应用中。

### 代码示例

```go
// 漏洞：exec.Command继承污染的环境变量
package main

import (
	"os/exec"
)

func executeCommand(cmdName string, args []string) error {
	// 问题：继承所有环境变量，包括被污染的PATH
	// 攻击者可设置 PATH=/tmp:/attacker/path
	cmd := exec.Command(cmdName, args...)
	return cmd.Run()
}

func compileCode(sourceFile string) error {
	// 问题：gcc会继承LD_PRELOAD环境变量
	// 攻击者可设置 LD_PRELOAD=/tmp/malicious.so
	cmd := exec.Command("gcc", "-o", "output", sourceFile)
	return cmd.Run()
}
```

### 快速定位核心操作
- **关键词扫描**：`exec.Command()`, `cmd.Run()`, `cmd.Output()`, 缺少 `cmd.Env`
- **命令执行**：直接使用exec.Command后无环境变量设置
- **缺少保护**：无cmd.Env或环境变量清理

### 快速定位保护机制
- **环境隔离**：`cmd.Env = []string{"PATH=/usr/bin:/bin"}`
- **明确设置**：完整指定必要的环境变量
- **删除危险变量**：避免LD_PRELOAD、JAVA_TOOL_OPTIONS等

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **未设置cmd.Env**：exec.Command后无cmd.Env赋值
2. **继承所有环境**：使用os.Environ()或不设置
3. **缺少环境验证**：无对环境变量的验证

### 误报排除
- ✗ 显式设置cmd.Env为安全的变量列表
- ✗ 仅包含必要的环境变量
- ✗ 删除所有危险变量

---

## Low Risk

给予低风险评级的场景：
1. 显式设置cmd.Env为受限的环境变量列表
2. 执行的命令使用绝对路径
3. 应用以受限用户账户运行

---

## 安全实现

```go
package main

import (
	"os"
	"os/exec"
)

// 安全的命令执行
func executeCommandSafe(cmdName string, args []string) error {
	cmd := exec.Command(cmdName, args...)

	// 显式设置环境变量（仅包含必要的）
	cmd.Env = []string{
		"PATH=/usr/bin:/bin",
		"HOME=/tmp/sandbox",
		"LANG=en_US.UTF-8",
	}

	return cmd.Run()
}

// 编译代码的安全实现
func compileCodeSafe(sourceFile string) error {
	cmd := exec.Command("/usr/bin/gcc", "-o", "output", sourceFile)

	// 清理环境变量
	cmd.Env = []string{
		"PATH=/usr/bin:/bin",
		"LANG=en_US.UTF-8",
	}

	return cmd.Run()
}
```

## 修复优先级

1. **立即修复（当天）**：设置cmd.Env为安全的环境变量列表
2. **快速修复（3天内）**：删除所有危险环境变量
3. **短期改善（1周内）**：验证执行的命令路径
4. **长期改进（1个月）**：使用受限用户账户运行应用
