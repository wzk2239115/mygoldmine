# PHP Phar 反序列化漏洞

**漏洞概述**  
通过 phar:// 伪协议触发反序列化，常出现在文件操作、文件包含、图片处理等场景。无需显式调用 `unserialize()`，大量文件操作函数均可触发，结合 POP Chain 实现 RCE。

---

## Details

### 典型代码示例

**场景1：文件操作函数触发**
```php
// 危险：用户可控路径且未过滤 phar://
$file = $_GET['file'];
file_get_contents($file);          // 触发点
file_exists($file);                // 触发点
is_dir($file);                     // 触发点
filesize($file);                   // 触发点
md5_file($file);                   // 触发点
```

**场景2：文件包含触发**
```php
// 危险：include/require 系列函数
$path = $_POST['template'];
include($path);                    // phar://evil.jpg 触发反序列化
require_once($path);               // 触发点
```

**场景3：图片处理触发**
```php
// 危险：GD 库、exif 函数
$image = $_FILES['avatar']['tmp_name'];
$size = getimagesize($image);      // 触发点
exif_read_data($image);            // 触发点
imagecreatefromjpeg($image);       // 触发点
```

**场景4：文件上传+重命名触发**
```php
// 危险：copy、rename 等文件操作
$src = $_POST['source'];
$dst = '/uploads/' . basename($src);
copy($src, $dst);                  // 触发点
rename($src, $dst);                // 触发点
```

**场景5：压缩/解压触发**
```php
// 危险：压缩包处理
$archive = $_GET['zip'];
$zip = new ZipArchive();
$zip->open($archive);              // 触发点
```

**场景6：XML/JSON 外部实体加载**
```php
// 危险：通过 XXE 或 SSRF 配合 phar://
$xml = simplexml_load_file($_GET['xml']);  // phar:// wrapper
```

**场景7：文件流操作**
```php
// 危险：fopen/fread/fgets 系列
$handle = fopen($_GET['log'], 'r');        // 触发点
fread($handle, 1024);
```

**场景8：Gadget Chain 示例**
```php
// 利用链：含有魔术方法的类
class FileManager {
    private $filename;
    
    function __destruct() {
        unlink($this->filename);   // 文件删除
    }
}

class Logger {
    private $handler;
    
    function __wakeup() {
        $this->handler->write();   // 任意方法调用
    }
}

class Executor {
    private $cmd;
    
    function __toString() {
        system($this->cmd);        // 命令执行
        return "";
    }
}
```

---

### 快速定位核心操作的技巧

**L1 - 关键词扫描：**
- 文件操作函数：`file_get_contents`、`file_exists`、`is_dir`、`is_file`、`filesize`、`filetype`、`file_put_contents`、`readfile`、`fopen`、`fread`、`fgets`、`fgetss`、`fgetcsv`、`stat`、`lstat`
- 文件包含函数：`include`、`require`、`include_once`、`require_once`
- 图片处理函数：`getimagesize`、`imagecreatefrom*`、`exif_read_data`、`exif_thumbnail`
- 压缩函数：`ZipArchive::open`、`gzopen`、`bz2open`
- 文件系统函数：`copy`、`rename`、`unlink`、`rmdir`、`touch`、`chmod`、`chown`、`is_executable`、`is_readable`、`is_writable`
- 哈希函数：`md5_file`、`sha1_file`、`hash_file`

**L2 - 跳读定位参数来源：**
- 检查上述函数的参数是否来自外部输入：`$_GET`、`$_POST`、`$_REQUEST`、`$_COOKIE`、`$_FILES`、`$_SERVER['PATH_INFO']`
- 关注包含用户可控部分的路径拼接：`$dir . $_GET['file']`
- 检查是否存在文件上传功能（任意扩展名上传或白名单仅校验扩展名）

**L3 - 逐行追踪数据流：**
- 跟踪用户输入从接收到传递给文件函数的完整流程
- 检查是否存在路径规范化：`realpath()`、`basename()`、路径拼接
- 验证参数过滤逻辑：是否仅过滤 `php://`、`file://` 而遗漏 `phar://`
- 确认文件上传后的存储路径是否可预测或可遍历
- 检查 `.htaccess` 或 nginx 配置是否禁止执行 `.jpg`、`.png` 等伪装后缀

**L4 - 跨模块追踪 POP Chain：**
- 全局搜索魔术方法：`__destruct`、`__wakeup`、`__toString`、`__call`、`__get`、`__set`、`__isset`、`__unset`、`__invoke`
- 识别危险魔术方法实现：命令执行（`system`、`exec`、`shell_exec`、`passthru`、`popen`、``cmd``）、文件操作、反射调用、动态函数调用（`call_user_func`、`$var()`）
- 检查第三方库/框架中的已知 Gadget：Laravel、ThinkPHP、Symfony、Yii、Zend、Guzzle、Monolog、SwiftMailer
- 追踪对象属性链：`$obj->prop1->prop2->dangerousMethod()`
- 关注 `__autoload` 或 `spl_autoload_register` 自动加载的类

---

### 快速定位保护机制的技巧

**L1 - 关键词扫描防护措施：**
- 协议白名单：`in_array($protocol, ['http', 'https'])`
- 路径黑名单：`strpos($path, 'phar://') !== false`
- 文件魔术字节检查：`finfo_file`、`mime_content_type`、`getimagesize` 返回值校验
- `phar.readonly` 配置：`ini_get('phar.readonly')`
- Stream Wrapper 禁用：`stream_wrapper_unregister('phar')`

**L2 - 跳读检查防护强度：**
```php
// 白名单示例（有效）
$allowed = ['http', 'https', 'ftp'];
$scheme = parse_url($url, PHP_URL_SCHEME);
if (!in_array($scheme, $allowed)) {
    die('Invalid protocol');
}

// 黑名单示例（可能被绕过）
if (strpos($path, 'phar://') !== false) {
    die('Phar not allowed');  // 大小写绕过：Phar://、PHAR://
}

// 后缀检查（不可靠）
$ext = pathinfo($file, PATHINFO_EXTENSION);
if (!in_array($ext, ['jpg', 'png'])) {
    die('Invalid extension');  // phar 可伪装成任意后缀
}
```

**L3 - 逐行分析防护有效性：**
- 协议过滤是否区分大小写（`phar://` vs `Phar://` vs `PHAR://`）
- 是否仅检查文件扩展名而未验证真实文件内容
- `parse_url()` 是否正确解析特殊格式：`phar://./file.jpg`、`phar://../../file.png`
- 文件上传是否重写文件内容（移除 phar stub）或重新编码图片
- 是否存在二次文件操作（上传后的预览、缩略图生成、病毒扫描）
- 魔术方法是否存在但当前未被利用（潜在风险）

**L4 - 架构层全局防护：**
- PHP 配置：`phar.readonly = On`（禁止写入 phar，但不影响反序列化）
- Stream Wrapper 禁用：`php.ini` 中 `disable_functions` 包含 `stream_wrapper_restore`
- WAF 规则：检测 `phar://` 协议特征、phar 文件头标识（`__HALT_COMPILER();`）
- 容器隔离：禁用不必要的文件系统访问、只读文件系统
- disable_functions 配置：禁用 `system`、`exec`、`passthru`、`shell_exec`、`pcntl_exec` 等命令执行函数（防御 POP Chain）
- open_basedir 限制：限制文件访问路径范围
- Suhosin/Hardened-PHP 扩展：检测反序列化异常行为

---

## Classify

### 真实漏洞的判定标准
1. **外部可控路径**：文件操作函数的路径参数来自用户输入（GET/POST/Cookie/文件上传）且未严格白名单校验协议
2. **存在 POP Chain**：代码中存在可利用的魔术方法链，能实现文件删除、命令执行、任意文件读写等危险操作
3. **可上传 phar 文件**：存在文件上传功能，允许上传伪装成图片等格式的 phar 文件，或能通过其他漏洞（SSRF、XXE）引入 phar
4. **无有效防护**：未禁用 phar wrapper、未严格校验文件内容、未使用协议白名单、或黑名单可绕过（大小写、编码）
5. **执行路径可达**：文件操作会实际执行（非死代码），且攻击者能控制触发时机

### 误报的典型特征
1. **路径不可控**：文件路径完全硬编码或来自数据库/配置文件等可信来源，用户无法影响
2. **协议严格白名单**：使用 `parse_url()` 提取协议并与白名单比对（区分大小写），仅允许 `http/https`
3. **phar.readonly = On 且无 POP Chain**：虽然配置无法阻止反序列化，但代码中无可利用的魔术方法
4. **文件内容完全重写**：上传的图片经 GD 库重新渲染（`imagecreatefrom*` + `image*` 保存），破坏 phar 结构
5. **不可达代码**：文件操作在测试代码、废弃模块或永远不执行的条件分支中

### 代码异味的识别
1. **弱黑名单**：仅过滤 `phar://` 小写形式，未考虑大小写变体或 URL 编码绕过
2. **仅校验扩展名**：依赖 `pathinfo()` 或正则匹配后缀，未使用 `finfo_file()` 验证文件头
3. **存在 Gadget 但未触发**：代码中有危险魔术方法但当前无文件上传或路径注入点
4. **半可控路径**：路径拼接中仅文件名可控，目录固定，但可能通过 `../` 目录穿越
5. **依赖客户端校验**：前端 JS 校验文件类型但后端未二次验证
6. **过时的防护措施**：仅检查 `php://` 和 `file://`，对 `phar://` 无认知

---

## Low Risk

### 低风险场景的评判依据

**完善的协议白名单**
- 使用 `parse_url()` 提取协议并与严格白名单比对（仅允许 `http`、`https`、`data`）
- 大小写不敏感过滤：`strtolower($scheme)`
- 对不在白名单的协议立即拒绝，无异常处理绕过

**文件内容深度校验**
- 使用 `finfo_file($file, FILEINFO_MIME_TYPE)` 校验 MIME 类型
- 对图片文件使用 `getimagesize()` 且验证返回值非 `false`
- 通过 GD 库重新渲染图片：`imagecreatefromjpeg()` → `imagejpeg()` 保存，彻底破坏 phar 结构
- 使用病毒扫描引擎（ClamAV）检测异常文件结构

**路径完全不可控**
- 文件路径完全硬编码或来自配置文件/数据库白名单
- 用户输入仅用于查询文件 ID，实际路径由系统生成
- 文件存储在对象存储（S3、OSS）且通过签名 URL 访问，无本地路径操作

**缺少可利用的 POP Chain**
- 项目中无第三方库的已知 Gadget
- 自定义类中魔术方法均为简单日志记录或属性初始化，无危险操作
- 禁用了命令执行函数：`disable_functions = system,exec,shell_exec,passthru,proc_open,popen,pcntl_exec`

**沙箱与隔离防护**
- 运行在容器中且文件系统只读（除特定上传目录）
- 使用 open_basedir 限制访问范围：`open_basedir = /var/www/html:/tmp`
- Seccomp/AppArmor 限制系统调用
- 文件上传目录设置 `noexec` 挂载选项

**多层防御机制**
- WAF 检测 phar 文件头特征：`__HALT_COMPILER();` 或十六进制 `3c3f706870`
- 上传文件自动重命名为随机字符串+时间戳，原始文件名不保留
- 文件操作日志完整记录，异常访问触发告警
- 定期扫描上传目录，检测包含 `__HALT_COMPILER` 的可疑文件

**业务场景限制**
- 文件操作仅用于内部管理后台，需要强认证（双因素/硬件令牌）
- 功能处于维护模式，计划迁移到对象存储方案
- 反序列化后即使触发 POP Chain，因 disable_functions 限制无法实现有效攻击