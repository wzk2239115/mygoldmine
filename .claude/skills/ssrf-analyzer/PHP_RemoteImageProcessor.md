# PHP_RemoteImageProcessor

**漏洞类型**: 图片处理功能从用户 URL 加载远程图片，未过滤内网地址导致的 SSRF

---

## Details

### 代码示例

**易受攻击的代码模式**:
```php
// file_get_contents 示例
$imageUrl = $_GET['url'];
$imageData = file_get_contents($imageUrl); // 直接加载远程图片
$image = imagecreatefromstring($imageData);
header('Content-Type: image/png');
imagepng($image);

// cURL 图片下载
$url = $_POST['image_url'];
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$imgData = curl_exec($ch);
file_put_contents('uploads/' . md5($url) . '.jpg', $imgData);

// GD 库远程加载
$remoteImg = $_REQUEST['img'];
$image = imagecreatefromjpeg($remoteImg); // 支持 URL 协议
imagefilter($image, IMG_FILTER_GRAYSCALE);
imagejpeg($image, 'processed.jpg');

// Imagick 处理远程图片
$imgSrc = $params['source'];
$imagick = new Imagick($imgSrc); // 可加载远程 URL
$imagick->thumbnailImage(200, 200);
$imagick->writeImage('thumb.jpg');
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 图片处理函数: `imagecreatefromjpeg()`, `imagecreatefrompng()`, `imagecreatefromstring()`, `new Imagick()`
- 远程数据获取: `file_get_contents()`, `curl_init()`, `curl_exec()`, `fopen()`, `copy()`
- 用户输入来源: `$_GET['url']`, `$_POST['image']`, `$_REQUEST`, `$params['src']`, `$input['img_url']`
- 图片上传处理: 路由或函数名含 `upload`, `image`, `thumbnail`, `resize`, `avatar`, `photo`

**L2 跳读定位**:
- 从图片处理路由/控制器入口扫描用户输入获取点
- 追踪 URL 参数流向到图片加载函数之间的数据流
- 重点关注: 完整 URL 作为参数传递、是否存在 URL 拼接或协议处理
- 检查文件后缀名验证是否仅检查扩展名而不验证域名/IP

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- URL 解析验证: `parse_url()` 后检查 `scheme`、`host` 组件
- 协议限制: 正则匹配 `/^https?:\/\//`、`in_array($scheme, ['http','https'])`
- 域名白名单: `in_array($host, $allowedDomains)`, `preg_match('/\.trusted\.com$/', $host)`
- IP 过滤函数: 搜索自定义函数名含 `isPrivate`, `isInternal`, `filterIP`, `checkHost`

**L3 逐行分析**:
- URL 解析实现: 检查 `parse_url()` 后是否同时验证 `scheme` 和 `host`
- IP 检测逻辑:
  - 是否使用 `filter_var($host, FILTER_VALIDATE_IP)` 判断是否为 IP
  - 是否使用 `ip2long()` 将 IP 转换后检查私有段 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8)
  - 检查是否过滤 `0.0.0.0`, `169.254.0.0/16`, `::1`, `localhost`
- 白名单绕过风险: `strpos()`, `startsWith()` 可能被 `@` 或子域名绕过
- 文件类型验证: 是否仅检查 URL 后缀而不验证响应的 `Content-Type`

**L4 跨模块追踪**:
- 追踪中间件或工具类中的 URL 验证函数完整实现
- 检查框架级的全局输入过滤器是否处理 URL 参数
- 验证配置文件中是否有 `allow_url_fopen=Off` 或 `disable_functions` 限制
- 检查是否使用代理服务或网络层面的出站规则限制

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- URL 完全由用户可控，无任何域名或 IP 验证
- 可通过构造内网地址访问内部资源 (如 `http://127.0.0.1`, `http://192.168.x.x`)
- 可访问云元数据服务 (`http://169.254.169.254/latest/meta-data/`)
- 协议未限制，允许使用 `file://`, `dict://`, `gopher://`, `php://` 等危险协议
- 保护机制存在可绕过缺陷 (如正则不严谨、URL 解析差异、进制转换绕过)

**误报判定**:
- URL 来自硬编码配置或后台管理员设置的白名单列表，非普通用户运行时输入
- 图片来源域名完全硬编码，用户仅可控路径参数 (如 `https://cdn.example.com/{$userPath}`)
- 存在完整且严格的验证机制: 协议限制 + 域名白名单 + IP 私有地址过滤 + DNS 重绑定防护
- 应用运行在完全隔离的沙箱环境，无任何内网资源可访问

**代码异味**:
- 仅有协议验证但无域名或 IP 限制 (允许任意公网及内网 HTTP 地址)
- 使用黑名单而非白名单 (如仅禁止 `127.0.0.1`, `localhost`，易被 `127.1`, `0.0.0.0` 等绕过)
- 仅检查 URL 字符串格式而不解析验证各组件
- URL 验证与实际使用之间存在二次处理 (如 URL 编码、重定向跟随)，可能产生 TOCTOU 问题
- 依赖文件扩展名判断是否为图片，未验证响应内容类型

---

## Low risk

### 低风险场景

**权限与场景受限**:
- 功能仅限管理员或特权用户使用，需强认证且有访问日志
- 有严格的速率限制和并发控制，难以进行大规模扫描
- 图片 URL 需经过预审核或由系统生成，非用户直接提交

**网络隔离保护**:
- 应用服务器部署在 DMZ 区域，与核心内网完全隔离
- 出站请求经过严格的防火墙/代理规则，仅允许访问特定外部域名
- 云环境已禁用元数据服务访问或使用 IMDSv2 强制 Token 认证

**响应限制与内容过滤**:
- 严格验证响应的 `Content-Type` 必须为图片 MIME 类型
- 响应数据经过图片重编码处理 (如 `imagejpeg()` 重新生成)，非原始响应透传
- 限制图片大小、超时时间极短，难以利用进行慢速攻击或端口扫描
- 处理结果不直接返回给用户，仅内部使用或异步处理

**部分缓解措施**:
- 有基础的协议限制 (仅 `http/https`) 且禁用了 `allow_url_include`
- 使用 DNS 缓存或多次解析验证，可部分缓解 DNS 重绑定攻击
- 有监控和异常检测机制，可及时发现内网访问尝试
- 目标内网环境无高价值资产或敏感服务暴露