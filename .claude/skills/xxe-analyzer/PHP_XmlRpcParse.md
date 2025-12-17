# PHP｜XML-RPC 请求解析未禁用实体

## Details

### 漏洞成因
PHP 的 XML-RPC 服务（如 `xmlrpc_server_create`, `xmlrpc_decode_request`，或基于 WordPress、Drupal 的 XML-RPC 端点）如果不在解析前禁用实体加载，将使攻击者通过 XML-RPC 请求中的 DTD 泄露文件或触发 SSRF。

### 代码示例

**易受攻击的代码：**
```php
$requestXml = file_get_contents('php://input');
$params = xmlrpc_decode_request($requestXml, $method); // 默认配置
$response = handle_method($method, $params);
```

**安全示例：**
```php
$requestXml = file_get_contents('php://input');
$previous = libxml_disable_entity_loader(true);
$params = xmlrpc_decode_request($requestXml, $method, 'utf-8');
libxml_disable_entity_loader($previous);
$response = handle_method($method, $params);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `xmlrpc_decode`, `xmlrpc_decode_request`, `xmlrpc_server_create`, `IXR_Server`, `wp_xmlrpc_server`。

**定位步骤：**
1. 搜索 XML-RPC 解析入口；
2. 跳读（L2）确认是否禁用实体或使用安全库；
3. 检查是否允许匿名调用。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `libxml_disable_entity_loader(true)`；
- 入口处过滤 `<DOCTYPE>`；
- 仅允许 HTTPS + 认证；
- 升级到支持安全配置的库。

**定位技巧：**
- 逐行读（L3）确认解析后是否恢复 loader 状态；
- 跨模块追踪（L4）检查框架自身的 XML-RPC 扩展是否已补丁。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 解析前统一禁用实体 | **L0（快速跳过）** | 风险低 |
| 部分入口遗漏禁用 | **L2（跳读）** | 快速补齐 |
| 默认解析所有 XML-RPC 请求 | **L3（逐行读）** | 高风险 |
| 服务开放给外网且匿名访问 | **L4（跨模块追踪）** | 必须彻底加固 |

## Classify

### 研判标准

#### 确认漏洞
1. XML-RPC 服务解析用户可控 XML；
2. 未禁用外部实体；
3. 可构造 payload 读取敏感资源或 SSRF。

#### 误报
1. 服务已停用或受防火墙限制；
2. 请求来源受限并有额外认证；
3. 服务端在解析前验证签名。

#### 代码异味
1. `libxml_disable_entity_loader` 未恢复导致全局状态混乱；
2. 依赖正则剥离 `<!DOCTYPE>`；
3. 无日志记录，难以排查攻击行为。

## Low risk

### 低风险评级场景

#### 1. XML-RPC 仅在内网使用
- 攻击面小，可暂降级。

#### 2. 请求需带签名或令牌
- 风险降低，但仍建议禁用实体。

#### 3. 已计划迁移至 JSON-RPC 或 REST
- 明确时间表，暂记低风险并跟踪。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内网使用 | 攻击面小 | 中 |
| 强认证 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
