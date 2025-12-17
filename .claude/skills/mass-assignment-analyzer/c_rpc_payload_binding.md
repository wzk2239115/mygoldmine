# C/C++ RPC 载荷批量赋值漏洞

## Details

### 漏洞成因
在 C/C++ 编写的 RPC/微服务架构中，常使用 gRPC、自研二进制协议或 JSON-RPC 将消息反序列化为结构体。若服务器端直接将解析后的结构体传递给业务逻辑并执行 `memcpy`、`assign`、`std::copy` 等批量赋值，而未验证字段合法性，攻击者即可在请求中加入额外字段覆盖敏感状态（如租户 ID、审批状态、额度、访问权限）。跨服务同步中，如果下游默认信任上游传入的对象，也会导致权限绕过。

### 代码示例

**易受攻击的代码：**
```c
typedef struct {
    uint32_t order_id;
    uint32_t tenant_id;
    double amount;
    bool approved;
} order_payload_t;

void handle_update_order(const uint8_t *buf, size_t len) {
    order_payload_t payload;
    deserialize_order(buf, len, &payload);
    // 未校验 tenant_id/approved
    apply_order_update(&payload);
}
```

**另一个不安全示例（gRPC Proto 直写）：**
```cpp
Status AccountService::Update(AccountRequest const* req, AccountReply* res) {
    Account account = repository.find(req->id());
    // 使用 Proto 生成的 MergeFrom 直接覆盖
    account.mutable_proto()->MergeFrom(req->proto());
    repository.save(account); // client 可设置 balance、role
    res->set_success(true);
    return Status::OK;
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：**
- 反序列化函数：`deserialize_*`, `ParseFromArray`, `MergeFrom`, `memcpy(&struct, buf, ...)`
- RPC handler：`handle_*`, `Service::Method`, `OnMessage`
- 结构体批量赋值：`memcpy`, `assign`, `operator=`, `MergeFrom`
- 多租户/权限字段：`tenant`, `role`, `approved`, `is_admin`

**定位步骤：**
1. 搜索 RPC 入口函数，查看反序列化后的处理逻辑。
2. 关注直接将载荷写入业务实体的代码。
3. 跳读（L2）确认是否有租户/权限校验或字段过滤。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- **字段过滤：** 白名单或忽略敏感字段的逻辑。
- **授权校验：** 校验调用者身份、租户范围。
- **数据验证：** `validate(payload)` 函数确保字段合法。
- **版本控制：** 旧客户端无法设置新增敏感字段。
- **签名/完整性校验：** 确认载荷未被篡改。

**定位技巧：**
- 对 Proto `MergeFrom` 使用，确认是否启用 `arena`, `mutable_field` 过滤。
- 检查服务间调用链，确保上游传递的敏感字段被隔离。
- 关注热修复/调试模式是否绕过校验。

#### 审计等级标注

| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 手动逐字段赋值并校验 | **L0（快速跳过）** | 无批量赋值 |
| 使用 `MergeFrom` 但忽略敏感字段 | **L2（跳读）** | 确认忽略逻辑完整 |
| 直接将请求对象持久化 | **L3（逐行读）** | 高风险 |
| 多服务链路传递敏感字段 | **L4（跨模块追踪）** | 需全链路分析 |

## Classify

### 研判标准

#### 确认漏洞
需满足以下条件：
1. **反序列化/批量赋值** 直接接受外部输入。
2. **缺乏字段过滤或权限验证**。
3. **导致敏感状态被篡改**（跨租户、审批绕过、额度修改等）。

#### 误报
以下情况可视为误报：
1. **请求通过签名/加密** 并来自受信任服务，且字段不可被攻击者伪造。
2. **服务端在持久化前执行二次校验**（例如对租户 ID 重写）。
3. **请求只包含读取字段**，无敏感写操作。

#### 代码异味
需记录的风险模式：
1. **`memcpy`/`MergeFrom` 无任何过滤**，即使目前字段不敏感也有隐患。
2. **使用黑名单过滤**，容易遗漏新增字段。
3. **上下游共用同一 protobuf 消息**，导致意外字段被暴露。
4. **调试接口沿用生产逻辑**，缺少校验。

## Low risk

### 低风险评级场景

#### 1. 内部可信链路
- **场景：** RPC 仅在受控内部网络使用，且有 mTLS。
- **风险评估：** 攻击面较小，但需防内部滥用。

#### 2. 服务端重写关键字段
- **场景：** 在持久化前强制设置租户 ID/角色。
- **风险评估：** 可降低风险，但需确保无绕过路径。

#### 3. 请求签名与版本控制
- **场景：** 消息需要签名且有严格 schema 校验。
- **风险评估：** 风险较低，但要验证校验不可跳过。

#### 4. 完整审计日志
- **场景：** 对敏感字段的变更有审计与告警。
- **风险评估：** 有助于监测，仍应修复根因。

### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 内部受控 + mTLS | 攻击面有限 | 中 |
| 服务端重写敏感字段 | 防止覆盖 | 低 |
| 签名 + schema 校验 | 防篡改 | 中 |
| 审计告警 | 及时发现异常 | 高（继续改进）|

