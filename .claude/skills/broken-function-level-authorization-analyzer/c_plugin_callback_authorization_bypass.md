# C/C++ 插件回调授权绕过

## Details

### 漏洞成因
C/C++ 应用常通过插件或事件回调扩展功能。若在注册回调或调用回调时仅根据插件名称进行匹配，而未校验当前会话是否具备执行权限，普通用户即可加载或触发原本仅限管理员使用的回调函数，执行敏感操作（如配置变更、设备控制、文件操作）。

### 代码示例

**易受攻击的代码：**
```c
typedef void (*plugin_cb_t)(Session *sess, const char *payload);

void register_plugin(const char *name, plugin_cb_t cb);

void on_event(Session *sess, const char *event, const char *payload) {
    plugin_cb_t cb = find_plugin(event);
    if (cb) {
        cb(sess, payload);  // 未校验 sess->role
    }
}

void plugin_admin_reset(Session *sess, const char *payload) {
    system("restore_factory_defaults");
}
```

**安全示例：**
```c
void register_plugin(const char *name, plugin_cb_t cb, Role required_role);

void on_event(Session *sess, const char *event, const char *payload) {
    PluginEntry *entry = find_plugin(event);
    if (!entry) return;
    if (!session_has_role(sess, entry->required_role)) {
        log_warn("unauthorized plugin call: %s", event);
        return;
    }
    entry->handler(sess, payload);
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `register_plugin`, `plugin_cb`, `callback`, `event`, `hook`, `listener`, `dispatch`。

**定位步骤：**
1. 搜索插件注册与事件触发接口；
2. 跳读（L2）确认回调调用前是否执行权限检查；
3. 检查插件元数据是否包含角色要求但未使用。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- 插件注册时记录所需权限；
- 回调前调用认证框架（RBAC/ACL）；
- 插件名称空间区分特权插件；
- 插件加载阶段验证签名、来源和权限。

**定位技巧：**
- 逐行读（L3）敏感插件（如系统重置、参数修改）的实现；
- 跨模块追踪（L4）插件触发点是否对外开放（HTTP、RPC、脚本 API）。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 插件回调统一封装权限检查 | **L0（快速跳过）** | 安全性高 |
| 插件元数据存在权限字段但部分未检查 | **L2（跳读）** | 快速确认遗漏 |
| 回调直接执行无任何校验 | **L3（逐行读）** | 高风险 |
| 插件可从外部输入加载并执行 | **L4（跨模块追踪）** | 全链路排查 |

## Classify

### 研判标准

#### 确认漏洞
1. 普通用户可触发特权插件回调；
2. 回调执行敏感操作且缺乏权限检查；
3. 漏洞可复现越权操作（恢复出厂、修改策略）。

#### 误报
1. 插件体系仅在管理员登录后启用，外部无法触达；
2. 回调内部自行校验权限并在无权限时拒绝执行；
3. 插件仅用于收集信息不涉及敏感写操作。

#### 代码异味
1. 插件回调校验散落各处，缺乏统一策略；
2. 仅通过插件名称约定权限而无强制检查；
3. 插件加载过程未验证签名，潜在植入恶意插件。

## Low risk

### 低风险评级场景

#### 1. 插件仅用于诊断
- **场景：** 回调只输出日志或诊断信息；
- **评估：** 影响小，可标低风险。

#### 2. 运行环境受控
- **场景：** 插件接口仅暴露给内部管理网络；
- **评估：** 攻击面有限，但需加固。

#### 3. 计划接入权限框架
- **场景：** 已安排统一权限模块改造；
- **评估：** 可暂列低风险并跟踪。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 诊断用途 | 影响有限 | 低 |
| 受控网络 | 攻击面小 | 中 |
| 改造在即 | 可暂缓 | 低 |
