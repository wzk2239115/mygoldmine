# Java | ProcessBuilder通配符展开注入漏洞

## 基本信息
- **难度等级：** ★★★☆☆ (中级)
- **审计时间：** 20-25分钟

## 🚀 30秒快速清单
- [ ] ProcessBuilder的参数列表中是否包含用户输入？
- [ ] 用户输入中是否存在通配符（*, ?, [], {}）？
- [ ] 是否验证和转义了用户输入的通配符？
- [ ] 是否对文件路径进行了白名单验证？

## Details

### 漏洞成因
Java的ProcessBuilder不会进行shell通配符展开，但如果将包含通配符的用户输入直接作为命令参数，某些情况下可能导致意外扩展。更常见的问题是使用 `find` 等命令时，用户输入的通配符被传递给shell解释，导致意外的文件匹配。例如 `find /data -name "*.txt"` 中如果用户可控 `-name` 后的参数，可能利用通配符进行目录遍历或访问未授权文件。

### 代码示例

```java
// 漏洞1：find命令的-name参数包含通配符且未验证
import java.io.IOException;

public class FileSearcher {

    public void searchFiles(String pattern) throws IOException {
        // pattern来自用户输入，如 "*.txt" 或 "*;rm -rf /*"
        ProcessBuilder pb = new ProcessBuilder(
            "/usr/bin/find",
            "/data",
            "-name",
            pattern  // 问题：用户输入的通配符未验证
        );

        // ProcessBuilder不展开通配符（这是好的）
        // 但find命令会解释通配符
        // 如果pattern是 "*/../../../etc/passwd"，
        // find会匹配到预期之外的文件

        Process process = pb.start();
    }
}
// 攻击场景：
// 1. pattern = "../../../etc/passwd" - 目录遍历
// 2. pattern = "*; cat /etc/shadow" - shell注入（如果使用sh -c）
```

```java
// 漏洞2：globbing导致意外的文件访问
public class DirectoryProcessor {

    public void listFiles(String directory) throws IOException {
        // directory可能来自用户输入
        ProcessBuilder pb = new ProcessBuilder(
            "/bin/ls",
            "-la",
            directory + "/*"  // 问题：字符串拼接，通配符会被展开
        );

        // 如果directory为 "/tmp"，则等价于 "ls -la /tmp/*"
        // find会列出/tmp下的所有文件
        // 但如果目录包含大量文件，可能导致命令行长度超过限制

        Process process = pb.start();
    }
}
```

```java
// 漏洞3：grep中的模式包含特殊字符
public class LogSearcher {

    public void searchLogs(String pattern) throws IOException {
        // pattern来自用户输入，未转义
        ProcessBuilder pb = new ProcessBuilder(
            "/usr/bin/grep",
            pattern,  // 问题：模式未转义
            "/var/log/app.log"
        );

        // 虽然ProcessBuilder不展开，但grep会解释正则表达式
        // 用户可以使用正则表达式来访问不应该看到的内容

        Process process = pb.start();
    }
}
```

### 快速定位核心操作
- **关键词扫描**：`ProcessBuilder`, `find`, `ls`, `grep`, 通配符字符 `*`, `?`, `[`, `]`
- **参数构造**：直接传递用户输入作为参数
- **文件路径操作**：`-name`, `-path`, `directory + "/*"`
- **缺少验证**：无输入验证或白名单

### 快速定位保护机制
- **输入验证**：验证用户输入不包含通配符字符
- **白名单**：从预定义的文件列表或目录中选择
- **转义**：使用 `Pattern.quote()` 转义正则表达式
- **路径验证**：确保路径在允许的范围内，无目录遍历

---

## Classify

### 确认漏洞（需满足以下任一条）
1. **通配符未转义**：用户输入可能包含 `*`, `?`, `[]` 等
2. **路径字符串拼接**：`path + "/*"` 或 `path + pattern`
3. **参数来自用户**：未验证的用户输入作为 `find`, `ls`, `grep` 等命令的参数
4. **目录遍历**：参数不验证 `../` 等目录遍历字符

**典型漏洞特征**：
- `new ProcessBuilder("/usr/bin/find", "/data", "-name", userPattern)`
- `directory + "/*"` 或 `path + pattern`
- 缺少 `Pattern.quote()` 或输入验证
- 缺少 `..` 检查

### 误报排除
- ✗ 使用 `Pattern.quote(userInput)` 转义用户输入
- ✗ 验证用户输入仅包含字母、数字、点、斜杠
- ✗ 从白名单中选择参数
- ✗ 验证路径不包含 `../`

### 代码异味（需进一步验证）
- △ 有输入验证但不够全面
- △ 使用了某种过滤但可能被绕过

---

## Low Risk

给予低风险评级的场景需满足以下全部条件：
1. 使用 `Pattern.quote()` 或等效方式转义用户输入
2. 验证路径不包含目录遍历（../）
3. 从白名单中验证用户输入
4. 限制搜索范围在安全的目录

---

## 安全实现

```java
package com.example.security.file;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.regex.Pattern;
import java.util.logging.Logger;

public class SecureFileSearcher {

    private static final Logger logger = Logger.getLogger(SecureFileSearcher.class.getName());
    private static final String SAFE_BASE_DIR = "/data/user_files";

    /**
     * 安全的文件搜索（使用find命令）
     */
    public static ProcessResult findFiles(String directory, String pattern) throws IOException {
        // 1. 验证目录路径
        if (!isValidDirectory(directory)) {
            throw new IllegalArgumentException("Invalid directory");
        }

        // 2. 验证搜索模式
        if (!isValidPattern(pattern)) {
            throw new IllegalArgumentException("Invalid pattern");
        }

        // 3. 构造命令参数
        ProcessBuilder pb = new ProcessBuilder(
            "/usr/bin/find",
            directory,
            "-maxdepth", "3",  // 限制搜索深度
            "-name",
            pattern
        );

        // 4. 隔离环境
        pb.environment().clear();
        pb.environment().put("PATH", "/usr/bin:/bin");

        // 5. 执行命令
        Process process = pb.start();
        String output = readOutput(process);

        try {
            int exitCode = process.waitFor();
            return new ProcessResult(exitCode, output);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("Process interrupted", e);
        }
    }

    /**
     * 验证目录是否安全
     */
    private static boolean isValidDirectory(String directory) {
        // 1. 检查是否为空
        if (directory == null || directory.isEmpty()) {
            return false;
        }

        // 2. 检查是否包含目录遍历
        if (directory.contains("..")) {
            return false;
        }

        // 3. 检查是否为允许的目录
        try {
            Path dirPath = Paths.get(directory).toRealPath();
            Path basePath = Paths.get(SAFE_BASE_DIR).toRealPath();

            // 确保目录在SAFE_BASE_DIR下
            return dirPath.startsWith(basePath);
        } catch (Exception e) {
            logger.warning("Invalid directory path: " + directory);
            return false;
        }
    }

    /**
     * 验证搜索模式
     */
    private static boolean isValidPattern(String pattern) {
        // 1. 检查长度
        if (pattern == null || pattern.isEmpty() || pattern.length() > 100) {
            return false;
        }

        // 2. 只允许通配符 * 和 ?，不允许 [] 或 {}
        if (pattern.contains("[") || pattern.contains("]") ||
            pattern.contains("{") || pattern.contains("}")) {
            return false;
        }

        // 3. 不允许目录遍历
        if (pattern.contains("/") || pattern.contains("..")) {
            return false;
        }

        // 4. 不允许引号和反引号
        if (pattern.contains("'") || pattern.contains("\"") || pattern.contains("`")) {
            return false;
        }

        return true;
    }

    /**
     * 读取进程输出
     */
    private static String readOutput(Process process) throws IOException {
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
     * 使用Java NIO安全地列出文件
     */
    public static java.util.List<String> listFilesSecurely(String directory) throws IOException {
        // 验证目录
        if (!isValidDirectory(directory)) {
            throw new IllegalArgumentException("Invalid directory");
        }

        Path dirPath = Paths.get(directory);
        java.util.List<String> files = new java.util.ArrayList<>();

        // 使用Files.list代替find命令
        try (var stream = Files.list(dirPath)) {
            stream.map(Path::toString)
                  .limit(1000)
                  .forEach(files::add);
        }

        return files;
    }

    /**
     * 安全的grep搜索
     */
    public static ProcessResult grepSearch(String pattern, String file) throws IOException {
        // 1. 验证搜索模式
        if (!isValidGrepPattern(pattern)) {
            throw new IllegalArgumentException("Invalid grep pattern");
        }

        // 2. 验证文件路径
        if (!isValidFilePath(file)) {
            throw new IllegalArgumentException("Invalid file path");
        }

        // 3. 使用Pattern.quote转义
        String quotedPattern = Pattern.quote(pattern);

        // 4. 执行grep
        ProcessBuilder pb = new ProcessBuilder(
            "/usr/bin/grep",
            "-n",
            quotedPattern,
            file
        );

        pb.environment().clear();
        pb.environment().put("PATH", "/usr/bin:/bin");

        Process process = pb.start();
        String output = readOutput(process);

        try {
            int exitCode = process.waitFor();
            return new ProcessResult(exitCode, output);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("Process interrupted", e);
        }
    }

    private static boolean isValidGrepPattern(String pattern) {
        return pattern != null && !pattern.isEmpty() && pattern.length() <= 200;
    }

    private static boolean isValidFilePath(String file) {
        if (file == null || file.isEmpty() || file.contains("..")) {
            return false;
        }

        try {
            Path filePath = Paths.get(file).toRealPath();
            Path basePath = Paths.get(SAFE_BASE_DIR).toRealPath();
            return filePath.startsWith(basePath);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * 进程结果
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

## 修复优先级

1. **立即修复（当天）**：验证用户输入，检查通配符和目录遍历字符
2. **快速修复（3天内）**：使用白名单验证，限制搜索目录范围
3. **短期改善（1周内）**：使用Java NIO代替shell命令（如可能）
4. **长期改进**：完整的安全审计和权限管理
