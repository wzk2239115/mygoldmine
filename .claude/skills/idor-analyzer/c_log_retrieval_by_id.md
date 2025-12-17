# C/C++ 日志文件检索 IDOR 漏洞

## Details

**代码示例：**
```c
// 漏洞示例1：直接使用用户输入拼接文件路径
void get_log_file(const char* log_id) {
    char filepath[256];
    sprintf(filepath, "/var/logs/%s.log", log_id);  // 直接拼接
    FILE* fp = fopen(filepath, "r");                // 无权限验证
    if (fp) {
        // 读取并返回日志内容
    }
}

// 漏洞示例2：通过日志ID查询数据库获取路径
void retrieve_log(int log_id) {
    char query[256];
    sprintf(query, "SELECT filepath FROM logs WHERE id=%d", log_id);
    // 执行查询获取filepath
    FILE* fp = fopen(filepath, "r");  // 无所有权验证
    // 返回日志内容
}

// 漏洞示例3：CGI/FastCGI环境读取日志
void handle_log_request() {
    char* log_name = getenv("QUERY_STRING");  // ?log=access.log
    char path[512];
    snprintf(path, sizeof(path), "/app/logs/%s", log_name);
    int fd = open(path, O_RDONLY);  // 无权限检查
    // 输出文件内容
}
```

**快速定位到核心操作（L1-L2）：**
- **文件操作函数（L1）：** 关键词扫描 `fopen`、`open`、`fread`、`read`、`ifstream`、`readfile`、`sendfile`
- **路径拼接（L1）：** 扫描 `sprintf`、`snprintf`、`strcat`、`strcpy`、`string::append` 与日志相关变量的组合
- **参数来源（L2）：** 跳读追踪参数来源，查找 `argv`、`getenv`、`recv`、HTTP解析函数、配置读取函数
- **数据库查询（L2）：** 跳读日志路径是否从数据库查询得到（`SELECT filepath/path/file`），查询条件是否来自用户输入

**快速定位到保护机制（L2-L4）：**
- **权限验证（L2）：** 跳读是否存在 `check_permission`、`verify_owner`、`user_id == owner_id` 等校验逻辑
- **路径验证（L2）：** 查找 `realpath`、`basename`、路径规范化、目录遍历检测（`..`、`/`）
- **白名单检查（L2）：** 是否存在允许访问的日志列表、文件名白名单匹配
- **会话关联（L3）：** 逐行检查是否验证当前用户会话与日志所有者的关联关系
- **访问控制列表（L4）：** 跨模块追踪是否调用ACL检查函数、权限管理模块

## Classify

**漏洞判定标准：**
- 用户可控参数（log_id/log_name）直接参与文件路径构造或数据库查询，且在文件读取前无所有权验证
- 无所有权验证即：未检查当前用户是否有权访问该日志资源
- 可通过遍历ID或文件名访问其他用户的日志文件

**误报场景：**
- 日志文件为全局公共资源（如系统运维日志），所有认证用户均可访问
- 存在隐式权限控制：如路径前缀包含 user_id（需确认 user_id 不可伪造）
- 日志ID通过不可预测的随机Token映射，且Token与用户会话绑定

**代码异味：**
- 虽有权限检查但实现不完整（如仅检查文件是否存在，未检查所有权）
- 权限检查逻辑冗余复杂，难以确认有效性
- 日志访问依赖前端鉴权或URL混淆

## Low risk

**低风险评级条件：**
- **访问范围受限：** 仅能访问当前用户自己创建的日志，其他用户日志通过物理隔离（独立目录、数据库分表）
- **信息价值低：** 日志内容为非敏感操作记录（如公开页面访问日志），不含PII、凭证、业务数据
- **认证门槛高：** 需要高权限角色（管理员）才能调用该功能，普通用户无法触及
- **已有部分防护：** 虽未完全修复但存在路径过滤、文件扩展名限制等缓解措施
- **生产环境不可达：** 该功能仅在内网或测试环境开放，生产环境已禁用或不可访问