# PHP 框架 CSP 配置安全审计指南

## Details

### 核心问题示例

```php
// 典型场景1：Laravel 中完全缺失CSP配置
// config/app.php - 未启用任何CSP相关中间件
'providers' => [
    // ... 其他provider
    // Illuminate\Http\Middleware\SetCacheHeaders::class 有，但无CSP中间件
],

// 路由处理器 - 响应未设置CSP头
Route::get('/dashboard', function() {
    return view('dashboard'); // 无CSP保护
});
```

```php
// 典型场景2：Symfony 框架中配置过于宽松
// config/packages/framework.yaml 或 config/packages/security.yaml
framework:
    # 未定义CSP或定义过于宽松
    http_client:
        max_redirects: 20

// 或者在Controller中设置的宽松策略
class ApiController extends Controller {
    public function getData(Request $request) {
        return new Response(
            $content,
            Response::HTTP_OK,
            ['Content-Security-Policy' => "default-src *"] // 完全无保护
        );
    }
}
```

```php
// 典型场景3：动态设置CSP导致配置不当
// Laravel Middleware中的动态CSP
class SetCspMiddleware {
    public function handle($request, $next) {
        // 根据用户角色动态设置，引入配置错误
        if ($request->user() && $request->user()->isAdmin()) {
            $csp = "default-src 'self' https://admin.example.com";
        } else {
            $csp = "default-src 'unsafe-inline' 'unsafe-eval'"; // 低权限用户反而保护更弱
        }

        $response = $next($request);
        $response->header('Content-Security-Policy', $csp);
        return $response;
    }
}
```

```php
// 典型场景4：框架默认配置与应用覆盖的冲突
// Laravel - 框架默认无CSP，应用层也未配置
// app/Http/Middleware/TrustProxies.php 存在但无CSP相关逻辑

// Symfony - security.yaml配置过于宽松
security:
    firewall:
        main:
            pattern: ^/
            # 仅配置认证，未配置CSP

// 与之对应的模板中包含不安全内容
<script>
    var config = {{ config|raw }};  // 直接输出配置对象
    loadUsers();  // 外联脚本
</script>
```

```php
// 典型场景5：环境特定配置导致生产环境保护缺失
// config/csp.php （Laravel常见模式）
return [
    'enabled' => env('CSP_ENABLED', false), // 生产默认关闭！
    'report_only' => env('CSP_REPORT_ONLY', true),
    'nonce' => true,
    'directives' => env('CSP_DIRECTIVES', [
        'default-src' => ["'self'"],
        'script-src' => ["'self'", "https://cdn.example.com"],
    ]),
];

// .env 中缺失CSP_ENABLED=true，导致上线仍未启用
```

### 快速定位核心操作 **【L1: 关键词扫描】**

审计时通过以下关键词扫描定位配置点：

**Laravel框架：**
- **middleware** 目录 - 查看是否存在CSP相关中间件
- **config/app.php** / **config/security.php** - 检查中间件注册
- **app/Http/Middleware/** - 自定义中间件定义位置
- **kernel.php** - 全局中间件链配置
- **routes/web.php** / **routes/api.php** - 路由级别的header设置
- **.env** 文件 - CSP_ENABLED, CSP_DIRECTIVES等环境变量
- **vendor/laravel/framework/src/Illuminate/Http/Middleware/** - 框架原生中间件

**Symfony框架：**
- **config/packages/framework.yaml** / **config/packages/security.yaml** - 框架级配置
- **config/routes.yaml** - 路由配置中的CSP声明
- **src/EventListener/** - 事件监听器（可在此设置响应头）
- **src/Kernel.php** - 内核配置与中间件(Middleware)
- **.env.local** - Symfony环境配置
- **vendor/symfony/http-foundation/Response.php** - 响应对象中的header设置

**通用关键词：**
- **Content-Security-Policy** / **CSP** - CSP头名称
- **setHeader()** / **header()** - PHP原生头设置
- **Response::header()** / **$response->headers->set()** - 框架API
- **middlewares** / **middleware** - 中间件声明
- **unsafe-inline** / **unsafe-eval** - 宽松指令
- **default-src** / **script-src** - CSP指令
- **nonce** / **hash** - 安全令牌机制

### 快速定位保护机制 **【L2: 跳读】**

检查框架中CSP的实现方式与配置完整性：

```php
// Laravel中的标准CSP配置位置
// 检查app/Http/Kernel.php中是否注册了CSP中间件
protected $middleware = [
    \App\Http\Middleware\SetCsrfToken::class,
    // 应该有类似以下配置：
    \App\Http\Middleware\SetCspHeader::class, // ✓ 正确实现
];

// 检查config/csp.php是否存在
// 检查.env中CSP相关变量是否启用

// Symfony中的标准位置检查
// config/packages/framework.yaml
framework:
    http_client:
        headers:
            Content-Security-Policy: "default-src 'self'" # ✓ 框架级配置

// 或通过EventListener在响应发送前设置
// src/EventListener/CspListener.php - 应该存在此类实现
```

**关键配置点检查流程 【L2: 跳读 → L3: 逐行读】：**

1. **L2阶段** - 快速定位关键文件
   - 查看是否存在 `config/csp.php` / `config/packages/framework.yaml`
   - 查看是否存在 CSP 相关中间件类（名称中含 `Csp` / `Security`）
   - 查看 `.env` 示例或文档中是否提及 CSP 配置

2. **L3阶段** - 逐行审查配置内容
   - 检查 CSP 是否启用（`enabled: true` 或中间件已注册）
   - 检查指令是否包含 `*` / `unsafe-inline` / `unsafe-eval`
   - 检查是否对所有路由生效或仅部分路由生效
   - 检查 `report_only` 是否在生产环境被误设为 true

3. **L3-L4阶段** - 逐行读与跨模块追踪
   ```php
   // 在中间件中追踪：
   - 请求如何进入中间件？(通过kernel.php全局注册？路由级别？)
   - 响应对象如何返回？(是否所有分支都设置了头？)
   - 是否存在未保护的路由或特殊处理的分支？

   // 在配置中追踪：
   - 指令来源(硬编码？环境变量？数据库？)
   - 是否进行了参数验证？
   - 不同环境的配置差异(开发、测试、生产)
   ```

## Classify

### 研判标准

**确定为漏洞的条件（同时满足）：**

1. **配置缺失或未启用**
   - 框架中完全未配置CSP头
   - CSP中间件已编写但未在kernel.php中注册
   - .env文件中明确设置 `CSP_ENABLED=false` 或缺失此变量导致默认关闭
   - 配置文件存在但所有路由响应均未包含CSP头

2. **配置严重过度宽松**
   - 使用 `default-src *` 或 `script-src *` 允许任意源
   - 包含 `default-src 'unsafe-inline'` 导致所有脚本都能内联执行
   - 包含 `default-src 'unsafe-eval'` 允许动态代码执行
   - 使用 `img-src data:` 而无限制地处理 data: URL（可能导致数据泄露）

3. **配置管理混乱导致实际保护失效**
   - 代码中存在CSP配置但环境变量/参数未正确设置导致实际无保护
   - 框架默认配置被硬编码的宽松策略覆盖
   - 存在多个相互冲突的CSP配置（多个中间件、多个配置文件）

4. **环境特定配置导致生产环保护缺失**
   - 生产环境的.env未设置CSP_ENABLED或CSP_DIRECTIVES
   - 开发环境有完整CSP但生产环境注释掉或默认禁用

**升级为高危的额外条件：**
- 应用同时处理敏感信息（用户数据、支付信息、认证令牌）且无CSP保护
- XSS防护不足，仅依赖CSP而无其他输入校验
- 配置错误导致某些关键页面（登录页、支付页）暴露

### 研判为误报的条件：

1. **合理的框架设计**
   - 框架未内置CSP但应用层通过中间件/监听器完整实现
   - CSP配置由专业的第三方包管理（如laravel-csp包），已验证安全性
   - 配置通过环境变量正确传入，.env.example中有完整示例

2. **受保护的宽松指令**
   - 虽使用 `unsafe-inline` 但同时采用 CSP nonce/hash机制限制脚本
   - 脚本都通过 `{{ csp_nonce() }}` 或 `{{ csp_hash() }}` 标记
   - HTML模板中的所有 `<script>` 标签都带有对应的nonce/hash属性

3. **应用无需严格保护的场景**
   - 应用为内部工具，仅员工访问，不处理敏感数据
   - 应用为静态内容展示（文档站、API文档），无用户交互
   - 应用有其他强有力的XSS防护（严格的输入验证、HTML纯文本输出、前端框架的自动转义）

### 代码异味的研判：

1. **配置存在但启用状态模糊**
   - `CSP_ENABLED` 环境变量默认值为 false 导致容易误配
   - 配置文件中的 `enabled` 字段注释不明确

2. **硬编码配置与框架设计冲突**
   - 中间件中硬编码CSP指令，无法通过配置文件调整
   - 不同路由的CSP策略分散在各个Controller中维护

3. **安全指令被注释或临时禁用**
   - 代码注释中包含 "TODO: 优化CSP" / "暂时移除严格策略" 等字样
   - 生产分支中存在为调试而宽松的配置

## Low risk

### 允许低风险评级的场景

1. **完整且一致的CSP框架实现**
   - 框架中存在专门的CSP处理层（中间件/监听器），配置集中管理
   - 所有HTTP响应都经过此层，无遗漏的路由
   - 配置包含合理的 `default-src 'self'` 和具体的 `script-src` 限制
   - 指令中不包含通配符 `*` 和 `unsafe-*`

2. **采用现代安全模式的配置**
   - 使用CSP nonce或hash机制，每次请求生成新的随机nonce
   - 框架提供的辅助函数（如 `{{ csp_nonce() }}`）在模板中正确使用
   - 外部脚本通过 `script-src https://trusted-cdn.com` 的域名白名单方式引入
   - 完全禁止内联脚本和动态代码执行

3. **环境配置的规范管理**
   - .env.example 中包含完整的CSP配置示例
   - .env.production 或CI/CD管道确保生产环境的CSP正确启用
   - 配置变更有文档说明和变更日志
   - 不同环境的策略有明确的理由说明（开发环境可能更宽松但生产严格）

4. **受保护的框架级宽松指令**
   - 虽使用 `img-src data:` 但应用不涉及用户上传数据或二进制数据处理
   - 虽使用 `style-src 'unsafe-inline'` 但通过其他机制（如sanitizer、审核）确保样式安全
   - 此时安全边界由其他层防护承载，CSP作为纵深防御的一层
