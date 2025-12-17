# Go - HTTP 处理器中缺失 CSP 响应头

## Details

**代码示例及风险特征：**

```go
// 漏洞模式 1：原生 net/http 处理器未设置 CSP 头
package main

import (
	"net/http"
)

func handleLogin(w http.ResponseWriter, r *http.Request) {
	// 直接渲染 HTML，未设置任何 CSP 相关响应头
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(`<html>
		<head><title>登陆</title></head>
		<body>
			<form method="post">
				<input name="username" />
				<input name="password" type="password" />
				<button>登陆</button>
			</form>
			<script>
				// 若用户数据未正确转义，可被注入恶意脚本
				console.log("User agent: " + navigator.userAgent);
			</script>
		</body>
	</html>`))
}

// 漏洞模式 2：多个路由分别处理，每个都缺失 CSP
func handleUserProfile(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html")
	// 缺失 CSP 头
	w.Write([]byte("<html>...</html>"))
}

func handleDashboard(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html")
	// 缺失 CSP 头
	w.Write([]byte("<html>...</html>"))
}

func main() {
	http.HandleFunc("/login", handleLogin)
	http.HandleFunc("/profile", handleUserProfile)
	http.HandleFunc("/dashboard", handleDashboard)
	http.ListenAndServe(":8080", nil)
}

// 漏洞模式 3：使用 http.ServeFile 提供 HTML，未设置响应头
func handleStaticHTML(w http.ResponseWriter, r *http.Request) {
	// 直接提供静态 HTML 文件，不设置安全响应头
	http.ServeFile(w, r, "public/index.html")
}

// 漏洞模式 4：模板渲染未添加 CSP 保护
import "html/template"

func handleTemplatePage(w http.ResponseWriter, r *http.Request) {
	tmpl := template.Must(template.ParseFiles("page.html"))
	// 缺失 CSP 头，模板中可能有用户输入
	tmpl.Execute(w, map[string]interface{}{
		"username": r.URL.Query().Get("user"),
	})
}

// 漏洞模式 5：自定义路由器（如 gorilla/mux）未全局设置 CSP
import "github.com/gorilla/mux"

func setupRouter() *mux.Router {
	router := mux.NewRouter()
	router.HandleFunc("/api/users", handleUsers)
	router.HandleFunc("/page", handlePage)
	// 仅在各处理器中设置，不在全局中间件层设置，容易遗漏
	return router
}

func handlePage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html")
	w.Write([]byte("<html>...</html>"))  // 缺失 CSP
}
```

### 快速定位核心操作 **L1: 关键词扫描**

| 关键词/特征 | 风险等级 | 说明 |
|-----------|---------|------|
| `w.Write()` / `w.WriteString()` + HTML | 🔴 高 | 返回 HTML 内容但未设置 CSP |
| `http.HandleFunc()` 处理 HTML 路由 | 🔴 高 | 原生路由处理，易遗漏 CSP 头 |
| `http.ServeFile()` 提供 `.html` 文件 | 🔴 高 | 静态 HTML 服务无默认 CSP |
| `template.Execute(w, ...)` 渲染模板 | 🔴 高 | 模板渲染结果未设置 CSP 头 |
| `mux.HandleFunc()` / `gin.GET()` / `echo.GET()` + HTML | 🔴 高 | 第三方路由器处理 HTML 路由 |
| `w.Header().Set("Content-Type", "text/html")` | 🟠 中 | 明确返回 HTML，**必须** 配合 CSP 头 |
| 仅在某些路由设置 CSP 头 | 🔴 高 | 部分路由保护，其他路由无防护 |
| 使用了中间件但未在中间件中设置 CSP | 🟡 中 | 中间件框架可用，但未充分利用 |

### 快速定位保护机制 **L2: 跳读 + L3: 逐行读**

| 检查项 | 审计等级 | 关键代码特征 |
|--------|---------|------------|
| **全局中间件设置 CSP** | **L2** | `net/http` 的 `http.HandlerFunc` 包装函数；`gin.Use(cspMiddleware)`；`echo.Use(cspMiddleware)` |
| **原生 net/http 的 ServeHTTP 实现** | **L2** | 自定义 `Handler` 实现 `ServeHTTP(w ResponseWriter, r *Request)` 接口，在其中设置 CSP |
| **CSP 头的设置位置** | **L2** | `w.Header().Set("Content-Security-Policy", "...")` 出现在所有返回 HTML 的路由前 |
| **ContentType 检查** | **L3** | 检查 `Content-Type: text/html` 的路由是否都有对应的 CSP 响应头 |
| **路由枚举** | **L3** | 遍历所有 `http.HandleFunc()`、`router.Handle()` 调用，识别返回 HTML 的路由 |
| **中间件顺序** | **L3** | CSP 设置中间件是否在其他中间件之前（确保不被覆盖） |
| **条件设置** | **L3** | 检查是否存在条件逻辑（如 `if path == "/admin" { 设置 CSP }`），确保无遗漏 |
| **跨中间件追踪** | **L4** | 追踪响应写入流程，检查是否存在多个中间件竞争响应头写入的情况 |
| **ResponseWriter 的 WriteHeader 时机** | **L4** | 确保 CSP 头设置在 `w.WriteHeader()` 或首次 `w.Write()` 之前 |

---

## Classify

### 真漏洞判定

对以下特征之一的存在表示确定性漏洞，需要立即修复：

1. **完全缺失 CSP 响应头**
   - HTTP 响应中完全没有 `Content-Security-Policy` 或 `Content-Security-Policy-Report-Only` 响应头
   - 返回的响应 `Content-Type` 为 `text/html` 但无 CSP 头
   - 在浏览器开发者工具中检查网络响应，所有 HTML 页面响应都缺失 CSP 头

2. **部分路由缺失 CSP 响应头**
   - 只有部分路由（如 `/admin`）设置了 CSP，其他路由（如 `/user/profile`、`/page`）未设置
   - 同一应用的不同端点有不一致的 CSP 策略设置
   - 攻击者可从未保护的路由注入脚本，绕过部分 CSP 防护

3. **中间件未生效导致路由无保护**
   - 代码中定义了 CSP 中间件，但因中间件注册不正确、顺序错误或条件判断有漏洞而未生效
   - 检查中间件是否真正被应用到所有 HTML 返回路由
   - 中间件中的 CSP 设置被后续中间件或处理器覆盖

4. **仅使用 Report-Only 模式**
   - 生产环境中仅使用 `Content-Security-Policy-Report-Only` 响应头
   - CSP 违规被记录但脚本仍被执行，无实际防护效果

5. **CSP 策略过于宽松**
   - 设置了 CSP 头，但指令为 `script-src *` 或 `default-src *` 等宽松配置
   - 等同于未设置有效的 CSP

### 误报排除标准

以下情况视为低风险或误报，不应作为严重漏洞上报：

1. **纯 API 后端**
   - 应用仅返回 JSON/XML 等数据，不返回 HTML
   - 即使缺失 CSP 头，也不会存在脚本注入风险

2. **所有 HTML 都由前端框架处理**
   - 后端仅作为 API，HTML 由客户端 SPA 框架（React、Vue 等）生成
   - 后端响应为数据，不需要 CSP 头

3. **内容完全静态**
   - 应用仅提供静态文件（如通过 `http.FileServer`）
   - 不包含任何动态 HTML 生成

4. **只有特定路由需要 CSP**
   - 应用有明确的业务需求：仅某些路由返回用户输入相关的 HTML
   - 其他路由为数据响应或静态内容，确实无需 CSP

### 代码异味（需关注）

以下特征不直接构成漏洞，但指示风险，需进一步审查：

1. **中间件框架但未充分利用**
   - 使用了 Gin、Echo 等框架，但 CSP 设置分散在各个处理器中
   - 应集中在中间件中管理，避免遗漏

2. **有条件的 CSP 设置**
   - CSP 设置存在条件判断（如 `if isProduction { 设置 CSP }`）
   - 生产环境应该无条件设置

3. **注释中提到 CSP 但未实现**
   - 代码注释中有 "TODO: Add CSP" 或 "需要设置 CSP"
   - 表示开发者意识到需要，但尚未实现

4. **错误处理路由未设置 CSP**
   - 错误页面（404、500 等）返回 HTML 但无 CSP
   - 攻击者可通过触发错误页面来注入脚本

5. **文件上传/下载 API 返回 HTML**
   - 某些文件处理端点在错误时返回 HTML，未设置 CSP
   - 可被用于 XSS 攻击

---

## Low risk

### 低风险评级条件

满足以下 **条件组合** 的场景可以降级为低风险：

#### 1. 全局中间件完全覆盖所有 HTML 路由

**条件：** 同时满足以下三点
- 在应用入口（`main` 函数或路由初始化处）统一注册了设置 CSP 的中间件或 `Handler` 包装
- 已验证所有返回 HTML 的路由都被该中间件覆盖（通过代码审查或测试）
- CSP 策略本身安全（不使用 `unsafe-inline`、`unsafe-eval`、通配符等）

**风险降级依据：** 虽然个别处理器代码中未显式设置，但全局中间件确保了防护的一致性和完整性

#### 2. 明确的技术架构划分

**条件：** 同时满足以下两点
- 应用架构明确分离：后端仅提供 API（JSON 响应），HTML 生成完全由前端处理
- 已验证后端所有路由的 `Content-Type` 均为 `application/json` 或其他非 HTML 类型

**风险降级依据：** 后端不返回 HTML，不存在 CSP 防护缺失的风险

#### 3. 框架级自动化防护

**条件：** 满足以下 **至少 2 项**
- 使用了经过安全审计的框架或库（如支持自动 CSP 的 middleware），版本最新且无已知 CVE
- 框架文档明确说明其自动添加 CSP 功能
- 通过框架配置文件（如 `config.yaml`）声明启用了 CSP 保护

**风险降级依据：** 框架承担安全责任，社区维护确保防护有效

#### 4. 业务上下文的低敏感性

**条件：**
- 应用为内网系统，仅限内部员工访问，或用户身份完全可信
- 应用返回的 HTML 内容完全由后端静态生成，不包含任何用户输入
- 页面中不包含敏感数据（密码、隐私信息等）

**风险降级依据：** 虽然技术上缺失 CSP，但业务风险被限制

---

### 具体场景示例

| 场景 | 全局中间件 | 返回内容 | CSP 策略 | 业务敏感度 | 风险等级 | 说明 |
|------|----------|--------|---------|-----------|---------|------|
| MVC 应用 + 框架中间件统一设置 | ✅ 有 | HTML | ✅ 安全 | 🔴 高 | 低 | 中间件确保完全覆盖 |
| 原生 net/http + 无中间件 | ❌ 无 | HTML | ❌ 无 | 🔴 高 | **高** | 每个路由都需显式设置 |
| 后端 API + 前端框架 | ❌ 无 | JSON | ✅ N/A | 🟢 低 | 低 | 后端无 HTML，无需 CSP |
| 错误处理返回 HTML | ⚠️ 部分 | HTML | ❌ 无 | 🟡 中 | 中 | 错误路由未被覆盖 |
| 静态文件服务 | ❌ 无 | HTML | ❌ 无 | 🟠 中 | 中 | 内容完全静态，但仍推荐设置 |

---

### 降级判定检查清单

评估时按以下顺序检查，**任一条件不满足则不能降级**：

- [ ] 已确认应用类型（HTML 生成 vs API vs 静态文件）
- [ ] 已遍历所有返回 `text/html` 的路由，确认返回内容列表完整
- [ ] 如果缺失 CSP，已确认存在全局中间件或架构特性确保防护
- [ ] 全局中间件的 CSP 策略本身是安全的（无 unsafe-inline/eval、无通配符）
- [ ] 已在多个浏览器/HTTP 工具中验证响应头确实包含 CSP
- [ ] 中间件顺序正确，CSP 设置不被后续操作覆盖

---

**最终规则：** 降级时应明确说明依赖的防护机制（如全局中间件），若该机制被移除或配置改变，风险等级应自动升级为高
