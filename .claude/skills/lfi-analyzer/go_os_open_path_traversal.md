# Go os.Open/ioutil 路径遍历与文件包含

## Details

### 漏洞成因

Go 应用使用 `os.Open()`、`ioutil.ReadFile()`、`os.ReadFile()`、`filepath.Join()` 等函数读取文件时，若直接将用户输入拼接到文件路径而未做路径规范化和白名单验证，攻击者可利用 `../` 相对路径实现目录遍历，访问应用目录外的敏感文件。此漏洞常见于 Web 服务器、文件服务接口、日志查看、配置读取等功能。

### 代码示例

**易受攻击的代码（文件下载）：**
```go
package main

import (
	"net/http"
	"os"
	"path/filepath"
)

func downloadFile(w http.ResponseWriter, r *http.Request) {
	filename := r.URL.Query().Get("file")  // file=../../etc/passwd
	filePath := filepath.Join("uploads", filename)

	file, err := os.Open(filePath)
	if err != nil {
		http.Error(w, "Not found", 404)
		return
	}
	defer file.Close()

	// 发送文件内容
	http.ServeContent(w, r, filename, time.Time{}, file)
}
```

**使用 ioutil 版本：**
```go
import "io/ioutil"

func readFile(w http.ResponseWriter, r *http.Request) {
	filename := r.URL.Query().Get("name")  // name=../../config.json
	filePath := "data/" + filename

	content, err := ioutil.ReadFile(filePath)
	if err != nil {
		http.Error(w, "Error", 500)
		return
	}
	w.Write(content)
}
```

**日志查看接口：**
```go
func viewLog(w http.ResponseWriter, r *http.Request) {
	logName := r.FormValue("log")  // log=../../var/log/syslog
	logPath := filepath.Join("/var/log/app", logName)

	content, err := os.ReadFile(logPath)
	if err != nil {
		http.Error(w, "Error", 500)
		return
	}
	w.Write(content)
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）

**关键词扫描：**
- 文件打开：`os.Open()`, `os.ReadFile()`, `ioutil.ReadFile()`, `ioutil.ReadDir()`
- 文件写入：`os.Create()`, `os.OpenFile()`, `ioutil.WriteFile()`
- 路径操作：`filepath.Join()`, `filepath.Clean()`, `path.Join()`
- 服务文件：`http.ServeFile()`, `http.ServeContent()`, `http.FileServer()`
- 输入源：`r.URL.Query()`, `r.FormValue()`, `r.Header.Get()`, `os.Args`

**定位步骤：**
1. 搜索 `os.Open`、`os.ReadFile`、`filepath.Join` 等函数调用。
2. 检查这些调用的参数是否包含变量，特别是来自 HTTP 请求的变量。
3. 追踪变量的来源：URL 参数、表单数据、请求头。
4. 确认是否有过滤或验证逻辑。

#### 保护机制定位（审计等级：L2-L3）

**检查是否存在：**
- **路径规范化：** `filepath.Clean()`, `filepath.Abs()`, `filepath.EvalSymlinks()`
- **前缀校验：** 规范化后检查 `strings.HasPrefix()` 基础目录
- **白名单验证：** 将用户输入与已知安全文件列表对比
- **路径分隔符检查：** 禁止 `..` 等危险字符
- **符号链接检查：** `os.Lstat()` 检测符号链接

**定位技巧：**
- 确认 `filepath.Clean()` 返回值是否真实用于后续操作。
- 检查 `filepath.Join()` 的参数顺序，若用户输入为绝对路径会覆盖基础目录。
- 验证符号链接处理：使用 `filepath.EvalSymlinks()` 后是否检查最终路径。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 白名单映射 | **L0（快速跳过）** | 用户输入仅为键值 |
| `filepath.Clean()` + 前缀校验 | **L2（跳读）** | 确认校验逻辑完备 |
| 直接拼接用户输入 | **L3（逐行读）** | 极高风险 |
| 符号链接 + 目录遍历 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞

满足以下条件判定为漏洞：
1. **用户可控路径** 用于文件读取或访问。
2. **缺乏有效防护**（无路径规范化、白名单、符号链接检查）。
3. **能够访问敏感资源**（读取配置、密钥、系统文件）。

#### 误报

可视为误报的情况：
1. **输入仅用于索引白名单字典**，返回固定文件。
2. **使用 `filepath.Clean()` 和 `strings.HasPrefix()` 进行前缀校验**。
3. **使用固定常量拼接路径，不受用户输入影响**。

#### 代码异味

需记录的潜在问题：
1. **使用 `filepath.Join()` 但用户输入为绝对路径**，会覆盖基础目录。
2. **字符串替换而非规范化**（如 `strings.ReplaceAll(path, "..", "")` 可被双层绕过）。
3. **符号链接未检查**，攻击者可创建符号链接绕过目录限制。
4. **异常处理泄露路径信息**，错误消息显示尝试的路径。

## Low risk

### 低风险评级场景

#### 1. 受控后台操作

- **场景：** 功能仅对管理员开放，认证与授权完善。
- **风险评估：** 外部攻击面小，但需防止账号滥用。

#### 2. 白名单保护 + 路径规范化

- **场景：** 使用 `filepath.Clean()` 规范化路径，检查 `strings.HasPrefix()` 前缀，且白名单完整。
- **风险评估：** 防护有效，但需确认白名单覆盖所有包含点。

#### 3. 容器/沙箱隔离

- **场景：** 应用运行在限制权限的容器中，访问目录层级有限。
- **风险评估：** 限制破坏面，但建议修复代码根本问题。

#### 4. 只读公开目录

- **场景：** 仅访问公开静态资源，无敏感信息。
- **风险评估：** 危害有限，但仍可能泄露目录结构。

### 风险降级条件总结

| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理员限定 | 攻击面小 | 中 |
| `filepath.Clean()` + 前缀校验 | 有效防护 | 低 |
| 符号链接检查 + 白名单 | 深度防御 | 低 |
| 容器/沙箱运行 | 限制影响面 | 高（持续跟进修复）|
