# PHP shell_exec() / 反引号运算符 命令注入

**漏洞场景**：文件管理、备份恢复、图像处理（ImageMagick/FFmpeg调用）、第三方服务调用、系统监控脚本、文件压缩解压等

---

## Details

**典型代码模式**：
```php
// 危险：shell_exec() 函数
$output = shell_exec("ls -la " . $_GET['dir']);
$result = shell_exec("convert {$uploadPath} output.png");
$data = shell_exec('ping -c 4 ' . $userInput);

// 危险：反引号运算符（等价于 shell_exec）
$output = `whoami`;
$files = `find /tmp -name {$filename}`;
```

**核心定位技巧**：
- 关键函数：`shell_exec()`、`exec()`、`system()`、`passthru()`、`popen()`、`proc_open()`
- 反引号运算符：`` `命令` ``（容易被忽略）
- 危险操作：使用 `.`、`"{$var}"`、双引号字符串插值拼接外部输入
- 数据流：`$_GET`/`$_POST`/`$_REQUEST`/`$_COOKIE` → 字符串拼接 → 命令执行函数

**保护机制定位**：
- 检查是否使用 `escapeshellcmd()` / `escapeshellarg()` 包装参数
- 查找白名单校验：`preg_match()`、`in_array()`、`switch-case` 硬编码值
- 确认输入来源：配置文件/数据库常量 vs 用户可控参数
- 框架防护：检查 Laravel Validator、Symfony Input Constraint

**审计等级**：**L3-L4**（逐行读/跨模块追踪）  
理由：需追溯参数从请求入口→业务逻辑→命令执行的完整链路，确认过滤时机与有效性

---

## Classify

| 分类 | 判定条件 |
|------|---------|
| **真实漏洞** | ① 输入来自外部（`$_GET`、`$_POST`、`$_FILES['name']`、`$_SERVER['HTTP_*']`）<br>② 直接拼接到命令字符串，或使用双引号变量插值<br>③ 未使用 `escapeshellarg()` 或白名单校验失效 |
| **误报** | ① 参数为硬编码字符串或配置文件常量<br>② 输入已通过严格正则校验（如 `^[a-zA-Z0-9._-]+$`）<br>③ 使用 `escapeshellarg()` 正确包裹每个参数 |
| **代码异味** | ① 输入来自数据库但缺乏字段约束说明<br>② 使用 `escapeshellcmd()` 而非 `escapeshellarg()`（可被绕过）<br>③ 仅黑名单过滤特殊字符（`;`、`|`、`&`、`$`、换行符等） |

**特别注意**：
- `escapeshellcmd()` 仅转义整个命令，无法防止参数注入
- 反引号运算符常被静态分析工具遗漏
- 字符串单引号 vs 双引号：单引号不解析变量（相对安全）

---

## Low risk

**降级评估条件**：
1. **受限运行环境**：Docker容器 + 禁用危险命令、`disable_functions` 配置、`open_basedir` 限制
2. **输入长度限制**：参数 `substr($input, 0, 10)` 截断且严格字符类型校验
3. **最小权限**：PHP进程以 `www-data` / `nobody` 运行、无 SUID 二进制文件
4. **业务特性**：管理后台功能且需要超级管理员权限 + 二次认证
5. **部分防护**：虽使用弱转义但参数位置固定（如文件扩展名），攻击面极窄

**注意**：低风险≠无风险，应在审计报告中标注为"待修复"，建议使用参数化调用或白名单映射。