# PHP｜大小写绕过漏洞

## Details

### 漏洞成因
PHP文件上传验证中，仅使用简单的字符串比较或黑名单过滤文件扩展名时，未考虑大小写 variations。攻击者可通过修改文件扩展名的大小写形式（如.PHP、.Php、.pHp等）绕过验证，因为文件系统在保存时通常保持原始大小写，而Web服务器（Apache/Nginx）对大小写不敏感，仍会解析执行PHP脚本。

### 代码示例

**易受攻击的代码：**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $file = $_FILES['upload'];
    $ext = pathinfo($file['name'], PATHINFO_EXTENSION);
    $blacklist = ['php', 'php3', 'php4', 'php5'];
    
    if (in_array($ext, $blacklist)) {
        die('PHP files not allowed');
    }
    
    // 大小写绕过：shell.PHP 可通过验证
    move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $file['name']);
}
```

**另一个不安全示例（strcasecmp问题）：**
```php
$ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
if ($ext === 'php') {
    die('PHP files not allowed');
}
// 但原始文件名仍保留大小写，可被利用
move_uploaded_file($file['tmp_name'], 'uploads/' . $file['name']);
```

**安全示例：**
```php
$file = $_FILES['upload'];
$ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
$blacklist = ['php', 'php3', 'php4', 'php5', 'phtml', 'pht'];

if (in_array($ext, $blacklist)) {
    die('PHP files not allowed');
}

// 使用随机文件名，不保留原始扩展名
$new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $new_filename);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 扩展名获取：`pathinfo`, `PATHINFO_EXTENSION`
- 黑名单检查：`in_array`, `strpos`, `preg_match`
- 大小写转换：`strtolower`, `strtoupper`

**定位步骤：**
1. 搜索上传处理逻辑，检查扩展名验证代码
2. 确认是否使用大小写转换函数统一处理扩展名
3. 验证黑名单比较是否区分大小写

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **统一大小写处理：** 使用`strtolower`或`strtoupper`标准化扩展名
- **白名单机制：** 只允许特定的小写扩展名
- **随机文件名：** 不保留用户原始文件名和扩展名
- **多重验证：** 结合MIME类型和内容检查

**定位技巧：**
- 检查是否仅依赖扩展名验证，未进行内容检测
- 确认文件保存时是否保留原始大小写扩展名
- 验证Web服务器配置是否区分大小写执行脚本

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用strtolower统一处理且随机命名 | **L0（快速跳过）** | 风险低 |
| 有大小写处理但保留原始文件名 | **L2（跳读）** | 需验证其他防护 |
| 无大小写处理，直接黑名单比较 | **L3（逐行读）** | 高风险 |
| 大小写混合验证逻辑复杂 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 扩展名验证未进行大小写统一处理
2. 黑名单比较区分大小写或过滤不完整
3. 文件保存保留原始大小写，Web服务器可执行

#### 误报
以下情景可判定为误报：
1. 统一使用strtolower处理扩展名并进行白名单验证
2. 使用随机文件名，不保留原始扩展名
3. 存储目录禁止脚本执行且有访问控制

#### 代码异味
需记录的风险：
1. 仅依赖扩展名黑名单，未考虑大小写变体
2. 有大小写处理但逻辑不完整（如只检查部分扩展名）
3. 验证和保存使用不同的扩展名提取方式

## Low risk

### 低风险评级场景

#### 1. 扩展名白名单验证
- **场景：** 使用strtolower统一处理后进行白名单验证
- **风险评估：** 可有效防止大小写绕过

#### 2. 内容类型检测
- **场景：** 通过文件头或内容分析确定文件类型
- **风险评估：** 不依赖扩展名，风险较低

#### 3. 存储隔离
- **场景：** 上传文件存储在非Web根目录或禁止执行目录
- **风险评估：** 即使绕过也无法直接执行

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 统一大小写处理 | 消除大小写差异 | 高 |
| 使用白名单机制 | 减少绕过可能性 | 高 |
| 随机文件名 | 不暴露文件类型 | 中 |
| 存储目录隔离 | 限制执行环境 | 高 |