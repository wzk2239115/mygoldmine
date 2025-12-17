# PHP｜CSP策略配置缺陷

## Details

### 漏洞成因
内容安全策略(CSP)是Web应用重要的安全防线，用于防止XSS、点击劫持等攻击。PHP应用中，当CSP策略配置过弱、包含不安全指令或使用通配符(*)允许所有来源时，会显著降低防护效果。常见错误包括：使用`unsafe-inline`允许内联脚本、`unsafe-eval`允许动态代码执行、过度宽松的`default-src *`、以及缺少关键的防护指令如`object-src`、`frame-ancestors`等。

### 代码示例

**易受攻击的代码 - 弱CSP策略：**
```php
// 危险的CSP配置 - 允许所有来源
header("Content-Security-Policy: default-src *; script-src * 'unsafe-inline'");

// 或者完全缺少CSP头
// 没有设置任何CSP策略
```

**易受攻击的代码 - 不安全指令：**
```php
// 允许内联脚本和eval() - 严重降低XSS防护
header("Content-Security-Policy: script-src 'self' 'unsafe-inline' 'unsafe-eval'");

// 过度宽松的对象源
header("Content-Security-Policy: object-src *; frame-ancestors *");
```

**易受攻击的代码 - 元标签配置错误：**
```php
// HTML中的CSP meta标签配置错误
?>
<meta http-equiv="Content-Security-Policy" content="default-src * 'unsafe-inline' 'unsafe-eval'">
<?php
```

**安全示例 - 严格的CSP策略：**
```php
// 严格的CSP配置
$csp = [
    "default-src 'self'",
    "script-src 'self' 'nonce-" . generateNonce() . "'", // 使用nonce而非unsafe-inline
    "style-src 'self' 'nonce-" . generateNonce() . "'",
    "img-src 'self' data: https:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'", // 防止点击劫持
    "object-src 'none'",      // 防止插件攻击
    "base-uri 'self'",
    "form-action 'self'"
];

header('Content-Security-Policy: ' . implode('; ', $csp));

function generateNonce() {
    return base64_encode(random_bytes(16));
}
```

**安全示例 - 框架级别的CSP：**
```php
// Laravel CSP配置示例
// config/secure-headers.php
return [
    'content-security-policy' => [
        'report-only' => false, // 生产环境设置为false
        'default-src' => ['self'],
        'script-src' => ['self', 'nonce' => true],
        'style-src' => ['self', 'nonce' => true],
        'img-src' => ['self', 'data:', 'https:'],
        'font-src' => ['self'],
        'connect-src' => ['self'],
        'frame-ancestors' => ['none'],
        'object-src' => ['none'],
        'base-uri' => ['self'],
        'form-action' => ['self'],
    ],
];
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- CSP头：`Content-Security-Policy`, `X-Content-Security-Policy`
- 不安全指令：`unsafe-inline`, `unsafe-eval`, `*` 
- Meta标签：`http-equiv="Content-Security-Policy"`

**定位步骤：**
1. 搜索项目中所有CSP相关的header设置
2. 检查HTML模板中的CSP meta标签
3. 验证CSP策略的具体内容和指令

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **严格的源限制：** 使用`'self'`而非通配符
- **Nonce/Hash机制：** 替代`unsafe-inline`
- **关键指令设置：** `frame-ancestors`, `object-src`, `base-uri`
- **报告机制：** CSP违规报告配置

**定位技巧：**
- 检查是否使用nonce或hash替代内联脚本
- 验证`frame-ancestors`是否设置为`'none'`
- 确认`object-src`是否适当限制
- 检查是否存在CSP报告URI配置

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 严格CSP+nonce机制 | **L0（快速跳过）** | 配置安全 |
| 有CSP但存在宽松指令 | **L2（跳读）** | 需验证具体策略 |
| 使用unsafe-inline/eval | **L3（逐行读）** | 高风险配置 |
| 完全缺少CSP | **L4（跨模块追踪）** | 严重缺失 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. CSP策略包含`unsafe-inline`或`unsafe-eval`指令
2. 使用通配符(*)允许所有外部资源
3. 缺少关键防护指令（frame-ancestors/object-src）
4. 完全未设置CSP策略

#### 误报
以下情景可判定为误报：
1. 使用nonce或hash机制管理内联资源
2. 严格限制资源来源，仅允许必要域
3. 关键防护指令配置正确
4. 使用CSP报告模式进行逐步部署

#### 代码异味
需记录的风险：
1. 策略中允许过多的外部域名
2. 在report-only模式下长期运行
3. 动态生成的CSP策略存在注入风险
4. 移动端和桌面端策略不一致

## Low risk

### 低风险评级场景

#### 1. 分阶段部署CSP
- **场景：** 使用report-only模式收集违规报告，逐步收紧策略
- **风险评估：** 合理的部署策略，风险可控

#### 2. 必要的宽松配置
- **场景：** 特定页面确实需要内联脚本，已评估风险
- **风险评估：** 业务需求驱动，已采取其他防护措施

#### 3. 框架内置CSP
- **场景：** 使用现代框架内置的CSP生成机制
- **风险评估：** 框架通常提供合理的默认配置

### CSP指令安全检查表

| 指令 | 安全设置 | 风险设置 | 检测要点 |
|------|----------|----------|----------|
| default-src | 'self' | * | 是否使用通配符 |
| script-src | 'nonce-' or 'sha256-' | 'unsafe-inline' | 是否允许内联脚本 |
| style-src | 'nonce-' or 'sha256-' | 'unsafe-inline' | 是否允许内联样式 |
| frame-ancestors | 'none' or 'self' | * | 点击劫持防护 |
| object-src | 'none' | * | 插件安全限制 |
| base-uri | 'self' | * | 基础URI限制 |

### 常见CSP绕过技术

| 绕过方法 | 适用条件 | 检测方法 | 防护建议 |
|----------|----------|----------|----------|
| 宽松策略利用 | 通配符允许 | 策略分析 | 严格限制来源 |
| JSONP回调 | 允许特定域名 | 域名审查 | 限制JSONP使用 |
| Angular模板 | ng-*属性绕过 | 框架审查 | 严格CSP设置 |
| 重定向滥用 | 允许重定向域名 | 重定向链分析 | 限制重定向来源 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 使用nonce/hash机制 | 替代unsafe-inline | 高 |
| 严格限制资源来源 | 最小权限原则 | 高 |
| 关键防护指令完备 | 全面防护 | 高 |
| 分阶段部署策略 | 风险控制 | 中 |