# Java | ProcessBuilder环境变量注入漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-30分钟

## 🚀 30秒快速清单
- [ ] ProcessBuilder是否继承了父进程的环境变量？
- [ ] 环境变量中是否存在用户可控的值（如PATH、LD_PRELOAD）？
- [ ] 是否调用了 `environment()` 方法清理环境变量？
- [ ] 是否验证了要执行的命令的完整路径？
- [ ] 用户输入是否可能修改关键环境变量？

## Details

### 漏洞成因
Java中的ProcessBuilder默认继承父进程的环境变量。如果父进程的环境变量（如PATH、LD_PRELOAD、IFS等）可被用户控制，或如果命令执行时环境变量未被清理，攻击者可以通过污染环境变量来执行恶意命令或库。此漏洞常见于需要执行外部程序或脚本的应用中。

### 代码示例

```java
// 漏洞1：ProcessBuilder继承父进程环境变量
import java.io.IOException;

public class CommandExecutor {

    public void executeCommand(String userInput) throws IOException {
        // 问题：ProcessBuilder默认继承所有环境变量
        ProcessBuilder pb = new ProcessBuilder("sh", "-c", userInput);

        // 未清理环境变量，攻击者可污染PATH
        // 设置 PATH=/tmp:/attacker/path
        // 来执行恶意命令
        Process process = pb.start();
    }
}
// 攻击场景：
// 1. 在/tmp中创建恶意脚本 ls, cat, grep 等
// 2. 设置环境变量 PATH=/tmp:$PATH
// 3. 当ProcessBuilder执行命令时，先从/tmp找命令
```

```java
// 漏洞2：LD_PRELOAD环境变量注入
public class LibraryLoader {

    public void compileSourceFile(String filename) throws IOException {
        // 编译命令，通常需要执行gcc或javac
        ProcessBuilder pb = new ProcessBuilder("gcc", "-o", "output", filename);

        // 问题：继承LD_PRELOAD环境变量
        // 攻击者可设置 LD_PRELOAD=/tmp/malicious.so
        // 在GCC执行时，恶意库会被加载并执行

        Process process = pb.start();
        process.waitFor();
    }
}
// LD_PRELOAD允许在程序启动时加载任意共享库
// 攻击者可在恶意库中执行任意代码
```

```java
// 漏洞3：IFS环境变量注入（分隔符污染）
public class FileProcessor {

    public void processFiles(String pattern) throws IOException {
        // 问题：pattern可能来自用户输入
        String cmd = "find /data -name " + pattern;

        ProcessBuilder pb = new ProcessBuilder("sh", "-c", cmd);

        // 未清理IFS（Internal Field Separator）
        // 攻击者可设置 IFS=\n
        // 使得find命令的参数分割方式改变

        Process process = pb.start();
    }
}
```

```java
// 漏洞4：HOME和TMPDIR环境变量污染
public class ConfigReader {

    public void readUserConfig() throws IOException {
        ProcessBuilder pb = new ProcessBuilder("cat", "~/.config/app.conf");

        // 问题1：HOME环境变量未清理
        // 攻击者可设置 HOME=/tmp/evil
        // 使得程序读取 /tmp/evil/.config/app.conf

        // 问题2：TMPDIR未清理
        // 攻击者可设置 TMPDIR=/dev/shm
        // 导致临时文件写入预期位置之外

        Process process = pb.start();
    }
}
```

```java
// 漏洞5：JAVA_TOOL_OPTIONS环境变量注入
public class JarRunner {

    public void runJar(String jarPath) throws IOException {
        // JAVA_TOOL_OPTIONS环境变量会被JVM自动处理
        ProcessBuilder pb = new ProcessBuilder("java", "-jar", jarPath);

        // 问题：JAVA_TOOL_OPTIONS可被攻击者设置
        // 攻击者可设置 JAVA_TOOL_OPTIONS=-javaagent:/tmp/malicious.jar
        // JVM会自动加载恶意Agent，执行任意代码

        Process process = pb.start();
        process.waitFor();
    }
}
```

### 快速定位核心操作
- **关键词扫描**：`ProcessBuilder`, `new ProcessBuilder()`, `environment()`, `start()`, 环境变量相关的命令执行
- **ProcessBuilder创建**：`new ProcessBuilder(...)`, `command()` 方法
- **命令执行**：`start()`, `waitFor()`
- **环境变量使用**：缺少 `environment().clear()` 或 `environment().remove()`
- **外部程序执行**：调用 `gcc`, `cc`, `java`, `sh` 等

### 快速定位保护机制
- **环境变量清理**：`ProcessBuilder pb = new ProcessBuilder(...); pb.environment().clear();`
- **最小权限原则**：仅设置必要的环境变量如 `PATH`, `HOME`
- **白名单验证**：验证执行的命令完整路径
- **参数分离**：不使用 `sh -c` 直接拼接命令，而是传递参数列表
- **禁用危险变量**：明确删除 `LD_PRELOAD`, `LD_LIBRARY_PATH`, `JAVA_TOOL_OPTIONS` 等

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **未清理环境变量**：ProcessBuilder未调用 `environment().clear()`
2. **继承危险变量**：PATH, LD_PRELOAD, JAVA_TOOL_OPTIONS等可被污染
3. **依赖环境PATH**：执行命令时使用相对路径或仅命令名
4. **使用sh -c执行**：通过shell执行字符串命令，易受环境变量影响
5. **HOME/TMPDIR未验证**：可被攻击者修改的目录路径

**典型漏洞特征**：
- `new ProcessBuilder(cmd1, cmd2, ...)` 后未调用 `environment().clear()`
- 直接使用 `ProcessBuilder pb = new ProcessBuilder("command")`
- 使用 `ProcessBuilder pb = new ProcessBuilder("sh", "-c", command)`
- 缺少 `environment().remove("LD_PRELOAD")`
- 缺少 `environment().remove("JAVA_TOOL_OPTIONS")`
- 执行 `find`, `gcc`, `java` 等程序时未设置完整路径

### 误报排除
- ✗ ProcessBuilder中显式调用 `environment().clear()`
- ✗ 明确指定命令的完整路径（如 `/usr/bin/find`）
- ✗ 明确删除危险环境变量：`environment().remove("LD_PRELOAD")`
- ✗ 不使用shell模式执行，直接传递参数列表
- ✗ 仅设置必要的环境变量
- ✗ 验证用户输入不包含目录遍历或环境变量引用

### 代码异味（需进一步验证）
- △ 调用 `environment().clear()` 但之后又添加了许多变量
- △ 只删除部分危险变量，忽略了其他（如JAVA_TOOL_OPTIONS）
- △ 执行的命令路径来自配置文件，但配置文件本身可被篡改

---

## Low Risk

### 给予低风险评级的场景

1. **环境变量隔离**
   - ProcessBuilder显式调用 `environment().clear()`
   - 仅添加必要的环境变量
   - 删除所有危险变量（LD_PRELOAD, LD_LIBRARY_PATH, JAVA_TOOL_OPTIONS）

2. **命令路径验证**
   - 使用绝对路径执行命令（`/usr/bin/find` 而非 `find`）
   - 从白名单中验证命令路径
   - 不允许用户指定要执行的命令

3. **参数分离**
   - 使用ProcessBuilder的参数列表，不使用shell模式
   - 不拼接字符串构造命令
   - 参数与命令分开传递

4. **输入验证**
   - 用户输入不包含目录遍历（../）
   - 用户输入不包含环境变量引用（$HOME, ${PATH}）
   - 输入经过严格白名单验证

5. **权限隔离**
   - 使用受限用户账户运行应用
   - 应用无法修改系统PATH
   - 应用目录对其他用户不可写

**评级建议**：对于执行编译器或系统工具的应用，环境变量注入可导致任意代码执行，应评为高危。

---

## 安全实现

### 推荐方案：ProcessBuilder安全执行

```java
package com.example.security.executor;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

public class SecureProcessExecutor {

    private static final Logger logger = Logger.getLogger(SecureProcessExecutor.class.getName());

    // 白名单：允许执行的命令
    private static final String[] ALLOWED_COMMANDS = {
        "/usr/bin/find",
        "/usr/bin/grep",
        "/usr/bin/cat",
        "/bin/ls",
        "/bin/pwd"
    };

    // 禁止的环境变量
    private static final String[] DANGEROUS_ENV_VARS = {
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "LD_AUDIT",
        "JAVA_TOOL_OPTIONS",
        "DYLD_INSERT_LIBRARIES",
        "PERLLIB"
    };

    /**
     * 安全执行命令（使用白名单和环境隔离）
     */
    public static ProcessResult executeCommand(String command, String... args) throws IOException {
        // 1. 验证命令是否在白名单中
        if (!isCommandAllowed(command)) {
            throw new IllegalArgumentException("Command not in whitelist: " + command);
        }

        // 2. 验证命令文件存在且是常规文件
        File commandFile = new File(command);
        if (!commandFile.exists() || !commandFile.isFile()) {
            throw new IOException("Command file not found or is not a regular file: " + command);
        }

        // 3. 构造参数列表
        List<String> cmdList = new ArrayList<>();
        cmdList.add(command);
        for (String arg : args) {
            // 验证参数不包含危险字符
            if (containsDangerousChars(arg)) {
                throw new IllegalArgumentException("Argument contains dangerous characters: " + arg);
            }
            cmdList.add(arg);
        }

        // 4. 创建ProcessBuilder并隔离环境变量
        ProcessBuilder pb = new ProcessBuilder(cmdList);

        // 5. 清理所有环境变量，从空白开始
        pb.environment().clear();

        // 6. 仅添加必要的环境变量
        Map<String, String> env = pb.environment();
        env.put("PATH", "/usr/bin:/bin"); // 最小化PATH
        env.put("HOME", "/tmp/sandbox"); // 限制HOME
        env.put("LANG", "en_US.UTF-8");

        // 7. 明确删除危险环境变量（以防万一）
        for (String dangerousVar : DANGEROUS_ENV_VARS) {
            env.remove(dangerousVar);
        }

        // 8. 设置工作目录
        pb.directory(new File("/tmp"));

        // 9. 重定向错误流
        pb.redirectErrorStream(true);

        // 10. 执行命令
        logger.info("Executing command: " + String.join(" ", cmdList));
        Process process = pb.start();

        // 11. 获取输出（使用超时防止死锁）
        String output = readProcessOutput(process);

        // 12. 等待进程完成
        int exitCode = process.waitFor();
        logger.info("Process exited with code: " + exitCode);

        return new ProcessResult(exitCode, output);
    }

    /**
     * 验证命令是否在白名单中
     */
    private static boolean isCommandAllowed(String command) {
        for (String allowedCmd : ALLOWED_COMMANDS) {
            if (command.equals(allowedCmd)) {
                return true;
            }
        }
        return false;
    }

    /**
     * 检查参数是否包含危险字符
     */
    private static boolean containsDangerousChars(String arg) {
        // 检查环境变量引用
        if (arg.contains("$") || arg.contains("`") || arg.contains("$(")) {
            return true;
        }

        // 检查目录遍历
        if (arg.contains("..")) {
            return true;
        }

        // 检查shell特殊字符（虽然使用了参数列表但仍需防御）
        if (arg.matches(".*[;&|<>].*")) {
            return true;
        }

        return false;
    }

    /**
     * 读取进程输出
     */
    private static String readProcessOutput(Process process) throws IOException {
        StringBuilder output = new StringBuilder();
        try (java.io.BufferedReader reader = new java.io.BufferedReader(
                new java.io.InputStreamReader(process.getInputStream()))) {
            String line;
            int lineCount = 0;
            while ((line = reader.readLine()) != null && lineCount < 1000) {
                output.append(line).append("\n");
                lineCount++;
            }
        }
        return output.toString();
    }

    /**
     * 进程结果包装类
     */
    public static class ProcessResult {
        private final int exitCode;
        private final String output;

        public ProcessResult(int exitCode, String output) {
            this.exitCode = exitCode;
            this.output = output;
        }

        public int getExitCode() {
            return exitCode;
        }

        public String getOutput() {
            return output;
        }

        public boolean isSuccess() {
            return exitCode == 0;
        }
    }
}
```

### 推荐方案：使用示例

```java
package com.example.security.controller;

import com.example.security.executor.SecureProcessExecutor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;

@RestController
@RequestMapping("/api/process")
public class ProcessController {

    /**
     * 安全搜索文件
     */
    @PostMapping("/find")
    public ResponseEntity<?> findFile(@RequestParam String pattern) {
        try {
            // 验证模式不包含危险字符
            if (!isValidPattern(pattern)) {
                return ResponseEntity.badRequest().body("Invalid pattern");
            }

            // 执行find命令
            SecureProcessExecutor.ProcessResult result =
                SecureProcessExecutor.executeCommand("/usr/bin/find", "/tmp", "-name", pattern);

            if (result.isSuccess()) {
                return ResponseEntity.ok(result.getOutput());
            } else {
                return ResponseEntity.status(400).body("Command failed");
            }
        } catch (IOException | IllegalArgumentException e) {
            return ResponseEntity.status(500).body("Error: " + e.getMessage());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return ResponseEntity.status(500).body("Interrupted");
        }
    }

    /**
     * 验证搜索模式
     */
    private boolean isValidPattern(String pattern) {
        // 只允许字母、数字、*, ?, -
        return pattern.matches("[a-zA-Z0-9*?\\-_.]+");
    }

    /**
     * 安全的grep操作
     */
    @PostMapping("/grep")
    public ResponseEntity<?> searchText(@RequestParam String keyword,
                                        @RequestParam String file) {
        try {
            // 验证关键词和文件
            if (!isValidKeyword(keyword) || !isValidFilePath(file)) {
                return ResponseEntity.badRequest().body("Invalid input");
            }

            // 执行grep命令
            SecureProcessExecutor.ProcessResult result =
                SecureProcessExecutor.executeCommand("/usr/bin/grep", "-n", keyword, file);

            return ResponseEntity.ok(result.getOutput());
        } catch (IOException | IllegalArgumentException e) {
            return ResponseEntity.status(500).body("Error: " + e.getMessage());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return ResponseEntity.status(500).body("Interrupted");
        }
    }

    private boolean isValidKeyword(String keyword) {
        return keyword.matches("[a-zA-Z0-9\\s\\-_.]+") && keyword.length() <= 100;
    }

    private boolean isValidFilePath(String path) {
        return !path.contains("..") && !path.contains("$") &&
               path.startsWith("/tmp") && path.length() <= 255;
    }
}
```

---

## 修复优先级

1. **立即修复（当天）**：调用 `environment().clear()` 清理环境变量
2. **快速修复（3天内）**：删除所有危险环境变量，仅添加必要的变量
3. **短期改善（1周内）**：实施命令白名单，验证命令完整路径
4. **中期优化（2周内）**：验证用户输入，避免危险字符
5. **长期改进（1个月）**：使用受限用户账户运行应用，完整的权限隔离
