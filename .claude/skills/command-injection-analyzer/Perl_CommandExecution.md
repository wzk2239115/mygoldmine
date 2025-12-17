# Perl 命令执行

## Details

**代码特征示例：**
```perl
# 使用反引号执行命令
my $result = `ls $user_input`;

# 使用 qx() 操作符（等同于反引号）
my @files = qx(find $directory -type f);

# 使用 system() 函数
system("rm", "file_$filename");  # 参数列表形式（相对安全）
system("rm file_$filename");     # 字符串形式（危险）

# 使用 exec() 函数
exec("python", "script.py", $args);

# 使用 open() 管道
open(my $fh, "grep $pattern $file |") or die;
while (<$fh>) { print; }
close($fh);

# 使用 open3 模块
use IPC::Open3;
my $pid = open3(\*CHLD_IN, \*CHLD_OUT, \*CHLD_ERR,
    "tar", "-czf", "backup.tar.gz", $path);

# 危险：直接在 open() 中使用管道
open(my $pipe, "cat $user_file |") or die;

# 使用 glob() 函数进行文件匹配（可能被利用）
my @files = glob("$pattern*");
```

**快速定位核心操作：**
- 全局搜索：`` ` ``（反引号）、`qx\(|qx\{`、`system\(|exec\(|open\(`
- 关注上下文：`$_[|@ARGV|<STDIN>|$ENV`
- 追踪数据流：从用户输入点到命令执行的完整路径
- 检查 system/open 是否使用列表形式（参数分离）或字符串形式（危险）

**快速定位保护机制：**
- 参数列表形式：`system("cmd", "arg1", "arg2")` 而非 `system("cmd arg1 arg2")`
- 使用 IPC::Open3、IPC::Run 等安全模块
- 白名单检查：正则匹配 `=~ /^[pattern]$/`、条件判断
- 转义函数：`quotemeta()`、`String::ShellQuote` 模块
- 过滤检查：`s/|tr/|grep `

**审计等级：L3（逐行读）**
- 反引号和 qx{} 危险性高，需逐行分析
- system/open 的参数形式决定安全性，需仔细区分
- 重点追踪变量插值中的用户输入

## Classify

**确认为漏洞：**
- 用户输入直接插值到反引号或 qx() 中：`` `ls $dir` ``
- 使用 system/exec/open 的字符串形式（无参数分离）：`system("grep $pattern file")`
- 使用 open() 管道时用户输入未转义：`open(my $fh, "cat $file |")`
- 过滤不完整：仅过滤部分特殊字符但遗漏某些 shell 元字符
- glob() 结果直接用于命令构造

**误报：**
- 命令字符串完全硬编码，无用户输入：`` `ls /tmp` ``
- 使用 system/exec 的参数列表形式且参数均为硬编码或验证过的输入
- 使用 IPC::Open3 或 IPC::Run 且参数化传递
- 使用 `quotemeta()` 正确转义所有用户输入

**代码异味：**
- 对用户输入进行黑名单过滤，但规则可能不够完善
- 混合使用字符串形式和列表形式的 system/exec
- 依赖前端验证或环境变量假设
- 权限控制存在但实现不够严谨

## Low risk

**低风险场景：**
- 执行命令需要认证用户且权限控制完善
- 使用 IPC::Run 或 IPC::Open3 进行参数化执行
- 仅在本地环境或内网使用，外部用户无法访问
- 执行的命令受限（仅能执行特定命令）
- 存在有效的输入长度限制和超时控制
- 日志审计机制完善

**降级因素：**
- Perl 脚本以低权限用户运行
- 容器化部署且无敏感挂载
- 命令执行失败不会造成信息泄露
