#!/usr/bin/env python3
import json, os
from pathlib import Path

SCAN_DIR = Path('/vol1/1000/mygoldmine-benchmark/2026-11-17/results/codex-security/sol')
SRC = Path('/vol1/1000/mygoldmine-benchmark/2026-11-17/targets/sol')

def lines(rel, start, end):
    text = (SRC / rel).read_text().splitlines()
    return "\n".join(text[start-1:end])

def ev(eid, label, rel, start, end, role, explanation):
    return {
        "id": eid,
        "label": label,
        "path": rel,
        "startLine": start,
        "endLine": end,
        "language": "c",
        "role": role,
        "code": lines(rel, start, end),
        "explanation": explanation,
    }

def finding(rule_id, anchor, title, summary, level, score, vector, rationale,
            category, cwes, locations, evidence, root_cause, remediation,
            validation_summary, attack, remediation_tests, preventive, candidate=None):
    prov = {"source": "local_plugin"}
    if candidate:
        prov["candidateId"] = candidate
    return {
        "ruleId": rule_id,
        "identity": {"anchor": anchor},
        "title": title,
        "summary": summary,
        "severity": {"level": level, "score": score, "scoringSystem": "CVSS:3.1", "vector": vector},
        "confidence": {"level": "high", "rationale": rationale},
        "taxonomy": {"category": category, "cwe": cwes},
        "locations": locations,
        "codeEvidence": evidence,
        "rootCause": {"summary": root_cause, "evidenceRefs": [e["id"] for e in evidence]},
        "remediation": remediation,
        "validation": {"method": "Static source review with attacker-controlled data-flow tracing", "summary": validation_summary},
        "attackPath": attack,
        "remediationTests": remediation_tests,
        "preventiveControls": preventive,
        "provenance": prov,
    }

findings = []

# 1. CONNECT client_id stack overflow
findings.append(finding(
    "memory-safety.connect-client-id-overflow",
    "connect-client-id-overflow",
    "Pre-authenticated CONNECT client ID overflows a 64-byte field on the stack",
    ("unpack_mqtt_connect reads an attacker-controlled 16-bit client ID length and copies that many "
     "bytes into connect.payload.client_id, a 64-byte array, then writes a NUL at client_id[cid_len]. "
     "The decoded packet lives in the stack-local io_event of process_message, so a CONNECT whose client ID "
     "exceeds 63 bytes overwrites the process_message stack frame with attacker bytes before any authentication."),
    "critical", 9.8, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ("The unchecked memcpy and the trailing NUL write are visible at mqtt.c:240-241; the destination is a "
     "64-byte array in mqtt.h, and io_event is a stack local in process_message at server.c:860. Packet size is "
     "bounded only by max_request_size, so a multi-kilobyte client ID is accepted."),
    "memory-corruption", ["CWE-121", "CWE-787"],
    [
        {"path": "src/mqtt.c", "startLine": 235, "endLine": 243, "role": "sink"},
        {"path": "src/mqtt.h", "startLine": 40, "endLine": 40, "role": "capacity"},
        {"path": "src/server.c", "startLine": 858, "endLine": 867, "role": "stack-frame"},
    ],
    [
        ev("connect-cid-copy", "Unbounded client ID copy into 64-byte field", "src/mqtt.c", 235, 243, "sink",
           "cid_len comes directly from the packet (u16). memcpy copies cid_len bytes into the 64-byte client_id and index write client_id[cid_len] adds a NUL past the array when cid_len >= 64."),
        ev("connect-cid-capacity", "Client ID field is 64 bytes", "src/mqtt.h", 40, 40, "capacity",
           "MQTT_CLIENT_ID_LEN is 64. Any client ID longer than 63 bytes overflows the destination."),
        ev("connect-stack-frame", "Decoded packet is a stack local of process_message", "src/server.c", 858, 867, "stack-frame",
           "io_event io is allocated on the process_message stack. The connect union member and its client_id array are therefore on the stack, immediately before the saved frame state."),
    ],
    "The decoder trusts the packet-supplied client ID length and copies it into a fixed 64-byte array on the stack.",
    ("Reject CONNECT when cid_len >= MQTT_CLIENT_ID_LEN or when cid_len exceeds the remaining packet body, and copy with "
     "a bounded length. Prefer allocating client IDs dynamically or enforcing the MQTT 3.1.1 23-byte minimum limit."),
    ("Source tracing shows a single unauthenticated CONNECT packet controls the copy length and the destination is the "
     "stack-resident io_event. No parser, size, or authentication check constrains cid_len before the copy."),
    {"summary": "A remote client can corrupt the broker's stack before authenticating.",
     "dataflow": {"summary": "CONNECT body bytes -> cid_len -> memcpy into stack-local client_id[64]",
                  "source": "MQTT CONNECT packet client ID length and bytes",
                  "sink": "memcpy(pkt->connect.payload.client_id, buf, cid_len) and client_id[cid_len] = 0",
                  "outcome": "Stack memory overwrite with attacker-controlled bytes in process_message"},
     "reachability": {"summary": "Any unauthenticated TCP client that can reach the MQTT listener sends one CONNECT packet.",
                       "attacker": "unauthenticated network client", "entrypoint": "TCP listener -> recv_packet -> process_message",
                       "preconditions": ["network reachability to the broker port"]},
     "impact": {"level": "critical", "rationale": "Attacker-controlled overwrite of a live stack frame can redirect control flow, leading to broker code execution or a crash."},
     "likelihood": {"level": "high", "rationale": "The overflow is a single packet with no protocol or authentication prerequisite."}},
    ["Send a CONNECT with a 64-byte client ID; assert it is rejected without corruption.",
     "Send a CONNECT with a 4096-byte client ID; assert the broker rejects it and stays alive (ASan build).",
     "Fuzz cid_len against lengths just under and over the 64-byte boundary."],
    ["Validate every attacker-supplied length against both the remaining packet size and the destination capacity before copying.",
     "Keep decoded packet storage off the stack or use dynamically sized fields."],
    candidate="cand-connect-client-id-overflow",
))

# 2. Write buffer overflow
findings.append(finding(
    "memory-safety.client-write-buffer-overflow",
    "client-write-buffer-overflow",
    "Unbounded writes into the fixed per-client write buffer corrupt the heap",
    ("client->wbuf is allocated with exactly max_request_size bytes, but SUBACK/UNSUBACK generation, retained-message "
     "replay, session resume replay and publish fan-out all append to wbuf + towrite without checking the remaining "
     "capacity. A retained PUBLISH close to max_request_size followed by a SUBSCRIBE (or two publishes delivered before "
     "the event loop flushes) writes past the allocation, corrupting heap metadata and adjacent objects."),
    "critical", 9.1, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ("The allocation is exact at server.c:397-399. Appends at handlers.c:227-228 and 615-618 and 632-634, "
     "handlers.c:331-338, handlers.c:668-669 and server.c:338-339 add packet sizes to towrite with no remaining-space "
     "check. towrite is reset only after a complete send at server.c:652, so multiple queued outputs accumulate."),
    "memory-corruption", ["CWE-787", "CWE-122"],
    [
        {"path": "src/server.c", "startLine": 397, "endLine": 399, "role": "allocation"},
        {"path": "src/handlers.c", "startLine": 615, "endLine": 618, "role": "sink"},
        {"path": "src/handlers.c", "startLine": 224, "endLine": 228, "role": "sink"},
        {"path": "src/handlers.c", "startLine": 629, "endLine": 634, "role": "sink"},
    ],
    [
        ev("wbuf-allocation", "Write buffer is exactly max_request_size", "src/server.c", 392, 399, "allocation",
           "rbuf and wbuf are both try_calloc(conf->max_request_size, 1). No spare capacity or growth is reserved for responses."),
        ev("wbuf-fanout", "Publish fan-out appends a whole packet to towrite", "src/handlers.c", 224, 231, "sink",
           "mqtt_pack writes the entire publish at wbuf + towrite, then towrite advances by len. Nothing checks towrite + len against max_request_size."),
        ev("wbuf-retained", "Retained-message replay memcpy has no capacity check", "src/handlers.c", 613, 619, "sink",
           "Each retained message matching a SUBSCRIBE is memcpy'd at wbuf + towrite and towrite grows by the retained size."),
        ev("wbuf-suback", "SUBACK is appended after retained replay", "src/handlers.c", 626, 634, "sink",
           "The SUBACK is packed at the current towrite after all retained messages, so even a retained message that fills wbuf overflows by the SUBACK length."),
        ev("wbuf-reset", "towrite is only reset after a complete send", "src/server.c", 642, 652, "lifecycle",
           "towrite accumulates across queued replies and is reset only when the whole buffer has been sent, so consecutive outputs do not start from zero."),
    ],
    "Every response path treats the per-client write buffer as unbounded even though it is allocated with exactly max_request_size bytes.",
    ("Track the remaining capacity for wbuf and fail or disconnect when a reply would exceed it; grow the buffer dynamically for queued messages. "
     "Validate retained and fan-out message sizes against the destination's free space before packing."),
    ("The fixed allocation and each unchecked append were traced. A retained PUBLISH of nearly max_request_size followed by a "
     "SUBSCRIBE reaches the retained replay memcpy and then appends a SUBACK past the end of wbuf."),
    {"summary": "A remote publisher can place a large retained message and then cause another client to subscribe to its topic, overflowing the subscriber's heap write buffer.",
     "dataflow": {"summary": "PUBLISH with RETAIN -> retained_msg copy -> SUBSCRIBE -> memcpy(wbuf + towrite) and SUBACK append",
                  "source": "attacker-supplied PUBLISH payload and topic",
                  "sink": "memcpy/mqtt_pack into client->wbuf at towerite",
                  "outcome": "Heap overflow beyond a max_request_size allocation"},
     "reachability": {"summary": "Two unauthenticated connections suffice: one publishes a large retained message, another subscribes to the topic.",
                       "attacker": "unauthenticated network client", "entrypoint": "PUBLISH handler and SUBSCRIBE handler",
                       "preconditions": ["anonymous access enabled (default) or any authenticated session", "retained flag set on the large publish"]},
     "impact": {"level": "critical", "rationale": "Heap corruption with attacker-influenced bytes can lead to code execution or broker crash."},
     "likelihood": {"level": "high", "rationale": "The sequence is simple and the default max_request_size leaves no headroom for the follow-up SUBACK."}},
    ["Publish a retained message of size max_request_size - small, then subscribe from another connection under ASan; assert no overflow and either delivery or a clean rejection.",
     "Queue two near-maximum publishes for one subscriber before its socket drains; assert the write path bounds the buffer.",
     "Add a unit test that asserts every append checks towrite + len <= max_request_size."],
    ["Centralize all writes to wbuf in a helper that returns an error when the destination is full.",
     "Size reply buffers from the actual packet being built and enforce a per-client output quota."],
    candidate="cand-write-buffer-overflow",
))

# 3. NULL/OOB dispatch
findings.append(finding(
    "memory-safety.null-and-out-of-bounds-dispatch",
    "null-and-out-of-bounds-dispatch",
    "Packet type dispatch tables contain NULL and out-of-bounds entries",
    ("mqtt_unpack indexes unpack_handlers[byte >> 4] and handle_command indexes handlers[type] without checking that the "
     "type is implemented. CONNACK (0x20), SUBACK (0x90) and the unmapped types 0xB0/0xD0 survive the opcode range check "
     "and reach a NULL function pointer or an out-of-bounds table read, crashing the single-process broker before authentication."),
    "high", 7.5, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
    ("unpack_handlers[11] has NULL at indexes 0, 2 and 9, while handlers[15] has NULL at 0, 2, 9, 11 and 13. "
     "server.c:512-513 admits opcodes 1 through 14, so 0x20, 0x90, 0xB0 and 0xD0 reach the unchecked calls at mqtt.c:434 and handlers.c:879."),
    "denial-of-service", ["CWE-476", "CWE-129"],
    [
        {"path": "src/mqtt.c", "startLine": 72, "endLine": 82, "role": "root-cause"},
        {"path": "src/mqtt.c", "startLine": 431, "endLine": 434, "role": "sink"},
        {"path": "src/handlers.c", "startLine": 62, "endLine": 76, "role": "root-cause"},
        {"path": "src/handlers.c", "startLine": 877, "endLine": 880, "role": "sink"},
        {"path": "src/server.c", "startLine": 505, "endLine": 513, "role": "reachability"},
    ],
    [
        ev("dispatch-unpack-table", "Unpack table is shorter than the packet-type space and has NULL slots", "src/mqtt.c", 72, 82, "root-cause",
           "unpack_handlers has 11 entries: index 0, 2 and 9 are NULL; indexes 11 and above are out of bounds. mqtt_unpack indexes it with the 4-bit packet type."),
        ev("dispatch-unpack-call", "Unchecked indirect call through the unpack table", "src/mqtt.c", 425, 435, "sink",
           "Only PINGREQ..DISCONNECT (12..14) return early. Every other type calls unpack_handlers[type], including NULL entries and types past the array end."),
        ev("dispatch-handler-table", "Handler table also has NULL slots", "src/handlers.c", 62, 76, "root-cause",
           "handlers[15] leaves index 0, 2, 9, 11 and 13 NULL; type 15 or greater would index past the array."),
        ev("dispatch-handler-call", "Unchecked indirect call through the handler table", "src/handlers.c", 877, 880, "sink",
           "handle_command calls handlers[type] with the type derived from the packet header, without validating that the slot is non-NULL."),
        ev("dispatch-opcode-check", "Opcode guard admits unimplemented types", "src/server.c", 505, 513, "reachability",
           "The guard rejects only opcode < CONNECT or opcode > DISCONNECT, so CONNACK (2), SUBACK (9), 11 and 13 continue to the decoder."),
    ],
    "The dispatch tables do not cover the entire packet-type space, and neither dispatch site validates table bounds or NULL entries.",
    ("Validate the packet type before both dispatch tables, reject every type the broker does not implement, and size the tables to the "
     "full 0-15 range with explicit NULL checks. Return a protocol error instead of calling through a missing entry."),
    ("Table contents and both indirect calls were inspected. A two-byte packet with type 2, 9, 11 or 13 reaches a NULL or out-of-bounds "
     "function pointer before CONNECT, so no authentication is needed."),
    {"summary": "An unauthenticated packet with an unimplemented type crashes the broker.",
     "dataflow": {"summary": "first MQTT byte -> type nibble -> unpack_handlers[type] / handlers[type]",
                  "source": "attacker-controlled MQTT fixed header",
                  "sink": "indirect call through unpack_handlers[type] and handlers[type]",
                  "outcome": "NULL or out-of-bounds function pointer dereference"},
     "reachability": {"summary": "Any client able to connect to the broker port can send one two-byte packet.",
                       "attacker": "unauthenticated network client", "entrypoint": "recv_packet -> process_message -> mqtt_unpack/handle_command",
                       "preconditions": ["network reachability"]},
     "impact": {"level": "high", "rationale": "A single small packet terminates the shared broker process, disrupting every connected client."},
     "likelihood": {"level": "high", "rationale": "The triggering packets are trivially generated and no state or authentication is required."}},
    ["Send 0x20 0x00, 0x90 0x00, 0xB0 0x00 and 0xD0 0x00 to a fresh connection; assert each is rejected with a protocol error and the broker remains alive.",
     "Fuzz all 256 first bytes with a zero remaining length under ASan/UBSan."],
    ["Guard both dispatch sites with a range check and a non-NULL check.",
     "Use a single table sized 16 with explicit handlers for every defined type and reject the rest."],
    candidate="cand-null-dispatch",
))

# 4. UNSUBSCRIBE double free
findings.append(finding(
    "memory-safety.unsubscribe-double-free",
    "unsubscribe-double-free",
    "UNSUBSCRIBE packet is destroyed twice, causing a heap double free",
    ("unsubscribe_handler calls mqtt_packet_destroy(&e->data) before returning REPLY, and process_message then calls "
     "mqtt_packet_destroy(&io.data) again for every non-PUBLISH reply. The destructor frees the topic tuples without "
     "clearing the pointers, so a pre-CONNECT UNSUBSCRIBE triggers a double free of the tuple array and each topic string."),
    "high", 8.1, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ("unsubscribe_handler destroys the packet at handlers.c:676. process_message destroys the same io.data at server.c:880. "
     "mqtt_packet_destroy frees pkt->subscribe.tuples and tuples[i].topic at mqtt.c:582-587 without nulling them."),
    "memory-corruption", ["CWE-415", "CWE-416"],
    [
        {"path": "src/handlers.c", "startLine": 674, "endLine": 678, "role": "first-free"},
        {"path": "src/server.c", "startLine": 877, "endLine": 880, "role": "second-free"},
        {"path": "src/mqtt.c", "startLine": 582, "endLine": 587, "role": "destructor"},
    ],
    [
        ev("unsub-first-free", "UNSUBSCRIBE handler destroys the decoded packet", "src/handlers.c", 674, 678, "first-free",
           "The handler frees e->data (which is io.data) and then returns REPLY."),
        ev("unsub-second-free", "process_message destroys the same packet for REPLY", "src/server.c", 868, 880, "second-free",
           "For REPLY, process_message calls mqtt_packet_destroy(&io.data) unless the type is PUBLISH. UNSUBSCRIBE is not exempt."),
        ev("unsub-destructor", "Destructor frees tuple storage without clearing pointers", "src/mqtt.c", 582, 587, "destructor",
           "SUBSCRIBE and UNSUBSCRIBE share this case: every tuple topic and the tuple array are freed, leaving dangling pointers in the packet."),
    ],
    "Ownership of the decoded packet is split: the UNSUBSCRIBE handler frees it and the common dispatch loop frees it again.",
    ("Remove the mqtt_packet_destroy call from unsubscribe_handler and let process_message own packet destruction, or transfer ownership explicitly. "
     "Make the destructor idempotent by clearing pointers and lengths after freeing."),
    ("Both free sites operate on the same io.data object and the destructor does not null the freed pointers. The UNSUBSCRIBE handler returns REPLY, "
     "which selects the second free in process_message."),
    {"summary": "One UNSUBSCRIBE packet frees the same heap objects twice.",
     "dataflow": {"summary": "UNSUBSCRIBE packet -> unsubscribe_handler frees e->data -> process_message frees io.data again",
                  "source": "attacker-controlled UNSUBSCRIBE packet",
                  "sink": "free_memory on the same tuples and topic strings twice",
                  "outcome": "Heap double free and allocator corruption"},
     "reachability": {"summary": "A single pre-CONNECT UNSUBSCRIBE packet reaches the handler; CONNECT is not required.",
                       "attacker": "unauthenticated network client", "entrypoint": "UNSUBSCRIBE handler",
                       "preconditions": ["one valid UNSUBSCRIBE packet"]},
     "impact": {"level": "high", "rationale": "Double free corrupts the allocator and can be turned into controlled heap reuse, potentially code execution."},
     "likelihood": {"level": "high", "rationale": "Every UNSUBSCRIBE reply exercises the double free deterministically."}},
    ["Send UNSUBSCRIBE with one topic on a fresh connection under ASan; assert no double-free report.",
     "Add a test that verifies process_message is the sole owner of decoded packet destruction."],
    ["Define one owner for each decoded packet and document the ownership transfer at the handler boundary.",
     "Null out freed pointers in mqtt_packet_destroy to make repeated destruction harmless."],
    candidate="cand-unsubscribe-double-free",
))

# 5. Parser length underflow
findings.append(finding(
    "memory-safety.decoder-length-underflow",
    "decoder-length-underflow",
    "Unsigned remaining-length arithmetic underflows in the MQTT decoder",
    ("unpack_mqtt_publish, unpack_mqtt_subscribe and unpack_mqtt_unsubscribe subtract header, topic and QoS lengths from the "
     "usize remaining length without checking that each field fits. A PUBLISH whose remaining length is smaller than 2 + topiclen "
     "wraps len to a huge value, and unpack_bytes then allocates len + 1 and memcpy's len bytes from the packet buffer. "
     "SUBSCRIBE/UNSUBSCRIBE loops similarly wrap and keep allocating and reading past the packet."),
    "high", 8.2, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:H",
    ("The subtraction sites are mqtt.c:314, 344/355/357 and 389/400. unpack_bytes at pack.c:411-417 uses the resulting "
     "len directly in try_alloc and memcpy. Because len is usize, any deficit becomes near SIZE_MAX rather than negative."),
    "memory-safety", ["CWE-191", "CWE-125", "CWE-787"],
    [
        {"path": "src/mqtt.c", "startLine": 304, "endLine": 316, "role": "root-cause"},
        {"path": "src/pack.c", "startLine": 411, "endLine": 424, "role": "sink"},
        {"path": "src/mqtt.c", "startLine": 342, "endLine": 358, "role": "root-cause"},
        {"path": "src/mqtt.c", "startLine": 385, "endLine": 401, "role": "root-cause"},
    ],
    [
        ev("len-publish-underflow", "PUBLISH subtracts topic length without a bounds check", "src/mqtt.c", 304, 316, "root-cause",
           "len is usize. After subtracting 2 + topiclen, any packet shorter than the declared topic length wraps len to a very large value, which becomes payloadlen."),
        ev("len-unpack-bytes", "unpack_bytes trusts the computed length", "src/pack.c", 411, 417, "sink",
           "try_alloc(len + 1) and memcpy(dest, *buf, len) use the wrapped length. For SIZE_MAX the allocation size wraps and memcpy reads and writes far beyond the packet and the allocated chunk."),
        ev("len-subscribe-loop", "SUBSCRIBE loop subtracts without checking remaining bytes", "src/mqtt.c", 342, 358, "root-cause",
           "When len is 1, len -= sizeof(u16) wraps to SIZE_MAX, so the loop does not terminate and repeatedly reads tuple headers past the received packet while reallocating."),
        ev("len-unsubscribe-loop", "UNSUBSCRIBE loop has the same unchecked subtraction", "src/mqtt.c", 385, 401, "root-cause",
           "The same underflow allows an unbounded loop and out-of-bounds topic reads for UNSUBSCRIBE packets."),
    ],
    "The decoder uses unsigned remaining-length arithmetic without validating each variable-length field against the bytes actually received.",
    ("Before each subtraction, verify that the field length fits in the remaining bytes (remaining >= 1 + 2 + topic_len for SUBSCRIBE tuples, "
     "and remaining >= 2 + topic_len for PUBLISH). Reject truncated packets with a protocol error instead of subtracting."),
    ("Each subtraction and the unpack_bytes sink were inspected. A three-byte PUBLISH with remaining length 1 and a zero topic length, or a "
     "SUBSCRIBE with one trailing byte, produces the underflow deterministically."),
    {"summary": "A short packet can force enormous allocation/copy sizes or an endless decode loop.",
     "dataflow": {"summary": "remaining length and topic length are both attacker-controlled; usize subtraction wraps; unpack_bytes/realloc consume the wrapped size",
                  "source": "MQTT PUBLISH/SUBSCRIBE/UNSUBSCRIBE fixed and variable headers",
                  "sink": "try_alloc(len + 1) / memcpy(dest, buf, len) / try_realloc loop",
                  "outcome": "Out-of-bounds read, oversized allocation, or infinite loop terminating the process"},
     "reachability": {"summary": "Any client can send a truncated PUBLISH/SUBSCRIBE/UNSUBSCRIBE packet; no CONNECT is required.",
                       "attacker": "unauthenticated network client", "entrypoint": "mqtt_unpack",
                       "preconditions": ["network reachability"]},
     "impact": {"level": "high", "rationale": "The underflow can crash or hang the shared broker and can expose memory through oversized reads."},
     "likelihood": {"level": "high", "rationale": "Crafting a truncated packet requires no special state and the wrapping arithmetic is unconditional."}},
    ["Send PUBLISH packets with remaining lengths 0-4 and topic length 0 under ASan; assert a clean protocol error.",
     "Send SUBSCRIBE and UNSUBSCRIBE packets with a single trailing byte; assert the decoder terminates with an error.",
     "Fuzz remaining length, topic length and tuple count combinations under ASan/UBSan."],
    ["Use checked subtraction helpers that return an error when the field does not fit in the remaining bytes.",
     "Bound every decoder allocation by the received packet size."],
    candidate="cand-parser-length-underflow",
))

# 6. Missing connection-state / auth check
findings.append(finding(
    "access-control.missing-connect-state-check",
    "missing-connect-state-check",
    "Packet handlers run before CONNECT, bypassing authentication and dereferencing a NULL session",
    ("process_message dispatches every decoded packet without checking client->connected or that a session exists. "
     "Authentication happens only inside connect_handler, so with allow_anonymous=false an unauthenticated client can still "
     "send PUBLISH (including RETAIN) and inject messages into broker topics. Session-dependent packets such as SUBSCRIBE, "
     "PUBACK, PUBREC and PUBCOMP similarly run with client->session == NULL and crash the broker."),
    "high", 8.2, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    ("server.c:867 calls handle_command unconditionally. The allow_anonymous check is confined to connect_handler at handlers.c:366-375. "
     "subscribe_handler dereferences e->client->session at handlers.c:588/593, and the PUBACK/PUBREC/PUBCOMP handlers dereference "
     "c->session at handlers.c:793/817/847."),
    "access-control", ["CWE-306", "CWE-287", "CWE-476"],
    [
        {"path": "src/server.c", "startLine": 858, "endLine": 867, "role": "root-cause"},
        {"path": "src/handlers.c", "startLine": 362, "endLine": 375, "role": "auth-check"},
        {"path": "src/handlers.c", "startLine": 583, "endLine": 593, "role": "sink"},
        {"path": "src/handlers.c", "startLine": 789, "endLine": 795, "role": "sink"},
    ],
    [
        ev("preconnect-dispatch", "Every packet is dispatched without a connected/session check", "src/server.c", 858, 867, "root-cause",
           "process_message decodes and calls handle_command for the packet type. There is no client->connected or client->session test before dispatch."),
        ev("preconnect-auth-location", "Authentication is only performed inside CONNECT", "src/handlers.c", 362, 375, "auth-check",
           "The allow_anonymous=false branch rejects missing or invalid credentials only while handling CONNECT. A PUBLISH never passes through this check."),
        ev("preconnect-subscribe-null", "SUBSCRIBE uses the session pointer without checking it", "src/handlers.c", 583, 593, "sink",
           "subscribe_handler passes e->client->session to topic_add_subscriber and dereferences it via list_push; a pre-CONNECT client has session == NULL."),
        ev("preconnect-puback-null", "PUBACK dereferences the session pointer", "src/handlers.c", 789, 795, "sink",
           "puback_handler indexes c->session->i_msgs and c->session->i_acks with no check that c->session exists."),
    ],
    "The packet dispatch layer has no connection-state authentication gate, so handler-level authentication in CONNECT can be bypassed and session-dependent handlers run with a NULL session.",
    ("Reject every packet other than CONNECT until the connection has completed a successful CONNECT and has a non-NULL session. "
     "Enforce authorization in the dispatch layer, not only in connect_handler, and return a protocol error for premature packets."),
    ("The dispatch call site and the CONNECT-only authentication branch were compared. PUBLISH has no session prerequisite and its handler "
     "performs no authorization, while SUBSCRIBE/PUBACK/PUBREC/PUBCOMP dereference the NULL pre-CONNECT session."),
    {"summary": "An unauthenticated client can publish into the broker and can crash it with premature session-dependent packets.",
     "dataflow": {"summary": "TCP packet before CONNECT -> process_message -> handle_command -> PUBLISH/SUBSCRIBE/ACK handler",
                  "source": "any MQTT packet sent before a successful CONNECT",
                  "sink": "publish_handler and session-dependent handlers",
                  "outcome": "Authentication bypass for PUBLISH; NULL session dereference for SUBSCRIBE/PUBACK/PUBREC/PUBCOMP"},
     "reachability": {"summary": "Any client can send PUBLISH or SUBSCRIBE as its first packet.",
                       "attacker": "unauthenticated network client", "entrypoint": "process_message",
                       "preconditions": ["network reachability", "allow_anonymous=false to demonstrate the authorization bypass"]},
     "impact": {"level": "high", "rationale": "The broker's authentication boundary is bypassed for message injection, and premature session packets crash the service."},
     "likelihood": {"level": "high", "rationale": "No state or credentials are required; the first packet after connect can be PUBLISH or SUBSCRIBE."}},
    ["With allow_anonymous=false, send PUBLISH as the first packet and assert the broker rejects it and does not store a retained message.",
     "Send SUBSCRIBE, PUBACK, PUBREC and PUBCOMP before CONNECT; assert each is rejected without a crash.",
     "Add a state-machine test that only CONNECT is accepted in the initial state."],
    ["Add an explicit connection state machine and authorize at dispatch time.",
     "Treat any non-CONNECT packet received before CONNECT as a protocol violation and close the connection."],
))

# 7. Session takeover UAF
findings.append(finding(
    "memory-safety.session-takeover-use-after-free",
    "session-takeover-use-after-free",
    "Duplicate client IDs share a session and free it while another connection still uses it",
    ("connect_handler looks up an existing session by client ID and reuses it for the new connection without disconnecting the "
     "old client or removing its clients_map entry. If the new connection keeps clean_session=false, both connections point at the "
     "same session; when the original connection later disconnects with clean_session=true, client_deactivate frees that session "
     "while the new connection still references it. Duplicate HASH_ADD_STR entries and the HASH_DEL of a shared session worsen the "
     "corruption."),
    "high", 8.1, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ("connect_handler finds cc->session by client ID at handlers.c:400 and keeps it when clean_session is false. It never closes the "
     "previous client, and it adds a second clients_map entry with the same key at handlers.c:425. client_deactivate frees the shared "
     "session at server.c:438-439 based only on the disconnecting client's clean_session flag."),
    "memory-corruption", ["CWE-416", "CWE-362"],
    [
        {"path": "src/handlers.c", "startLine": 399, "endLine": 425, "role": "root-cause"},
        {"path": "src/server.c", "startLine": 425, "endLine": 445, "role": "sink"},
    ],
    [
        ev("takeover-session-reuse", "Existing session is reused without disconnecting the prior client", "src/handlers.c", 399, 425, "root-cause",
           "When a session already exists and clean_session is false, cc->session is reused and session_present is set. The previous client remains connected and still points to the same session object."),
        ev("takeover-duplicate-map-entry", "A second clients_map entry is added for the same client ID", "src/handlers.c", 424, 425, "root-cause",
           "HASH_ADD_STR inserts the new client under the same client_id key that the old client already uses, so lookups and deletions become ambiguous."),
        ev("takeover-session-free", "Disconnect frees the shared session", "src/server.c", 425, 445, "sink",
           "client_deactivate frees client->session when the disconnecting client's clean_session is true, even if another connected client still references that same session."),
    ],
    "Session ownership is not exclusive to one connection: a reused session can be referenced by multiple clients and freed by whichever clean-session client disconnects first.",
    ("On a duplicate client ID, disconnect and unregister the existing connection before adopting its session (MQTT takeover semantics), or reject the "
     "new connection. Keep exactly one clients_map entry per client ID and reference-count sessions by owning connection."),
    ("The session lookup, the missing disconnect of the old client, the duplicate hash insertion and the session free on disconnect were traced as one "
     "ownership chain. Two connections with the same client ID are sufficient to obtain a dangling session pointer."),
    {"summary": "An attacker can force two connections to share a session and then free it while the other connection continues to use it.",
     "dataflow": {"summary": "client ID -> HASH_FIND_STR(server.sessions) -> shared session -> clean-session disconnect -> free while second client still references it",
                  "source": "attacker-chosen client ID and clean-session flag",
                  "sink": "client_deactivate -> DECREF(client->session)",
                  "outcome": "Use-after-free of the shared client_session"},
     "reachability": {"summary": "Two connections using the same client ID; the second uses clean_session=false and the first disconnects with clean_session=true.",
                       "attacker": "unauthenticated network client", "entrypoint": "connect_handler and client_deactivate",
                       "preconditions": ["two connections with the same client ID"]},
     "impact": {"level": "high", "rationale": "A freed session remains reachable from a live connection, allowing heap reuse and potential code execution or data corruption."},
     "likelihood": {"level": "high", "rationale": "Client IDs are attacker-chosen and the broker never terminates the prior connection during takeover."}},
    ["Open two connections with the same client ID and clean_session=false, then disconnect the first with clean_session=true and publish/subscribe from the second under ASan.",
     "Assert the broker keeps exactly one clients_map entry per client ID after a takeover.",
     "Add a takeover test that verifies the old connection is closed before the new connection adopts the session."],
    ["Implement MQTT 3.1.1 session takeover by closing the existing connection and removing its map entry before reusing the session.",
     "Reference-count sessions by connection and free them only when the last owner releases them."],
    candidate="cand-session-takeover",
))

# 8. Inflight ACK stale pointer
findings.append(finding(
    "memory-safety.inflight-ack-stale-pointer",
    "inflight-ack-stale-pointer",
    "Inflight ACK retransmission packs through a NULL packet pointer",
    ("inflight_msg_check resends pending ACKs with mqtt_pack(p, c->wbuf + c->towrite), but p is only assigned in the preceding "
     "message branch and is NULL when only an ACK is pending. A client can create an ACK-only inflight entry by sending PUBREC "
     "for an unused packet ID; after the 20-second retransmission timer, mqtt_pack dereferences NULL and crashes the broker. "
     "The call also uses the wrong buffer size, since size was computed from the ACK packet."),
    "medium", 5.3, "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H",
    ("p is initialized to NULL at server.c:314 and assigned only inside the i_msgs branch. The ACK branch at server.c:354 calls "
     "mqtt_pack(p, ...) instead of mqtt_pack(&ack, ...). pubrec_handler sets c->session->i_acks[pkt_id] without creating an i_msgs entry."),
    "denial-of-service", ["CWE-476"],
    [
        {"path": "src/server.c", "startLine": 311, "endLine": 356, "role": "sink"},
        {"path": "src/handlers.c", "startLine": 803, "endLine": 818, "role": "input"},
    ],
    [
        ev("inflight-p-initial", "p starts NULL and is set only in the message branch", "src/server.c", 311, 315, "sink",
           "struct mqtt_packet *p = NULL is declared once for the whole timer callback; the message retransmission branch is the only assignment."),
        ev("inflight-ack-pack", "ACK branch passes p instead of &ack", "src/server.c", 345, 356, "sink",
           "The ACK branch builds a local struct mqtt_packet ack but serializes p, which is NULL when no message was resent for this index."),
        ev("inflight-pubrec-sets-ack", "PUBREC creates an ACK-only inflight entry", "src/handlers.c", 803, 818, "input",
           "pubrec_handler writes c->session->i_acks[pkt_id] = time(NULL) without creating a corresponding i_msgs entry, so the ACK branch can run alone."),
    ],
    "The retransmission helper reuses a pointer from the message branch for the ACK branch and never reinitializes it.",
    ("Pass &ack to mqtt_pack in the ACK branch and compute the size from the same packet that is serialized. Reset p per iteration or "
     "avoid sharing it between the two branches."),
    ("The pointer lifetime and the PUBREC input path were inspected. A connected client that sends PUBREC for an unused packet ID creates "
     "an ACK-only entry that reaches the NULL pack after the retransmission delay."),
    {"summary": "A connected client can make the broker dereference NULL during ACK retransmission.",
     "dataflow": {"summary": "PUBREC pkt_id -> i_acks[pkt_id] set -> 20-second timer -> ACK branch -> mqtt_pack(NULL)",
                  "source": "attacker-controlled PUBREC packet identifier",
                  "sink": "mqtt_pack(p) with p == NULL",
                  "outcome": "NULL pointer dereference and broker crash"},
     "reachability": {"summary": "A connected (or pre-CONNECT PUBREC-crashing) client sends PUBREC with an unused packet ID and waits for the timer.",
                       "attacker": "network client with an MQTT session", "entrypoint": "inflight_msg_check timer",
                       "preconditions": ["a connected client", "20 seconds elapsed"]},
     "impact": {"level": "medium", "rationale": "The broker process terminates after a short delay, disrupting all clients, but exploitation is limited to denial of service."},
     "likelihood": {"level": "medium", "rationale": "Requires a valid session and the retransmission interval, but the input is a single ordinary PUBREC."}},
    ["Send PUBREC with an unused packet ID from a connected client, wait for the timer, and assert no crash.",
     "Unit-test inflight_msg_check with an ACK-only session entry."],
    ["Serialize the packet that was built in the same branch and scope the retransmission pointer to each branch.",
     "Validate packet identifiers before storing ACK state."],
))

review = {
    "surfaces": [
        {"id": "packet-framing-decode", "label": "Packet framing, remaining length and field decoding", "disposition": "reported",
         "receiptRefs": [], "notes": "CONNECT client ID overflow and unsigned remaining-length underflow confirmed."},
        {"id": "dispatch-state-machine", "label": "Packet dispatch and CONNECT state machine", "disposition": "reported",
         "receiptRefs": [], "notes": "NULL/out-of-bounds dispatch entries and missing pre-CONNECT gate confirmed."},
        {"id": "client-write-buffer", "label": "Per-client write buffer and subscriber fan-out", "disposition": "reported",
         "receiptRefs": [], "notes": "Unbounded appends and retained replay overflow confirmed."},
        {"id": "packet-ownership", "label": "Decoded packet ownership and destruction", "disposition": "reported",
         "receiptRefs": [], "notes": "UNSUBSCRIBE is destroyed by both handler and dispatch loop."},
        {"id": "session-lifecycle", "label": "Client/session identity and lifecycle", "disposition": "reported",
         "receiptRefs": [], "notes": "Duplicate client ID shares a session that can be freed under the other connection."},
        {"id": "topic-store", "label": "Topic trie, subscriptions and retained messages", "disposition": "no_issue_found",
         "receiptRefs": [], "notes": "Retained-message storage itself reviewed; the reported retained path issue is the unbounded replay copy in client-write-buffer."},
        {"id": "authz-handshake", "label": "Authentication and connection-state authorization", "disposition": "reported",
         "receiptRefs": [], "notes": "Authentication is enforced only in connect_handler; dispatch accepts pre-CONNECT packets."},
    ],
    "explicitExclusions": [
        {"pattern": "passwd.py", "reason": "Local administrative password-file generation helper; no remote input path."},
        {"pattern": "conf/sol.conf", "reason": "Deployment configuration; reviewed for defaults, but malformed local configuration is not a remote attacker capability."},
        {"pattern": "tests/**", "reason": "Test harness code is not part of the broker's network attack surface."},
    ],
    "deferred": [],
}

manifest = json.loads((SCAN_DIR / "scan-manifest.json").read_text())
manifest["scan"]["complete"] = True
manifest["scan"]["status"] = "completed"
manifest["scan"]["reviewState"] = review
manifest["scan"]["review"] = {"excludedPaths": [e["pattern"] for e in review["explicitExclusions"]]}
manifest["scan"]["mode"] = "repository"

findings_doc = {"findings": findings}
draft = {"manifest": manifest, "findings": findings_doc, "reviewState": review}
out = SCAN_DIR / "drafts" / "final-draft.json"
out.write_text(json.dumps(draft, indent=2) + "\n")
print("wrote", out, "findings:", len(findings))
