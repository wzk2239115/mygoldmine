# Command Injection - 环境变量污染攻击

## Details

### 什么是环境变量污染

环境变量污染（Environment Variable Injection/Pollution）是指攻击者通过控制或修改进程的环境变量，影响应用或其执行的系统命令行为的攻击。与直接的命令注入不同，环境变量污染不需要在命令字符串中注入代码，而是利用系统对环境变量的处理机制。

### 常见的环境变量污染攻击

#### 1. PATH 污染

**原理：** 操作系统在执行不带完整路径的命令时，会按照 PATH 环境变量中的目录顺序搜索可执行文件。攻击者可以通过控制 PATH 来指向恶意的可执行文件。

**危险代码：**
```java
// Java 示例
String[] cmd = {"grep", "pattern", "file.txt"};
Runtime.getRuntime().exec(cmd);  // 危险：不使用完整路径
```

**攻击方式：**
```bash
# 攻击者准备恶意脚本
mkdir /tmp/attacker
echo '#!/bin/bash
  echo "Hacked by attacker"
  cat /etc/passwd > /tmp/attacker/output.txt
' > /tmp/attacker/grep
chmod +x /tmp/attacker/grep

# 修改 PATH 环境变量
export PATH=/tmp/attacker:$PATH

# 当应用执行 grep 命令时，会执行攻击者的版本
```

**影响：** 如果应用以 root 或其他特权用户运行，攻击者可以执行任意命令。

#### 2. LD_PRELOAD 污染

**原理：** LD_PRELOAD 环境变量指定在程序加载前预加载的共享库。攻击者可以注入恶意的共享库来拦截系统调用。

**危险代码：**
```python
# Python 示例
import os
import subprocess

# 应用调用系统命令
os.system("some_command")  # 危险：继承环境变量
```

**攻击方式：**
```c
// evil.c - 恶意共享库
#include <stdlib.h>
#include <unistd.h>

int system(const char *cmd) {
    // 拦截 system() 调用，执行恶意代码
    setuid(0);  // 如果原进程有权限
    system("cat /etc/shadow > /tmp/attacker/shadow");
    return 0;
}
```

```bash
# 编译恶意库
gcc -shared -fPIC evil.c -o /tmp/attacker/evil.so

# 运行应用时设置 LD_PRELOAD
export LD_PRELOAD=/tmp/attacker/evil.so
./vulnerable_app
```

#### 3. LD_LIBRARY_PATH 污染

**原理：** LD_LIBRARY_PATH 指定动态链接库的搜索路径。攻击者可以在其中放置恶意的库文件。

**攻击方式：**
```bash
# 创建恶意的 libc
# 当应用加载时，会使用攻击者的 libc 而非系统的

export LD_LIBRARY_PATH=/tmp/attacker:$LD_LIBRARY_PATH
./vulnerable_app
```

#### 4. IFS 污染

**原理：** IFS（Internal Field Separator）定义 shell 如何分割单词。攻击者可以通过修改 IFS 来改变命令解析。

**危险代码：**
```bash
#!/bin/bash
# 危险：直接执行用户输入
user_input=$1
grep "$user_input" file.txt  # 看起来被引用了，但 IFS 污染仍可能有效
```

**攻击方式：**
```bash
# 设置 IFS 为空格
export IFS=";"

# 当 shell 解析命令时，会按照新的 IFS 分割
# 原本的 grep "pattern" file.txt 可能变成 "grep" ";" "pattern"
```

### 典型代码示例

**Java - 继承 PATH 污染：**
```java
public class VulnerableCommand {
    public static void main(String[] args) throws Exception {
        // 危险：不使用完整路径
        String[] cmd = {"grep", "-r", "pattern", "/var/www"};
        Process p = Runtime.getRuntime().exec(cmd);

        // 如果 PATH 被污染，会执行 /tmp/attacker/grep
    }
}
```

**安全版本：**
```java
public class SafeCommand {
    public static void main(String[] args) throws Exception {
        // 安全：使用完整路径
        String[] cmd = {"/bin/grep", "-r", "pattern", "/var/www"};
        Process p = Runtime.getRuntime().exec(cmd);
    }
}
```

**Python - LD_PRELOAD 污染：**
```python
import os
import subprocess

# 危险：继承所有环境变量
subprocess.run(["some_binary"], cwd="/home/app")

# 如果 LD_PRELOAD 被设置，恶意库会被加载
```

**安全版本：**
```python
import os
import subprocess

# 安全：设置清洁的环境变量
clean_env = {
    'PATH': '/bin:/usr/bin:/usr/local/bin',
    'HOME': '/home/app'
}
# 移除危险的变量：LD_PRELOAD, LD_LIBRARY_PATH, IFS 等

p = subprocess.run(["some_binary"], env=clean_env)
```

**Go - PATH 污染：**
```go
package main

import (
    "os/exec"
)

func main() {
    // 危险：不使用完整路径
    cmd := exec.Command("wget", "http://example.com/file")
    cmd.Run()
}
```

**安全版本：**
```go
package main

import (
    "os/exec"
)

func main() {
    // 安全：使用完整路径
    cmd := exec.Command("/usr/bin/wget", "http://example.com/file")
    cmd.Run()
}
```

### 快速定位核心操作（L1: 关键词扫描）

**危险环境变量：**
- `PATH` - 可执行文件搜索路径
- `LD_PRELOAD` - 预加载共享库
- `LD_LIBRARY_PATH` - 库文件搜索路径
- `LD_AUDIT` - 审计库
- `JAVA_TOOL_OPTIONS` - Java 工具选项
- `PYTHONPATH` - Python 模块搜索路径
- `IFS` - Shell 字段分隔符
- `HOME`, `SHELL`, `TMPDIR` - 路径相关
- `RUBYLIB` - Ruby 库路径
- `PERL5LIB` - Perl 库路径

**命令执行函数：**
```
Java:
  Runtime.getRuntime().exec()
  ProcessBuilder.start()

Python:
  os.system()
  subprocess.run()
  subprocess.Popen()

Go:
  exec.Command()
  syscall.Exec()

PHP:
  system()
  exec()
  shell_exec()
  passthru()
  proc_open()

C/C++:
  system()
  fork() + execvp()
  popen()
```

**危险模式：**
```
// 不使用完整路径
exec.Command("wget", ...)
subprocess.run(["curl", ...])
Runtime.getRuntime().exec("grep ...")

// 继承所有环境变量
Runtime.getRuntime().exec(cmd)  // Java 默认继承
subprocess.run(cmd)              // Python 默认继承

// 用户可控的 PATH 设置
String path = request.getParameter("path");
Process p = Runtime.getRuntime().exec(...);
```

### 快速定位保护机制（L2: 跳读）

**环境变量清理：**
```java
// Java 示例：清理环境变量
Map<String, String> env = ProcessBuilder.environment();
env.clear();
env.put("PATH", "/bin:/usr/bin:/usr/local/bin");
env.put("HOME", "/home/app");
// 移除 LD_PRELOAD, LD_LIBRARY_PATH 等
```

**完整路径使用：**
```python
# Python 示例：始终使用完整路径
which_result = subprocess.check_output(["/usr/bin/which", "wget"])
wget_path = which_result.strip()
subprocess.run([wget_path, "http://example.com"])
```

**命令白名单：**
```go
// Go 示例：白名单允许的命令
allowedCommands := map[string]string{
    "wget": "/usr/bin/wget",
    "curl": "/usr/bin/curl",
}

if path, ok := allowedCommands[cmd]; ok {
    exec.Command(path, args...).Run()
} else {
    return fmt.Errorf("Command not allowed")
}
```

**审计技巧（L3: 逐行读）：**
- 查找所有命令执行的地方
- 检查是否使用了完整路径（以 `/` 开头）
- 查找是否明确设置了环境变量（而非继承）
- 检查环境变量是否包含来自用户输入的值
- 验证 PATH 是否被限制为安全的目录

**跨模块保护（L4: 跨模块追踪）：**
- 是否存在全局的环境变量清理函数
- 框架层面是否提供了安全的命令执行 API
- 容器/沙箱是否限制了环境变量的修改
- 是否禁用了 LD_PRELOAD 等危险的环境变量

## Classify

### 确认为漏洞

- 应用执行不带完整路径的命令（如 `grep`, `wget` 而非 `/bin/grep`, `/usr/bin/wget`）
- 环境变量未被清理，直接继承
- PATH 包含用户可写入的目录（如 `/tmp`）
- 应用以 root 或其他高权限用户运行
- 可以通过 PoC 验证：创建恶意的可执行文件，通过 PATH 污染被执行

### 误报场景

- 所有命令都使用了完整路径
- 环境变量被显式清理，仅包含安全值
- PATH 仅包含系统目录（`/usr/bin`, `/bin`），不包含用户目录
- 应用运行在隔离的容器中，无法修改父进程的环境变量
- 操作系统级别禁用了 LD_PRELOAD（使用 `-z noload` 标志编译）

### 代码异味

- 命令执行代码分散在多个模块，难以统一审计
- 某些地方使用完整路径，某些地方不使用
- 环境变量设置不一致
- 没有统一的命令执行封装

## Low risk

### 降级为低风险的情况

- **完整路径**：所有执行的命令都使用了绝对路径
- **环境清理**：显式清理了所有危险的环境变量（LD_PRELOAD, LD_LIBRARY_PATH, IFS 等）
- **安全 PATH**：PATH 仅包含系统目录，不包含用户目录或临时目录
- **低权限运行**：应用运行在非 root 用户，权限受限
- **容器隔离**：应用运行在 Docker/Kubernetes 等容器中，进程隔离

### 需要额外评估的因素

- 应用运行的权限级别
- 是否存在 SUID/SGID 位（提升权限的风险）
- 应用是否与不受信任的代码共享环境
- 是否有其他方式修改环境变量（配置文件、启动脚本）
- 是否存在时间窗口使 PATH 可被修改
