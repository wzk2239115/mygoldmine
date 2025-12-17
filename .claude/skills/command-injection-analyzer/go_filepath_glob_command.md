# Go | filepath.Glob结果用于exec.Command漏洞

## 基本信息
- **难度等级：** ★★☆☆☆ (初级)
- **审计时间：** 15-20分钟

## 🚀 30秒快速清单
- [ ] 是否使用了filepath.Glob()或path/filepath包？
- [ ] glob结果是否直接用于exec.Command的参数？
- [ ] 是否验证了glob返回的文件路径？
- [ ] 是否使用了参数列表而非字符串拼接？

## Details

### 漏洞成因
Go的filepath.Glob()返回与模式匹配的文件路径列表。如果这些路径直接用于exec.Command的参数，特别是包含特殊字符的文件名，可能导致意外的命令执行或参数注入。此问题常见于需要批处理文件的应用中。

### 代码示例

```go
// 漏洞：glob结果直接用于命令参数
package main

import (
	"os/exec"
	"path/filepath"
)

func processLogs() error {
	// 获取所有日志文件
	files, err := filepath.Glob("/var/log/app/*.log")
	if err != nil {
		return err
	}

	for _, logFile := range files {
		// 问题：文件名中的特殊字符可能导致问题
		// 虽然exec.Command使用参数列表（相对安全）
		// 但仍需验证文件名
		cmd := exec.Command("gzip", "-9", logFile)
		cmd.Run()
	}

	return nil
}

func findAndExecute() error {
	// glob结果
	files, err := filepath.Glob("/data/*.txt")
	if err != nil {
		return err
	}

	// 问题：直接作为命令参数
	for _, file := range files {
		cmd := exec.Command("cat", file)
		cmd.Run()
	}

	return nil
}
```

### 快速定位核心操作
- **关键词扫描**：`filepath.Glob()`, `exec.Command()`, glob结果作为参数
- **Glob调用**：`filepath.Glob()`, `doublestar.Glob()`
- **命令执行**：glob结果直接用于exec.Command参数
- **缺少验证**：无对glob结果的验证

### 快速定位保护机制
- **路径验证**：验证glob结果不包含目录遍历（../）
- **白名单**：验证文件路径在允许的目录内
- **参数列表**：使用exec.Command的参数列表（已是安全的）
- **错误处理**：检查glob错误和不存在的文件

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **未验证glob结果**：直接使用glob返回的路径
2. **允许目录遍历**：glob结果包含../
3. **未检查路径有效性**：无对路径的验证

### 误报排除
- ✗ 验证glob结果不包含../
- ✗ 验证文件在允许的目录范围内
- ✗ 检查文件存在性和可访问性

---

## Low Risk

给予低风险评级的场景：
1. 验证所有glob结果的路径
2. 确保文件在预期目录范围内
3. 检查文件权限和存在性

---

## 安全实现

```go
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// 安全的glob处理
func processFilesSafe(pattern string, safeDir string) error {
	// 验证模式
	if !strings.Contains(pattern, safeDir) {
		return fmt.Errorf("pattern must be in safe directory")
	}

	// 执行glob
	files, err := filepath.Glob(pattern)
	if err != nil {
		return err
	}

	// 处理每个文件
	for _, file := range files {
		// 验证路径安全性
		if !isPathSafe(file, safeDir) {
			continue
		}

		// 执行命令
		cmd := exec.Command("gzip", "-9", file)
		if err := cmd.Run(); err != nil {
			fmt.Printf("Error processing %s: %v\n", file, err)
		}
	}

	return nil
}

// 验证路径安全性
func isPathSafe(filePath string, baseDir string) bool {
	// 检查目录遍历
	if strings.Contains(filePath, "..") {
		return false
	}

	// 检查路径是否在允许的目录范围内
	absPath, err := filepath.Abs(filePath)
	if err != nil {
		return false
	}

	absBase, err := filepath.Abs(baseDir)
	if err != nil {
		return false
	}

	return strings.HasPrefix(absPath, absBase)
}

// 安全的文件查找和处理
func findAndProcessSafe(directory string) error {
	// 验证目录
	if _, err := os.Stat(directory); err != nil {
		return err
	}

	// glob模式
	pattern := filepath.Join(directory, "*.txt")

	files, err := filepath.Glob(pattern)
	if err != nil {
		return err
	}

	for _, file := range files {
		// 验证文件存在性
		if _, err := os.Stat(file); err != nil {
			continue
		}

		// 执行命令（参数列表模式已很安全）
		cmd := exec.Command("cat", file)
		if err := cmd.Run(); err != nil {
			fmt.Printf("Error processing %s: %v\n", file, err)
		}
	}

	return nil
}
```

## 修复优先级

1. **立即修复（当天）**：验证glob结果不包含目录遍历
2. **快速修复（3天内）**：验证文件在允许的目录范围内
3. **短期改善（1周内）**：添加路径白名单验证
4. **长期改进（1个月）**：完整的文件访问控制
