# C_SSTI_Custom_Parser_Code_Execution

**漏洞类型**: C/C++ 自定义模板解析器中用户输入导致的代码执行

---

## Details

### 代码示例

**易受攻击的代码模式**:
```c
// C/C++ 中的自定义模板解析器容易引入 SSTI 漏洞
// 特别是涉及字符串拼接、动态代码生成或命令执行时

// 场景1：使用 system/popen 执行模板内容
#include <stdlib.h>
#include <string.h>
char user_template[1024];
strcpy(user_template, get_request_param("template"));
// 危险：直接执行用户输入
system(user_template);
popen(user_template, "r");

// 场景2：自定义模板解析器不安全地处理用户输入
void render_template(const char* template_str) {
    char command[2048];
    // 查找 {{ }} 并提取表达式
    const char* start = strstr(template_str, "{{");
    const char* end = strstr(template_str, "}}");
    if (start && end) {
        char expr[512];
        strncpy(expr, start + 2, end - start - 2);
        // 危险：执行提取的表达式
        sprintf(command, "bash -c '%s'", expr);
        system(command);
    }
}

// 场景3：使用 eval 式的字符串到代码转换
#include <dlfcn.h>
void execute_template_code(const char* code) {
    // 动态编译和加载用户代码（极度危险）
    FILE* f = fopen("/tmp/template.c", "w");
    fprintf(f, "#include <stdio.h>\nvoid run() { %s }", code);
    fclose(f);
    system("gcc -shared -o /tmp/template.so /tmp/template.c");
    void* handle = dlopen("/tmp/template.so", RTLD_LAZY);
    void (*run)() = dlsym(handle, "run");
    run(); // 执行用户代码
}

// 场景4：不安全的字符串格式化
void format_template(const char* template, const char* user_data) {
    char output[2048];
    // 危险：用户数据包含格式化字符串
    sprintf(output, template, user_data); // 可能导致格式化字符串攻击
    printf("%s", output);
}

// 场景5：使用 exec 族函数
void process_template(const char* template_path, const char* data) {
    char* args[] = {"/bin/sh", "-c", NULL, NULL};
    // 危险：用户可控的命令
    char cmd[1024];
    sprintf(cmd, "cat %s | sed 's/{{data}}/%s/'", template_path, data);
    args[2] = cmd;
    execvp(args[0], args);
}

// 场景6：模板路径拼接导致路径遍历
void load_template(const char* name) {
    char path[512];
    // 危险：未验证的路径拼接
    sprintf(path, "/templates/%s.html", name);
    FILE* f = fopen(path, "r");
    // 处理文件...
}
```

### 快速定位核心操作 **[L1-L2]**

**L1 关键词扫描**:
- 命令执行: `system()`, `popen()`, `exec*()`, `sh`, `bash`
- 字符串操作: `sprintf()`, `strcpy()`, `strcat()`, `strstr()`
- 动态加载: `dlopen()`, `dlsym()`, `LoadLibrary()`
- 文件操作: `fopen()`, `fread()`, `fwrite()`
- 用户输入: `argv`, `getenv()`, `fgets()`, `scanf()`
- 格式化: `printf()`, `fprintf()`, `snprintf()` with user format

**L2 跳读定位**:
- 从用户输入追踪到 system/exec 调用
- 检查字符串拼接是否包含用户可控部分
- 搜索模板解析逻辑中的代码执行点
- 定位文件路径构造是否可控
- 关注自定义的 eval 式功能实现

### 快速定位保护机制 **[L2-L4]**

**L2 跳读检测**:
- 输入验证: 白名单、长度限制、字符过滤
- 沙箱环境: chroot、seccomp、capabilities
- 路径规范化: realpath()、路径前缀检查
- 参数化执行: 避免字符串拼接
- 禁用危险函数: 移除 system/exec 调用

**L3 逐行分析**:
- 命令执行:
  - system() 参数是否完全可控
  - exec*() 参数构造是否安全
  - 是否使用了 execve() 的参数化形式
- 字符串处理:
  - sprintf/strcpy 是否检查边界
  - strstr/strchr 提取的内容是否验证
  - 字符串拼接前是否转义特殊字符
- 模板解析:
  - 是否实现了安全的解析器（词法、语法分析）
  - 表达式求值是否限制了操作符
  - 变量替换是否转义输出
- 文件操作:
  - fopen 路径是否规范化
  - 是否检查 ../ 等路径遍历
  - 文件权限是否验证
- 动态加载:
  - dlopen 路径是否白名单限制
  - 加载的代码来源是否可信
  - 是否在受限环境中执行

**L4 跨模块追踪**:
- 追踪从输入解析 → 模板处理 → 代码执行的完整流程
- 检查编译选项（FORTIFY_SOURCE、PIE、ASLR）
- 验证运行时环境（SELinux、AppArmor）
- 检查依赖库的安全配置
- 追踪模板缓存和预编译机制

---

## Classify

### 漏洞判定标准

**确认为漏洞**:
- 用户输入直接传递给 system/exec/popen
- 自定义解析器执行模板中的代码
- 动态编译和加载用户提供的代码
- sprintf 使用用户可控的格式字符串
- 文件路径拼接未经验证导致路径遍历

**误报判定**:
- 所有输入经过严格白名单验证
- 使用参数化 API（如 execve 正确使用）
- 模板完全预定义，用户仅控制数据值
- 实现了完整的沙箱隔离
- C++ 使用了安全的模板引擎库

**代码异味**:
- 大量使用 system/popen 而非安全 API
- 字符串拼接用于构造命令或路径
- 使用 sprintf 而非 snprintf
- 自定义解析器未经安全审计
- 缺乏输入长度和字符验证
- 使用 strcpy/strcat 而非安全版本
- 动态加载代码未限制来源

---

## Low risk

### 低风险场景

**功能与权限隔离**:
- 功能仅限特权用户使用
- 需要多因素身份验证
- 部署在隔离的沙箱环境
- 严格的权限控制和审计

**架构设计防护**:
- 完全移除 system/exec 等危险函数
- 使用成熟的 C++ 模板引擎库（如 inja、Jinja2Cpp）
- 实现白名单式的表达式求值器
- 模板在编译时验证和预处理

**输入与输出保护**:
- 所有输入经过严格白名单验证
- 路径规范化后检查前缀
- 命令使用 execve 参数数组形式
- 输出经过适当转义处理
- 输入长度严格限制

**监控与运行环保**:
- 应用在 chroot/容器中运行
- 启用 seccomp 限制系统调用
- SELinux/AppArmor 强制访问控制
- 完整的审计日志和异常监控
- ASLR、DEP、Stack Canary 等保护启用
