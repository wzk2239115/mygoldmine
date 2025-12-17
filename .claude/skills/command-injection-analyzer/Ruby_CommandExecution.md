# Ruby 命令执行

## Details

**代码特征示例：**
```ruby
# 使用反引号执行命令
result = `ls #{user_input}`

# 使用 %x{} 语法
files = %x{find #{directory} -type f}

# 使用 system() 函数
system("rm " + filename)

# 使用 exec() 函数（替换当前进程）
exec("python script.py #{args}")

# 使用 Kernel.spawn() - 返回进程ID
pid = spawn("ffmpeg -i #{input_file} output.mp4")

# 使用 IO.popen() - 管道调用
output = IO.popen("grep #{pattern} #{file}").read

# 使用 Open3 模块
Open3.popen3("tar -czf backup.tar.gz #{path}") { |stdin, stdout, stderr| }

# 使用 backtick 的符号版本
result = send(:`, "cat #{filename}")
```

**快速定位核心操作：**
- 全局搜索：`` ` ``（反引号）、`%x{|}`、`system\(|exec\(|spawn\(|popen\(`
- 关注上下文：`params\[|request\.|ENV\[|ARGV|gets|$stdin`
- 追踪数据流：从用户输入点到命令执行的完整路径
- 检查是否使用了字符串插值 `#{}` 或字符串拼接 `+`

**快速定位保护机制：**
- 白名单检查：`Array#include?`、`case/when` 语句、正则匹配
- 参数化执行：使用数组形式而非字符串拼接
- 转义函数：`Shellwords.escape`、`Shellwords.shelljoin`
- 过滤检查：`gsub(|sub(|tr(`

**审计等级：L3（逐行读）**
- 反引号和 %x{} 危险性高，需逐行分析
- 重点追踪字符串插值中的用户输入
- 检查所有保护机制是否可被绕过

## Classify

**确认为漏洞：**
- 用户输入通过字符串插值 `#{}` 嵌入到反引号或 %x{} 中：`` `ls #{dir}` ``
- 用户输入直接拼接到 system/exec 的命令字符串：`system("grep " + pattern + " file")`
- 使用 spawn 或 popen 执行拼接后的命令字符串
- 过滤不完整：仅过滤部分字符但遗漏某些 shell 元字符
- 白名单校验存在逻辑漏洞：可通过路径穿越、编码绕过

**误报：**
- 命令字符串完全硬编码，无用户输入：`` `ls /tmp` ``
- 用户输入仅用于参数，通过数组形式传递且无 shell 调用：`system(["ls", "-l", user_input])`
- 使用 `Shellwords.escape` 正确转义所有用户输入参数
- 使用 Open3 或 Process 库且参数化传递

**代码异味：**
- 对用户输入进行黑名单过滤，但规则可能不够完善
- 使用 `Shellwords.shelljoin` 但命令结构复杂
- 依赖前端验证或环境变量假设
- 权限控制存在但实现不够严谨

## Low risk

**低风险场景：**
- 执行命令需要认证用户且权限控制完善
- 用户输入通过 `Shellwords.escape` 转义且命令结构简单
- 仅在本地环境或内网使用，外部用户无法访问
- 执行的命令受限（仅能执行特定命令，如 `ls`、`echo`）
- 存在有效的输入长度限制和超时控制
- 日志审计机制完善

**降级因素：**
- Ruby 进程以低权限用户运行（如 nobody）
- 容器化部署且无敏感挂载
- 命令执行失败不会造成信息泄露
