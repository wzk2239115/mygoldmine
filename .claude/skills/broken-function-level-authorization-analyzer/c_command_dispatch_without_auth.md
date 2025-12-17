# C/C++ 命令路由缺失授权校验

## Details

### 漏洞成因
在 C/C++ 服务端程序中，常见通过字符串匹配或函数指针表实现命令路由（command dispatch）。若仅依据命令名称选择处理函数，而未在进入函数前核验当前调用者身份或角色，就可能使普通用户调用管理员命令、执行敏感操作。此类路由通常出现在控制台指令、RPC 服务、嵌入式设备的命令通道或者插件系统中。

### 代码示例

**易受攻击的代码：**
```c
// 命令 -> 处理函数映射
struct CommandEntry {
    const char *name;
    void (*handler)(Session *sess, const char *payload);
};

void do_shutdown(Session *sess, const char *payload) {
    // 仅管理员允许执行
    system("shutdown -h now");
}

void handle_command(Session *sess, const char *cmd, const char *payload) {
    for (size_t i = 0; i < CMD_TABLE_SIZE; ++i) {
        if (strcmp(cmd_table[i].name, cmd) == 0) {
            cmd_table[i].handler(sess, payload);   // 未校验 sess->role
            return;
        }
    }
}
```

**改进示例：**
```c
bool ensure_role(Session *sess, Role required) {
    return sess && sess->role >= required;
}

void handle_command(Session *sess, const char *cmd, const char *payload) {
    for (size_t i = 0; i < CMD_TABLE_SIZE; ++i) {
        if (strcmp(cmd_table[i].name, cmd) == 0) {
            if (!ensure_role(sess, cmd_table[i].required_role)) {
                log_warn("unauthorized command: %s", cmd);
                return;
            }
            cmd_table[i].handler(sess, payload);
            return;
        }
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `command`, `dispatch`, `handler`, `func_table`, `strcmp`, `map<string, function>`。

**定位步骤：**
1. 搜索命令表或函数指针数组的定义与使用；
2. 跳读确认入口函数（如 `handle_command`）是否在调用处理函数前检查用户角色；
3. 关注 `Session`、`User` 结构中是否包含权限字段但未使用。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 统一的权限校验函数（`ensure_role`、`require_permission`）；
- 命令表中声明 `required_role`、`capability` 等元数据；
- 在进入 handler 前调用 ACL/RBAC 框架；
- 命令分层：公共命令与管理员命令使用不同路由。

**定位技巧：**
- 对识别出的危险命令进行逐行读（L3），检查是否直接调用敏感 API；
- 跨模块追踪（L4）命令入口是否可被未认证通道触发（如网络、串口、RPC 网关）。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 命令入口统一调用授权模块 | **L0（快速跳过）** | 已有正式校验 |
| 部分命令带权限字段但未覆盖 | **L2（跳读）** | 快速确认遗漏 |
| 没有任何角色判断直接调用 handler | **L3（逐行读）** | 高风险 |
| 命令可从多通道触发且无统一校验 | **L4（跨模块追踪）** | 必须全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 命令路由允许来自普通用户的请求直接执行敏感命令；
2. 无角色/权限校验或依赖客户端传参控制；
3. 能复现越权操作（关闭设备、导出配置、修改系统参数）。

#### 误报
1. 命令路由入口在调用前固定地执行权限校验；
2. 敏感命令所在模块仅在受信任通道调用（硬件隔离、独立认证）；
3. 命令只是读取公共信息，不涉及敏感状态。

#### 代码异味
1. 仅在 handler 内部打印日志但未拒绝未授权调用；
2. 依赖命令名称前缀（如 `admin_`）区分权限，没有真正校验；
3. 权限校验散布在各 handler 中，缺乏统一封装。

## Low risk

### 低风险评级场景

#### 1. 调试命令，仅在受控环境使用
- **场景：** 命令路由仅在研发/测试设备开放；
- **评估：** 可降级，但需确保不会流入生产。

#### 2. 命令只读取非敏感信息
- **场景：** 即使被滥用，也只返回系统状态，未影响安全；
- **评估：** 标记低风险，并提醒未来可能扩展。

#### 3. 计划迁移到统一权限框架
- **场景：** 团队已排期改造命令路由并引入权限模块；
- **评估：** 可暂列低风险，但需跟踪落地。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 受控环境 | 攻击面小 | 中 |
| 仅阅览信息 | 影响有限 | 低 |
| 改造计划明确 | 可暂缓 | 低 |
