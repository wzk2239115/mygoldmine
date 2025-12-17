# Go Content-Disposition 文件名注入

## Details

**审计等级：L1（关键词扫描）/ L2（跳读）**

**危险函数特征：**
- `w.Header().Set("Content-Disposition", value)` 直接设置
- 文件名直接拼接：`fmt.Sprintf("attachment; filename=%s", name)`
- 从文件系统或用户输入读取文件名

**快速定位核心操作：**
1. 搜索关键字：`Content-Disposition`、`filename=`、`attachment`
2. 追踪文件名来源：`Query().Get()`、`FormValue()`、文件路径
3. 检查是否使用双引号
4. 查看是否过滤特殊字符

**快速定位保护机制：**
- 特殊字符过滤：`strings.ReplaceAll()`
- 白名单验证：正则表达式检查
- URL 编码：`url.QueryEscape()`
- RFC 5987 编码：标准编码方式

**代码示例：**
```go
// 危险：用户文件名直接用于下载
func download(w http.ResponseWriter, r *http.Request) {
    filename := r.URL.Query().Get("file")
    w.Header().Set("Content-Disposition",
        fmt.Sprintf("attachment; filename=%s", filename))  // 危险
}

// 危险：Form 参数作为文件名
func export(w http.ResponseWriter, r *http.Request) {
    name := r.FormValue("export_name")
    header := "attachment; filename=" + name
    w.Header().Set("Content-Disposition", header)  // 危险
}

// 危险：路径参数
func serveFile(w http.ResponseWriter, r *http.Request) {
    fname := r.PathValue("name")
    w.Header().Set("Content-Disposition",
        fmt.Sprintf("attachment; filename=%s", fname))  // 危险
}
```

## Classify

**漏洞（High）：**
- 用户文件名未验证
- 文件名包含特殊字符导致头分割
- 允许目录遍历

**误报：**
- 文件名系统生成
- 经过白名单验证
- 使用安全方法

**代码异味（Medium）：**
- 仅过滤部分字符
- 黑名单不完整
- 间接来源

## Low risk

**以下情况评为低风险：**
- 文件名硬编码
- 严格白名单验证
- RFC 合规编码
- 内部来源且已验证

## SKILL - 审计专业技巧

### 1. 源头追踪分析

**关键追踪点：**
- 外部输入源识别：`Query().Get()`, `FormValue()`, `PostFormValue()`, `Header().Get()`, `PathValue()`
- 间接输入源：数据库查询结果、缓存内容（需检查数据如何入库）
- 日志/用户数据：用户上传的文件名、导入的数据

**实际案例：**
```go
// 案例1：中等风险 - 数据库源
func downloadFile(w http.ResponseWriter, r *http.Request) {
    fileID := r.URL.Query().Get("id")
    file := db.GetFile(fileID)  // 数据库查询
    // 风险评估：取决于file.Name如何入库
    // - 若用户上传时未验证 → HIGH
    // - 若系统生成 → LOW
    w.Header().Set("Content-Disposition",
        "attachment; filename="+file.Name)
}

// 案例2：真实漏洞 - 多步拼接隐蔽性
func exportData(w http.ResponseWriter, r *http.Request) {
    format := r.URL.Query().Get("fmt")
    filename := "export_" + format  // 看似安全的拼接
    w.Header().Set("Content-Disposition",
        fmt.Sprintf("attachment; filename=%s", filename))
    // 攻击：fmt=data.csv%0dSet-Cookie: admin=1
    // 结果：文件名变为 export_data.csv\r 导致头注入
}
```

### 2. 特殊字符检测模式

**需要严格控制的字符集：**

| 字符 | 十进制 | 风险等级 | 说明 |
|------|--------|---------|------|
| `\r` | 13 | CRITICAL | HTTP头分割（回车） |
| `\n` | 10 | CRITICAL | HTTP头分割（换行） |
| `"` | 34 | HIGH | 破坏文件名边界 |
| `;` | 59 | HIGH | 破坏Content-Disposition参数 |
| `,` | 44 | MEDIUM | 分割多个值 |
| `\0` | 0 | HIGH | 字符串截断 |
| `%` | 37 | MEDIUM | 可能导致双编码 |

**检查方式：**
```go
// 错误示范：不完全的过滤
func badFilter(filename string) string {
    // 仅过滤\r\n，忽略了其他注入向量
    return strings.ReplaceAll(filename, "\r", "")
}

// 正确示范：RFC 5987合规编码
func safeFilename(filename string) string {
    // RFC 5987: filename*=UTF-8''[编码值]
    return fmt.Sprintf("attachment; filename*=UTF-8''%s",
        url.QueryEscape(filename))
}
```

### 3. 真实漏洞 vs 误报区分

**真实漏洞特征（High Risk）：**
1. **直接拼接且无检验**
   ```go
   w.Header().Set("Content-Disposition", "attachment; filename="+userInput)
   // 红旗：直接字符串操作，无任何过滤
   ```

2. **仅过滤部分字符**
   ```go
   safe := strings.ReplaceAll(userInput, "\r\n", "")
   w.Header().Set("Content-Disposition", "attachment; filename="+safe)
   // 红旗：遗漏了双引号、分号等，存在字符编码绕过风险
   ```

3. **虚假编码保护**
   ```go
   encoded := base64.StdEncoding.EncodeToString([]byte(userInput))
   w.Header().Set("Content-Disposition", "attachment; filename="+encoded)
   // 风险：base64不是HTTP头部的安全编码方式
   // Content-Disposition: attachment; filename=dXNlcj1hZG1pbg==
   // 仍可能被解析为特殊字符
   ```

**误报特征（Low Risk）：**
1. **严格白名单**
   ```go
   fileID := r.URL.Query().Get("id")
   if matched, _ := regexp.MatchString(`^\d{1,10}$`, fileID); !matched {
       http.Error(w, "Invalid ID", 400)
       return
   }
   file := files[fileID]  // 从预定义Map获取
   w.Header().Set("Content-Disposition", "attachment; filename="+file.Name)
   // 安全：通过ID间接访问，ID本身经过严格验证
   ```

2. **系统生成的文件名**
   ```go
   filename := fmt.Sprintf("report_%d_%s.pdf",
       time.Now().Unix(), uuid.New().String())
   w.Header().Set("Content-Disposition", "attachment; filename="+filename)
   // 安全：由系统生成，不含用户输入
   ```

3. **RFC 5987标准编码**
   ```go
   filename := r.URL.Query().Get("name")
   escaped := fmt.Sprintf("UTF-8''%s",
       net.QueryEscape(filename))
   w.Header().Set("Content-Disposition",
       fmt.Sprintf("attachment; filename*=%s", escaped))
   // 安全：遵循RFC标准的百分比编码
   ```

### 4. 审计检查清单

**代码审计顺序：**

- [ ] **第1步：确认数据流向**
  - 文件名来自哪个API/函数？
  - 是否可跟踪到原始数据源？
  - 若来自数据库，检查入库时是否验证

- [ ] **第2步：检查过滤策略**
  - 是否存在任何过滤？(无过滤=HIGH RISK)
  - 过滤列表是白名单还是黑名单？
  - 是否使用了标准库的安全函数？

- [ ] **第3步：验证编码方式**
  - 是否使用RFC 5987编码？
  - URL编码的实现是否正确？
  - 是否使用了不恰当的编码方式？

- [ ] **第4步：环境上下文**
  - WAF/反向代理是否有额外保护？
  - 浏览器版本是否影响漏洞可利用性？
  - 是否有其他防护措施（如CSP）？

### 5. 误报常见场景

**容易被误报为HIGH的低风险代码：**

```go
// 场景1：从已验证的特定来源获取
func downloadTemplate(w http.ResponseWriter, r *http.Request) {
    templateName := r.URL.Query().Get("name")
    // 实际上：名称受mux约束或早期验证已过滤
    // Content-Disposition: attachment; filename=template_report.xlsx
    // 风险等级：LOW（仅限已授权的模板）
}

// 场景2：多层防护的组合
func exportUserData(w http.ResponseWriter, r *http.Request) {
    userID := getCurrentUserID(r)  // 认证用户
    filename := db.GetUserFileName(userID)

    // 额外防护层：Content-Security-Policy + X-Content-Type-Options
    w.Header().Set("X-Content-Type-Options", "nosniff")
    w.Header().Set("Content-Type", "application/octet-stream")
    w.Header().Set("Content-Disposition", "attachment; filename="+filename)
    // 风险评估：LOW（用户数据 + 多层防护）
}
```

### 6. 实战经验总结

**常见误区：**
1. ❌ 认为`url.QueryEscape`可直接用于Content-Disposition（需RFC 5987包装）
2. ❌ 仅检查是否包含`\r\n`而忽略其他字符（需完整列表）
3. ❌ 信任数据库数据而不追踪入库来源（数据库非安全边界）
4. ❌ 混淆URL编码和HTTP头编码（两者不同）

**正确的安全编码实现参考：**
```go
import (
    "fmt"
    "net/url"
    "strings"
)

func SetSafeContentDisposition(w http.ResponseWriter, filename string) {
    // RFC 5987编码：推荐方式
    header := fmt.Sprintf("attachment; filename*=UTF-8''%s",
        url.QueryEscape(filename))
    w.Header().Set("Content-Disposition", header)
}
```
