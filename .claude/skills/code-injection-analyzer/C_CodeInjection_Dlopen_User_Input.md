# C/C++ 代码注入：dlopen() 动态加载用户可控库

## Details

### 漏洞成因

`dlopen()` 函数用于在运行时动态加载共享库（.so 文件），当库的路径或名称由用户输入直接控制时，攻击者可通过指定恶意库的路径或利用 `rpath`/`runpath` 搜索顺序、环境变量污染等方式注入并加载任意恶意代码。关键风险在于：(1) 动态加载允许攻击者选择加载的库文件；(2) 库加载时执行全局构造函数和初始化代码；(3) 路径解析过程存在多个可被利用的漏洞点（如 `LD_LIBRARY_PATH` 劫持、相对路径遍历、符号链接跟随等）。

### 代码示例

```c
// 危险示例 1：直接使用用户输入作为库路径
char *lib_path = getenv("LIB_PATH");
if (!lib_path) lib_path = argv[1];
void *handle = dlopen(lib_path, RTLD_LAZY);
if (!handle) {
    perror("dlopen");
    return 1;
}
// 攻击: LIB_PATH=/tmp/malicious.so 或 argv[1]=/tmp/evil.so

// 危险示例 2：拼接用户输入到库路径
char lib_name[256];
snprintf(lib_name, sizeof(lib_name), "/opt/libs/%s", user_input);
void *handle = dlopen(lib_name, RTLD_LAZY);
// 攻击: user_input=../../tmp/malicious.so 导致路径遍历

// 危险示例 3：使用相对路径加载库
char *module = $_GET['module'];  // Web 应用中的用户输入
char path[512];
strcpy(path, module);
strcat(path, ".so");
void *handle = dlopen(path, RTLD_LAZY);
// 攻击: 在当前工作目录或 LD_LIBRARY_PATH 中放置恶意库

// 危险示例 4：环境变量影响的库搜索
const char *lib_prefix = getenv("APP_LIB_PREFIX");
char lib_path[1024];
snprintf(lib_path, sizeof(lib_path), "%s/libmodule.so", lib_prefix);
void *handle = dlopen(lib_path, RTLD_LAZY);
// 攻击: APP_LIB_PREFIX=/tmp/malicious 导致加载恶意库

// 危险示例 5：直接使用库名不指定路径
const char *lib_name = getenv("MODULE_NAME");
void *handle = dlopen(lib_name, RTLD_LAZY);
// 攻击: MODULE_NAME=./malicious 导致从当前目录加载

// 危险示例 6：RTLD_GLOBAL 标志增加风险
void *handle = dlopen(user_lib_path, RTLD_LAZY | RTLD_GLOBAL);
// RTLD_GLOBAL 使加载的库符号在全局命名空间可见，增加了符号覆盖攻击的可能性
```

### 快速定位核心操作 `[L1:关键词扫描]`

**关键函数和宏识别：**
- 搜索关键字：`dlopen(`、`dlsym(`、`dlerror()`、`RTLD_LAZY`、`RTLD_NOW`、`RTLD_GLOBAL`、`RTLD_LOCAL`
- 相关函数：`dlopen()`、`dlopen2()`、`dlmopen()`（多命名空间加载）
- 搜索模式：
  ```
  dlopen\s*\(\s*[a-zA-Z_].*user|getenv|argv|stdin
  dlopen\s*\(\s*[^"]/.*RTLD
  dlopen.*getenv.*\)
  dlopen.*snprintf|sprintf|strcat
  ```

**危险标记识别：**
- `dlopen()` 的第一个参数（库路径）包含用户可控变量
- 库路径包含用户输入、环境变量、命令行参数或配置文件值
- 使用相对路径而非绝对路径加载库
- 使用了 `RTLD_GLOBAL` 或 `RTLD_NODELETE` 等特殊标志
- 库路径通过字符串拼接、sprintf、snprintf 等函数构造
- 库名称或路径可能包含目录遍历字符（`../`）
- 使用了环境变量（如 `LD_LIBRARY_PATH`、`APP_LIB_PATH`）

**详细定位技巧 `[L2:跳读]`：**
- 定位每个 `dlopen()` 调用，回溯第一个参数的来源
- 追踪路径变量从用户输入源到 `dlopen()` 的传播路径
- 检查是否使用了绝对路径（以 `/` 开头）或相对路径
- 标记所有参与路径构造的变量，包括环境变量和字符串操作
- 检查是否存在路径验证或规范化（canonicalization）
- 对于间接库加载（通过动态符号查询），需要追踪被加载库的来源

### 快速定位保护机制 `[L3:逐行读]`

**路径验证和规范化：**
- 搜索关键字：`realpath()`、`canonicalize_file_name()`、`validate`、`check`、`verify`
- 检查是否使用了绝对路径验证
  ```c
  // 有效的保护示例
  if (lib_path[0] != '/') {
      fprintf(stderr, "Only absolute paths allowed\n");
      return -1;
  }
  void *handle = dlopen(lib_path, RTLD_LAZY);
  ```
- 检查是否规范化了路径并移除了 `..` 和符号链接
  ```c
  char real_path[PATH_MAX];
  if (!realpath(lib_path, real_path)) {
      perror("realpath");
      return -1;
  }
  // 验证规范化后的路径
  if (strncmp(real_path, "/opt/libs/", 10) != 0) {
      return -1;  // 不在预期目录
  }
  void *handle = dlopen(real_path, RTLD_LAZY);
  ```

**库名白名单：**
- 搜索预定义的库列表或映射表
  ```c
  const char *allowed_libs[] = {
      "/opt/libs/libmodule1.so",
      "/opt/libs/libmodule2.so",
      NULL
  };
  ```
- 检查是否进行了精确匹配或白名单验证
- 验证白名单是否包含所有可能的库且不太宽泛

**环境隔离：**
- 搜索 `clearenv()`、`unsetenv()` 调用以清理危险的环境变量
- 检查是否明确设置了 `LD_LIBRARY_PATH` 为安全值
- 查找权限降级（`setuid()`、`setgid()`、`chroot()`）以限制文件系统访问
- 检查是否使用了 seccomp、AppArmor 或 SELinux 来限制 dlopen 行为

**库符号覆盖防护 `[L4:跨模块追踪]`：**
- 检查是否使用了 `RTLD_LOCAL` 替代 `RTLD_GLOBAL`（限制符号在全局命名空间的可见性）
- 验证加载的库的符号是否与关键系统库或应用库产生冲突
- 检查是否有符号版本控制（symbol versioning）以防止符号覆盖
- 查看是否有在加载后进行的符号合法性验证

---

## Classify

### 确认为漏洞的必要条件

**漏洞判定流程：**

1. **用户输入可达 dlopen() 的库路径参数**：
   - 库路径直接来自用户输入（网络请求、命令行参数、环境变量、文件内容等）
   - 库路径通过字符串操作（拼接、替换等）包含了用户数据
   - 路径可能来自数据库或其他可被污染的源（二阶注入）

2. **路径验证和规范化不充分**：
   - 无验证：直接使用用户输入 → 漏洞
   - 部分验证：仅检查部分属性（如只验证后缀）但未验证整个路径 → 可能是漏洞
   - 可绕过的验证：验证逻辑存在缺陷（如使用黑名单而非白名单）→ 漏洞
   - 充分验证：完整的白名单检查或绝对路径规范化 → 低风险或误报

3. **库搜索路径可被污染**：
   - 相对路径加载时，当前工作目录或 `LD_LIBRARY_PATH` 可被攻击者控制
   - 搜索顺序存在可被利用的漏洞（如优先搜索当前目录）
   - 文件权限允许攻击者在搜索路径中创建恶意库

### 误报判定标准

- **库路径完全由应用内部生成，不受用户输入影响**：
  ```c
  const char *lib_path = "/opt/libs/libmodule.so";
  void *handle = dlopen(lib_path, RTLD_LAZY);
  ```

- **库路径来自编译时常量或受信的配置文件**：
  ```c
  #define LIB_PATH "/usr/lib/libmodule.so"
  void *handle = dlopen(LIB_PATH, RTLD_LAZY);
  ```

- **用户输入仅用于索引库白名单，不作为路径内容**：
  ```c
  const char *libs[] = {"/lib/mod1.so", "/lib/mod2.so"};
  int index = atoi(user_input);
  if (index < 0 || index >= 2) return;
  void *handle = dlopen(libs[index], RTLD_LAZY);
  ```

- **库路径经过严格的路径规范化和验证**：
  ```c
  char real_path[PATH_MAX];
  realpath(user_input, real_path);
  if (strncmp(real_path, "/opt/trusted/", 13) != 0) {
      return -1;  // 拒绝不在预期目录的路径
  }
  void *handle = dlopen(real_path, RTLD_LAZY);
  ```

### 代码异味识别

- **混合使用绝对路径和相对路径**：表明可能存在逻辑错误或不一致的安全策略
- **使用相对路径加载关键库**：增加了 `LD_LIBRARY_PATH` 劫持的风险
- **动态构造库路径但缺乏规范化**：如 `sprintf(path, "%s/lib%s.so", prefix, name)`
- **环境变量参与路径构造但未清理**：如直接使用 `getenv()` 而无验证
- **库加载后无符号验证**：加载后应至少验证关键函数的存在性和签名
- **使用 `RTLD_GLOBAL` 但不清楚其符号隔离后果**：可能导致符号覆盖攻击
- **深层的函数调用链**：库路径通过多个函数传递，难以追踪其来源和安全性

---

## Low risk

### 低风险评级场景

**场景一：完整的库路径白名单**
- 库路径来自预定义的、有限的白名单集合
- 白名单在代码中硬编码或由系统管理员控制的配置文件提供
- 用户输入仅用于选择白名单中的条目，不作为路径内容本身
- 示例：
  ```c
  const char *allowed_libs[] = {
      "/usr/lib/libmodule1.so",
      "/usr/lib/libmodule2.so",
      "/usr/lib/libmodule3.so",
      NULL
  };

  int lib_index = get_lib_index(user_input);
  if (lib_index < 0 || lib_index >= 3) {
      return -1;
  }
  void *handle = dlopen(allowed_libs[lib_index], RTLD_LAZY);
  ```
- 评级依据：白名单限制了可加载的库，攻击面被消除

**场景二：严格的绝对路径验证**
- 库路径在使用前通过 `realpath()` 等函数规范化
- 规范化后的路径与预期的安全目录进行前缀匹配
- 路径中不存在 `..` 或符号链接
- 示例：
  ```c
  char real_path[PATH_MAX];
  if (!realpath(user_lib_path, real_path)) {
      return -1;  // 路径不存在或无法规范化
  }
  if (strncmp(real_path, "/opt/trusted_libs/", 18) != 0) {
      return -1;  // 路径不在预期目录
  }
  void *handle = dlopen(real_path, RTLD_LAZY);
  ```
- 评级依据：规范化和前缀匹配防止了目录遍历和符号链接攻击

**场景三：环境清理和隔离**
- 应用在启动时清理了危险的环境变量（如 `LD_LIBRARY_PATH`）
- 使用 `clearenv()` 或 `unsetenv()` 清理后，仅设置必需的环境变量
- 应用以低权限用户（如 `nobody`）运行，限制了文件系统访问
- 示例：
  ```c
  clearenv();
  setenv("PATH", "/bin:/usr/bin", 1);
  setenv("HOME", "/tmp", 1);
  setuid(nobody_uid);
  // 现在 dlopen 的搜索路径受到显著限制
  ```
- 评级依据：环境隔离和权限限制防止了 `LD_LIBRARY_PATH` 劫持

**场景四：使用 RTLD_LOCAL 和符号隔离**
- 库通过 `RTLD_LOCAL` 标志加载，而非 `RTLD_GLOBAL`
- 加载的库符号不会覆盖全局符号空间中的符号
- 应用在加载库后验证了关键函数的存在性
- 示例：
  ```c
  void *handle = dlopen(lib_path, RTLD_LAZY | RTLD_LOCAL);
  if (!handle) return -1;

  // 验证关键函数存在
  int (*func)(int) = (int (*)(int))dlsym(handle, "expected_function");
  if (!func) {
      dlclose(handle);
      return -1;  // 库不包含预期函数
  }
  ```
- 评级依据：符号隔离防止了符号覆盖攻击

**场景五：非网络可达的库路径**
- 库路径来自本地配置文件或编译时常量，非网络用户输入
- 库文件本身存储在受保护的目录（如仅管理员可修改）
- 应用无权访问用户可写的目录
- 示例：在容器环境中，库路径指向只读的系统目录
- 评级依据：攻击者无法通过网络或权限有限的方式修改库文件

**场景六：SELinux 或 AppArmor 限制**
- 系统配置了强制访问控制（MAC），如 SELinux 或 AppArmor
- 策略明确限制了应用可加载的库的路径
- 应用进程仅被允许访问特定的库目录
- 示例：SELinux 策略阻止应用加载不在 `/opt/libs/` 的库
- 评级依据：MAC 强制执行了库加载的白名单

**场景七：静态链接或预加载**
- 应用使用静态链接，不依赖动态库加载
- 关键库通过编译时链接而非运行时 `dlopen()` 加载
- 仅加载用户无法控制路径的基础系统库
- 评级依据：减少了动态加载的攻击面

### 评级决策补充

- **相对路径加载但当前工作目录受控** → 中等风险或高风险
  - 例：使用相对路径但未验证当前工作目录是否安全

- **库路径包含环境变量但未清理** → 中等风险或高风险
  - 例：`snprintf(path, sizeof(path), "%s/lib.so", getenv("PREFIX"))` 未验证 PREFIX

- **路径验证不完整（仅检查后缀或中间部分）** → 中等风险或高风险
  - 例：仅验证路径以 `.so` 结尾，未验证完整路径的合法性

- **使用 RTLD_GLOBAL 且库来自不可信源** → 高风险
  - 例：加载用户指定的库且使用 RTLD_GLOBAL，可能导致符号覆盖

- **深层的路径构造链且中间缺乏验证** → 需要详细分析
  - 例：用户输入 → function1 → function2 → dlopen()，需要追踪每一步

- **库加载后调用任意函数** → 高风险
  - 例：通过 dlsym() 加载用户指定的函数名并调用
