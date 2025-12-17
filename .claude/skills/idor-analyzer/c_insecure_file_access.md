## C/C++ 不安全文件访问 IDOR

### Details

**代码示例：**
```c
// 直接拼接用户输入到文件路径
char filepath[256];
sprintf(filepath, "/data/files/%s", user_input);  // 危险点
FILE *fp = fopen(filepath, "r");

// 命令行参数直接作为文件路径
int main(int argc, char *argv[]) {
    FILE *fp = fopen(argv[1], "r");  // 危险点
}

// 未校验所有权的文件操作
int user_id = get_user_id();
char filename[128];
scanf("%s", filename);  // 用户可控
FILE *fp = fopen(filename, "r");  // 无权限校验
```

**快速定位核心操作技巧（L2-L3）：**
- 搜索文件操作函数：`fopen`、`open`、`fread`、`fwrite`、`stat`、`access`、`unlink`、`remove`、`rename`
- 定位字符串拼接函数：`sprintf`、`snprintf`、`strcat`、`strncat`、`strcpy` + 文件路径相关变量
- 追踪路径参数来源：逆向追踪到 `argv`、`getenv`、`scanf`、`fgets`、网络输入等用户可控点
- 关注相对路径构造：查找包含 `../`、`./`、`%s`、`%d` 等动态拼接模式

**快速定位保护机制技巧（L3-L4）：**
- **路径校验（L3）**：搜索 `realpath`、`canonicalize_file_name`、路径标准化函数
- **前缀检查（L2）**：查找 `strncmp`、`strstr` 配合白名单目录检查（如 `/var/app/public`）
- **黑名单过滤（L2）**：搜索 `strstr(path, "..")` 或 `strchr(path, '/')` 等特征字符检测
- **权限校验（L4）**：追踪 `stat`→`st_uid`/`st_gid` 比对、`access(path, R_OK)` 调用、ACL 检查逻辑
- **符号链接防护（L3）**：查找 `lstat`、`O_NOFOLLOW` 标志、`readlink` 检查
- **chroot/namespace（L4）**：跨模块追踪是否运行在受限环境

### Classify

**漏洞判定条件（三要素）：**
1. **用户可控输入**：文件路径全部或部分来自外部输入（argv、环境变量、标准输入、网络、配置文件可被篡改）
2. **缺失权限校验**：未验证当前用户对目标文件的所有权或访问权限
3. **影响范围可越界**：可访问到非预期目录或其他用户的文件资源

**误报识别：**
- 文件路径完全硬编码且无用户输入参与
- 存在 `realpath` 后严格前缀匹配（如确保结果在 `/app/data/` 下）
- 程序运行在严格的 chroot jail 或容器隔离环境
- 已通过数据库映射表将用户 ID 与文件路径关联并校验所有权

**代码异味（需进一步确认）：**
- 仅检查 `..` 但未处理符号链接或多斜杠（如 `////etc/passwd`）
- 使用 `access()` 检查但存在 TOCTOU 竞态窗口
- 仅限制文件扩展名（如 `.txt`）但未限制目录范围
- 依赖客户端传入的"安全"标志位而非服务端重新校验

### Low risk

**符合以下条件可评为低风险：**
- **访问范围已隔离**：程序以低权限用户运行且只能访问特定目录（通过文件系统权限强制）
- **数据非敏感**：可访问的文件仅包含公开信息或已脱敏数据
- **读写分离**：仅存在文件读取而无删除/修改操作，且读取内容有二次校验
- **影响面可控**：单用户本地工具（非网络服务），攻击者需本地执行权限
- **补偿控制存在**：虽路径可控但内容返回前有严格的所有权或业务逻辑校验
- **日志可审计**：所有文件访问均有完整日志且实时监控异常路径访问