# PHP 中的 CSP unsafe-inline 漏洞审计指南

## Details

### 核心问题示例

```php
// 典型场景1：header函数中的CSP配置
header("Content-Security-Policy: script-src 'unsafe-inline'");
header("Content-Security-Policy: default-src 'unsafe-inline'");

// 典型场景2：内联脚本与用户输入组合
echo '<script>';
echo "const userData = '" . $_GET['name'] . "';";
echo '</script>';

// 典型场景3：动态样式内联（CSS unsafe-inline）
echo '<style>';
echo ".user-color { color: " . $_POST['color'] . "; }";
echo '</style>';

// 典型场景4：事件处理器中的内联属性
echo '<img src="image.jpg" onerror="alert(\'' . $_GET['msg'] . '\')">';

// 典型场景5：模板引擎中的内联脚本（如Blade, Twig）
<script>
    var apiKey = "{{ $userInput }}";
    var config = @json($untrustedArray);
</script>

// 典型场景6：通过DOM操作注入内联脚本
echo '<div id="content"></div>';
echo '<script>';
echo "document.getElementById('content').innerHTML = '" . $userContent . "';";
echo '</script>';

// 典型场景7：JSON响应中的脚本注入
$response = [
    'callback' => $_GET['function_name'],
    'data' => "console.log('" . $userData . "');"
];
header('Content-Type: application/json');
echo json_encode($response);
```

### 快速定位核心操作 **【L1: 关键词扫描】**

审计时通过以下关键词扫描定位内联脚本执行风险：

- **header()** / **header_remove()** - CSP策略设置点
- **echo / print** - 输出脚本内容
- **内联script标签** - `<script>...</script>` 直接在PHP中生成
- **内联事件属性** - `onclick`, `onerror`, `onload` 等
- **内联style标签** - `<style>...</style>` 动态生成
- **style属性** - `style="..."` 动态赋值
- **json_encode()** - 返回可能被脚本化的JSON数据
- **sprintf() / printf()** - 格式化输出到脚本上下文
- **模板变量** - `{{ }}`, `<%= %>`, `{# #}` 等模板语法
- **ob_get_contents()** / 输出缓冲 - 输出包含动态脚本

### 快速定位保护机制 **【L2: 跳读】**

检查CSP头部配置与防护机制：

```php
// 关键CSP检查点（L2跳读）
header("Content-Security-Policy: script-src 'unsafe-inline'");  // 高风险
header("Content-Security-Policy: style-src 'unsafe-inline'");   // 中风险
header("Content-Security-Policy: default-src 'unsafe-inline'"); // 高风险
header("Content-Security-Policy: script-src 'unsafe-inline' 'unsafe-eval'"); // 极高风险

// CSP存在性检查
// - 在框架初始化文件中查找（通常在 index.php, config/, bootstrap/）
// - 在中间件层查找（如 Middleware/, app/Http/Middleware/）
// - 在配置文件中查找（config/security.php, .htaccess）
```

**关键检查位置【L2-L3: 跳读到逐行读】**

- **入口文件** - index.php, public/index.php 中的初始header设置
- **框架配置** - app/config/, config/app.php, config/security.php
- **中间件层** - app/Middleware/, app/Http/Middleware/SecurityHeaders.php
- **视图模板** - resources/views/ 中的 `<script>` 和 `<style>` 标签
- **AJAX响应** - api/, controller/ 中返回脚本内容的端点
- **.htaccess** - Apache配置中的Header指令
- **Composer依赖** - 第三方库中的CSP配置（通过service provider）

**L3逐行读技巧**：
- 追踪用户输入（$_GET, $_POST, $_COOKIE, $_SERVER）从进入到脚本输出的完整路径
- 检查输入是否经过 htmlspecialchars(), json_encode(), addslashes() 等编码函数
- 对比不同环境（开发/生产）的CSP配置差异

## Classify

### 研判标准

**确定为漏洞的条件（同时满足）：**

1. 代码中存在内联脚本或内联样式生成（在PHP中直接输出 `<script>`, `<style>`, event属性等）
2. CSP策略明确包含 `script-src 'unsafe-inline'` 或 `style-src 'unsafe-inline'` 或 `default-src 'unsafe-inline'`
3. 内联脚本/样式的内容包含可控源的用户输入（$_GET, $_POST, 数据库值、API响应等）
4. 未进行充分的内容编码/转义（或编码不适应目标上下文）

**升级为高危的额外条件：**

- 用户输入未经任何过滤或检查
- 内联脚本在认证之前执行（如登录页面的XSS）
- 涉及敏感操作（转账、删除、权限修改）
- 可导致Session劫持、CSRF、数据篡改

**升级为严重的额外条件：**

- 涉及管理员或高权限用户的操作页面
- 内联脚本可执行任意代码（如直接调用敏感API）

### 研判为误报的条件：

1. **内容完全由系统控制，无用户输入**
   - 脚本内容在部署时静态定义，运行时不变
   - 仅用于初始化配置、调用公开API、显示静态数据

2. **充分的上下文编码保护**
   - 应用了正确的编码函数：
     - JSON内容：json_encode() 使用 JSON_HEX_AMP | JSON_HEX_APOS 标志
     - HTML属性内：htmlspecialchars($input, ENT_QUOTES, 'UTF-8')
     - JavaScript字符串中：使用json_encode() 或显式转义反斜杠、引号、尖括号
   - 编码位置正确（在输出点，而非输入点）

3. **CSP 多层防护**
   - 虽有 unsafe-inline 但使用 nonce 或 hash 限制具体脚本执行（减弱风险）
   - 同时配置 frame-ancestors, object-src, base-uri 等指令
   - 配合 X-Content-Type-Options: nosniff, X-Frame-Options: DENY

4. **框架级内置防护**
   - 使用安全的模板引擎带有自动转义（如Blade、Twig with autoescape=true）
   - 框架自动对所有动态输出进行HTML编码
   - 验证框架版本与配置确实启用了保护

### 代码异味的研判：

1. **过度宽松的CSP** - 使用 `default-src 'unsafe-inline'` 而非针对性的 `script-src` 指令
2. **遗留注释** - 代码中有 `/* TODO: remove unsafe-inline */` 或 `// unsafe-inline for debugging`
3. **条件性unsafe-inline** - 仅在开发环境禁用，生产环境启用 → 需确认生产是否真需要
4. **模板中混合输出** - PHP变量直接在 `<script>` 中输出而非独立的数据属性 → 建议重构为data属性

## Low risk

### 允许低风险评级的场景

1. **受限的内容来源**
   - 内联脚本仅包含系统生成的配置常量（不涉及用户数据）
   - 用户输入仅用于数据属性（如 `data-value="...""`）而非脚本逻辑
   - 使用 JSON API 传输用户数据，脚本端通过 fetch 加载（分离内容与脚本）

2. **充分的编码保护**
   - JSON 数据通过 `json_encode()` 输出，明确指定 ENT_QUOTES 编码
   - 在JSON中的任何用户输入验证确认为纯文本（无HTML特殊字符）
   - HTML 属性中的用户输入使用 `htmlspecialchars(..., ENT_QUOTES, 'UTF-8')`
   - 样式表中的用户输入（color值、URL）经过URL编码或白名单检查

3. **框架级自动防护**
   - 确认框架（Laravel, Symfony, Yii）版本在安全支持范围内
   - 模板引擎配置中 autoescape 明确为 true（Blade 默认启用）
   - 框架更新日志未提及相关安全补丁需应用

4. **多层安全边界**
   - 虽有 unsafe-inline 但：
     - 使用 script-src 的 nonce 值限制特定脚本执行
     - CSP report-uri 配置完整，能检测违规
     - Cookie 设置 Secure, HttpOnly, SameSite=Strict
     - 无跨域脚本加载（script-src 无 http://, https://, *)
   - 此时安全边界由编码和nonce限制而非CSP的unsafe-inline黑名单承载

5. **隔离的动态内容**
   - 用户控制的内容加载到 iframe 中，iframe 设置 sandbox 属性（禁用脚本）
   - iframe src 受限于同域或白名单域名
   - 父窗口与iframe通过 postMessage 通信，验证origin
