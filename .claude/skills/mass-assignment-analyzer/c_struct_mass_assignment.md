# C/C++ 批量赋值漏洞

## Details

### 漏洞成因
在 C/C++ 项目中，自研 REST/RPC 框架或第三方序列化库（cJSON、rapidjson、protobuf JSON mapping 等）常将外部输入自动映射到 `struct`/类实例。如果映射过程未限制可写字段，攻击者可以提交额外属性覆盖敏感字段（如 `is_admin`、`status`、`tenant_id`、`balance`），从而绕过权限控制或篡改业务数据。常见场景包括配置热更新、设备策略下发、嵌入式管理后台、微服务之间的结构体反序列化等。

### 代码示例

**易受攻击的代码：**
```c
typedef struct {
    char username[32];
    char email[64];
    bool is_admin;
} user_t;

int update_user(const char *json_payload) {
    user_t user = {0};
    cJSON *root = cJSON_Parse(json_payload);
    // 未验证字段，客户端可传 is_admin=true
    strcpy(user.username, cJSON_GetObjectItem(root, "username")->valuestring);
    strcpy(user.email, cJSON_GetObjectItem(root, "email")->valuestring);
    cJSON *admin = cJSON_GetObjectItem(root, "is_admin");
    if (admin) {
        user.is_admin = admin->valueint;
    }
    persist_user(&user);
    cJSON_Delete(root);
    return 0;
}
```

**另一个不安全示例（反射式赋值）：**
```cpp
struct DeviceConfig {
    std::string name;
    std::string timezone;
    bool remoteShellEnabled;
};

void applyConfig(const Json::Value &json) {
    DeviceConfig cfg{};
    for (auto it = json.begin(); it != json.end(); ++it) {
        const std::string key = it.key().asString();
        // 使用自定义反射映射字段，缺少白名单
        setFieldByName(cfg, key, it->asString());
    }
    saveConfig(cfg); // 攻击者可提交 remoteShellEnabled=true
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- JSON/XML 解析库：`cJSON_Parse`, `rapidjson::Document`, `Json::Value`, `protobuf::util::JsonParse`
- 反射/字段映射函数：`memcpy(&struct, ...)`, `setFieldByName`, `field_map`, `offsetof`
- 配置热更新接口、REST/RPC 处理函数、`applyConfig`, `update_*`
- 表单/命令处理函数中对结构体的批量赋值

**定位步骤：**
1. 搜索解析函数与结构体赋值函数共现的代码。
2. 关注循环遍历 JSON 键值或使用字段映射表的实现。
3. 跳读（L2）检查是否存在字段白名单或敏感字段保护。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段白名单：** 显式列出允许写入的键值数组或 `switch` 分支。
- **敏感字段屏蔽：** `if (strcmp(key, "is_admin") == 0) continue;`
- **权限校验：** 在赋值前确认调用者角色、租户范围。
- **结构体初始化：** 使用默认安全值、拒绝未知字段。

**定位技巧：**
- 确认解析后是否调用 `filter_keys` 等辅助函数。
- 检查函数返回值是否处理未知字段（如记录告警或报错）。
- 对配置同步等跨模块逻辑，跟踪数据是否再次校验。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 全部字段手动赋值并显式列出 | **L0（快速跳过）** | 无自动映射 |
| 使用映射但包含白名单/敏感字段过滤 | **L2（跳读）** | 确认过滤逻辑正确 |
| 自动遍历赋值 + 接受任意字段 | **L3（逐行读）** | 高风险 |
| 多模块配置下发或跨租户同步 | **L4（跨模块追踪）** | 需追踪全链路 |

## Classify

### 研判标准

#### 确认漏洞
满足以下条件判定为批量赋值漏洞：
1. **存在自动映射**：使用循环或反射将输入字段赋值给结构体/对象。
2. **输入可控**：字段直接来自外部请求或不可信源。
3. **敏感字段可被覆盖**：缺乏白名单/过滤，导致权限、角色、状态等字段被篡改。

#### 误报
以下情况可判定为误报：
1. **仅赋值白名单字段**，其他字段被忽略或拒绝。
2. **敏感字段在协议层被剥离**，客户端无法提交。
3. **仅用于受控内部通信**，并与强校验/签名配合保证完整性。

#### 代码异味
需警惕但暂未构成漏洞的场景：
1. **白名单不完整**，部分敏感字段未列出。
2. **过滤依赖配置文件**，配置可被管理员误改。
3. **接受未知字段但仅记录日志**，未及时阻断。
4. **同一函数既处理受控配置又处理用户输入**，逻辑混杂易误用。

## Low risk

### 低风险评级场景

#### 1. 内部管理通道
- **场景：** 接口仅供受信任管理员调用，并有额外鉴权。
- **风险评估：** 攻击面小，但需防凭证泄露。

#### 2. 默认只读结构体
- **场景：** 结构体敏感字段只在服务端赋值，客户端无法覆盖。
- **风险评估：** 风险较低，但需确保不会被重新赋值。

#### 3. 配置受签名保护
- **场景：** 配置包由服务器签名校验，客户端无法篡改。
- **风险评估：** 可降低风险，但需验证签名过程不可绕过。

#### 4. 容器/权限隔离
- **场景：** 即使被覆盖，进程权限受限导致危害有限。
- **风险评估：** 限制影响面，但仍需修复根源。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 管理接口且多重鉴权 | 攻击面小 | 中 |
| 白名单 + 敏感字段只读 | 技术防护完善 | 低 |
| 配置签名/校验 | 防止篡改 | 中 |
| 权限隔离/沙箱 | 限制危害 | 高（仍需持续改进）|

