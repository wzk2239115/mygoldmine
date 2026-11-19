# libcoap 安全审计报告（进行中）

- 项目: libcoap (C, CoAP 协议库)
- 源码版本: a4de0faea54d3d548924c8b9f6e67b72a36cbac3 (2026-11-16)
- 状态: 审计进行中，本文件将随子任务逐步更新。

## 审计范围与方法

- 目标：libcoap 4.3.5-dev 核心库（`src/`）、OSCORE 实现（`src/oscore/`）、示例服务端/客户端（`examples/`）的关键网络入口。
- 项目类型：C 原生协议库（`native_library` / `protocol_library`），单一工程，非 Monorepo；`ext/tinydtls` 子模块未初始化。
- 方法：项目画像 -> 覆盖规划（8 个高风险边界）-> 按信任边界分派内存安全、整数溢出、数据流、密码学分析 -> 归一化与证据复核 -> 报告。
- 信任边界：TB-NET-DGRAM、TB-NET-STREAM、TB-WS、TB-OSCORE、TB-URI、TB-BLOCK、TB-TLS-BACKEND、TB-CONFIG-FILE、TB-APP-HANDLER、TB-PROXY、TB-PLATFORM-IO。
- 初筛：已读取 Jev triage（`triage/jev-infra.json`，485 单元）。高分单元集中在构建脚本（`scripts/*.sh`、`autogen.sh`）与示例脚本的 `subprocess_exec`，属构建期行为、非远端可达攻击面；`src/coap_openhitls.c`、`examples/coap-server.c`（含 OSCORE 配置加载段）标记为 `untrusted_model_input`，已纳入阅读顺序参考。Jev 仅用于召回，不作为候选问题。
- 约束：仅做漏洞定位、根因分析、最小复现思路与修复建议；不编写可直接武器化的利用代码；未执行动态验证的条目保持 `unverified`。

## 候选问题

### LIBCOAP-MED-001：OSCORE Appendix B.2 kid_context 的 CBOR 包装缓冲区空间少算 1 字节

- 严重度：中危（可达性受限，需启用 B.2 测试模式）
- 位置：`src/oscore/oscore.c:217-231`；缓冲区 `src/coap_oscore.c:418`（`oscore_option[255]`）；触发调用 `src/coap_oscore.c:540-543`
- 根因：B.2 分支把 `oscore_cbor_put_bytes()` 的可用空间参数传为 `rem_space`，但目标指针是 `&option_buffer[offset+1]`，实际可用空间为 `rem_space-1`。当 CBOR 头长度 `nb` 与 `kid_context.length` 之和恰好等于 `rem_space` 时，`memcpy` 会写到 `option_buffer[255]`，越过 255 字节缓冲区 1 字节（`src/oscore/oscore_cbor.c:105-118`）。
- 可达性：仅当客户端启用 RFC8613 Appendix B.2 测试模式（`src/coap_oscore.c:43-56`）时，`session->b_2_step != NONE`；恶意服务端返回的 `kid_context` 会经 `src/coap_oscore.c:1209,1214-1234` 更新为安全上下文 `id_context`，后续请求编码时触发越界写。
- 影响：栈缓冲区越界写 1 字节，写入值来自攻击者可控 `kid_context` 的末字节；生产默认配置不可达。
- 修复建议：传给 `oscore_cbor_put_bytes()` 的空间改为 `rem_space-1`，并在调用前显式校验 `nb + length <= rem_space-1`；解码侧 `255-1-1-...` 边界改为带下溢保护的判断。
- 验证状态：`unverified`（静态推演，未运行 ASan）。

### LIBCOAP-LOW-001：Uri-Path-Abbrev 回退重传时载荷被加到旧 PDU 并随旧 PDU 释放

- 严重度：低危（功能/数据完整性问题）
- 位置：`src/coap_net.c:1801-1809`；`coap_pdu_duplicate_lkd()` `src/coap_pdu.c:271-327`
- 根因：回退路径生成 `new` 后，1815 行附近的 `coap_add_data(pdu, data_len, data)` 把载荷加到旧 `pdu`，随后 `coap_delete_pdu_lkd(pdu)` 释放旧 PDU；`coap_pdu_duplicate_lkd()` 只复制选项、不复制载荷，导致重传 PDU 丢失请求体。
- 影响：客户端使用 Uri-Path-Abbrev 且请求带载荷时，回退重传丢失载荷；不构成远端可利用的内存破坏。
- 修复建议：改为 `coap_add_data(new, data_len, data)`，失败时释放 `new` 并返回错误。
- 验证状态：`unverified`（静态代码阅读）。

### LIBCOAP-HIGH-001：coap_ws_close 用 100 字节栈缓冲复读未完成 WebSocket 帧

- 严重度：高（内存破坏；需启用 WS 端点并满足关闭时序）
- 位置：`src/coap_ws.c:761-764`（续读）、`src/coap_ws.c:697-707`（唯一一次帧长校验）、`src/coap_ws.c:897-918`（`uint8_t buf[100]` + `coap_ws_close` 排空循环）、`src/coap_session.c:596-597`、`src/coap_io.c:415-426`
- 根因：续读分支直接用会话缓存的 `data_size/data_ofs` 调 `l_read()`，不再用当前 `datalen` 校验；`coap_ws_close()` 关闭握手时以 100 字节栈缓冲调用 `coap_ws_read()`，若存在未完成大帧（`data_size>100`、`all_hdr_in=1`），`recv`/`SSL_read` 会把最多 `data_size` 字节写入 100 字节栈缓冲。
- 触发链：WS 客户端声明 101..1472 字节帧、只发部分载荷 → 服务端保留 `all_hdr_in=1` → 会话空闲超时释放（默认 300s）或 reconnect 触发 `l_close` → `coap_ws_close` 的 select 排空窗口内对端送达数据 → 栈越界写。
- 影响：远端可控数据越界写入栈，服务端崩溃或潜在代码执行；TLS 后端经 `SSL_read` 同样越界。
- 修复建议：续读长度改为 `min(data_size-data_ofs, datalen)`，或在 `coap_ws_read` 入口对 `all_hdr_in=1` 复核 `data_size <= datalen`；关闭排空改用不小于 `COAP_MAX_FS` 的缓冲。
- 验证状态：`unverified`（静态复核确认缺少复核；需 ASan 动态验证触发时序）。

### LIBCOAP-LOW-002：单字节 WebSocket Close 载荷读取未初始化字节

- 严重度：低危
- 位置：`src/coap_ws.c:720-729`
- 根因：长度 1 的 Close 帧执行 `(data[0]<<8)+data[1]`，`data[1]` 未初始化；Close 载荷长度 1 本应以 1002 协议错误关闭。
- 影响：关闭码含未初始化字节并回显给对端，信息价值有限。
- 修复建议：Close 载荷长度必须为 0 或 ≥2，否则以 1002 关闭。

### LIBCOAP-MED-002：OSCORE 响应侧短密文路径未回滚重放窗口（拒绝服务）

- 严重度：中危（需 OSCORE + 明文 UDP + on-path 攻击者）
- 位置：`src/coap_oscore.c:1368-1382`（先推进 `last_seq`）、`src/coap_oscore.c:1482-1501`（响应分支未回滚）、`src/coap_oscore.c:1542-1550`（其他失败路径有回滚）
- 根因：解密前即校验并推进 `rcp_ctx->last_seq`；响应分支在 `encrypt_len <= tag_len` 时直接报错，未调用 `oscore_roll_back_seq()`。
- 影响：on-path 攻击者伪造高 PIV、token 匹配的 OSCORE 响应即可推进客户端重放窗口，使后续真实响应被丢弃，形成会话级 DoS。
- 修复建议：响应分支所有解密失败路径都调用 `oscore_roll_back_seq()`，或把 `last_seq` 更新推迟到 AEAD 验证成功之后。

### LIBCOAP-LOW-003：coap_rebuild_pdu_for_proxy 移除 Proxy-Uri 后使用旧指针

- 严重度：低危（语义/正确性，未确认越界）
- 位置：`src/coap_oscore.c:288-322`；`src/coap_pdu.c:635-639`
- 根因：`coap_split_proxy_uri()` 解析出的 `uri.host/path/query` 指向 PDU 内 Proxy-Uri 值；`coap_remove_option()` 的 `memmove` 压缩缓冲后，这些指针仍被用于构造 Uri-Host/Port/Path/Query。
- 影响：OSCORE 代理请求目标可能取自被移动后的字节（后续选项/载荷），与客户端意图不一致；指针仍在原分配缓冲内。
- 修复建议：移除选项前复制 host/path/query 到独立缓冲。

### LIBCOAP-LOW-004：代理 Hop-Limit 缺省与端点比较问题

- 严重度：低危（需代理配置）
- 位置：`src/coap_net.c:4094`、`src/coap_proxy.c:1214`、`src/coap_net.c:3954`
- 根因：仅在 Hop-Limit 存在时递减、不补默认值；端点名比较区分大小写。
- 影响：特定代理部署下可能形成自环/放大。
- 修复建议：始终补默认 Hop-Limit，转发前检测自环，端点比较规范化。

### LIBCOAP-LOW-005：%2F 主机被解析为本地 AF_UNIX 目标

- 严重度：低危（需 FWD_DYNAMIC 代理）
- 位置：`src/coap_uri.c:260`、`src/coap_address.c:749`
- 根因：URI 主机中的 `%2F` 解码后作为本地 UNIX 套接字路径。
- 影响：动态代理可被诱导连接任意本地套接字。
- 修复建议：代理默认禁止 AF_UNIX 目标，或解析层拒绝百分号编码的本地路径。

## 待核实假设

（待补充）

## 覆盖与限制

- 覆盖记录：`.workspace/findings/coverage-ledger.json`；计划：`.workspace/findings/coverage-plan.json`。
- 已完成：COV-PROF-001（项目画像）、COV-PLAN-001（覆盖规划）、COV-MEM-OSCORE（OSCORE 内存安全，含 1 条候选、8 条假设）。
- 进行中：COV-MEM-PDU、COV-MEM-WS、COV-INT-OPT-CBOR；待派发：COV-INT-BLOCK、COV-DF-NET-DISPATCH、COV-DF-PROXY-URI、COV-CRYPTO-OSCORE-DTLS。
- 尚未覆盖：TLS 后端实现（OpenSSL/GnuTLS/Mbed-TLS/OpenHiTLS/TinyDTLS）、平台 I/O 层、RIOT/Contiki/lwIP 移植示例。
- 仓库只有一个压缩提交，无法做历史 diff 对比；结论完全依赖静态代码阅读。
