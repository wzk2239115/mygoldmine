# sol MQTT Broker 安全审计报告

- 项目标识：`benchmark-sol`（项目目录 `sol`）
- 显示名称：Sol — 简化版 MQTT 3.1.1 Broker（C / epoll）
- 源码版本：`373d84877d22031b45a7f3599297f691eab09230`（CHANGELOG/CMake `VERSION 0.18.5`）
- 审计方式：静态源码审计（容器内无 C 编译器与 OpenSSL 头文件，未做动态验证）
- 系统语言：简体中文

> 说明：本报告只给出漏洞定位、根因、最小复现思路与修复建议，不包含可直接武器化的利用代码。
> 所有条目的 `verification.status` 均为 `unverified`，即"静态审阅确认了代码路径，但未在运行环境中复现"。

---

## 1. 项目画像

| 项 | 值 |
|---|---|
| 语言 | C（C11），约 10.7k 行 |
| 类型 | 网络服务 / MQTT 3.1.1 Broker（`agent-harness` 之外的 `model-serving`/协议服务类） |
| 构建 | CMake + OpenSSL + pthread |
| 入口 | `src/sol.c:70 main()` → `server.c:start_server()` → epoll/poll/select 事件循环 |
| 核心攻击面 | TCP/UNIX socket 上的 MQTT 报文解析与命令分发 |
| 外部依赖 | OpenSSL（TLS）、`crypt(3)`（口令校验） |

关键模块：

- `src/server.c`：连接接收、报文分帧（`recv_packet`）、事件分发（`process_message`）
- `src/mqtt.c` + `src/pack.c`：MQTT 报文反序列化（攻击面最集中）
- `src/handlers.c`：CONNECT / PUBLISH / SUBSCRIBE / ACK 等命令处理
- `src/topic_store.c` / `src/trie.c` / `src/subscriber.c`：主题订阅与通配符匹配
- `src/config.c` / `src/network.c`：配置解析、TLS、认证

## 2. 信任边界与攻击面

1. **未认证网络输入 → 报文解析器**（最高风险）
   `server.c:470 recv_packet` 只校验 opcode 落在 1..14、剩余长度不超过 `max_request_size`，
   随后把整包交给 `mqtt_unpack`。解析器对"声明长度"与"实际剩余字节"之间没有任何一致性校验，
   并把多个 16 位长度字段直接用于 `memcpy`/分配/循环控制。
2. **连接状态机 → 命令处理**
   `handlers.c:877 handle_command` 直接用包类型索引函数表；ACK 类命令不检查客户端是否已完成 CONNECT。
3. **跨客户端共享状态**
   订阅表、通配符列表、会话表在多线程 + 互斥锁下被并发访问，存在离线客户端/陈旧指针路径。
4. **配置与认证**
   `allow_anonymous` 默认为 `true`（`config.c:369`），TLS 服务端 `SSL_VERIFY_NONE`（`network.c:373`），
   口令文件解析缺少边界检查。

## 3. 候选问题

> 严重度依据：可达性（是否无需认证、单包/少包即可触发）+ 影响（内存破坏 > 进程终止 > 信息泄露 > 配置弱点）。

| ID | 严重度 | 标题 | 位置 |
|---|---|---|---|
| SOL-001 | Critical | CONNECT 报文 client_id 长度未校验导致栈缓冲区溢出 | `src/mqtt.c:239-243` |
| SOL-002 | High | PUBLISH 剩余长度整数下溢导致进程 `exit()` 终止 | `src/mqtt.c:314-316` |
| SOL-003 | High | SUBSCRIBE/UNSUBSCRIBE 长度下溢导致无限循环、越界读与内存耗尽 | `src/mqtt.c:342-358`、`386-401` |
| SOL-004 | High | 报文类型 2/9 命中空函数指针、类型 11 越界读取派发表 | `src/mqtt.c:72-82`、`431-434` |
| SOL-005 | High | 未 CONNECT 时发送 ACK 报文导致空 `session` 解引用 | `src/handlers.c:793-796` 等 |
| SOL-006 | Medium | QoS0 发布给已离线的持久会话客户端时使用已关闭的 fd / 陈旧客户端结构 | `src/handlers.c:225-230` |
| SOL-007 | Medium | `match_subscription` 对 `index()` 返回值未判空导致空指针解引用 | `src/handlers.c:292-294` |
| SOL-008 | Medium | SUBSCRIBE topic 长度为 0 时出现负下标栈越界读写 | `src/handlers.c:557-569` |
| SOL-009 | High | `mqtt_decode_length` 无界读取续传位，可在堆缓冲区尾部之外读取 | `src/mqtt.c:136-153` |
| SOL-010 | Medium | 内存上限未强制、写缓冲无容量检查、保留消息泄漏 | `src/handlers.c:747`、`356-375` |
| SOL-011 | Medium | TLS 服务端不校验客户端证书 + 默认匿名访问 | `src/network.c:373`、`src/config.c:369` |
| SOL-012 | Low | 口令文件解析对畸形行越界读写 | `src/config.c:445-470` |
| SOL-013 | Low | PUBLISH topic 长度为 0 时读取 `topic[-1]` | `src/handlers.c:703` |
| SOL-014 | Low | `check_passwd` 未处理 `crypt()` 返回 NULL | `src/util.c:142-145` |
| SOL-015 | Medium | 全局锁与客户端锁加锁顺序相反，可造成死锁 | `src/handlers.c:152`、`209`、`580-581` |

### SOL-001（Critical）CONNECT client_id 栈缓冲区溢出

- **位置**：`src/mqtt.c:220-260`（`unpack_mqtt_connect`），关键行 `239-243`；
  目标缓冲区 `struct mqtt_connect.payload.client_id` 为 `u8[64]`（`src/mqtt.h:181`，`MQTT_CLIENT_ID_LEN=64` 见 `src/mqtt.h:40`）。
- **根因**：`cid_len` 来自报文字节 10–11（16 位、完全由客户端控制），代码只判断 `cid_len > 0`，
  没有与 `MQTT_CLIENT_ID_LEN` 或实际剩余长度 `len` 比较，直接
  `memcpy(pkt->connect.payload.client_id, buf, cid_len)` 并写 `client_id[cid_len] = '\0'`。
- **可达性**：`process_message` 中 `struct io_event io = {.client = c};`（`src/server.c:860`），
  `io.data` 是**栈上**的 `struct mqtt_packet`，因此这是一次可远程触发、无需认证的**栈溢出**。
  `cid_len` 最大 65535，可覆写 `client_id` 之后的 `username/password/will_*` 指针以及 `io` 之外的栈内容
  （含保存的返回地址），溢出内容即攻击者报文中的字节。
- **影响**：内存破坏 → 远程代码执行（可靠性取决于目标编译选项与栈布局）；最低限度是稳定的进程崩溃。
- **最小复现思路**：建立 TCP 连接后发送一个 CONNECT 报文，固定头 `0x10` + 合法的剩余长度（≥ 12+N），
  变长头按 `[len=0x0004]["MQTT"][level][flags][keepalive][client_id_len]` 排列，
  把 `client_id_len` 设为 `0xFFFF`，随后填充 ≥65535 字节的报文体；解析器会把整段报文体复制进 64 字节字段。
- **修复建议**：解析前校验 `len >= SKIP_PROTOCOL_NAME + 5`；把 `cid_len` 与 `MQTT_CLIENT_ID_LEN` 取最小/直接拒绝
  `cid_len > MQTT_CLIENT_ID_LEN-1`；同时按剩余长度逐字段递减并校验，任何字段超出剩余长度立即返回错误。

### SOL-002（High）PUBLISH 长度下溢导致进程退出

- **位置**：`src/mqtt.c:296-322`，关键行 `314-316`；分配器 `src/pack.c:411-418` 与 `src/memory.c:46-56`。
- **根因**：`len` 为 `usize`（无符号）。`len -= (sizeof(u16) + pkt->publish.topiclen);` 在
  `topiclen > len - 2` 时回绕成接近 `SIZE_MAX` 的值，随后
  `unpack_bytes(&buf, len)` → `try_alloc(len + 1)` → `malloc` 失败 → `exit(EXIT_FAILURE)`。
  同时 `pkt->publish.payloadlen = len` 还被截断为 32 位，后续使用该长度的地方会出现不一致。
- **影响**：单个未认证报文即可让 broker 进程直接退出（拒绝服务）；若 `len+1` 恰好回绕为 0，
  则 `memcpy(dest, buf, SIZE_MAX)` 会变成大规模越界写，存在进一步内存破坏风险。
- **最小复现思路**：发送 `0x30`（PUBLISH QoS0）+ 剩余长度 `0x05`，报文体前两字节为 `0xFF 0xFF`
  （topic 长度 65535），后接 3 字节任意数据；`5 - 2 - 65535` 回绕。
- **修复建议**：所有长度减法前先判 `topiclen <= len - 2`；使用 `size_t` 明确语义并在下溢时返回
  `-MQTT_ERR`；`try_alloc` 不应以 `exit()` 处理来自网络的大小。

### SOL-003（High）SUBSCRIBE/UNSUBSCRIBE 长度下溢 → 无限循环

- **位置**：`src/mqtt.c:324-367`（SUBSCRIBE）、`369-410`（UNSUBSCRIBE）。
- **根因**：`for (; len > 0; ++i) { len -= sizeof(u16); ... len -= topic_len; len -= sizeof(u8); }`，
  `len` 为 `usize`。当剩余长度为奇数或 `topic_len` 大于剩余字节数时立即回绕为极大值，
  循环条件永远成立。循环内 `unpack_string16` 持续从 `buf` 越界读取并做最多 64KB 的分配，
  `try_realloc(subscribe.tuples, (i+1)*...)` 持续增长。
- **影响**：CPU 空转 + 内存无界增长（`max_memory` 未强制，见 SOL-010）→ 最终 `try_alloc` 触发 `exit()` 或越界读崩溃；
  未认证即可触发。
- **最小复现思路**：发送 `0x82` + 剩余长度 `0x05`，报文体 = `pkt_id(2B)` + `0xFF 0xFF` + `qos(1B)`。
- **修复建议**：循环入口校验 `len >= 2 + 2 + 1`；每次读取后显式检查
  `topic_len <= len - 2` 与 `len >= sizeof(u8)`；限制 `tuples_len` 上限（例如 1024）。

### SOL-004（High）报文类型派发未覆盖全部类型

- **位置**：`src/mqtt.c:72-82`（`unpack_handlers[11]`，索引 0/2/9 为 `NULL`）、`src/mqtt.c:422-437`；
  `src/handlers.c:59-75`（`handlers[15]`，索引 9/11/13 为 `NULL`）、`877-880`。
- **根因**：`mqtt_unpack` 仅对 `type >= PINGREQ(12) && type <= DISCONNECT(14)` 提前返回，
  其余类型直接调用 `unpack_handlers[type]`。而 `server.c:512` 的校验允许 opcode 1..14，
  因此客户端可发送 2（CONNACK）或 9（SUBACK）命中 `NULL` 函数指针；
  发送 11（UNSUBACK）时 `opcode > UNSUBSCRIBE` 会走 `server.c:519-523` 的提前返回路径，
  随后 `unpack_handlers[11]` **越过数组上界**读取一个函数指针并调用。
  即便越界读侥幸返回有效地址，`handle_command(11)` 也会命中 `handlers[11] == NULL`。
- **影响**：未认证远程拒绝服务；越界函数指针调用在不同编译/布局下可能造成控制流劫持。
- **最小复现思路**：连接后发送 `0x20 0x00` + 2 个填充字节（CONNACK 方向非法的报文），
  或发送 `0x90 ...`（SUBACK）。`server.c:512` 的类型检查不会拦截这两个值。
- **修复建议**：把派发表大小与类型枚举对齐（15 项），对所有 `NULL` 槽位显式返回协议错误；
  `mqtt_unpack` 中增加 `type < ARRAY_SIZE(unpack_handlers)` 边界判断；
  按 MQTT 规范只接受服务端方向上合法的包类型。

### SOL-005（High）未 CONNECT 的 ACK 报文触发空 session 解引用

- **位置**：`src/handlers.c:785-800`（PUBACK）、`803-820`（PUBREC）、`839-855`（PUBCOMP）。
- **根因**：`client_init`（`src/server.c:381-404`）把 `client->session` 置为 `NULL`，
  而 ACK 处理函数直接访问 `c->session->i_msgs[pkt_id]` / `c->session->i_acks[pkt_id]`，
  没有任何"必须先完成 CONNECT"的状态检查。
- **影响**：单个 `0x40 0x02 0x00 0x01` 报文即可造成空指针写，进程崩溃（未认证 DoS）。
- **最小复现思路**：TCP 连接建立后，第一件事就发送 PUBACK（`0x40`，剩余长度 2，包标识 1），
  不发送 CONNECT。
- **修复建议**：在 `process_message`/`handle_command` 入口统一校验
  `c->connected == true`（PINGREQ/DISCONNECT 除外），否则按协议错误断开。

### SOL-006（Medium）QoS0 发布使用已关闭 fd 的离线客户端

- **位置**：`src/handlers.c:160-232`，关键行为在 `225-230`。
- **根因**：`publish_message` 中对 `pkt->header.bits.qos > AT_MOST_ONCE` 的分支检查了
  `!sc || sc->online == false` 并转为离线队列；但 QoS0 分支没有该检查，
  直接 `pthread_mutex_lock(&sc->mutex)`、写入 `sc->wbuf` 并 `enqueue_event_write(sc)`。
  `client_deactivate`（`server.c:412-453`）在 `clean_session == false` 时不会把客户端从
  `server.clients_map` 移除，而 `close_connection` 已经关闭了 fd。
- **影响**：向已关闭（且可能已被复用）的 fd 注册写事件；若 fd 被新连接复用，
  数据会被写到其它客户端的连接上，造成跨连接信息泄露/串话。
- **修复建议**：QoS0 分支同样跳过 `!sc || sc->online == false`；
  `client_deactivate` 无条件 `HASH_DEL(server.clients_map, client)`；
  在 `enqueue_event_write` 前校验 `client->online`。

### SOL-007（Medium）match_subscription 空指针解引用

- **位置**：`src/handlers.c:261-303`，关键行 `292-294`。
- **根因**：`ptopic = index(ptopic, '/')` 在剩余串中没有 `/` 时返回 `NULL`，
  下一行 `if (ptopic[0] == '/')` 没有判空就解引用。
  构造：订阅 `a/+/+`，再向 `a/b` 发布（发布路径会给主题补尾部 `/`）。
  第一轮后 `ptopic` 指向末尾 `/`，第二轮 `index(..., '/')` 返回 `NULL`，
  随后 `ptopic[0]` 解引用空指针。另 `ptopic[j]`（`handlers.c:279`）在 `j` 超过主题长度时会越界读。
- **影响**：持有订阅关系的客户端可触发 broker 崩溃（拒绝服务）。
- **修复建议**：在 `index()` 之后立即判空；`ptopic[j]` 改为在 `j < strlen(ptopic)` 范围内比较；
  用显式的逐级 token 比较替代指针跳跃。

### SOL-008（Medium）SUBSCRIBE topic 长度为 0 的负下标

- **位置**：`src/handlers.c:545`（`unsigned char rcs[s->tuples_len]`）、`557-569`。
- **根因**：`char topic[s->tuples[i].topic_len + 2]` 后立即访问
  `topic[s->tuples[i].topic_len - 1]` 与 `topic[.. - 2]`；当 `topic_len == 0` 时下标为
  `(u16)-1` 提升后的巨大值/负偏移，读写落在 VLA 之前的栈内存。
- **影响**：栈越界读；若相邻字节恰好为 `'#'`、`'/'`，还会执行 `topic[-1] = '\0'` 的单字节越界写。
- **修复建议**：`topic_len == 0` 时直接以协议错误拒绝；统一用有符号/边界显式判断代替 `len - 1`。

### SOL-009（High）mqtt_decode_length 无界读取与长度截断

- **位置**：`src/mqtt.c:136-153`；调用点 `src/server.c:545`，校验 `src/server.c:551`。
- **根因**：解码循环 `do { c = *buf++; ... } while (c & 128);` 没有 4 字节上限
  （源码 TODO 亦承认），而 `recv_packet` 只保证前 4 字节属于当前报文。
  `rbuf` 在报文处理后被重复使用且不清零（`server.c:867` 只重置 `rpos/read/toread`），
  因此攻击者可以先用一个报文体把 `rbuf[4..]` 填满 `0xFF`，再发送一个新报文让前 3 个长度字节也带续传位，
  解码器就会沿 `rbuf` 一直读到分配区之外（默认 `max_request_size = 512KB`）。
  另外返回值 `usize` 被赋给 `unsigned int pktlen`，存在 32 位截断。
- **影响**：未认证远程堆越界读，读到未映射页时进程崩溃（DoS）；截断使"声明长度"与实际解析位置可能不一致。
- **最小复现思路**：先发送一个报文体为全 `0xFF` 的合法大包，再发送 `0xFF 0xFF 0xFF ...` 开头的新报文，
  观察解码器读取越界（ASAN 下为 heap-buffer-overflow）。
- **修复建议**：最多读取 4 字节，超过即视为协议错误；校验第 5 字节的续传位；
  使用 `size_t` 接收返回值并在与 `max_request_size` 比较后再收窄类型。

### SOL-010（Medium）内存与写缓冲缺乏上限

- **位置**：`src/handlers.c:747`（保留消息覆盖）、`src/handlers.c:356-375`（`set_connack` 续传队列直接追加到 `wbuf`）、
  `src/handlers.c:230`（发布时 `wbuf + towrite` 无容量检查）、`src/config.c:228-229`/`424`。
- **根因**：
  1. `max_memory` 只被解析和打印，`memory_used()` 仅用于统计（`server.c:236`），从不参与准入控制；
  2. 每次设置 retained 消息直接覆盖 `t->retained_msg` 而不释放旧值 → 内存泄漏；
  3. 写路径普遍假设 `towrite + len <= max_request_size`（源码 `// TODO check for write buffer size exceed` 已标注）。
- **影响**：慢速/不读数据的订阅者或大量保留消息可把内存推到 OOM；由于 `try_alloc` 在失败时 `exit()`，
  最终表现为进程终止（DoS）。
- **修复建议**：在 `mqtt_pack` 之前统一校验剩余缓冲；对 `towrite + len > max_request_size` 的客户端断开或阻塞；
  retained 消息更新时先 `free_memory` 旧值；把 `max_memory` 接入 `try_alloc` 的准入判断。

### SOL-011（Medium）TLS 不校验客户端证书 + 默认匿名

- **位置**：`src/network.c:373` `SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, client_certificate_verify);`；
  `src/config.c:369` `config.allow_anonymous = true;`。
- **根因**：服务端显式关闭客户端证书校验（`client_certificate_verify` 永远不会被调用），
  同时默认允许匿名连接；示例配置 `conf/sol.conf` 也未开启 `allow_anonymous false`。
- **影响**：任何能连到端口的客户端都可以订阅/发布任意主题；若部署时监听非回环地址，等于开放中继与数据面暴露。
- **修复建议**：需要双向认证时使用 `SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT`；
  默认 `allow_anonymous = false`，并在文档中明确生产部署必须配置口令/TLS。

### SOL-012（Low）口令文件解析越界

- **位置**：`src/config.c:443-471`。
- **根因**：`while (*puname != ':') username[i++] = *puname++;` 与
  `while (*puname != '\n') password[i++] = *puname++;` 都没有长度上限，也不判断字符串结束符；
  畸形行（无 `:` 或最后一行无换行）会继续读过 `line[0xFFF]` 并写入 `username[0xFF]`/`password[0xFFF]` 之外。
- **影响**：配置文件被破坏或被低权限用户篡改时，启动阶段栈溢出。
- **修复建议**：用 `strchr`/`strtok_r` 找到分隔符并校验长度；两个循环都加上 `i < sizeof(buf)-1`。

### SOL-013（Low）PUBLISH topic 长度为 0 的越界读

- **位置**：`src/handlers.c:696-706`。
- **根因**：`p->topic[p->topiclen - 1]` 在 `topiclen == 0` 时读取 `topic[-1]`，
  即 `try_alloc` 写在数据之前的 `size_t` 长度头。
- **影响**：堆越界读一个字节；结合 `snprintf` 的分支选择，可能影响后续主题规范化结果。
- **修复建议**：`topiclen == 0` 直接拒绝。

### SOL-014（Low）check_passwd 未处理 crypt 返回 NULL

- **位置**：`src/util.c:142-145`。
- **根因**：`STREQ(crypt(passwd, salt), salt, strlen(salt))`；`crypt()` 在 salt 非法或底层失败时返回 `NULL`，
  宏内部随即对 `NULL` 做字符串比较。
- **影响**：配置了非法 hash 时认证路径崩溃。输入来自本地口令文件，攻击面有限。
- **修复建议**：先判 `char *h = crypt(...); if (!h) return false;`，并使用常量时间比较。

### SOL-015（Medium）锁顺序反转导致死锁

- **位置**：`src/handlers.c:151-152`、`209`、`225`（`publish_message`）与 `580-581`、`654-655`
  （`subscribe_handler` / `unsubscribe_handler`）；线程数配置 `src/server.h:39`（`THREADSNR 2`）。
- **根因**：`publish_message` 先取全局 `mutex` 再取目标客户端 `sc->mutex`；
  订阅/退订路径先取 `c->mutex` 再取全局 `mutex`。两者顺序相反，构成 ABBA 死锁。
- **影响**：并发订阅 + 发布即可让两个 worker 线程永久互相等待，broker 停止处理请求（拒绝服务）。
- **最小复现思路**：客户端 A 订阅主题 T 并保持连接；客户端 B 高频向 T 发布；同时 A 高频发送
  SUBSCRIBE/UNSUBSCRIBE。多线程构建下可观察到线程挂起、服务无响应。
- **修复建议**：统一全模块加锁顺序（例如一律"全局锁 → 客户端锁"），
  或对订阅表与客户端状态使用不同的锁粒度并在文档中固定锁层级。

## 4. 验证结论

| ID | 状态 | 说明 |
|---|---|---|
| SOL-001 | unverified | 静态确认 `cid_len` 无上界并写入 64 字节字段；容器内无编译器，未运行 ASAN 复现 |
| SOL-002 | unverified | 静态确认无符号下溢路径与 `exit()` 逻辑 |
| SOL-003 | unverified | 静态确认循环条件在回绕后恒真 |
| SOL-004 | unverified | 静态确认派发表槽位与类型校验范围 |
| SOL-005 | unverified | 静态确认 `session` 初值为 `NULL` 且无状态检查 |
| SOL-006 | unverified | 依赖 fd 复用时序，静态确认调用路径 |
| SOL-007 | unverified | 静态构造出 `index()` 返回 `NULL` 的分支 |
| SOL-008 | unverified | 静态确认负下标表达式 |
| SOL-009 | unverified | 静态确认解码循环无上限；需要两包序列，未动态复现 |
| SOL-010 | unverified | 静态确认配置项未被使用 |
| SOL-011 | unverified | 静态确认默认值与 `SSL_VERIFY_NONE` |
| SOL-012 | unverified | 静态确认循环无边界 |
| SOL-013 | unverified | 静态确认表达式 |
| SOL-014 | unverified | 静态确认缺少 NULL 检查 |
| SOL-015 | unverified | 静态确认两处加锁顺序相反且 `THREADSNR=2` |

**未验证原因**：审计容器内不存在 `gcc/cc/clang/make/cmake` 与 OpenSSL 头文件（`/usr/include/openssl/ssl.h` 缺失），
无法构建目标，也没有可用的隔离运行环境，因此所有结论停留在静态审阅级别。

## 5. 修复优先级建议

1. **立即**：SOL-001（栈溢出）、SOL-002/SOL-003（解析器长度下溢）、SOL-004（派发表），
   都在"未认证 + 单包"可达路径上，建议在 `mqtt_unpack` 之前加入统一的"字段长度 vs 剩余长度"校验层。
2. **短期**：SOL-005、SOL-009、SOL-007、SOL-008 —— 补齐状态机前置条件与所有边界判断。
3. **中期**：SOL-006、SOL-010、SOL-011 —— 连接生命周期、内存/缓冲上限、默认安全配置。
4. **长期**：SOL-012/013/014 —— 本地输入健壮性。

通用建议：把解析器的所有 `memcpy`/`try_alloc`/循环控制改为基于"已校验的剩余字节数"的显式游标 API，
禁止裸用报文声明长度；为 `mqtt.c`／`handlers.c` 引入 fuzz 目标（libFuzzer + ASAN）。

## 6. 覆盖与限制

- 已阅读：`src/mqtt.c`、`src/pack.c`、`src/mqtt.h`、`src/server.c`（关键路径）、`src/handlers.c`（全部）、
  `src/memory.c`、`src/memorypool.c`、`src/topic.c`、`src/topic_store.c`、`src/subscriber.c`、
  `src/util.c`、`src/config.c`（关键段）、`src/network.c`（TLS/连接段）、`src/sol.c`、构建与配置文件。
- 未深入：`src/ev.c`（事件循环后端）、`src/trie.c` 的插入/删除路径、`src/bst.c`、`src/list.c`、
  `src/iterator.c`、`src/logging.c`、`src/uthash.h`（第三方）。
  其中 `trie.c:292-320` 的 `try_realloc` 局部指针更新与 `children_prefix_find` 共用旧指针
  存在理论上的 use-after-free 风险，但需要在深层前缀遍历中触发，本次未完成验证，不列为候选。
- 工具：`triage/jev-infra.json` 存在（71 个单元），已按 `priority >= 0.6` 优先阅读
  （`src/sol.c`、`src/config.c`、`src/network.c`、`src/server.c`、`src/handlers.c`）。
  Jev 仅用于安排阅读顺序，未作为任何候选问题的依据。
- 本次未执行动态验证、未构建环境、未获取 CVE 编号；报告中不包含任何 CVE 断言。
- 未发现仓库内硬编码的密钥或凭据；`conf/sol.conf` 引用的证书路径在仓库中不存在（`certs/` 未提交），
  不影响上述结论。
