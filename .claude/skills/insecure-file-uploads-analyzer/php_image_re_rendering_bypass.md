# PHP｜二次渲染绕过漏洞

## Details

### 漏洞成因
PHP应用中处理用户上传的图片时，常使用GD库或ImageMagick进行尺寸调整、水印添加、格式转换等操作。这些图片处理函数会重新解析和生成图片内容，理论上可以清除图片中嵌入的恶意代码。但是，攻击者可以通过精心构造的图片文件，在图片的特定数据结构（如EXIF元数据、注释块、颜色表等）中植入恶意PHP代码。如果二次渲染过程未完全清除这些元数据或特定数据块，恶意代码可能得以保留，当用户访问处理后的图片文件时仍可触发代码执行。

### 代码示例

**易受攻击的代码 - 不完整的图片处理：**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $file = $_FILES['upload'];
    $tmp_name = $file['tmp_name'];
    
    // 验证图片类型
    $image_info = getimagesize($tmp_name);
    if ($image_info === false) {
        die('Invalid image');
    }
    
    // 根据类型创建图片资源
    switch ($image_info[2]) {
        case IMAGETYPE_JPEG:
            $image = imagecreatefromjpeg($tmp_name);
            break;
        case IMAGETYPE_PNG:
            $image = imagecreatefrompng($tmp_name);
            break;
        case IMAGETYPE_GIF:
            $image = imagecreatefromgif($tmp_name);
            break;
        default:
            die('Unsupported image type');
    }
    
    // 仅调整尺寸，可能保留恶意元数据
    $width = imagesx($image);
    $height = imagesy($image);
    $new_image = imagecreatetruecolor(800, 600);
    imagecopyresampled($new_image, $image, 0, 0, 0, 0, 800, 600, $width, $height);
    
    // 保存处理后的图片，但可能保留EXIF数据
    imagejpeg($new_image, __DIR__ . '/uploads/resized_' . $file['name']);
    
    imagedestroy($image);
    imagedestroy($new_image);
}
```

**易受攻击的代码 - 格式转换保留元数据：**
```php
$tmp_name = $_FILES['upload']['tmp_name'];

// 转换为统一格式（如PNG）
$image = imagecreatefromstring(file_get_contents($tmp_name));
if ($image === false) {
    die('Invalid image');
}

// 直接保存为PNG，可能保留原始图片中的元数据
imagepng($image, 'uploads/converted.png');
imagedestroy($image);
```

**攻击示例 - 构造恶意图片：**
```php
// 创建一个包含PHP代码的JPEG图片
$code = '<?php phpinfo(); ?>';

// 创建基础图片
$image = imagecreatetruecolor(100, 100);
$bg_color = imagecolorallocate($image, 255, 255, 255);
imagefill($image, 0, 0, $bg_color);

// 保存为JPEG
ob_start();
imagejpeg($image, null, 100);
$jpeg_data = ob_get_clean();

// 在JPEG数据后追加PHP代码（简化示例）
$malicious_image = $jpeg_data . "\n" . $code;

// 保存恶意图片
file_put_contents('malicious_with_code.jpg', $malicious_image);

// 某些图片处理函数可能无法完全清除追加的数据
```

**安全示例 - 严格的图片重建：**
```php
$file = $_FILES['upload'];
$tmp_name = $file['tmp_name'];

// 1. 多重验证
$image_info = getimagesize($tmp_name);
if ($image_info === false) {
    die('Invalid image');
}

$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime_type = finfo_file($finfo, $tmp_name);
finfo_close($finfo);

$allowed_types = ['image/jpeg', 'image/png', 'image/gif'];
if (!in_array($mime_type, $allowed_types)) {
    die('Invalid image type');
}

// 2. 根据检测类型严格重建图片
$width = $image_info[0];
$height = $image_info[1];

switch ($image_info[2]) {
    case IMAGETYPE_JPEG:
        $source = imagecreatefromjpeg($tmp_name);
        // 创建新的纯净图片资源
        $new_image = imagecreatetruecolor($width, $height);
        // 复制像素数据，不包含元数据
        imagecopy($new_image, $source, 0, 0, 0, 0, $width, $height);
        
        // 保存为新的JPEG文件，不包含EXIF数据
        $output_file = $tmp_name . '_clean';
        imagejpeg($new_image, $output_file, 90);
        break;
        
    case IMAGETYPE_PNG:
        $source = imagecreatefrompng($tmp_name);
        $new_image = imagecreatetruecolor($width, $height);
        
        // 保持PNG透明度
        imagealphablending($new_image, false);
        imagesavealpha($new_image, true);
        imagecopy($new_image, $source, 0, 0, 0, 0, $width, $height);
        
        $output_file = $tmp_name . '_clean';
        imagepng($new_image, $output_file, 9);
        break;
        
    case IMAGETYPE_GIF:
        $source = imagecreatefromgif($tmp_name);
        $new_image = imagecreatetruecolor($width, $height);
        
        // GIF可能需要特殊处理保持调色板
        imagetruecolortopalette($new_image, false, 256);
        imagecopy($new_image, $source, 0, 0, 0, 0, $width, $height);
        
        $output_file = $tmp_name . '_clean';
        imagegif($new_image, $output_file);
        break;
        
    default:
        die('Unsupported image type');
}

// 清理资源
imagedestroy($source);
imagedestroy($new_image);

// 3. 验证重建后的图片
if (getimagesize($output_file) === false) {
    die('Image reconstruction failed');
}

// 4. 使用随机文件名和严格权限
$ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
$new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
move_uploaded_file($output_file, __DIR__ . '/uploads/' . $new_filename);

// 设置文件权限（禁止执行）
chmod(__DIR__ . '/uploads/' . $new_filename, 0644);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 图片处理：`imagecreatefromjpeg`, `imagecreatefrompng`, `imagecreatefromgif`
- 尺寸调整：`imagecopyresampled`, `imagecopyresized`
- 文件保存：`imagejpeg`, `imagepng`, `imagegif`
- EXIF处理：`exif_read_data`, `exif_imagetype`

**定位步骤：**
1. 搜索图片处理相关函数的使用
2. 确认是否仅进行简单的尺寸调整或格式转换
3. 验证是否对处理后的图片进行安全检查

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **像素级重建：** 创建新的图片资源并逐像素复制
- **元数据清理：** 不保留原始的EXIF、注释等元数据
- **多重验证：** 处理前后都进行图片完整性检查
- **格式严格：** 不允许不受支持的图片格式

**定位技巧：**
- 检查是否创建新的`imagecreatetruecolor`资源
- 确认是否使用`imagecopy`而非`imagecopymerge`
- 验证是否对处理后的文件进行二次检测

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 像素级重建+多重验证 | **L0（快速跳过）** | 风险低 |
| 有图片处理但保留元数据 | **L2（跳读）** | 需验证绕过风险 |
| 仅简单尺寸调整 | **L3（逐行读）** | 高风险 |
| 复杂的图片处理流程 | **L4（跨模块追踪）** | 需深入分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 仅进行表面的图片处理（如尺寸调整）
2. 未创建新的纯净图片资源
3. 保留或可能保留原始的元数据
4. 未对处理后的图片进行安全检查

#### 误报
以下情景可判定为误报：
1. 创建新的图片资源并逐像素复制数据
2. 使用严格的图片格式转换和重建
3. 处理前后都进行完整性验证
4. 存储目录禁止脚本执行

#### 代码异味
需记录的风险：
1. 仅使用`imagecopyresampled`等函数进行简单处理
2. 有图片处理但未考虑元数据清理
3. 未验证处理后的图片完整性
4. 处理逻辑过于简单，未考虑安全因素

## Low risk

### 低风险评级场景

#### 1. 严格的像素级重建
- **场景：** 创建新的图片资源并逐像素复制数据
- **风险评估：** 可有效清除原始图片中的恶意内容

#### 2. 格式标准化
- **场景：** 统一转换为安全的图片格式并重建
- **风险评估：** 消除格式相关的安全隐患

#### 3. 多重验证机制
- **场景：** 处理前后都进行图片完整性检查
- **风险评估：** 及时发现处理过程中的异常情况

### 常见图片格式风险分析

| 格式 | 潜在风险 | 安全处理方式 | 注意事项 |
|------|----------|--------------|----------|
| JPEG | EXIF数据注入 | 重新压缩 | 注意质量损失 |
| PNG | 文本块注入 | 过滤辅助数据块 | 保持透明度 |
| GIF | 注释扩展块 | 重建调色板 | 注意动画帧 |
| BMP | 较少元数据 | 直接重建 | 文件大小较大 |
| TIFF | 多IFD结构 | 严格过滤 | 格式复杂 |

### 绕过技术总结

| 绕过方法 | 目标格式 | 检测难度 | 防护策略 |
|----------|----------|----------|----------|
| EXIF注入 | JPEG | 低 | 清除EXIF数据 |
| 文本块注入 | PNG | 中 | 过滤文本块 |
| 注释注入 | GIF | 中 | 重建逻辑结构 |
| 数据追加 | 所有格式 | 低 | 严格格式重建 |
| 多帧隐藏 | GIF | 高 | 帧数据清理 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 像素级重建 | 彻底清除原始内容 | 高 |
| 格式标准化 | 消除格式相关风险 | 高 |
| 多重验证 | 提高安全性 | 中 |
| 存储隔离 | 限制执行环境 | 高 |