# C/C++ 配置文件IDOR漏洞

## Details

### 代码示例

```c
// 典型漏洞代码
void load_config(const char* config_id) {
    char path[256];
    snprintf(path, sizeof(path), "/configs/%s.conf", config_id);  // 直接拼接用户输入
    FILE* fp = fopen(path, "r");  // 未验证所有权
    if (fp) {
        // 读取并应用配置
        parse_config(fp);
        fclose(fp);
    }
}

// 通过命令行参数读取
int main(int argc, char* argv[]) {
    if (argc > 1) {
        load_config_file(argv[1]);  // 直接使用用户提供的路径
    }
}

// HTTP处理场景
void handle_request(const char* config_name) {
    std::ifstream config_file(std::string("/data/") + config_name);  // 字符串拼接
    // 直接读取配置内容返回
}
```

### 快速定位核心操作 (L2:跳读)

**文件操作函数**：`fopen()`, `open()`, `ifstream::open()`, `std::filesystem::path`, `read()`, `fread()`

**路径拼接特征**：`sprintf/snprintf` + 用户输入变量，`std::string` 连接操作符 `+`，`strcat/strncat`

**入口点**：命令行参数 `argv[]`，网络请求解析后的变量，配置ID/文件名参数，环境变量 `getenv()`

**定位技巧**：搜索文件操作函数 → 回溯路径来源 → 检查是否包含外部输入

### 快速定位保护机制 (L3:逐行读)

**所有权验证**：
- 文件属性检查：`stat()` 后比对 `st_uid`, `st_gid`
- ACL检查：`acl_get_file()`, `acl_check()`
- 数据库关联：查询配置所有者与当前用户匹配

**路径规范化**：
- `realpath()` 解析实际路径，防止 `../` 遍历
- `canonicalize_file_name()` 标准化路径
- 白名单目录前缀校验：`strncmp(path, ALLOWED_DIR, len)`

**访问控制**：
- 用户身份验证：`getuid()`, `geteuid()` 与预期值比较
- 权限位检查：`access()` 函数使用
- 会话令牌验证：自定义 `validate_session()` 逻辑

**审计技巧**：
1. 关注路径使用前是否调用 `realpath()` (L1:关键词扫描)
2. 检查是否存在 `if (uid == owner_uid)` 类似条件判断 (L2:跳读)
3. 追踪用户身份传递链：从认证点到资源访问点 (L4:跨模块追踪)

## Classify

**确认漏洞**：
- 外部输入直接用于构造文件路径，无任何所有权验证
- 仅进行路径遍历防护但缺少资源所属关系校验
- 使用硬编码凭证或固定UID进行权限判断

**误报场景**：
- 配置文件为全局只读资源，设计上允许所有认证用户访问
- 路径完全来自内部映射表，外部输入仅作索引键且经过严格校验
- 文件操作前已通过独立权限系统验证（需追踪确认验证逻辑有效）

**代码异味**：
- 存在所有权检查但逻辑可被绕过（如仅检查文件存在性）
- 部分路径分支有验证，其他分支缺失
- 依赖客户端传递的用户ID进行服务端验证

**研判关键**：
1. 明确配置资源的敏感性与可见性设计意图
2. 验证所有权校验的完整性：是否覆盖所有代码路径
3. 评估绕过可能性：竞态条件、符号链接、权限提升

## Low risk

**低风险情况**：
- 配置文件仅包含非敏感公开信息（如UI主题、语言偏好）
- 资源位于容器/沙箱环境，即使越权也无法访问其他用户真实数据
- 应用为单用户程序，不存在多租户隔离需求
- 配置文件路径已通过严格白名单机制限制在安全目录范围内
- 已实施完善的审计日志，异常访问可及时发现和响应

**风险评估要点**：
- 配置内容是否包含密钥、凭证、内部路径等敏感信息
- 是否可通过配置注入影响系统行为（如修改日志路径导致覆盖关键文件）
- 横向越权影响范围：单个用户数据泄露 vs 多用户批量暴露