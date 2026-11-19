# Security Review: sol

## Scope

The scan was configured for the include paths and exclusions listed below.

- Scan mode: repository
- Target kind: git\_worktree
- Target ID: target\_sha256\_2918393a005d2f1a51ed200775af03f62779b65cbc9127937ee6747fbf8737a1
- Revision: 373d84877d22031b45a7f3599297f691eab09230
- Snapshot digest: codex-security-snapshot/v1:sha256:90a9aaf0853034ca9c071ef712b2764bb7029ccab11863cb27f966f728f30f92
- Included paths: .
- Excluded paths: none

Limitations and exclusions:
- Excluded passwd.py: Excluded from review
- Excluded conf/sol.conf: Excluded from review
- Excluded tests/\*\*: Excluded from review

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 8 |
| Severity mix | critical: 2, high: 5, medium: 1 |
| Confidence mix | high: 8 |
| Validation mode | not recorded |

Canonical artifacts: `scan-manifest.json` and `findings.json`. This report is a deterministic projection of those files.

## Threat Model

# Sol MQTT broker threat model

## Scope
Entire repository at `373d84877d22031b45a7f3599297f691eab09230`. Product is a C MQTT 3.1.1 broker with a TCP listener (default 127.0.0.1:1883), optional TLS, and a single shared process serving all clients. The default configuration permits anonymous clients (`allow_anonymous = true`) and allocates a fixed per-client read/write buffer of `max_request_size` (512KB default; 50MB in `conf/sol.conf`).

## Assets
Broker process integrity and availability; authenticated session state; queued and retained MQTT messages; topic subscriptions; authentication records; internal `$SOL` statistics; host memory and file descriptors.

## Attacker capabilities
An unauthenticated network client can open one or more TCP connections and send arbitrary MQTT bytes, including malformed remaining lengths, packet types, variable-length fields, duplicate client IDs, and oversized publishes. A lower-trust authenticated client can additionally use any valid username/password when anonymous access is disabled. Clients can be slow readers and can disconnect/reconnect with chosen client IDs and clean-session flags.

## Trust boundaries and controls
1. Network bytes -> `recv_packet` framing -> `mqtt_unpack` field decoding. The decoder must validate every attacker-supplied length against the received packet and destination capacity.
2. Decoded packet -> `handle_command` dispatch. Only packet types with implemented handlers should be dispatched, and a CONNECT handshake should precede session-dependent operations.
3. Handler -> per-client write buffer and subscriber fan-out. Writes must be bounded by `max_request_size`; offline/queue replay must not exceed the destination buffer.
4. Client-selected client ID -> session lookup and `clients_map`. A session must not be silently shared with a different connection unless the protocol's takeover semantics are applied.
5. Packet ownership -> destructor. Each decoded packet must be destroyed exactly once.

## Security objectives
Reject malformed or unsupported MQTT input without memory corruption or process termination; keep each client's sessions and queued messages isolated; preserve broker availability; do not expose or corrupt data across clients.

## Assumptions and uncertainty
The broker is deployed as a shared service reachable by untrusted MQTT clients. Authentication, if enabled, is username/password only; there is no topic ACL in this source. Whether a particular deployment exposes the listener to the internet is deployment-dependent, but the default network parser is reachable by any client that can reach the configured port. Runtime exploitation was not performed because the scan environment lacks a C compiler; validation is source-backed.

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [Unbounded writes into the fixed per-client write buffer corrupt the heap](#finding-1) | critical | high | inline below |
| [Pre-authenticated CONNECT client ID overflows a 64-byte field on the stack](#finding-2) | critical | high | inline below |
| [Packet handlers run before CONNECT, bypassing authentication and dereferencing a NULL session](#finding-3) | high | high | inline below |
| [UNSUBSCRIBE packet is destroyed twice, causing a heap double free](#finding-4) | high | high | inline below |
| [Packet type dispatch tables contain NULL and out-of-bounds entries](#finding-5) | high | high | inline below |
| [Duplicate client IDs share a session and free it while another connection still uses it](#finding-6) | high | high | inline below |
| [Unsigned remaining-length arithmetic underflows in the MQTT decoder](#finding-7) | high | high | inline below |
| [Inflight ACK retransmission packs through a NULL packet pointer](#finding-8) | medium | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] Unbounded writes into the fixed per-client write buffer corrupt the heap

| Field | Value |
| --- | --- |
| Severity | critical |
| Confidence | high |
| Confidence rationale | The allocation is exact at server.c:397-399. Appends at handlers.c:227-228 and 615-618 and 632-634, handlers.c:331-338, handlers.c:668-669 and server.c:338-339 add packet sizes to towrite with no remaining-space check. towrite is reset only after a complete send at server.c:652, so multiple queued outputs accumulate. |
| Category | memory-corruption |
| CWE | CWE-787, CWE-122 |
| Affected lines | src/server.c:397-399, src/handlers.c:615-618, src/handlers.c:224-228, src/handlers.c:629-634 |

#### Summary

client-\>wbuf is allocated with exactly max\_request\_size bytes, but SUBACK/UNSUBACK generation, retained-message replay, session resume replay and publish fan-out all append to wbuf + towrite without checking the remaining capacity. A retained PUBLISH close to max\_request\_size followed by a SUBSCRIBE (or two publishes delivered before the event loop flushes) writes past the allocation, corrupting heap metadata and adjacent objects.

#### Root Cause

Every response path treats the per-client write buffer as unbounded even though it is allocated with exactly max\_request\_size bytes.

**Write buffer is exactly max\_request\_size** — `src/server.c:392-399`

rbuf and wbuf are both try\_calloc(conf-\>max\_request\_size, 1). No spare capacity or growth is reserved for responses.

```c
    if (!client->rbuf)
        client->rbuf =
            try_calloc(conf->max_request_size, sizeof(unsigned char));
    client->wrote   = ATOMIC_VAR_INIT(0);
    client->towrite = ATOMIC_VAR_INIT(0);
    if (!client->wbuf)
        client->wbuf =
            try_calloc(conf->max_request_size, sizeof(unsigned char));
```

**Publish fan-out appends a whole packet to towrite** — `src/handlers.c:224-231`

mqtt\_pack writes the entire publish at wbuf + towrite, then towrite advances by len. Nothing checks towrite + len against max\_request\_size.

```c
#if THREADSNR > 0
        pthread_mutex_lock(&sc->mutex);
#endif
        mqtt_pack(pkt, sc->wbuf + sc->towrite);
        sc->towrite += len;
#if THREADSNR > 0
        pthread_mutex_unlock(&sc->mutex);
#endif
```

**Retained-message replay memcpy has no capacity check** — `src/handlers.c:613-619`

Each retained message matching a SUBSCRIBE is memcpy'd at wbuf + towrite and towrite grows by the retained size.

```c
        // Retained message? Publish it
        // TODO move after SUBACK response
        if (t->retained_msg) {
            size_t len = alloc_size(t->retained_msg);
            memcpy(c->wbuf + c->towrite, t->retained_msg, len);
            c->towrite += len;
        }
```

**SUBACK is appended after retained replay** — `src/handlers.c:626-634`

The SUBACK is packed at the current towrite after all retained messages, so even a retained message that fills wbuf overflows by the SUBACK length.

```c
    struct mqtt_packet pkt = {.header = (union mqtt_header){.byte = SUBACK_B}};
    mqtt_suback(&pkt, s->pkt_id, rcs, s->tuples_len);

#if THREADSNR > 0
    pthread_mutex_lock(&c->mutex);
#endif
    size_t len = mqtt_size(&pkt, NULL);
    mqtt_pack(&pkt, c->wbuf + c->towrite);
    c->towrite += len;
```

**towrite is only reset after a complete send** — `src/server.c:642-652`

towrite accumulates across queued replies and is reset only when the whole buffer has been sent, so consecutive outputs do not start from zero.

```c
    ssize_t wrote =
        send_data(&c->conn, c->wbuf + c->wrote, c->towrite - c->wrote);
    if (errno != EAGAIN && errno != EWOULDBLOCK && wrote < 0)
        goto clientdc;
    c->wrote += wrote > 0 ? wrote : 0;
    if (c->wrote < c->towrite && errno == EAGAIN)
        goto eagain;
    // Update information stats
    info.bytes_sent += c->towrite;
    // Reset client written bytes track fields
    c->towrite = c->wrote = 0;
```

#### Validation

The fixed allocation and each unchecked append were traced. A retained PUBLISH of nearly max\_request\_size followed by a SUBSCRIBE reaches the retained replay memcpy and then appends a SUBACK past the end of wbuf.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

PUBLISH with RETAIN -\> retained\_msg copy -\> SUBSCRIBE -\> memcpy(wbuf + towrite) and SUBACK append

- **Source:** attacker-supplied PUBLISH payload and topic

- **Sink:** memcpy/mqtt\_pack into client-\>wbuf at towerite

- **Outcome:** Heap overflow beyond a max\_request\_size allocation

#### Reachability

Two unauthenticated connections suffice: one publishes a large retained message, another subscribes to the topic.

- **Attacker:** unauthenticated network client

- **Entry point:** PUBLISH handler and SUBSCRIBE handler

Preconditions:
- anonymous access enabled (default) or any authenticated session
- retained flag set on the large publish

#### Severity

**Critical** — The scan assigned critical severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** critical
- **Rationale:** Heap corruption with attacker-influenced bytes can lead to code execution or broker crash.

Likelihood assessment:
- **Level:** high
- **Rationale:** The sequence is simple and the default max\_request\_size leaves no headroom for the follow-up SUBACK.

#### Remediation

Track the remaining capacity for wbuf and fail or disconnect when a reply would exceed it; grow the buffer dynamically for queued messages. Validate retained and fan-out message sizes against the destination's free space before packing.

Tests:
- Publish a retained message of size max\_request\_size - small, then subscribe from another connection under ASan; assert no overflow and either delivery or a clean rejection.
- Queue two near-maximum publishes for one subscriber before its socket drains; assert the write path bounds the buffer.
- Add a unit test that asserts every append checks towrite + len \<= max\_request\_size.

Preventive controls:
- Centralize all writes to wbuf in a helper that returns an error when the destination is full.
- Size reply buffers from the actual packet being built and enforce a per-client output quota.

<a id="finding-2"></a>

### [2] Pre-authenticated CONNECT client ID overflows a 64-byte field on the stack

| Field | Value |
| --- | --- |
| Severity | critical |
| Confidence | high |
| Confidence rationale | The unchecked memcpy and the trailing NUL write are visible at mqtt.c:240-241; the destination is a 64-byte array in mqtt.h, and io\_event is a stack local in process\_message at server.c:860. Packet size is bounded only by max\_request\_size, so a multi-kilobyte client ID is accepted. |
| Category | memory-corruption |
| CWE | CWE-121, CWE-787 |
| Affected lines | src/mqtt.c:235-243, src/mqtt.h:40, src/server.c:858-867 |

#### Summary

unpack\_mqtt\_connect reads an attacker-controlled 16-bit client ID length and copies that many bytes into connect.payload.client\_id, a 64-byte array, then writes a NUL at client\_id\[cid\_len\]. The decoded packet lives in the stack-local io\_event of process\_message, so a CONNECT whose client ID exceeds 63 bytes overwrites the process\_message stack frame with attacker bytes before any authentication.

#### Root Cause

The decoder trusts the packet-supplied client ID length and copies it into a fixed 64-byte array on the stack.

**Unbounded client ID copy into 64-byte field** — `src/mqtt.c:235-243`

cid\_len comes directly from the packet (u16). memcpy copies cid\_len bytes into the 64-byte client\_id and index write client\_id\[cid\_len\] adds a NUL past the array when cid\_len \>= 64.

```c
    buf += unpack(buf, "BHH", &pkt->connect.byte,
                  &pkt->connect.payload.keepalive, &cid_len);

    /* Read the client id */
    if (cid_len > 0) {
        memcpy(pkt->connect.payload.client_id, buf, cid_len);
        pkt->connect.payload.client_id[cid_len] = '\0';
        buf += cid_len;
    }
```

**Client ID field is 64 bytes** — `src/mqtt.h:40`

MQTT\_CLIENT\_ID\_LEN is 64. Any client ID longer than 63 bytes overflows the destination.

```c
#define MQTT_CLIENT_ID_LEN                 64 // including nul char
```

**Decoded packet is a stack local of process\_message** — `src/server.c:858-867`

io\_event io is allocated on the process\_message stack. The connect union member and its client\_id array are therefore on the stack, immediately before the saved frame state.

```c
static void process_message(struct ev_ctx *ctx, struct client *c)
{
    struct io_event io = {.client = c};
    /*
     * Unpack received bytes into a mqtt_packet structure and execute the
     * correct handler based on the type of the operation.
     */
    mqtt_unpack(c->rbuf + c->rpos, &io.data, *c->rbuf, c->read - c->rpos);
    c->toread = c->read = c->rpos = 0;
    c->rc = handle_command(io.data.header.bits.type, &io);
```

#### Validation

Source tracing shows a single unauthenticated CONNECT packet controls the copy length and the destination is the stack-resident io\_event. No parser, size, or authentication check constrains cid\_len before the copy.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

CONNECT body bytes -\> cid\_len -\> memcpy into stack-local client\_id\[64\]

- **Source:** MQTT CONNECT packet client ID length and bytes

- **Sink:** memcpy(pkt-\>connect.payload.client\_id, buf, cid\_len) and client\_id\[cid\_len\] = 0

- **Outcome:** Stack memory overwrite with attacker-controlled bytes in process\_message

#### Reachability

Any unauthenticated TCP client that can reach the MQTT listener sends one CONNECT packet.

- **Attacker:** unauthenticated network client

- **Entry point:** TCP listener -\> recv\_packet -\> process\_message

Preconditions:
- network reachability to the broker port

#### Severity

**Critical** — The scan assigned critical severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** critical
- **Rationale:** Attacker-controlled overwrite of a live stack frame can redirect control flow, leading to broker code execution or a crash.

Likelihood assessment:
- **Level:** high
- **Rationale:** The overflow is a single packet with no protocol or authentication prerequisite.

#### Remediation

Reject CONNECT when cid\_len \>= MQTT\_CLIENT\_ID\_LEN or when cid\_len exceeds the remaining packet body, and copy with a bounded length. Prefer allocating client IDs dynamically or enforcing the MQTT 3.1.1 23-byte minimum limit.

Tests:
- Send a CONNECT with a 64-byte client ID; assert it is rejected without corruption.
- Send a CONNECT with a 4096-byte client ID; assert the broker rejects it and stays alive (ASan build).
- Fuzz cid\_len against lengths just under and over the 64-byte boundary.

Preventive controls:
- Validate every attacker-supplied length against both the remaining packet size and the destination capacity before copying.
- Keep decoded packet storage off the stack or use dynamically sized fields.

<a id="finding-3"></a>

### [3] Packet handlers run before CONNECT, bypassing authentication and dereferencing a NULL session

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | server.c:867 calls handle\_command unconditionally. The allow\_anonymous check is confined to connect\_handler at handlers.c:366-375. subscribe\_handler dereferences e-\>client-\>session at handlers.c:588/593, and the PUBACK/PUBREC/PUBCOMP handlers dereference c-\>session at handlers.c:793/817/847. |
| Category | access-control |
| CWE | CWE-306, CWE-287, CWE-476 |
| Affected lines | src/server.c:858-867, src/handlers.c:362-375, src/handlers.c:583-593, src/handlers.c:789-795 |

#### Summary

process\_message dispatches every decoded packet without checking client-\>connected or that a session exists. Authentication happens only inside connect\_handler, so with allow\_anonymous=false an unauthenticated client can still send PUBLISH (including RETAIN) and inject messages into broker topics. Session-dependent packets such as SUBSCRIBE, PUBACK, PUBREC and PUBCOMP similarly run with client-\>session == NULL and crash the broker.

#### Root Cause

The packet dispatch layer has no connection-state authentication gate, so handler-level authentication in CONNECT can be bypassed and session-dependent handlers run with a NULL session.

**Every packet is dispatched without a connected/session check** — `src/server.c:858-867`

process\_message decodes and calls handle\_command for the packet type. There is no client-\>connected or client-\>session test before dispatch.

```c
static void process_message(struct ev_ctx *ctx, struct client *c)
{
    struct io_event io = {.client = c};
    /*
     * Unpack received bytes into a mqtt_packet structure and execute the
     * correct handler based on the type of the operation.
     */
    mqtt_unpack(c->rbuf + c->rpos, &io.data, *c->rbuf, c->read - c->rpos);
    c->toread = c->read = c->rpos = 0;
    c->rc = handle_command(io.data.header.bits.type, &io);
```

**Authentication is only performed inside CONNECT** — `src/handlers.c:362-375`

The allow\_anonymous=false branch rejects missing or invalid credentials only while handling CONNECT. A PUBLISH never passes through this check.

```c
    /*
     * If allow_anonymous is false we need to check for an existing
     * username:password pair match in the authentications table
     */
    if (conf->allow_anonymous == false) {
        if (c->bits.username == 0 || c->bits.password == 0)
            goto bad_auth;
        else {
            struct authentication *auth = NULL;
            HASH_FIND_STR(server.auths, (char *)c->payload.username, auth);
            if (!auth || !check_passwd((char *)c->payload.password, auth->salt))
                goto bad_auth;
        }
    }
```

**SUBSCRIBE uses the session pointer without checking it** — `src/handlers.c:583-593`

subscribe\_handler passes e-\>client-\>session to topic\_add\_subscriber and dereferences it via list\_push; a pre-CONNECT client has session == NULL.

```c
        if (!index(topic, '+')) {
            struct subscriber *tmp;
            HASH_FIND_STR(t->subscribers, c->client_id, tmp);
            if (c->clean_session == true || !tmp) {
                if (!tmp) {
                    tmp = topic_add_subscriber(t, e->client->session,
                                               s->tuples[i].qos);
                    // we increment reference for the subscriptions session
                    INCREF(tmp, struct subscriber);
                }
                list_push(e->client->session->subscriptions, t);
```

**PUBACK dereferences the session pointer** — `src/handlers.c:789-795`

puback\_handler indexes c-\>session-\>i\_msgs and c-\>session-\>i\_acks with no check that c-\>session exists.

```c
    log_debug("Received PUBACK from %s (m%u)", c->client_id, pkt_id);
#if THREADSNR > 0
    pthread_mutex_lock(&c->mutex);
#endif
    inflight_msg_clear(&c->session->i_msgs[pkt_id]);
    c->session->i_msgs[pkt_id].packet = NULL;
    c->session->i_acks[pkt_id]        = -1;
```

#### Validation

The dispatch call site and the CONNECT-only authentication branch were compared. PUBLISH has no session prerequisite and its handler performs no authorization, while SUBSCRIBE/PUBACK/PUBREC/PUBCOMP dereference the NULL pre-CONNECT session.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

TCP packet before CONNECT -\> process\_message -\> handle\_command -\> PUBLISH/SUBSCRIBE/ACK handler

- **Source:** any MQTT packet sent before a successful CONNECT

- **Sink:** publish\_handler and session-dependent handlers

- **Outcome:** Authentication bypass for PUBLISH; NULL session dereference for SUBSCRIBE/PUBACK/PUBREC/PUBCOMP

#### Reachability

Any client can send PUBLISH or SUBSCRIBE as its first packet.

- **Attacker:** unauthenticated network client

- **Entry point:** process\_message

Preconditions:
- network reachability
- allow\_anonymous=false to demonstrate the authorization bypass

#### Severity

**High** — The scan assigned high severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** high
- **Rationale:** The broker's authentication boundary is bypassed for message injection, and premature session packets crash the service.

Likelihood assessment:
- **Level:** high
- **Rationale:** No state or credentials are required; the first packet after connect can be PUBLISH or SUBSCRIBE.

#### Remediation

Reject every packet other than CONNECT until the connection has completed a successful CONNECT and has a non-NULL session. Enforce authorization in the dispatch layer, not only in connect\_handler, and return a protocol error for premature packets.

Tests:
- With allow\_anonymous=false, send PUBLISH as the first packet and assert the broker rejects it and does not store a retained message.
- Send SUBSCRIBE, PUBACK, PUBREC and PUBCOMP before CONNECT; assert each is rejected without a crash.
- Add a state-machine test that only CONNECT is accepted in the initial state.

Preventive controls:
- Add an explicit connection state machine and authorize at dispatch time.
- Treat any non-CONNECT packet received before CONNECT as a protocol violation and close the connection.

<a id="finding-4"></a>

### [4] UNSUBSCRIBE packet is destroyed twice, causing a heap double free

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | unsubscribe\_handler destroys the packet at handlers.c:676. process\_message destroys the same io.data at server.c:880. mqtt\_packet\_destroy frees pkt-\>subscribe.tuples and tuples\[i\].topic at mqtt.c:582-587 without nulling them. |
| Category | memory-corruption |
| CWE | CWE-415, CWE-416 |
| Affected lines | src/handlers.c:674-678, src/server.c:877-880, src/mqtt.c:582-587 |

#### Summary

unsubscribe\_handler calls mqtt\_packet\_destroy(&e-\>data) before returning REPLY, and process\_message then calls mqtt\_packet\_destroy(&io.data) again for every non-PUBLISH reply. The destructor frees the topic tuples without clearing the pointers, so a pre-CONNECT UNSUBSCRIBE triggers a double free of the tuple array and each topic string.

#### Root Cause

Ownership of the decoded packet is split: the UNSUBSCRIBE handler frees it and the common dispatch loop frees it again.

**UNSUBSCRIBE handler destroys the decoded packet** — `src/handlers.c:674-678`

The handler frees e-\>data (which is io.data) and then returns REPLY.

```c
    log_debug("Sending UNSUBACK to %s", c->client_id);

    mqtt_packet_destroy(&e->data);

    return REPLY;
```

**process\_message destroys the same packet for REPLY** — `src/server.c:868-880`

For REPLY, process\_message calls mqtt\_packet\_destroy(&io.data) unless the type is PUBLISH. UNSUBSCRIBE is not exempt.

```c
    switch (c->rc) {
    case REPLY:
    case MQTT_NOT_AUTHORIZED:
    case MQTT_BAD_USERNAME_OR_PASSWORD:
        /*
         * Write out to client, after a request has been processed in
         * worker thread routine. Just send out all bytes stored in the
         * reply buffer to the reply file descriptor.
         */
        enqueue_event_write(c);
        /* Free resource, ACKs will be free'd closing the server */
        if (io.data.header.bits.type != PUBLISH)
            mqtt_packet_destroy(&io.data);
```

**Destructor frees tuple storage without clearing pointers** — `src/mqtt.c:582-587`

SUBSCRIBE and UNSUBSCRIBE share this case: every tuple topic and the tuple array are freed, leaving dangling pointers in the packet.

```c
    case SUBSCRIBE:
    case UNSUBSCRIBE:
        for (unsigned i = 0; i < pkt->subscribe.tuples_len; i++)
            free_memory(pkt->subscribe.tuples[i].topic);
        free_memory(pkt->subscribe.tuples);
        break;
```

#### Validation

Both free sites operate on the same io.data object and the destructor does not null the freed pointers. The UNSUBSCRIBE handler returns REPLY, which selects the second free in process\_message.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

UNSUBSCRIBE packet -\> unsubscribe\_handler frees e-\>data -\> process\_message frees io.data again

- **Source:** attacker-controlled UNSUBSCRIBE packet

- **Sink:** free\_memory on the same tuples and topic strings twice

- **Outcome:** Heap double free and allocator corruption

#### Reachability

A single pre-CONNECT UNSUBSCRIBE packet reaches the handler; CONNECT is not required.

- **Attacker:** unauthenticated network client

- **Entry point:** UNSUBSCRIBE handler

Preconditions:
- one valid UNSUBSCRIBE packet

#### Severity

**High** — The scan assigned high severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** high
- **Rationale:** Double free corrupts the allocator and can be turned into controlled heap reuse, potentially code execution.

Likelihood assessment:
- **Level:** high
- **Rationale:** Every UNSUBSCRIBE reply exercises the double free deterministically.

#### Remediation

Remove the mqtt\_packet\_destroy call from unsubscribe\_handler and let process\_message own packet destruction, or transfer ownership explicitly. Make the destructor idempotent by clearing pointers and lengths after freeing.

Tests:
- Send UNSUBSCRIBE with one topic on a fresh connection under ASan; assert no double-free report.
- Add a test that verifies process\_message is the sole owner of decoded packet destruction.

Preventive controls:
- Define one owner for each decoded packet and document the ownership transfer at the handler boundary.
- Null out freed pointers in mqtt\_packet\_destroy to make repeated destruction harmless.

<a id="finding-5"></a>

### [5] Packet type dispatch tables contain NULL and out-of-bounds entries

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | unpack\_handlers\[11\] has NULL at indexes 0, 2 and 9, while handlers\[15\] has NULL at 0, 2, 9, 11 and 13. server.c:512-513 admits opcodes 1 through 14, so 0x20, 0x90, 0xB0 and 0xD0 reach the unchecked calls at mqtt.c:434 and handlers.c:879. |
| Category | denial-of-service |
| CWE | CWE-476, CWE-129 |
| Affected lines | src/mqtt.c:72-82, src/mqtt.c:431-434, src/handlers.c:62-76, src/handlers.c:877-880, src/server.c:505-513 |

#### Summary

mqtt\_unpack indexes unpack\_handlers\[byte \>\> 4\] and handle\_command indexes handlers\[type\] without checking that the type is implemented. CONNACK (0x20), SUBACK (0x90) and the unmapped types 0xB0/0xD0 survive the opcode range check and reach a NULL function pointer or an out-of-bounds table read, crashing the single-process broker before authentication.

#### Root Cause

The dispatch tables do not cover the entire packet-type space, and neither dispatch site validates table bounds or NULL entries.

**Unpack table is shorter than the packet-type space and has NULL slots** — `src/mqtt.c:72-82`

unpack\_handlers has 11 entries: index 0, 2 and 9 are NULL; indexes 11 and above are out of bounds. mqtt\_unpack indexes it with the 4-bit packet type.

```c
static mqtt_unpack_handler *unpack_handlers[11] = {NULL,
                                                   unpack_mqtt_connect,
                                                   NULL,
                                                   unpack_mqtt_publish,
                                                   unpack_mqtt_ack,
                                                   unpack_mqtt_ack,
                                                   unpack_mqtt_ack,
                                                   unpack_mqtt_ack,
                                                   unpack_mqtt_subscribe,
                                                   NULL,
                                                   unpack_mqtt_unsubscribe};
```

**Unchecked indirect call through the unpack table** — `src/mqtt.c:425-435`

Only PINGREQ..DISCONNECT (12..14) return early. Every other type calls unpack\_handlers\[type\], including NULL entries and types past the array end.

```c
    int rc      = MQTT_OK;
    u8 type     = byte >> 4;

    pkt->header = (union mqtt_header){.byte = byte};

    /* Call the appropriate unpack handler based on the message type */
    if (type >= PINGREQ && type <= DISCONNECT)
        return rc;

    rc = unpack_handlers[type](buf, pkt, len);

```

**Handler table also has NULL slots** — `src/handlers.c:62-76`

handlers\[15\] leaves index 0, 2, 9, 11 and 13 NULL; type 15 or greater would index past the array.

```c
static handler *handlers[15] = {NULL,
                                connect_handler,
                                NULL,
                                publish_handler,
                                puback_handler,
                                pubrec_handler,
                                pubrel_handler,
                                pubcomp_handler,
                                subscribe_handler,
                                NULL,
                                unsubscribe_handler,
                                NULL,
                                pingreq_handler,
                                NULL,
                                disconnect_handler};
```

**Unchecked indirect call through the handler table** — `src/handlers.c:877-880`

handle\_command calls handlers\[type\] with the type derived from the packet header, without validating that the slot is non-NULL.

```c
int handle_command(unsigned type, struct io_event *event)
{
    return handlers[type](event);
}
```

**Opcode guard admits unimplemented types** — `src/server.c:505-513`

The guard rejects only opcode \< CONNECT or opcode \> DISCONNECT, so CONNACK (2), SUBACK (9), 11 and 13 continue to the decoder.

```c
        if (c->read == 2) {
            opcode = *c->rbuf >> 4;

            /*
             * Check for OPCODE, if an unknown OPCODE is received return an
             * error
             */
            if (DISCONNECT < opcode || CONNECT > opcode)
                return -ERRPACKETERR;
```

#### Validation

Table contents and both indirect calls were inspected. A two-byte packet with type 2, 9, 11 or 13 reaches a NULL or out-of-bounds function pointer before CONNECT, so no authentication is needed.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

first MQTT byte -\> type nibble -\> unpack\_handlers\[type\] / handlers\[type\]

- **Source:** attacker-controlled MQTT fixed header

- **Sink:** indirect call through unpack\_handlers\[type\] and handlers\[type\]

- **Outcome:** NULL or out-of-bounds function pointer dereference

#### Reachability

Any client able to connect to the broker port can send one two-byte packet.

- **Attacker:** unauthenticated network client

- **Entry point:** recv\_packet -\> process\_message -\> mqtt\_unpack/handle\_command

Preconditions:
- network reachability

#### Severity

**High** — The scan assigned high severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** high
- **Rationale:** A single small packet terminates the shared broker process, disrupting every connected client.

Likelihood assessment:
- **Level:** high
- **Rationale:** The triggering packets are trivially generated and no state or authentication is required.

#### Remediation

Validate the packet type before both dispatch tables, reject every type the broker does not implement, and size the tables to the full 0-15 range with explicit NULL checks. Return a protocol error instead of calling through a missing entry.

Tests:
- Send 0x20 0x00, 0x90 0x00, 0xB0 0x00 and 0xD0 0x00 to a fresh connection; assert each is rejected with a protocol error and the broker remains alive.
- Fuzz all 256 first bytes with a zero remaining length under ASan/UBSan.

Preventive controls:
- Guard both dispatch sites with a range check and a non-NULL check.
- Use a single table sized 16 with explicit handlers for every defined type and reject the rest.

<a id="finding-6"></a>

### [6] Duplicate client IDs share a session and free it while another connection still uses it

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | connect\_handler finds cc-\>session by client ID at handlers.c:400 and keeps it when clean\_session is false. It never closes the previous client, and it adds a second clients\_map entry with the same key at handlers.c:425. client\_deactivate frees the shared session at server.c:438-439 based only on the disconnecting client's clean\_session flag. |
| Category | memory-corruption |
| CWE | CWE-416, CWE-362 |
| Affected lines | src/handlers.c:399-425, src/server.c:425-445 |

#### Summary

connect\_handler looks up an existing session by client ID and reuses it for the new connection without disconnecting the old client or removing its clients\_map entry. If the new connection keeps clean\_session=false, both connections point at the same session; when the original connection later disconnects with clean\_session=true, client\_deactivate frees that session while the new connection still references it. Duplicate HASH\_ADD\_STR entries and the HASH\_DEL of a shared session worsen the corruption.

#### Root Cause

Session ownership is not exclusive to one connection: a reused session can be referenced by multiple clients and freed by whichever clean-session client disconnects first.

**Existing session is reused without disconnecting the prior client** — `src/handlers.c:399-425`

When a session already exists and clean\_session is false, cc-\>session is reused and session\_present is set. The previous client remains connected and still points to the same session object.

```c
    // First we check if a session is present
    HASH_FIND_STR(server.sessions, cc->client_id, cc->session);
    if (cc->session && c->bits.clean_session == true)
        // Clean session true, we have to clean old session, if any
        HASH_DEL(server.sessions, cc->session);
    else if (cc->session)
        session_present = 1;

    cc->connected = true;

    log_info("New client connected as %s (c%i, k%u)", c->payload.client_id,
             c->bits.clean_session, c->payload.keepalive);

    /*
     * If no session was found or the client is a new connecting client or an
     * anonymous one, we create a session here
     */
    if (c->bits.clean_session == true || !cc->session) {
        cc->session = client_session_alloc(cc->client_id);
        INCREF(cc->session, struct client_session);
        HASH_ADD_STR(server.sessions, session_id, cc->session);
    }

    cc->session->clean_session = c->bits.clean_session;

    // Let's track client on the global map to be used on publish
    HASH_ADD_STR(server.clients_map, client_id, cc);
```

**A second clients\_map entry is added for the same client ID** — `src/handlers.c:424-425`

HASH\_ADD\_STR inserts the new client under the same client\_id key that the old client already uses, so lookups and deletions become ambiguous.

```c
    // Let's track client on the global map to be used on publish
    HASH_ADD_STR(server.clients_map, client_id, cc);
```

**Disconnect frees the shared session** — `src/server.c:425-445`

client\_deactivate frees client-\>session when the disconnecting client's clean\_session is true, even if another connected client still references that same session.

```c
    client->online = false;

#if THREADSNR > 0
    pthread_mutex_lock(&mutex);
#endif
    if (client->clean_session == true) {
        if (client->session) {
            topic_store_remove_wildcard(server.store, client->client_id);
            list_foreach(item, client->session->subscriptions)
            {
                topic_del_subscriber(item->data, client);
            }
            HASH_DEL(server.sessions, client->session);
            DECREF(client->session, struct client_session);
        }
        if (client->connected == true)
            HASH_DEL(server.clients_map, client);
        memorypool_free(server.pool, client);
    }
#if THREADSNR > 0
    pthread_mutex_unlock(&mutex);
```

#### Validation

The session lookup, the missing disconnect of the old client, the duplicate hash insertion and the session free on disconnect were traced as one ownership chain. Two connections with the same client ID are sufficient to obtain a dangling session pointer.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

client ID -\> HASH\_FIND\_STR(server.sessions) -\> shared session -\> clean-session disconnect -\> free while second client still references it

- **Source:** attacker-chosen client ID and clean-session flag

- **Sink:** client\_deactivate -\> DECREF(client-\>session)

- **Outcome:** Use-after-free of the shared client\_session

#### Reachability

Two connections using the same client ID; the second uses clean\_session=false and the first disconnects with clean\_session=true.

- **Attacker:** unauthenticated network client

- **Entry point:** connect\_handler and client\_deactivate

Preconditions:
- two connections with the same client ID

#### Severity

**High** — The scan assigned high severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** high
- **Rationale:** A freed session remains reachable from a live connection, allowing heap reuse and potential code execution or data corruption.

Likelihood assessment:
- **Level:** high
- **Rationale:** Client IDs are attacker-chosen and the broker never terminates the prior connection during takeover.

#### Remediation

On a duplicate client ID, disconnect and unregister the existing connection before adopting its session (MQTT takeover semantics), or reject the new connection. Keep exactly one clients\_map entry per client ID and reference-count sessions by owning connection.

Tests:
- Open two connections with the same client ID and clean\_session=false, then disconnect the first with clean\_session=true and publish/subscribe from the second under ASan.
- Assert the broker keeps exactly one clients\_map entry per client ID after a takeover.
- Add a takeover test that verifies the old connection is closed before the new connection adopts the session.

Preventive controls:
- Implement MQTT 3.1.1 session takeover by closing the existing connection and removing its map entry before reusing the session.
- Reference-count sessions by connection and free them only when the last owner releases them.

<a id="finding-7"></a>

### [7] Unsigned remaining-length arithmetic underflows in the MQTT decoder

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The subtraction sites are mqtt.c:314, 344/355/357 and 389/400. unpack\_bytes at pack.c:411-417 uses the resulting len directly in try\_alloc and memcpy. Because len is usize, any deficit becomes near SIZE\_MAX rather than negative. |
| Category | memory-safety |
| CWE | CWE-191, CWE-125, CWE-787 |
| Affected lines | src/mqtt.c:304-316, src/pack.c:411-424, src/mqtt.c:342-358, src/mqtt.c:385-401 |

#### Summary

unpack\_mqtt\_publish, unpack\_mqtt\_subscribe and unpack\_mqtt\_unsubscribe subtract header, topic and QoS lengths from the usize remaining length without checking that each field fits. A PUBLISH whose remaining length is smaller than 2 + topiclen wraps len to a huge value, and unpack\_bytes then allocates len + 1 and memcpy's len bytes from the packet buffer. SUBSCRIBE/UNSUBSCRIBE loops similarly wrap and keep allocating and reading past the packet.

#### Root Cause

The decoder uses unsigned remaining-length arithmetic without validating each variable-length field against the bytes actually received.

**PUBLISH subtracts topic length without a bounds check** — `src/mqtt.c:304-316`

len is usize. After subtracting 2 + topiclen, any packet shorter than the declared topic length wraps len to a very large value, which becomes payloadlen.

```c
    /* Read packet id */
    if (pkt->header.bits.qos > AT_MOST_ONCE) {
        pkt->publish.pkt_id = unpack_integer(&buf, 'H');
        len -= sizeof(u16);
    }

    /*
     * Message len is calculated subtracting the length of the variable header
     * from the Remaining Length field that is in the Fixed Header
     */
    len -= (sizeof(u16) + pkt->publish.topiclen);
    pkt->publish.payloadlen = len;
    pkt->publish.payload    = unpack_bytes(&buf, len);
```

**unpack\_bytes trusts the computed length** — `src/pack.c:411-417`

try\_alloc(len + 1) and memcpy(dest, \*buf, len) use the wrapped length. For SIZE\_MAX the allocation size wraps and memcpy reads and writes far beyond the packet and the allocated chunk.

```c
u8 *unpack_bytes(u8 **buf, usize len)
{
    u8 *dest = try_alloc(len + 1);
    memcpy(dest, *buf, len);
    dest[len] = '\0';
    *buf += len;
    return dest;
```

**SUBSCRIBE loop subtracts without checking remaining bytes** — `src/mqtt.c:342-358`

When len is 1, len -= sizeof(u16) wraps to SIZE\_MAX, so the loop does not terminate and repeatedly reads tuple headers past the received packet while reallocating.

```c
    for (; len > 0; ++i) {
        /* Read length bytes of the first topic filter */
        len -= sizeof(u16);

        /* We have to make room for additional incoming tuples */
        subscribe.tuples =
            try_realloc(subscribe.tuples, (i + 1) * sizeof(*subscribe.tuples));
        subscribe.tuples[i].topic_len =
            unpack_string16(&buf, &subscribe.tuples[i].topic);

        if (!subscribe.tuples[i].topic)
            goto err;

        len -= subscribe.tuples[i].topic_len;
        subscribe.tuples[i].qos = unpack_integer(&buf, 'B');
        len -= sizeof(u8);
    }
```

**UNSUBSCRIBE loop has the same unchecked subtraction** — `src/mqtt.c:385-401`

The same underflow allows an unbounded loop and out-of-bounds topic reads for UNSUBSCRIBE packets.

```c
    usize i = 0;
    for (; len > 0; ++i) {

        /* Read length bytes of the first topic filter */
        len -= sizeof(u16);

        /* We have to make room for additional incoming tuples */
        unsubscribe.tuples = try_realloc(unsubscribe.tuples,
                                         (i + 1) * sizeof(*unsubscribe.tuples));
        unsubscribe.tuples[i].topic_len =
            unpack_string16(&buf, &unsubscribe.tuples[i].topic);

        if (!unsubscribe.tuples[i].topic)
            goto err;

        len -= unsubscribe.tuples[i].topic_len;
    }
```

#### Validation

Each subtraction and the unpack\_bytes sink were inspected. A three-byte PUBLISH with remaining length 1 and a zero topic length, or a SUBSCRIBE with one trailing byte, produces the underflow deterministically.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

remaining length and topic length are both attacker-controlled; usize subtraction wraps; unpack\_bytes/realloc consume the wrapped size

- **Source:** MQTT PUBLISH/SUBSCRIBE/UNSUBSCRIBE fixed and variable headers

- **Sink:** try\_alloc(len + 1) / memcpy(dest, buf, len) / try\_realloc loop

- **Outcome:** Out-of-bounds read, oversized allocation, or infinite loop terminating the process

#### Reachability

Any client can send a truncated PUBLISH/SUBSCRIBE/UNSUBSCRIBE packet; no CONNECT is required.

- **Attacker:** unauthenticated network client

- **Entry point:** mqtt\_unpack

Preconditions:
- network reachability

#### Severity

**High** — The scan assigned high severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** high
- **Rationale:** The underflow can crash or hang the shared broker and can expose memory through oversized reads.

Likelihood assessment:
- **Level:** high
- **Rationale:** Crafting a truncated packet requires no special state and the wrapping arithmetic is unconditional.

#### Remediation

Before each subtraction, verify that the field length fits in the remaining bytes (remaining \>= 1 + 2 + topic\_len for SUBSCRIBE tuples, and remaining \>= 2 + topic\_len for PUBLISH). Reject truncated packets with a protocol error instead of subtracting.

Tests:
- Send PUBLISH packets with remaining lengths 0-4 and topic length 0 under ASan; assert a clean protocol error.
- Send SUBSCRIBE and UNSUBSCRIBE packets with a single trailing byte; assert the decoder terminates with an error.
- Fuzz remaining length, topic length and tuple count combinations under ASan/UBSan.

Preventive controls:
- Use checked subtraction helpers that return an error when the field does not fit in the remaining bytes.
- Bound every decoder allocation by the received packet size.

<a id="finding-8"></a>

### [8] Inflight ACK retransmission packs through a NULL packet pointer

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | p is initialized to NULL at server.c:314 and assigned only inside the i\_msgs branch. The ACK branch at server.c:354 calls mqtt\_pack(p, ...) instead of mqtt\_pack(&ack, ...). pubrec\_handler sets c-\>session-\>i\_acks\[pkt\_id\] without creating an i\_msgs entry. |
| Category | denial-of-service |
| CWE | CWE-476 |
| Affected lines | src/server.c:311-356, src/handlers.c:803-818 |

#### Summary

inflight\_msg\_check resends pending ACKs with mqtt\_pack(p, c-\>wbuf + c-\>towrite), but p is only assigned in the preceding message branch and is NULL when only an ACK is pending. A client can create an ACK-only inflight entry by sending PUBREC for an unused packet ID; after the 20-second retransmission timer, mqtt\_pack dereferences NULL and crashes the broker. The call also uses the wrong buffer size, since size was computed from the ACK packet.

#### Root Cause

The retransmission helper reuses a pointer from the message branch for the ACK branch and never reinitializes it.

**p starts NULL and is set only in the message branch** — `src/server.c:311-315`

struct mqtt\_packet \*p = NULL is declared once for the whole timer callback; the message retransmission branch is the only assignment.

```c
    (void)ctx;
    size_t size           = 0;
    time_t now            = time(NULL);
    struct mqtt_packet *p = NULL;
    struct client *c, *tmp;
```

**ACK branch passes p instead of &ack** — `src/server.c:345-356`

The ACK branch builds a local struct mqtt\_packet ack but serializes p, which is NULL when no message was resent for this index.

```c
            if (c->session->i_acks[i] > 0 &&
                (now - c->session->i_acks[i]) > 20) {
                log_debug("Re-sending ack to %s", c->client_id);
                struct mqtt_packet ack;
                mqtt_ack(&ack, i);
                // Set DUP flag to 1
                mqtt_set_dup(&ack);
                size = mqtt_size(&ack, NULL);
                // Serialize the packet and send it out again
                mqtt_pack(p, c->wbuf + c->towrite);
                c->towrite += size;
                enqueue_event_write(c);
```

**PUBREC creates an ACK-only inflight entry** — `src/handlers.c:803-818`

pubrec\_handler writes c-\>session-\>i\_acks\[pkt\_id\] = time(NULL) without creating a corresponding i\_msgs entry, so the ACK branch can run alone.

```c
static int pubrec_handler(struct io_event *e)
{
    struct client *c = e->client;
    unsigned pkt_id  = e->data.ack.pkt_id;
    log_debug("Received PUBREC from %s (m%u)", c->client_id, pkt_id);
#if THREADSNR > 0
    pthread_mutex_lock(&c->mutex);
#endif
    mqtt_pack_mono(c->wbuf + c->towrite, PUBREL, pkt_id);
    c->towrite += MQTT_ACK_LEN;
#if THREADSNR > 0
    pthread_mutex_unlock(&c->mutex);
#endif
    // Update inflight acks table
    c->session->i_acks[pkt_id] = time(NULL);
    log_debug("Sending PUBREL to %s (m%u)", c->client_id, pkt_id);
```

#### Validation

The pointer lifetime and the PUBREC input path were inspected. A connected client that sends PUBREC for an unused packet ID creates an ACK-only entry that reaches the NULL pack after the retransmission delay.

Validation method: Static source review with attacker-controlled data-flow tracing

#### Dataflow

PUBREC pkt\_id -\> i\_acks\[pkt\_id\] set -\> 20-second timer -\> ACK branch -\> mqtt\_pack(NULL)

- **Source:** attacker-controlled PUBREC packet identifier

- **Sink:** mqtt\_pack(p) with p == NULL

- **Outcome:** NULL pointer dereference and broker crash

#### Reachability

A connected (or pre-CONNECT PUBREC-crashing) client sends PUBREC with an unused packet ID and waits for the timer.

- **Attacker:** network client with an MQTT session

- **Entry point:** inflight\_msg\_check timer

Preconditions:
- a connected client
- 20 seconds elapsed

#### Severity

**Medium** — The scan assigned medium severity; no separate canonical severity rationale was recorded.

Additional runtime or deployment evidence could raise or lower this severity.

Impact assessment:
- **Level:** medium
- **Rationale:** The broker process terminates after a short delay, disrupting all clients, but exploitation is limited to denial of service.

Likelihood assessment:
- **Level:** medium
- **Rationale:** Requires a valid session and the retransmission interval, but the input is a single ordinary PUBREC.

#### Remediation

Pass &ack to mqtt\_pack in the ACK branch and compute the size from the same packet that is serialized. Reset p per iteration or avoid sharing it between the two branches.

Tests:
- Send PUBREC with an unused packet ID from a connected client, wait for the timer, and assert no crash.
- Unit-test inflight\_msg\_check with an ACK-only session entry.

Preventive controls:
- Serialize the packet that was built in the same branch and scope the retransmission pointer to each branch.
- Validate packet identifiers before storing ACK state.
