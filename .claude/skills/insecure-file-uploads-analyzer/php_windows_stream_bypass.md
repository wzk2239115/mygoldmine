# PHP｜Windows文件流绕过漏洞 (::$DATA)

## Details

### 漏洞成因
在Windows系统上，NTFS文件系统支持交替数据流（Alternate Data Streams, ADS）特性，允许文件存在多个数据流。主数据流通过`filename`访问，而附加数据流通过`filename:streamname`语法访问。特殊的是，`::$DATA`表示文件的默认数据流。当PHP应用处理文件上传时，如果仅对原始文件名进行黑名单过滤，攻击者可以通过在文件名后添加`::$DATA`（如`shell.php::$DATA`）绕过验证，因为`pathinfo()`等函数会将其识别为合法的文件名，而Windows系统会将其保存为PHP文件。

### 代码示例

**易受攻击的代码：**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $file = $_FILES['upload'];
    $filename = $file['name'];
    $ext = pathinfo($filename, PATHINFO_EXTENSION);
    $blacklist = ['php', 'php3', 'php4', 'php5'];
    
    if (in_array($ext, $blacklist)) {
        die('PHP files not allowed');
    }
    
    // Windows流绕过：shell.php::$DATA 可通过验证
    // pathinfo会返回'php'作为扩展名，但::$DATA部分被忽略
    move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $filename);
}
```

**另一个不安全示例（strrchr问题）：**
```php
$filename = $_FILES['upload']['name'];
$ext = strrchr($filename, '.'); // 查找最后一个点
if (strtolower($ext) === '.php') {
    die('PHP files not allowed');
}
// shell.php::$DATA 中 strrchr 返回 '.php::$DATA'
// 但比较失败，绕过验证
```

**安全示例：**
```php
$file = $_FILES['upload'];
$filename = $file['name'];

// 去除Windows流标记
if (strpos($filename, '::') !== false) {
    die('Invalid filename');
}

// 严格的白名单验证
$ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
$whitelist = ['jpg', 'jpeg', 'png', 'gif'];

if (!in_array($ext, $whitelist)) {
    die('File type not allowed');
}

// 使用随机文件名
$new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $new_filename);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件名处理：`$_FILES['name']`, `pathinfo`, `strrchr`
- 黑名单检查：`in_array`, `strpos`, `preg_match`
- Windows流：`::$DATA`, `::`, `str_ireplace`

**定位步骤：**
1. 搜索上传处理逻辑，检查文件名验证代码
2. 确认是否检测和处理Windows流标记`::`
3. 验证扩展名提取是否准确处理特殊字符

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **流标记检测：** 明确拒绝包含`::`的文件名
- **白名单机制：** 只允许特定的安全扩展名
- **随机文件名：** 不依赖用户提供的文件名
- **系统检测：** 识别Windows环境并采取额外防护

**定位技巧：**
- 检查是否使用`str_ireplace`或类似函数处理流标记
- 确认是否对文件名进行净化处理
- 验证是否在不同操作系统下测试上传功能

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 明确拒绝::且使用随机命名 | **L0（快速跳过）** | 风险低 |
| 有白名单但未检测流标记 | **L2（跳读）** | 需验证Windows环境风险 |
| 仅黑名单过滤，无流处理 | **L3（逐行读）** | 高风险 |
| 复杂文件名处理逻辑 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 未检测和处理Windows流标记`::`
2. 扩展名验证可通过流标记绕过
3. 运行在Windows系统或共享存储环境

#### 误报
以下情景可判定为误报：
1. 明确检测并拒绝包含`::`的文件名
2. 使用随机文件名，不保留原始文件名
3. 仅在Linux/Unix环境部署，无Windows兼容性需求

#### 代码异味
需记录的风险：
1. 仅依赖简单的扩展名检查，未考虑系统特性
2. 有流处理但逻辑不完整（如只替换部分情况）
3. 验证和保存使用不同的文件名处理方式

## Low risk

### 低风险评级场景

#### 1. 非Windows环境
- **场景：** 应用仅在Linux/Unix系统运行，无Windows兼容性需求
- **风险评估：** 流标记绕过在此环境下无效

#### 2. 严格文件名净化
- **场景：** 使用正则表达式或白名单严格限制文件名字符
- **风险评估：** 可有效防止流标记注入

#### 3. 内容类型检测
- **场景：** 通过文件内容而非文件名确定文件类型
- **风险评估：** 不依赖扩展名，风险较低

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 检测并拒绝流标记 | 消除系统特性利用 | 高 |
| 非Windows环境 | 天然免疫 | 中 |
| 随机文件名 | 不暴露文件类型 | 高 |
| 内容类型检测 | 多重验证 | 高 |