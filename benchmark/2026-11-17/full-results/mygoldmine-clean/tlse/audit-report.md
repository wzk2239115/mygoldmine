# TLSe 安全审计报告

- 项目标识：tlse
- 显示名称：TLSe（单文件 C 语言 TLS/DTLS 实现）
- 源码版本：25be48a4f0176b7242d8c5955fc325e92b487838（"Fix for #164"）
- 审计方式：静态审计（源码阅读 + 技能分析），未执行动态验证
- 报告状态：**进行中（增量更新）**

## 1. 项目概览

TLSe 是单文件 C 语言 TLS 1.0–1.3 / DTLS 1.0–1.2 实现，辅以 libtomcrypt 作为密码库，
并附带 DTLS-SRTP / WebRTC RTCPeerConnection 支持。

| 文件 | 行数 | 说明 |
|------|------|------|
| `tlse.c` | 15009 | 协议主体：记录层、握手、证书校验、导出/导入、STUN、SRTP |
| `x509.c` | 11945 | ASN.1/X.509 解析（`TLS_FULL_X509` 时 include 进 tlse.c） |
| `libtomcrypt.c` | 35615 | 第三方密码库 amalgamation |
| `tls_root_ca.h` | 3730 | 内置 Mozilla 根证书（PEM 字符串） |
| `examples/*.c` | ~700 | 客户端/服务端示例 |

信任边界：网络字节流（TLS 记录、握手消息、证书、STUN 报文）→ 长度解析/状态机 → 内存分配、
密钥派生、证书链校验 → 应用数据。

## 1.5 审计方法与覆盖记录

| 阶段 | 内容 | 产物 |
|------|------|------|
| 画像 | `project-profiler`：单文件 C 库，`project_types` 为空，`native_memory.detected=true` | `.workspace/tasks/orch-001/project-profile.json` |
| 初筛 | Jev infra profile（192 单元），仅用于安排阅读顺序 | `triage/jev-infra.json` |
| 第 1/2 波 | 原生内存安全 + IPC 反序列化（`memory-safety-analyzer`、`ipc-serialization-analyzer`） | `memsafety-stun.json`、`memsafety-x509.json`、`serialization-import.json` |
| 归并 | `hypothesis-critic` 去重与可达性/严重度校准 | `findings.normalized.json`、`hypothesis-review.md` |
| 第 3 波 | 密码学校验、整数下溢、证书长度符号转换补证；证书长度假设经 `memory-safety-analyzer` 复核被反证，另产出低危越界读 `MEM-CERTLEN-001` | `.workspace/findings/crypto-*`、`integer-*`、`memsafety-certlen.json` |
| 覆盖记录 | 6 条覆盖条目，schema 校验通过 | `.workspace/findings/coverage-ledger.json` |

技能版本（`SKILL.md` SHA-256）：`memory-safety-analyzer` = `53301e64…a4a93a`；
`ipc-serialization-analyzer` = `2130ed07…1c131d192`。

对 `hypothesis-critic` 提出的一处字节数修正（REALM 越界阈值改为 `realm_len>=718`、越界改为 46 字节）
已独立复核并**否决**：`memcpy(ptr, realm, realm_len)` 的起点是 `key+username_len+1`，最后写入下标为
`username_len+realm_len`，故阈值为 `>=717`（username_len=513 时）、最大越界 47 字节。枚举复核见
`coverage-ledger.json` 中 `COV-STUN-001.fact_corrections`。

## 2. 候选问题

说明：以下全部为**静态源码级候选**，未构建、未运行目标代码，`verification.status` 均为 `unverified`。
「可达性」按库的预期用法判定（宿主把网络数据交给相应公共 API），并逐条标注前提。

### TLSE-2026-0001 tls_stun_parse 在 MESSAGE-INTEGRITY 校验前把攻击者可控 REALM 拷入固定栈缓冲区 key[0x4CE]，导致栈越界写

| 项 | 内容 |
|----|------|
| 严重度 | 高危（Critical） |
| 可达性 | 默认路径（前提：宿主调用 `tls_peerconnection_iterate` 处理网络报文的 STUN 分支） |
| CWE | CWE-787 越界写 |
| 位置 | `tlse.c:13085`、`tlse.c:13184`、`tlse.c:13254`、`tlse.c:13201-13218`、`tlse.c:13240` |
| 验证状态 | unverified（静态） |

**根因**

`tls_stun_parse` 用固定大小的栈缓冲区拼接 `USERNAME:REALM:pwd` 作为 MD5 密钥材料：

```c
char key[0x4CE];                                  /* 1230 字节，tlse.c:13085 */
...
if (attr_len > 513) return TLS_BROKEN_PACKET;     /* USERNAME 上限 513，13184 */
...
if (attr_len > 763) return TLS_BROKEN_PACKET;     /* REALM 上限 763，13254 */
...
memcpy(ptr, username, username_len); ptr += username_len; *ptr=':'; ptr++;   /* 13203-13207 */
memcpy(ptr, realm, realm_len);                                             /* 13210 */
ptr += username_len;                              /* 13211，步进量写错，应为 realm_len */
```

三个属性各自的上限都小于 1230，但**拼接后的总长度不受 1230 约束**：

```
513 (USERNAME) + 1 (':') + 763 (REALM) + 1 (':') + 24 (local_pwd) + 1 (NUL) = 1303 > 1230
```

因此当 `username_len + realm_len > 1229`（最后一字节下标 = `username_len + realm_len`）（例如 `username_len=513`、`realm_len>=717`）时，
13210 行的 `memcpy` 就已越过 `key` 末尾；`realm_len=763` 时写到 `key+1276`，最多越界 47 字节。

校验顺序进一步放大了影响：`memcmp` 比对 MESSAGE-INTEGRITY 在 13240 行，**位于拼接之后**，
攻击者不需要知道 `local_pwd` 即可触发越界写。

**影响**

未认证远程攻击者可向使用 DTLS-SRTP/WebRTC 的进程写入最多 47 字节栈数据，覆盖相邻局部变量与
保存的寄存器。未启用栈保护时可影响控制流；启用 `-fstack-protector` 时至少造成远程拒绝服务。
攻击发生于任何证书/凭据校验之前。

**最小复现思路（非武器化）**

在隔离构建中启用 AddressSanitizer，构造一个 STUN Binding Request（type=0x0001，
magic cookie 0x2112A442），属性序列为 USERNAME(len=513)、REALM(len=763)、MESSAGE-INTEGRITY(len=20)，
调用 `tls_stun_parse(buf, buf_len, pwd, 24, 0, addr, 0, NULL)`，观察 `stack-buffer-overflow` 报告。
无需构造有效 HMAC。

**修复建议**

1. 拼接前显式校验 `username_len + 1 + realm_len + 1 + pwd_len + 1 <= sizeof(key)`，超限直接返回错误；
2. 把 `key` 容量提升到至少 1303 字节（或改为按需分配/带边界写入）；
3. 修正 `tlse.c:13211` 的 `ptr += username_len` 为 `ptr += realm_len`；
4. 建议把 MESSAGE-INTEGRITY 的长度/字段合法性校验尽量前移，但校验顺序不能替代容量校验。

**反证/限制**

- 若宿主不在网络路径调用 `tls_peerconnection_iterate`，该路径不可达；
- `pwd` 来自 `channel->local_pwd`（24 字符 + NUL，`tlse.c:13721`），本身不放大溢出；
- 即使修正 13211 的步进错误，1303 > 1230 仍越界，说明根因是容量与拼接长度不匹配。

### TLSE-2026-0002 默认 ASN.1 分支中零长度 BIT STRING 使 set_sign_key 的 len 下溢为 -1，触发超长 memcpy 堆越界写

| 项 | 内容 |
|----|------|
| 严重度 | 高危（High） |
| 可达性 | 默认构建（未定义 `TLS_FULL_X509`）下由对端证书内容触发 |
| CWE | CWE-787 越界写（有符号长度下溢） |
| 位置 | `tlse.c:11589-11590`、`tlse.c:4594-4598`、`tlse.c:4546-4558`、`tlse.c:11766-11783`、`tlse.c:8702` |
| 验证状态 | unverified（静态） |

**根因**

默认构建走 `_private_asn1_parse`（`#ifdef TLS_FULL_X509` 未定义，`tlse.c:11308`；仓库内无该宏定义）。
BIT STRING 分支未校验长度：

```c
case 0x03:
    ...
    if ((level == 2) && (idx == 3) && (fields[0] == 1)) {
        tls_certificate_set_sign_key(cert, &buffer[pos], length);   /* 11589-11590，length 可为 0 */
    }
```

`tls_certificate_set_sign_key` 无条件读取 `val[0]` 并在其为 0 时自减长度：

```c
void tls_certificate_set_sign_key(struct TLSCertificate *cert, const unsigned char *val, int len) {
    if (!val[0]) { val++; len--; }        /* len==0 时 len 变为 -1，tlse.c:4597-4598 */
    tls_certificate_set_copy(&cert->sign_key, val, len);
```

`tls_certificate_set_copy` 用 `len+1` 分配、再 `memcpy(..., len)`：

```c
if (len) {
    *member = (unsigned char *)TLS_MALLOC(len + 1);   /* malloc(0)，glibc 返回非 NULL */
    if (*member) {
        memcpy(*member, val, len);                    /* len == -1 → size_t SIZE_MAX，4546-4553 */
```

`len` 为 `int`，`-1` 在 `memcpy` 的 `size_t` 参数位置变成 `SIZE_MAX`，即以巨大长度向 `malloc(0)`
堆块写入，几乎必然立即破坏堆并崩溃。

**影响**

对端（服务端证书或客户端证书，`is_server` 为 0/1 都会走该分支）可在证书内容校验之前触发堆越界写。
典型后果是远程拒绝服务；若堆布局可被控制则存在进一步利用风险。

**最小复现思路（非武器化）**

在启用 ASan 的隔离构建中，构造一个 DER 证书，使其 tbsCertificate 的第 3 个 TLV 为 `03 00`
（BIT STRING、长度 0），后接任意字节，调用 `asn1_parse(NULL, der, len, 0)` 或经
`tls_parse_certificate` 注入，观察 `heap-buffer-overflow` / `negative-size-param`。

**修复建议**

1. `tls_certificate_set_sign_key` / `tls_certificate_set_key` 入口拒绝 `len <= 0`（或先判断 `val[0]` 前要求 `len > 0`）；
2. `tls_certificate_set_copy` 改为 `if (len > 0)`，并对 `len + 1` 做上限检查，避免有符号下溢转换成 `size_t`；
3. `_private_asn1_parse` 的 `case 0x03` 在 `length == 0` 时跳过或返回错误。

**反证/限制**

- 定义 `TLS_FULL_X509` 时走 `x509.c` 的 `parse_x509_cert_relaxed`，本缺陷不参与编译；
- 若目标 libc 的 `malloc(0)` 返回 NULL，则 `memcpy` 不执行，缺陷退化为 1 字节越界读；glibc 返回非 NULL；
- 触发需构造特定 ASN.1 结构，但解析器不校验元素顺序或签名，构造门槛低。

### TLSE-2026-0003 tls_import_context 读取 mac_length 前缺少边界检查，可越界读取 1 字节

| 项 | 内容 |
|----|------|
| 严重度 | 低危（Low） |
| 可达性 | requires-config（仓库内仅有自导出后自导入的示例调用点） |
| CWE | CWE-125 越界读 |
| 位置 | `tlse.c:12858`、`tlse.c:12812-12814`、`tlse.c:788` |
| 验证状态 | unverified（静态） |

**根因**

`tls_import_context` 其余字段读取前都有 `TLS_IMPORT_CHECK_SIZE`，但 `mac_length` 读取没有：

```c
key_lengths = buffer[buf_pos++];
TLS_IMPORT_CHECK_SIZE(buf_pos, key_lengths, buf_len)
memcpy(temp, &buffer[buf_pos], key_lengths);
buf_pos += key_lengths;
...
mac_length = buffer[buf_pos++];   /* tlse.c:12858，缺检查；buf_pos 可等于 buf_len */
```

`TLS_IMPORT_CHECK_SIZE` 允许 `key_lengths == buf_len - buf_pos`，此时 `buf_pos == buf_len`，
12858 行读取 `buffer[buf_len]`，越界 1 字节。读取值随后作为 `mac_length`：>48 时销毁上下文，
否则下一处检查也会失败，因此仅造成单字节越界读，可能触发页边界崩溃。

**影响**

若导入缓冲区可被攻击者控制，可造成 1 字节越界读与潜在拒绝服务；未见信息泄露或写内存路径。

**最小复现思路**

启用 ASan，构造满足 `length == buf_len - 5`、`iv_len<=16` 且 `key_lengths` 恰好消耗完全部剩余
字节的缓冲区，调用 `tls_import_context(buf, buf_len)`，观察越界读报告。

**修复建议**

在 12858 行前增加 `TLS_IMPORT_CHECK_SIZE(buf_pos, 1, buf_len)`；并对 `key_lengths` 增加
`2 <= key_lengths <= sizeof(temp)` 的显式校验，同时与 cipher 的期望密钥长度做交叉校验。

### TLSE-2026-0004 tls_import_context 的 CBC 分支使用未初始化的栈 IV 字节

| 项 | 内容 |
|----|------|
| 严重度 | 低危（Low） |
| 可达性 | requires-config（需导入非自身导出的缓冲区，且 cipher 为 CBC 类） |
| CWE | CWE-457 未初始化变量 |
| 位置 | `tlse.c:12768-12769`、`tlse.c:12798-12810`、`tlse.c:12851`、`libtomcrypt.c:33364-33366` |
| 验证状态 | unverified（静态） |

**根因**

`local_iv`/`remote_iv` 是 16 字节未初始化栈数组，导入时只按 `iv_len`（0..16）复制，
随后 `_private_tls_crypto_create` 经 `cbc_start` 复制完整 16 字节 IV。当 `iv_len < 16` 时，
剩余字节是栈残留，被当作首条记录的 IV 使用，造成状态不确定与信息泄露风险。

**修复建议**

导入时按 cipher 校验 `iv_len` 必须等于该 cipher 的 IV 长度并拒绝不一致值，或在复制前
`memset(local_iv/remote_iv, 0, sizeof(...))`。

### TLSE-2026-0005 TLS_REEXPORTABLE 导入路径未检查 TLS_MALLOC 返回值即 memcpy

| 项 | 内容 |
|----|------|
| 严重度 | 低危（Low） |
| 可达性 | opt-in（仅在定义 `-DTLS_REEXPORTABLE` 时编译） |
| CWE | CWE-476 空指针解引用 |
| 位置 | `tlse.c:12816-12820` |
| 验证状态 | unverified（静态） |

**根因**

```c
context->exportable_keys = TLS_MALLOC(key_lengths);
memcpy(context->exportable_keys, temp, key_lengths);   /* 未判空 */
```

分配失败且 `key_lengths > 0` 时对 NULL 写入。同函数其他缓冲区均有判空，此处遗漏。

**修复建议**

分配后检查返回值，失败时 `tls_destroy_context(context)` 并返回 NULL。


### TLSE-2026-0006 tls_parse_verify_request 在 DTLS HelloVerifyRequest 握手体短于 3 字节时读取 buf[13]，造成 1 字节堆越界读

| 项 | 内容 |
|----|------|
| 严重度 | 低危（Low） |
| 可达性 | 需配置（DTLS 客户端角色 `context->dtls=1`、`is_server=0`，且 `connection_status==0`） |
| CWE | CWE-125 越界读 |
| 位置 | `tlse.c:7886`、`tlse.c:7888`、`tlse.c:7889`；调用点 `tlse.c:9953`；前置校验 `tlse.c:7847`、`tlse.c:9828`、`tlse.c:9856` |
| 验证状态 | unverified（静态） |

**根因**

`tls_parse_verify_request` 以固定偏移表示 DTLS 握手头长度：`res = 11`（3 字节 length + 2 字节 message_seq + 3 字节 fragment_offset + 3 字节 fragment_length）。`tlse.c:7886` 的
`CHECK_SIZE(bytes_to_follow, buf_len - res, TLS_NEED_MORE_DATA)` 中 `bytes_to_follow` 就是握手体长度 `L`，而传参时 `buf_len = L + 11`，因此该检查恒成立（`L <= L`），只保证 `buf_len >= 11`。
随后 `tlse.c:7888` 无条件 `res += 2`（`res` 变为 13），`tlse.c:7889` 直接读取 `len = buf[res]`，未先校验剩余长度是否至少 3 字节。

**触发路径**

网络 DTLS 记录 → `tls_consume_stream`（`tlse.c:12434`）→ `tls_parse_message`（`tlse.c:10428`）→ `tls_parse_payload`（`tlse.c:9801`）case `0x03`（`tlse.c:9949-9957`）：
`payload_size = L + 11`，`CHECK_SIZE(L + 12, record_len)` 通过后调用 `tls_parse_verify_request(buf + 1, L + 11)`；`_private_dtls_check_packet`（`tlse.c:7843`）的 `CHECK_SIZE(11, buf_len)` 只保证 `buf_len >= 11`，
`L∈{0,1,2}` 时 `buf_len∈{11,12,13}` 恰好通过，最终 `tlse.c:7889` 读取 `buf[13]`，超出有效下标范围（`L=0` 时越界 3 字节，`L=2` 时越界 1 字节）。

**影响**

单字节堆越界读，读取的值只用于 `tlse.c:7894` 的 `CHECK_SIZE` 与 `tlse.c:7895` 的 `TLS_MALLOC` 长度，不会回显给对端，也未发现写链。实际后果是 ASan 报告或越界触及页边界时的进程崩溃（拒绝服务）。
`L∈{0,1}` 时 `buf_len - res = L - 2 < 0`，`len`（`unsigned char` 提升为 `int`）与负值做有符号比较，`7894` 直接返回 `TLS_NEED_MORE_DATA`，不执行 `memcpy`；`L=2` 时只有越界读到 0 才继续，走 `if (len)` 假分支。

**最小无害复现思路（非武器化）**

在隔离 ASan 构建中令 `context->dtls=1`、`context->is_server=0`，向 `tls_consume_stream` 投递单个 25 字节最小 DTLS 记录：13 字节记录头
（`type=22`、`version=0xFEFD`、`epoch=0`、`seq=0`、`record_len=12`）+ 12 字节握手消息（`type=0x03`、24 位 `length=0x000000`、`message_seq=0`、`fragment_offset=0`、`fragment_length=0`），
观察 `tlse.c:7889` 处 `heap-buffer-overflow READ of size 1`。

**修复建议**

在 `tlse.c:7886` 之后、`res += 2` 之前补充边界检查，例如 `CHECK_SIZE(3, buf_len - res, TLS_NEED_MORE_DATA)`（或先计算 `body_remaining = buf_len - 11` 并要求 `>= 3` 再读取 version 与 cookie_len），
并把 `buf[res]` 的读取统一移到所有长度校验之后。

### 3.1 已复核排除或降级为假设的条目

| 编号 | 内容 | 位置 | 复核结论 |
|------|------|------|----------|
| HYP-CERTLEN-001 | TLS1.3 `context_size` 使 `res > buf_len` 后符号转换令越界读通过校验 | `tlse.c:8637-8710` | 已反证：`tlse.c:8677` 的 `CHECK_SIZE(3, buf_len - res)` 两实参均为 `int`，`res > buf_len` 时按有符号比较立即返回，不会到达 `8678` 的 `buf[res]`；`tlse.c:8644` 的 `size_of_all_certificates` 实为握手体长度 `L`，`L<=4` 时 `8646` 提前返回 |
| HYP-CERTLEN-002 | 同族 `buf_len - res` 模式在 `tls_parse_hello` / `_private_tls_parse_dh` / `_private_tls_parse_random` 中是否存在 `res > buf_len` 前置路径 | `tlse.c:8170-8840` | 已核对为安全：`8178` 的 `hello_min_size=41/49` 保证 `buf_len > res`；`8802/8805`、`8820/8824/8829` 均先检查，`size` 为 `unsigned short` 提升为 `int` 后按有符号比较 |

## 3. 待核实假设

以下条目证据不足以定为候选问题，保留为假设（均未动态验证）。

| 编号 | 假设 | 位置 | 为何未升级为候选 |
|------|------|------|------------------|
| H-01 | STUN 属性 padding 记账使 `stun_message_len` 最多超出实际报文 3 字节，`hmac_process` 产生 ≤3 字节越界读 | `tlse.c:13279-13284`、`tlse.c:13235` | 是否越过真实分配边界取决于宿主接收缓冲区大小（通常远大于报文），影响限于信息泄露/DoS |
| H-02 | STUN 报文触发未对齐 16/32 位加载，在严格对齐架构上产生未定义行为 | `tlse.c:13122-13123`、`tlse.c:13151-13152` | 依赖部署架构与编译器选项，x86 可容忍 |
| H-03 | `tls_stun_build` 公共 API 无输出缓冲区长度参数，外部调用方传小缓冲区可越界写 | `tlse.c:13374-13415` | 库内调用方使用 `msg[1024]` 因而安全；属 API 契约风险，非网络可达 |
| H-04 | 序列化会话状态无完整性/来源认证，跨信任域导入可接管或伪造会话 | `tlse.c:12635-12964` | 属设计权衡（文档说明用于同机 pre-forked worker 迁移）；仓库内无跨信任域调用点 |
| H-05 | 导入后未校验 `cipher`/`version`/`is_server`/`connection_status`/`dtls`，可造成状态不一致 | `tlse.c:12757-12964` | 未证实可导出到内存破坏或认证绕过 |
| H-06 | `iv_len` 静默截断、`key_lengths`/`mac_length` 与 cipher 未交叉校验 | `tlse.c:12798-12858` | 与 TLSE-2026-0004 同源，单独影响未证实 |
| H-07 | 导入路径对多字节字段使用未对齐指针强制转换 | `tlse.c:12781-12894` | 同上，依赖架构 |
| H-08 | `_private_asn1_parse` 中 `tls_certificate_set_key` 在 `length==0` 时读取 `val[0]` 造成 1 字节越界读 | `tlse.c:11546-11549`、`tlse.c:4581-4589` | 证书缓冲通常位于更大记录缓冲区中，未确认可越过分配边界 |
| H-09 | `asn1_parse` 忽略 `_private_asn1_parse` 返回值，提前中止时返回半初始化证书，下游可能空指针解引用 | `tlse.c:11766-11783` | 需确认具体下游字段是否在未校验情况下解引用，可能仅 DoS |
| H-10 | `X509_COPY_BYTES` 宏仅校验 `from_len < size`，未校验 `from_start + from_len <= size` | `tlse.c:11312` | 逐函数核对未构造出可触发输入；仅在 `TLS_FULL_X509` 下编译，保留为防御性假设 |
| H-11 | `srtp_decrypt` 中 `srtcp_index` 读取早于 `payload_len - tag_size - 4 < 0` 检查 | `tlse.c:14920`、`tlse.c:14925` | 该检查对无符号运算恒为假，需确认 `payload_len - tag_size < 4` 是否可构造（由第 3 波整数分析核实） |
| H-12 | `supported_versions` 扩展 `for (i = 1; i < limit; i += 2)` 在 `limit` 为奇数时可读 1 字节越界 | `tlse.c:8495-8514` | 需构造 `extension_len` 为偶数、`limit=extension_len-1` 为奇数的报文体；越界读幅度 1 字节且仍在记录缓冲内 |
| H-13 | `tls_parse_certificate` 指纹分支 `buf_len -= 2;` 疑为 `buf_len_ -= 2` 笔误 | `tlse.c:8741` | 经推演循环受 `buf_len_ <= 1/<= 2` 保护，最多写 95 字节于 100 字节缓冲，未越界；但语义错误降低可维护性 |
| H-14 | `tls_parse_certificate` 指纹分支 `sha256_process(&state, cert->bytes, cert->len)` 中 `cert->bytes` 可能为 NULL | `tlse.c:8721`、`tlse.c:8703-8712` | 当 `certificate_size2 == 0` 或分配失败时 `bytes/len` 为 0；库实现需确认 `sha256_process(NULL,0)` 行为 |
| H-15 | `tls_parse_payload` 中 `unsigned char local_buffer[0x40000 + 12]` 约 256 KB 栈数组 | `tlse.c:9802` | 属栈耗尽风险，取决于线程栈大小；未证实可利用 |
| H-16 | DTLS 分片重组 `TLS_REALLOC(fragment_buffer, data_length * sizeof(char *))` 以指针大小放大分配 | `tlse.c:12543` | 分配偏大（8×）但不导致越界；`data_length/fragment_offset/fragment_length` 校验自洽 |

## 4. 覆盖范围与限制

**已覆盖**

- Jev 初筛（`triage/jev-infra.json`，192 个单元）仅用于安排阅读顺序，不作为候选问题。
- 项目画像：`project_types` 为空，`native_memory.detected=true`，推荐技能为 `memory-safety-analyzer` 与 `ipc-serialization-analyzer`。
- 第 1/2 波（原生内存与反序列化）：STUN/WebRTC 栈缓冲区、TLS 记录层与握手解析、ASN.1/X.509 两条编译分支、`tls_export_context`/`tls_import_context` 二进制反序列化。
- 第 3 波（补证与换视角）：密码学与证书校验（签名算法策略、Finished、证书链、SNI/SAN）、整数下溢与 SRTP/RTCP 长度处理。

**限制**

- 全部结论为静态源码级判断，未构建、未运行目标代码，未做 ASan/UBSan/MSan/Valgrind 动态验证；`verification.status` 全部为 `unverified`。
- 仓库内没有生产部署上下文，可达性按「库的预期用法」推断并逐条标注前提：需要宿主把网络数据交给相应公共 API。
- `tls_import_context` 在仓库内仅有自导出后自导入的示例调用点（`examples/tlshelloworld.c:190-192`），无法证明攻击者可控导入缓冲区。
- `TLS_FULL_X509`、`TLS_REEXPORTABLE`、`TLS_SRTP` 等宏在仓库内均未定义，仅在 `TLSE_COMPILE_DEFINITIONS` 外部注入时启用；相关结论已标注 opt-in/requires-config。
- 未做 CVE 检索（环境限制为仅允许 Claude API 与 jev-triage 访问）。本报告未引用任何 CVE 编号。
- 未发现需要报告的硬编码私钥或令牌；仓库内 `root.pem`、`tls_root_ca.h` 仅含公开根证书（151/152 个 `BEGIN CERTIFICATE` 块，无私钥块）。
- 覆盖率：本报告不声称对全仓库的完整覆盖；有界预算内优先覆盖了网络可达的协议解析与内存操作路径。
