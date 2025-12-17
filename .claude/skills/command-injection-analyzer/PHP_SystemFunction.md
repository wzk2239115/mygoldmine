# PHP System Function 命令注入

## Details

**代码特征示例：**
```php
system($_GET['cmd']);
exec("ping " . $_POST['host'], $output);
shell_exec("convert image.jpg -resize " . $size);
passthru("tar -czf backup.tar.gz " . $filename);
`ffmpeg -i {$_FILES['video']['tmp_name']} output.mp4`;
popen("grep " . $keyword . " file.txt", "r");
proc_open($command, $descriptors, $pipes);
```

**快速定位核心操作：**
- 全局搜索：`system\(|exec\(|shell_exec\(|passthru\(|popen\(|proc_open\(|^`（反引号）
- 关注上下文：`$_GET|$_POST|$_REQUEST|$_COOKIE|$_FILES|file_get_contents\('php://input'`
- 追踪数据流：从用户输入点到命令执行函数的完整路径

**快速定位保护机制：**
- 白名单检查：`in_array()|array_key_exists()|preg_match('/^[a-zA-Z0-9]+$/')`
- 转义函数：`escapeshellarg()|escapeshellcmd()`
- 过滤检查：`filter_var()|preg_replace()|str_replace()`
- 禁用检查：`disable_functions` 配置项

**审计等级：L3（逐行读）**  
- 命令执行函数危险性高，需逐行分析数据流
- 重点追踪用户输入如何传递到执行函数
- 检查所有保护机制是否可被绕过

## Classify

**确认为漏洞：**
- 用户可控参数直接拼接到命令中，无任何过滤：`system("ping " . $_GET['ip'])`
- 使用 `escapeshellcmd()` 但参数未用引号包裹（可通过添加参数绕过）
- 过滤不完整：仅过滤 `;|&` 但遗漏换行符 `%0a`、反引号等
- 白名单校验存在逻辑漏洞：可通过路径穿越、双重编码等绕过

**误报：**
- 执行的命令完全硬编码，无用户输入：`exec("/usr/bin/backup.sh")`
- 用户输入仅用于选择预定义命令索引：`$cmds = ['ls', 'ps']; system($cmds[$_GET['id']]);` 且有严格边界检查
- 使用 `escapeshellarg()` 正确包裹每个用户输入参数

**代码异味：**
- 对用户输入进行黑名单过滤，但过滤规则可能不够完善
- 使用 `escapeshellcmd()` 但命令结构复杂
- 依赖前端验证或客户端过滤
- 权限控制存在但实现不够严谨

## Low risk

**低风险场景：**
- 执行命令需要管理员权限，且权限验证机制完善可靠
- 用户输入被 `escapeshellarg()` 包裹且命令结构简单：`exec("tool --input=" . escapeshellarg($input))`
- 仅在本地环境或内网使用，外部用户无法访问
- 命令执行失败不会造成信息泄露或系统影响
- 存在有效的 WAF 或 IDS 监控异常命令模式
- PHP 配置 `disable_functions` 已禁用相关危险函数（但需确认配置生效）

**降级因素：**
- 执行用户为低权限账户（如 www-data）且系统加固良好
- 存在命令执行时间限制和输出长度限制
- 有完善的审计日志记录所有命令执行