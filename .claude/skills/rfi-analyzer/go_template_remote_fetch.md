# Go 远程模板拉取导致 RFI

## Details

### 代码示例
```go
// 典型漏洞模式：从用户输入获取 URL，下载远程模板并执行
func fetchTemplate(templateURL string) error {
    resp, err := http.Get(templateURL)  // 未校验 URL 来源
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    
    tmpFile, _ := ioutil.TempFile("", "template-*.tpl")  // 临时文件路径可预测
    defer os.Remove(tmpFile.Name())
    
    io.Copy(tmpFile, resp.Body)  // 直接写入响应内容
    
    // 执行模板或脚本
    tmpl, _ := template.ParseFiles(tmpFile.Name())
    tmpl.Execute(os.Stdout, data)  // 或使用 exec.Command 等执行
    return nil
}
```

### 快速定位核心操作技巧（L2：跳读）
- **HTTP 客户端调用**：搜索 `http.Get`、`http.Post`、`http.DefaultClient.Do`、第三方 HTTP 库（`resty`、`grequests`）
- **文件写入操作**：关注 `ioutil.TempFile`、`os.Create`、`os.WriteFile` 与 HTTP 响应体的组合
- **执行操作**：查找 `template.Parse*`、`exec.Command`、`plugin.Open`、`unsafe` 包、`reflect.Call`
- **数据流追踪**：从 HTTP Handler 参数（`r.URL.Query`、`r.FormValue`、`r.PostForm`）到网络请求的完整链路

### 快速定位保护机制技巧（L1：关键词扫描）
- **URL 白名单**：`strings.HasPrefix`、`url.Parse` 后检查 `Host`、正则匹配域名
- **协议限制**：检查 `scheme == "https"` 或拒绝 `file://`、`ftp://`
- **重定向控制**：自定义 `http.Client` 的 `CheckRedirect`
- **内容类型校验**：`resp.Header.Get("Content-Type")`、魔数检测
- **路径规范化**：`filepath.Clean`、`filepath.Abs`、`strings.Contains("..")`
- **沙箱执行**：容器化、`syscall.Chroot`、资源限制

## Classify

**漏洞确认条件**：
1. URL 参数来自外部输入（HTTP 请求、配置文件、数据库、消息队列）
2. 缺少 URL 来源校验或校验可绕过（如仅检查协议、Host 解析错误、SSRF 绕过）
3. 下载内容直接写入文件系统并执行（模板解析、命令执行、动态加载）

**误报判定**：
- URL 硬编码在代码中且不可变
- URL 从受信任的内部配置管理系统获取且具备严格的变更审计
- 下载内容仅用于数据存储，不涉及解析或执行逻辑

**代码异味**：
- URL 从配置文件读取但缺少运行时校验
- 存在白名单但规则过于宽松（如 `*.com` 通配符）
- 临时文件权限过大（644/755）或路径可预测
- 缺少下载大小限制和超时控制

## Low risk

**低风险场景**（仍需记录但可降低优先级）：
1. **执行环境隔离**：在只读容器、无网络权限的沙箱、或严格 SELinux/AppArmor 策略下执行
2. **影响面受限**：仅内网服务可访问且网络已分段隔离，外部攻击者无法触达
3. **内容强校验**：下载后进行数字签名验证、哈希比对、或结构化校验（如 JSON Schema）
4. **非直接执行**：下载内容仅用于静态分析、日志记录、或需人工审核后才能执行
5. **短期过渡方案**：代码注释标注为待重构，且存在工单跟踪和明确的下线时间表