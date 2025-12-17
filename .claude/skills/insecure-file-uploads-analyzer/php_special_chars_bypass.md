# PHP｜特殊字符绕过漏洞

## Details

### 漏洞成因
PHP文件上传验证中，当使用简单的字符串处理函数（如`strrchr`、`str_replace`、`trim`等）进行黑名单过滤时，未考虑特殊字符的组合和顺序。攻击者可以通过在扩展名前添加空格、点号、特殊符号（如`shell.php.`、`shell.php `、`shell.php::$DATA`等）绕过验证。这些特殊字符在Windows系统下会被自动处理或忽略，使得恶意文件仍能被执行，而验证逻辑却认为文件类型已被安全处理。

### 代码示例

**易受攻击的代码 - 空格绕过：**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $file = $_FILES['upload'];
    $filename = $file['name'];
    $ext = strrchr($filename, '.'); // 查找最后一个点
    
    if (strtolower($ext) === '.php') {
        die('PHP files not allowed');
    }
    
    // 空格绕过：shell.php 可通过验证
    move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $filename);
}
```

**易受攻击的代码 - 点号绕过：**
```php
$filename = $_FILES['upload']['name'];
$ext = pathinfo($filename, PATHINFO_EXTENSION);
$blacklist = ['php', 'php3', 'php4', 'php5'];

// 双写绕过：shell.pphphp -> 经过str_replace后变成shell.php
$filename = str_ireplace($blacklist, '', $filename);

if (!in_array(strtolower($ext), $blacklist)) {
    move_uploaded_file($_FILES['upload']['tmp_name'], 'uploads/' . $filename);
}
```

**易受攻击的代码 - 组合绕过：**
```php
$filename = $_FILES['upload']['name'];
// 尝试移除各种后缀
$filename = str_ireplace(['.php', '.asp', '.jsp'], '', $filename);
$filename = str_ireplace(['.php3', '.php4', '.php5'], '', $filename);

// 组合攻击：shell.php. . (点和空格组合) 可能绕过
move_uploaded_file($_FILES['upload']['tmp_name'], 'uploads/' . $filename);
```

**安全示例：**
```php
$file = $_FILES['upload'];
$filename = $file['name'];

// 1. 去除首尾空格和点号
$filename = trim($filename, " \t\n\r\0\x0B.");

// 2. 检测非法字符
if (preg_match('/[<>:\\|\?\*]/', $filename)) {
    die('Invalid filename');
}

// 3. 使用白名单验证
$ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
$whitelist = ['jpg', 'jpeg', 'png', 'gif', 'pdf'];

if (!in_array($ext, $whitelist)) {
    die('File type not allowed');
}

// 4. 使用随机文件名
$new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
move_uploaded_file($file['tmp_name'], __DIR__ . '/uploads/' . $new_filename);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 字符串处理：`strrchr`, `str_replace`, `str_ireplace`, `trim`, `rtrim`
- 扩展名获取：`pathinfo`, `strrpos`, `substr`
- 黑名单处理：`in_array`, `strpos`, `preg_match`

**定位步骤：**
1. 搜索上传处理逻辑，检查文件名和扩展名处理
2. 确认是否使用安全的字符串处理函数
3. 验证是否考虑各种特殊字符组合

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **输入净化：** 使用`trim`去除首尾特殊字符
- **白名单验证：** 只允许特定的安全扩展名
- **正则验证：** 使用严格模式匹配文件名
- **随机命名：** 不依赖用户提供的文件名

**定位技巧：**
- 检查是否使用`pathinfo`替代字符串函数
- 确认是否对文件名进行正则表达式验证
- 验证是否检测连续的特殊字符

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用pathinfo+白名单+随机命名 | **L0（快速跳过）** | 风险低 |
| 有白名单但字符串处理不安全 | **L2（跳读）** | 需验证绕过风险 |
| 仅依赖str_replace等简单处理 | **L3（逐行读）** | 高风险 |
| 复杂的字符串替换逻辑 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 使用不安全的字符串处理函数进行过滤
2. 未考虑特殊字符的组合和顺序
3. 过滤后的文件名仍可被系统识别为危险类型

#### 误报
以下情景可判定为误报：
1. 使用`pathinfo`等安全函数提取扩展名
2. 采用白名单机制且进行严格的输入验证
3. 使用随机文件名，不保留用户输入

#### 代码异味
需记录的风险：
1. 仅依赖简单的字符串替换，未考虑绕过可能性
2. 多次使用不同的字符串处理函数，逻辑混乱
3. 验证和保存使用不同的处理方式

## Low risk

### 低风险评级场景

#### 1. 严格的文件名验证
- **场景：** 使用正则表达式严格限制文件名字符
- **风险评估：** 可有效防止特殊字符注入

#### 2. 内容类型检测
- **场景：** 通过文件头或内容分析确定文件类型
- **风险评估：** 不依赖扩展名，风险较低

#### 3. 系统环境限制
- **场景：** 在Linux系统下运行，对特殊字符处理严格
- **风险评估：** Windows下的绕过技术在Linux下无效

### 特殊绕过技术总结

| 绕过技术 | 示例 | 适用环境 | 检测方法 |
|----------|------|----------|----------|
| 空格绕过 | `shell.php ` | Windows | 检查trim处理 |
| 点号绕过 | `shell.php.` | Windows | 检查rtrim处理 |
| 双写绕过 | `shell.pphphp` | 全平台 | 检查str_replace逻辑 |
| 组合绕过 | `shell.php. .` | Windows | 检查连续特殊字符 |
| NULL绕过 | `shell.php%00.jpg` | 旧版本PHP | 检查NULL字符处理 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 使用pathinfo提取扩展名 | 避免字符串处理问题 | 高 |
| 严格的白名单验证 | 减少绕过可能性 | 高 |
| 随机文件名 | 不暴露文件类型 | 高 |
| 输入净化处理 | 消除特殊字符 | 中 |