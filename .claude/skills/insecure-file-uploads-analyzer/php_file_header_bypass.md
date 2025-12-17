# PHP｜文件头检测绕过漏洞

## Details

### 漏洞成因
PHP文件上传验证中，为了允许用户上传图片等特定类型文件，开发者常使用`getimagesize()`、`exif_imagetype()`、`finfo_file()`等函数检测文件的真实类型。这些函数通过读取文件的头部字节（魔术字节）来判断文件类型。攻击者可以构造一个包含恶意PHP代码的图片文件（如图片木马），或者在PHP脚本前添加合法的图片文件头，使检测函数误判为合法图片，从而绕过文件类型验证，实现代码执行。

### 代码示例

**易受攻击的代码 - 简单文件头检测：**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $file = $_FILES['upload'];
    $tmp_name = $file['tmp_name'];
    
    // 仅检测文件头，容易被绕过
    $image_info = getimagesize($tmp_name);
    if ($image_info === false) {
        die('Not a valid image');
    }
    
    // 允许上传，但实际上可能是图片木马
    move_uploaded_file($tmp_name, __DIR__ . '/uploads/' . $file['name']);
}
```

**易受攻击的代码 - exif_imagetype检测：**
```php
$tmp_name = $_FILES['upload']['tmp_name'];

// 使用exif_imagetype检测
$image_type = exif_imagetype($tmp_name);
if (!in_array($image_type, [IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_GIF])) {
    die('Only JPG, PNG, GIF allowed');
}

// 图片木马可通过此检测
move_uploaded_file($tmp_name, 'uploads/' . $_FILES['upload']['name']);
```

**易受攻击的代码 - finfo检测：**
```php
$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime_type = finfo_file($finfo, $_FILES['upload']['tmp_name']);
finfo_close($finfo);

if (!in_array($mime_type, ['image/jpeg', 'image/png', 'image/gif'])) {
    die('Invalid file type');
}

move_uploaded_file($_FILES['upload']['tmp_name'], 'uploads/' . $_FILES['upload']['name']);
```

**安全示例 - 多重验证+内容重写：**
```php
$file = $_FILES['upload'];
$tmp_name = $file['tmp_name'];

// 1. 文件头检测
$image_info = getimagesize($tmp_name);
if ($image_info === false) {
    die('Not a valid image');
}

// 2. MIME类型验证
$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime_type = finfo_file($finfo, $tmp_name);
finfo_close($finfo);

$allowed_mimes = ['image/jpeg', 'image/png', 'image/gif'];
if (!in_array($mime_type, $allowed_mimes)) {
    die('Invalid image type');
}

// 3. 扩展名验证
$ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
$allowed_exts = ['jpg', 'jpeg', 'png', 'gif'];
if (!in_array($ext, $allowed_exts)) {
    die('Invalid extension');
}

// 4. 重新生成图片（去除潜在的恶意代码）
switch ($image_info[2]) {
    case IMAGETYPE_JPEG:
        $image = imagecreatefromjpeg($tmp_name);
        imagejpeg($image, $tmp_name . '_new', 100);
        break;
    case IMAGETYPE_PNG:
        $image = imagecreatefrompng($tmp_name);
        imagepng($image, $tmp_name . '_new', 0);
        break;
    case IMAGETYPE_GIF:
        $image = imagecreatefromgif($tmp_name);
        imagegif($image, $tmp_name . '_new');
        break;
}

// 5. 使用随机文件名
$new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
move_uploaded_file($tmp_name . '_new', __DIR__ . '/uploads/' . $new_filename);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 图片检测：`getimagesize`, `exif_imagetype`, `finfo_open`
- MIME检查：`finfo_file`, `mime_content_type`
- 文件处理：`imagecreatefromjpeg`, `imagecreatefrompng`

**定位步骤：**
1. 搜索上传处理逻辑，检查文件类型检测函数
2. 确认是否仅依赖单一的文件头检测方法
3. 验证是否进行内容重写或二次处理

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **多重验证：** 结合文件头、MIME、扩展名检测
- **内容重写：** 使用GD库重新生成图片
- **白名单机制：** 只允许特定的图片类型
- **文件隔离：** 存储在非执行目录

**定位技巧：**
- 检查是否使用`imagecreatefrom*`函数重新处理图片
- 确认是否对上传后的文件进行内容检查
- 验证是否禁用PHP在上传目录的执行权限

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 内容重写+多重验证+随机命名 | **L0（快速跳过）** | 风险低 |
| 多重验证但无内容重写 | **L2（跳读）** | 需验证其他防护 |
| 仅单一文件头检测 | **L3（逐行读）** | 高风险 |
| 复杂的图片处理逻辑 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 仅使用单一的文件头检测方法
2. 未进行内容重写或二次验证
3. 上传目录可执行PHP脚本

#### 误报
以下情景可判定为误报：
1. 使用GD库重新生成图片内容
2. 多重验证机制（文件头+MIME+扩展名）
3. 存储目录禁止脚本执行

#### 代码异味
需记录的风险：
1. 仅依赖`getimagesize`等单一检测方法
2. 有检测但未验证扩展名一致性
3. 未考虑图片木马的可能性

## Low risk

### 低风险评级场景

#### 1. 图片内容重写
- **场景：** 使用GD库重新生成图片，去除原始内容
- **风险评估：** 可有效清除潜在的恶意代码

#### 2. 多重验证机制
- **场景：** 结合文件头、MIME类型、扩展名多重验证
- **风险评估：** 提高绕过难度，降低风险

#### 3. 存储安全
- **场景：** 上传文件存储在非Web根目录或禁止执行目录
- **风险评估：** 即使绕过也无法直接执行

### 常见绕过方法总结

| 绕过方法 | 示例 | 检测难度 | 防护建议 |
|----------|------|----------|----------|
| 图片木马 | `GIF89a<?php phpinfo();?>` | 低 | 内容重写 |
| 文件头伪造 | 在PHP文件前添加GIF头 | 中 | 多重验证 |
| 复合文件 | 图片+PHP代码组合 | 高 | 深度内容分析 |
| 元数据注入 | 在EXIF中植入代码 | 高 | 元数据清理 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内容重写处理 | 清除恶意代码 | 高 |
| 多重验证机制 | 提高绕过难度 | 高 |
| 存储目录隔离 | 限制执行环境 | 高 |
| 定期安全扫描 | 及时发现威胁 | 中 |