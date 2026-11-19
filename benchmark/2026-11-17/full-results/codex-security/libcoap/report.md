# Security Review: libcoap

## Scope

Repository-wide static review of libcoap 4.3.5 (revision a4de0fae) covering CoAP PDU and option parsing, WebSocket framing and close, block-wise Block1/Q-Block reassembly, OSCORE decryption and external credential lookup, Appendix B.1.2/B.2 state, and URI/proxy handling. Six source-backed findings identify the attacker path and the deployment conditions required for impact.

- Scan mode: repository
- Target kind: git\_worktree
- Target ID: target\_sha256\_10d44786099544bad5e59dc28ec6d0ce22ef0b2de457760f5a3f7ca967c2165d
- Revision: a4de0faea54d3d548924c8b9f6e67b72a36cbac3
- Snapshot digest: codex-security-snapshot/v1:sha256:868747fbdfeec18f41a2ef392ede1963b4708eed591631e4cc97641062afea81
- Included paths: .
- Excluded paths: none
- Artifacts reviewed: src/coap\_ws.c, src/coap\_oscore.c, src/oscore/oscore\_context.c, src/oscore/oscore.c, src/oscore/oscore\_cbor.c, src/coap\_block.c, src/coap\_pdu.c, src/coap\_net.c, src/coap\_str.c, src/coap\_io.c, src/coap\_session.c, include/coap3/coap\_oscore.h, include/coap3/coap\_block.h, include/coap3/coap\_ws\_internal.h
- Scan context: Repository-wide review at the supplied snapshot. The checkout is grafted, so history-based diffing was unavailable and the current source was treated as authoritative. Network-reachable parsers and protocol state machines were prioritized.

Limitations and exclusions:
- No compiler, sanitizer, or dynamic target execution was available; findings are established by source review and attack-path tracing.
- Several findings require non-default application configuration: an external OSCORE credential callback that returns multiple recipients, RFC 8613 Appendix B.2 mode, or server-side Block1 single-body/Q-Block reassembly.
- The pdu\_408\_build payload-marker write and the Uri-Path-Abbrev retransmit body loss were reviewed but are not reported as findings: the former is not reachable together with the mandatory Q-Block options on the default UDP PDU size, and the latter is a correctness defect without a demonstrated security boundary.

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 8 |
| Severity mix | high: 2, medium: 3, low: 3 |
| Confidence mix | high: 8 |
| Validation mode | Static source review, boundary and arithmetic analysis, and source-backed attack-path tracing; no execution of the target. |

Canonical artifacts: `scan-manifest.json` and `findings.json`. This report is a deterministic projection of those files.

## Threat Model

libcoap is a C implementation of CoAP used as a library and through example clients and servers. It parses UDP, TCP, TLS/DTLS, and WebSocket traffic; decodes options and bodies; implements block-wise transfer, observe, caching, proxying, persistence, and OSCORE. Network peers control packets and metadata, while applications choose resources, authentication, and deployment exposure. The critical invariant is that untrusted wire data must be length-checked and bounded before it reaches indexes, arithmetic, copies, allocations, formatting, or protocol state transitions.

### Assets

- Integrity and confidentiality of CoAP resources, request and response bodies, and OSCORE or DTLS/TLS-protected content
- Process memory and control flow of applications embedding libcoap
- Availability of CoAP servers, clients, proxies, and resource-directory services
- Credentials and key material used by DTLS/TLS, OSCORE, PSK, PKI, and configuration paths
- CoAP endpoint identity, token and request correlation, block-wise reassembly, observe state, and proxy routing decisions

### Trust Boundaries

- Unauthenticated or authenticated network peers to UDP/TCP/WS listeners and client response processing
- DTLS/TLS/OSCORE authenticated content versus plaintext parsing and error-reporting paths
- CoAP wire message and option encoding to internal parsed PDU structures and application callbacks
- Client, server, and proxy application layer to filesystem persistence, resource-directory records, and configured credentials
- Test and fuzz harnesses from production library paths; fixtures demonstrate parser behavior but are not themselves deployed services

### Attacker Capabilities

- Send arbitrary CoAP datagrams or streams, including malformed headers, options, token lengths, block options, observe operations, and bodies
- Control message size, option repetition and order, extended option widths and deltas, URI paths, content-format values, and block-wise state
- Potentially hold a valid DTLS/TLS/PSK/OSCORE identity and send authenticated but otherwise adversarial messages
- Supply malicious responses to clients, or interact with proxies and resource-directory endpoints where enabled
- Cannot assume operator-level configuration changes, local filesystem access, or access to private keys unless source evidence establishes them

### Security Objectives

- Reject malformed or oversized wire input without out-of-bounds access, integer overflow, uncontrolled allocation, or persistent resource exhaustion
- Preserve message parsing and protocol state isolation across peers and concurrent requests
- Enforce authenticated-message integrity and the intended scope of OSCORE, DTLS, and TLS protections
- Prevent untrusted URIs, proxy targets, persistence input, or cache keys from escaping expected resource boundaries
- Avoid disclosing usable credentials or private keys through source-distributed files

### Assumptions

- Network-facing library code is reachable wherever an application exposes a CoAP listener; endpoint configuration and credentials are application policy.
- The current snapshot is the authorized release source; previous commits are not available for comparison because the checkout is grafted.
- A denial-of-service finding requires a source-backed repeatable trigger with meaningful service impact, not merely an error path.

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [OSCORE external credential lookup can return a context with no recipient and crash the server](#finding-1) | high | high | inline below |
| [WebSocket close path can overflow a 100-byte stack buffer with a partial frame](#finding-2) | high | high | inline below |
| [Block1 reassembly can hand uninitialized heap bytes to the application](#finding-3) | medium | high | inline below |
| [OSCORE Appendix B.2 kid\_context encoder writes past the 255-byte stack buffer and underflows its remaining-space counter](#finding-4) | medium | high | inline below |
| [Appendix B.2 creates unbounded OSCORE contexts before authentication](#finding-5) | medium | high | inline below |
| [pdu\_408\_build writes the payload marker without checking capacity](#finding-6) | low | high | inline below |
| [Short OSCORE responses advance the replay window without rollback](#finding-7) | low | high | inline below |
| [Uri-Path-Abbrev fallback retransmit drops the request body](#finding-8) | low | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] OSCORE external credential lookup can return a context with no recipient and crash the server

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The no-match path leaves \*recipient\_ctx unset and explicitly assigns NULL to the context chain; the caller initializes rcp\_ctx to NULL at line 939 and dereferences it after checking only osc\_ctx. |
| Category | null-pointer-dereference |
| CWE | CWE-476 |
| Affected lines | src/oscore/oscore\_context.c:371-396, src/coap\_oscore.c:1064-1069, src/coap\_oscore.c:1146-1157 |

#### Summary

When an application registers an external credential callback with coap\_oscore\_register\_external\_handlers() and the callback returns a configuration with multiple recipients, oscore\_find\_context() assigns \*recipient\_ctx only when a recipient matches the request KID. If none matches, it frees every recipient, leaves \*recipient\_ctx NULL, sets tmp\_ctx-\>recipient\_chain = NULL, and still returns the context. coap\_oscore\_decrypt\_pdu() then calls coap\_oscore\_session\_set\_recipient\_ctx(session, NULL), which is a no-op, and dereferences rcp\_ctx-\>initial\_state, crashing on a single unauthenticated OSCORE request with an unknown KID.

#### Validation

The no-match branch never assigns \*recipient\_ctx; the caller initializes it to NULL and dereferences it after only checking that osc\_ctx is non-NULL. No check exists between the lookup and line 1156.

Validation method: Static source review and source-backed attack-path tracing

#### Dataflow

An OSCORE request supplies a KID absent from the multi-recipient configuration returned by the application callback. oscore\_find\_context returns the context but leaves the recipient pointer NULL. The request path stores the NULL recipient and immediately reads rcp\_ctx-\>initial\_state.

#### Reachability

Any peer that can send an OSCORE option to a server using the external credential callback with multiple recipients. The KID is carried in the OSCORE option and can be chosen by the attacker.

#### Severity

**High** — A single crafted OSCORE packet can crash a server that uses the public external credential API with a multi-recipient configuration. The attacker needs no valid OSCORE key, only a KID absent from the returned recipient set.

Lower if the application never registers oscore\_find\_cb or always returns a single-recipient configuration; raise if the crash is shown on a default deployment.

#### Remediation

Initialize \*recipient\_ctx = NULL at the start of the callback path and return NULL when no recipient matches, freeing the temporary context. Reject the request when osc\_ctx is non-NULL but rcp\_ctx is NULL before storing or dereferencing the recipient.

Source finding: Initialize \*recipient\_ctx = NULL at the start of the callback path and return NULL when no recipient matches, freeing the temporary context. Also reject the request when osc\_ctx is non-NULL but rcp\_ctx is NULL before storing or dereferencing the recipient.

Tests:
- Register an external callback returning two recipients, send an OSCORE request with an unknown KID, and verify the server returns 4.01 instead of crashing.
- Add a unit test for oscore\_find\_context with a multi-recipient conf and an unmatched KID asserting a NULL result.

Preventive controls:
- Treat (osc\_ctx != NULL, rcp\_ctx == NULL) as an invalid state at every lookup site.

<a id="finding-2"></a>

### [2] WebSocket close path can overflow a 100-byte stack buffer with a partial frame

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The one-time size check, the stale-size continuation read, and the 100-byte close buffer are all explicit in source. The only residual uncertainty is timing the remaining bytes into the drain window, not whether the unchecked write exists. |
| Category | memory-corruption |
| CWE | CWE-121, CWE-787 |
| Affected lines | src/coap\_ws.c:697-707, src/coap\_ws.c:762-764, src/coap\_ws.c:900-914 |

#### Summary

coap\_ws\_close() drains pending input into uint8\_t buf\[100\] by calling coap\_ws\_read(session, buf, 100). If a large binary frame was only partially consumed, all\_hdr\_in remains set and data\_ofs \< data\_size; coap\_ws\_read() skips the header-time size check and calls l\_read(&data\[data\_ofs\], data\_size - data\_ofs), so a peer that supplies the remaining frame bytes during the 1 ms drain windows writes attacker-controlled data past buf.

#### Validation

The continuation read at line 762 uses the stored frame size, while the size check at line 698 applies only during header parsing. The close drain at line 914 passes a 100-byte buffer, establishing the overflow condition.

Validation method: Static source review and source-backed attack-path tracing

#### Dataflow

A WS peer sends a masked binary frame header announcing more than 100 bytes (for example 1400), delivers only part of the payload, and leaves data\_ofs \< data\_size with all\_hdr\_in set. On teardown coap\_ws\_close() drains with buf\[100\]; the resume path skips header parsing and requests data\_size - data\_ofs bytes from l\_read, which writes the peer's remaining payload past buf.

#### Reachability

Requires an exposed WS/WSS endpoint and a close while a partial frame is outstanding. The built-in 300 s idle-session timeout frees the session (src/coap\_io.c:420-427); an application-configured max\_idle\_sessions evicts it deterministically (src/coap\_session.c:1324-1327). The peer supplies the remaining bytes for the 5 x 1 ms select() drain windows.

#### Severity

**High** — An unauthenticated WebSocket peer can reach a 100-byte stack buffer with a stale, attacker-chosen frame length and write past it. The resulting memory corruption can crash the process and may permit control-flow hijack on any WS/WSS listener.

Lower if the platform read never writes more than the caller-supplied capacity or if the close drain cannot run while all\_hdr\_in is set. Raise confidence with a dynamic reproducer.

#### Remediation

Clamp the continuation read to min(data\_size - data\_ofs, datalen) and reject the frame if it cannot fit; in coap\_ws\_close(), size the drain buffer for the maximum accepted frame or do not call coap\_ws\_read with a smaller buffer.

Source finding: Clamp the continuation read to min(data\_size - data\_ofs, datalen) and abort the frame if it cannot fit, or reject the frame when all\_hdr\_in is set and data\_size exceeds datalen. In coap\_ws\_close(), use a drain buffer at least as large as the maximum accepted frame or do not call coap\_ws\_read with a smaller buffer.

Tests:
- Build with ASan, send a masked binary frame of length 500 with only 10 payload bytes, trigger close, then send the remaining 490 bytes during the drain window; verify no stack write occurs.
- Add a unit test that calls coap\_ws\_read with a partial frame and then a 100-byte buffer and asserts the read length is clamped.

Preventive controls:
- Route all frame payload reads through a helper that always takes the caller's remaining capacity.
- Keep a single frame-size validation at the point of each read, not only during header parsing.

<a id="finding-3"></a>

### [3] Block1 reassembly can hand uninitialized heap bytes to the application

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | coap\_new\_binary() does not zero the payload area, and the copy is performed only for the current segment. The offset is computed from the current block SZX with no equality check against lg\_srcv-\>szx, so a size change leaves a gap. |
| Category | information-disclosure |
| CWE | CWE-457, CWE-200 |
| Affected lines | src/coap\_block.c:3604, src/coap\_block.c:4050-4058, src/coap\_block.c:4590-4624, src/coap\_str.c:42-46 |

#### Summary

coap\_block\_build\_body\_lkd() allocates a body of total bytes with coap\_new\_binary() and copies only each received segment at its offset. If a client changes SZX between blocks so the next offset jumps past data already received, the gap is never initialized. give\_app\_data later sets pdu-\>body\_data to that buffer and pdu-\>body\_length to total\_len, so an application that returns the body, such as an echo or proxy resource, discloses heap contents.

#### Validation

The uninitialized allocation, segment-only copy, offset from the current SZX, and full-length handoff form a complete path. No dynamic reproduction was performed.

Validation method: Static source review and source-backed dataflow tracing

#### Dataflow

A client sends block 0 with SZX=0, NUM=0, M=1 and 16 bytes, then block 1 with SZX=6, NUM=1, M=0 and 1024 bytes. offset becomes 1 \<\< 10 = 1024 and total becomes 2048; blocks\_add\_entry tracks only NUM contiguity, so the ranges merge. coap\_block\_build\_body\_lkd() grows the body to offset + length and copies only the new segment; bytes 16 through 1023 are never initialized. give\_app\_data() sets body\_length = total\_len, so an application that returns the body discloses the gap.

#### Reachability

Requires server-side Block1 reassembly using COAP\_BLOCK\_SINGLE\_BODY, COAP\_BLOCK\_NOT\_RANDOM\_BLOCK1, or Q-Block, plus an application resource that exposes the reassembled body. The example server enables this mode with -L 3.

#### Severity

**Medium** — A remote client can cause uninitialized heap memory to be returned as request body data, potentially exposing previous request data, pointers, or key material. The server must have library-side single-body or Q-Block reassembly enabled.

Raise if the application exposes a body-echo or body-processing resource that returns data to the peer. Lower if the application never enables SINGLE\_BODY, NOT\_RANDOM\_BLOCK1, or Q-Block reassembly.

#### Remediation

Zero-initialize the body allocation, or track received byte ranges and reject any Block1 sequence with a gap or overlap. Compute offsets from the SZX established for the transfer and require each segment to start at the next expected byte.

Tests:
- Send Block1 with num=0,szx=0,len=16,m=1 followed by num=1,szx=3,len=128,m=0 and assert the application body has no uninitialized bytes.
- Run the reassembly test under ASan and MSan and reject any gap.

Preventive controls:
- Maintain an explicit received-range map instead of only block numbers.

<a id="finding-4"></a>

### [4] OSCORE Appendix B.2 kid\_context encoder writes past the 255-byte stack buffer and underflows its remaining-space counter

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | The pointer arithmetic and the size passed to oscore\_cbor\_put\_bytes() are explicit: the pointer advances past the length byte without reducing rem\_space, and the post-write decrement can underflow. |
| Category | memory-corruption |
| CWE | CWE-787, CWE-193 |
| Affected lines | src/oscore/oscore.c:218-231, src/oscore/oscore\_cbor.c:104-118, src/coap\_oscore.c:418, src/coap\_oscore.c:540-543 |

#### Summary

oscore\_encode\_option\_value() points the CBOR writer at option\_buffer\[offset+1\] but passes rem\_space unchanged. The bytes actually available at that pointer are rem\_space - 1. When the CBOR header plus kid\_context length equals rem\_space, oscore\_cbor\_put\_bytes() writes the final byte to option\_buffer\[255\], one past the 255-byte stack array, and the following rem\_space -= 1 underflows to SIZE\_MAX. The key-id bound check is then bypassed, memcpy(&option\_buffer\[offset\], key\_id, ...) writes past the array, and the returned offset of 256 or more is passed to coap\_insert\_option(), which reads past the stack array. The encoder runs when Appendix B.2 is configured and b\_2\_step is not NONE, with attacker-influenced kid\_context bytes.

#### Validation

With offset=1 and rem\_space=254 before any PIV, ptr begins at index 2 while 254 bytes are advertised; the final byte reaches index 255, rem\_space becomes SIZE\_MAX after the decrement, and the following key-id copy at offset 256 is unbounded.

Validation method: Static source review and arithmetic boundary analysis

#### Dataflow

A malicious OSCORE server supplies an R2 value whose length makes the client's B.2 kid\_context (R2 || ID1) align exactly with the advertised space. On the next request, oscore\_encode\_option\_value() writes the CBOR length and payload one byte past option\_buffer\[255\], underflows rem\_space, and then copies the key id past the array; the oversized returned length is inserted as the OSCORE option.

#### Reachability

A client with rfc8613\_b\_2 enabled communicating with a malicious server; the server controls R2 length and can align the CBOR header plus kid\_context to rem\_space.

#### Severity

**Medium** — A malicious OSCORE peer can drive a stack out-of-bounds write and read with attacker-influenced kid\_context and key-id bytes. Reachability requires the non-default Appendix B.2 mode, so impact is conditional on deployment; it can be raised where B.2 is enabled.

Raise if B.2 is enabled in a production deployment or if the adjacent stack bytes are control values. Lower if B.2 is never enabled.

#### Remediation

Pass rem\_space - 1 to oscore\_cbor\_put\_bytes() and require rem\_space \> 1; check nb + kid\_context.length against the true remaining capacity, guard the rem\_space decrement against underflow, and derive the next offset from the bounded return value.

Source finding: Pass rem\_space - 1 to oscore\_cbor\_put\_bytes() and require rem\_space \> 1. Also validate nb + kid\_context.length against the true remaining capacity before copying, and derive the next offset from the bounded return value.

Tests:
- Build the OSCORE option with a kid\_context sized so the CBOR header plus payload equals rem\_space and run under ASan; assert no stack-buffer-overflow.
- Add unit tests for the maximum kid\_context length in Appendix B.2 mode.

Preventive controls:
- Centralize OSCORE option buffer accounting so the pointer offset and remaining size are updated together.

<a id="finding-5"></a>

### [5] Appendix B.2 creates unbounded OSCORE contexts before authentication

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | The duplicate is linked into the context list in oscore\_duplicate\_ctx(), and the decrypt error path contains no matching context deletion. |
| Category | resource-exhaustion |
| CWE | CWE-770 |
| Affected lines | src/coap\_oscore.c:1081-1122, src/oscore/oscore\_context.c:657-746, src/coap\_oscore.c:1856-1867 |

#### Summary

In Appendix B.2 mode, coap\_oscore\_decrypt\_pdu() duplicates the OSCORE context for a request carrying an unknown kid\_context and links it into context-\>p\_osc\_ctx before the AEAD tag is verified. The decryption-failure and error paths free only the PDU and associations, never the duplicated context. Repeated requests with unique kid\_context values accumulate contexts, each holding a copy of the master secret, salt, and derived keys, until memory is exhausted.

#### Validation

The duplicate is inserted before decryption and the error path has no context cleanup; no dynamic reproduction was performed.

Validation method: Static source review and source-backed call-path tracing

#### Dataflow

A request with a valid recipient KID and a unique unknown kid\_context enters the B.2 fallback, duplicates the context, and fails AEAD verification. Each request leaves one attached context behind; repeating with new kid\_context values grows memory without bound.

#### Reachability

Requires rfc8613\_b\_2 enabled and knowledge of a valid recipient KID, observable in OSCORE traffic or guessable in deployments using short KIDs.

#### Severity

**Medium** — An attacker who knows a valid KID can cause unbounded memory growth and eventual denial of service without possessing the OSCORE key. Appendix B.2 is a non-default feature.

Raise if B.2 is enabled on a long-running public server and the KID is predictable or observable. Lower if B.2 is disabled or contexts are periodically purged.

#### Remediation

Do not attach the duplicated context until the AEAD tag verifies, or explicitly free and unlink it on every decryption failure. Add a bound on the number of B.2 contexts and expire idle ones.

Tests:
- Send 1000 requests with unique kid\_context values and a known KID; assert the process context count and RSS remain bounded.
- Verify the error path frees the duplicate context under ASan/LSan.

Preventive controls:
- Cap per-context OSCORE contexts and use a reference-counted temporary context during verification.

<a id="finding-6"></a>

### [6] pdu\_408\_build writes the payload marker without checking capacity

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The unchecked marker write and the exact-fill token add are explicit in source. The claimed wire trigger is contradicted by the RFC 9177 Q-Block1 Size1/RTag requirement at src/coap\_block.c:3542-3547, so confidence is high that the defect is latent rather than remotely reachable on default UDP. |
| Category | memory-corruption |
| CWE | CWE-787 |
| Affected lines | src/coap\_block.c:1867-1880, src/coap\_pdu.c:395-412, src/coap\_pdu.c:439-446 |

#### Summary

pdu\_408\_build() ignores the return values of coap\_add\_token() and coap\_add\_option\_internal() and then unconditionally writes COAP\_PAYLOAD\_START at pdu-\>token\[pdu-\>used\_size++\], so it writes one byte past the heap allocation whenever the token exactly fills the PDU. The defect is real, but the previously claimed remote trigger is not reachable in the default configuration: a Q-Block1 request must also carry Size1 and RTag options plus a URI path to reach this path, and with the default 1152-byte UDP MTU the session PDU is about 1148 bytes, so a token large enough to fill used\_size leaves no room for those mandatory options; the request either omits them and is rejected with 4.00, or exceeds the MTU and is rejected during parsing, before pdu\_408\_build() runs. Reachability is limited to a build or transport that admits a PDU-filling token together with the mandatory Q-Block options, or to future caller misuse; no such trigger was demonstrated.

#### Validation

The token can consume exactly alloc\_size and the marker write is unconditional, confirming the defect. Reachability analysis shows the described Q-Block1 request cannot also carry the mandatory Size1 and RTag options within the default 1148-byte UDP PDU, so no remote trigger was demonstrated and the item is retained as a latent one-byte heap write.

Validation method: Static source review, arithmetic analysis, and reachability review

#### Dataflow

pdu\_408\_build() copies lg\_srcv-\>last\_token into a PDU sized to the session MTU, ignores a failed Content-Format option add, and then writes the payload marker unconditionally, so the marker lands one byte past the allocation when the token exactly fills the PDU. On default UDP this cannot be driven from the wire: the Q-Block1 request must also carry Size1 and RTag, which do not fit alongside a PDU-filling token.

#### Reachability

Latent. The sink is reached only for a Q-Block1 request with missing blocks, and RFC 9177 section 4.3 requires that request to carry Size1 and RTag (src/coap\_block.c:3542-3547) in addition to a URI path. With the default 1152-byte UDP MTU, coap\_session\_max\_pdu\_size() yields about 1148 bytes, so a token large enough to fill used\_size leaves no space for the mandatory options and the request is rejected before pdu\_408\_build() runs. Reaching the write requires a build or transport that admits both a PDU-filling token and the mandatory Q-Block options within one PDU, or a caller that supplies an oversized last\_token. No such configuration or trigger was demonstrated.

#### Severity

**Low** — The unchecked one-byte heap write is real and could corrupt allocator metadata, but the only identified caller cannot be driven with a PDU-filling token on the default UDP transport because the mandatory Q-Block1 Size1 and RTag options must fit in the same request. No remote trigger was demonstrated, so this is retained as a low-severity latent memory-safety defect.

Raise if a build or transport is shown to admit a PDU-filling extended token together with the mandatory Q-Block1 Size1 and RTag options, or if pdu\_408\_build() gains a caller that can pass an oversized last\_token. Keep low while the default UDP path rejects such requests.

#### Remediation

Check both coap\_add\_token() and coap\_add\_option\_internal() results. Call coap\_pdu\_check\_resize(pdu, pdu-\>used\_size + 1) before writing the marker; on failure, delete the PDU and return NULL so the caller defers the 4.08.

Tests:
- Under a build or transport that admits a maximum-size token alongside Q-Block1 Size1 and RTag options, send a Q-Block1 request with missing blocks and run under ASan; verify no heap-buffer-overflow.
- Add a unit test for pdu\_408\_build with a token that exactly fills the PDU.

Preventive controls:
- Always route payload marker insertion through a helper that performs a capacity check.

<a id="finding-7"></a>

### [7] Short OSCORE responses advance the replay window without rollback

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The sequence window is advanced at line 1371 and the short-ciphertext path at lines 1482-1501 omits the rollback that other failure paths perform. |
| Category | denial-of-service |
| CWE | CWE-400 |
| Affected lines | src/coap\_oscore.c:1364-1382, src/coap\_oscore.c:1481-1501, src/coap\_oscore.c:1541-1551 |

#### Summary

For a response carrying a Partial IV, coap\_oscore\_decrypt\_pdu() validates and advances rcp\_ctx-\>last\_seq before AEAD verification. If the ciphertext is too short, where encrypt\_len \<= tag\_len, the response branch jumps to error without calling oscore\_roll\_back\_seq(), unlike the request branch and the generic decrypt-failure path. An on-path attacker can forge a high-PIV short response that matches the token and association, causing later legitimate responses with lower PIVs to be rejected as replays.

#### Validation

The window advancement precedes decryption, and the short-ciphertext response branch lacks the rollback present in the adjacent failure paths.

Validation method: Static source review and source-backed attack-path tracing

#### Dataflow

An on-path attacker observes an outstanding OSCORE request or association and injects a response with a higher Partial IV but a ciphertext no longer than the AEAD tag. The client advances the replay window, then rejects the genuine response as a replay.

#### Reachability

Requires an OSCORE client, an on-path attacker able to forge a response with the expected token, and a partial IV in the response.

#### Severity

**Low** — The attacker must be on-path and able to inject a response matching an outstanding OSCORE request or association. Impact is limited to a client session denial of service.

Raise if the client uses long-lived OSCORE sessions or if the attack can be repeated cheaply across many associations.

#### Remediation

Call oscore\_roll\_back\_seq(rcp\_ctx) on every response decryption failure, including the encrypt\_len \<= tag\_len case, or defer last\_seq updates until after successful AEAD verification.

Tests:
- Inject a response with a high PIV and short ciphertext, then deliver a genuine lower-PIV response; assert the genuine response is accepted.
- Add a unit test that checks rollback\_valid is cleared and last\_seq is restored on the short-ciphertext path.

Preventive controls:
- Centralize response failure cleanup so every path rolls back the replay state.

<a id="finding-8"></a>

### [8] Uri-Path-Abbrev fallback retransmit drops the request body

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The code adds data to the old PDU and then assigns pdu = new; the duplicate helper copies only options. |
| Category | data-integrity |
| CWE | CWE-670 |
| Affected lines | src/coap\_net.c:1793-1811, src/coap\_pdu.c:271-281 |

#### Summary

When a server has rejected Uri-Path-Abbrev, coap\_send() duplicates the request with the abbreviation expanded into new. The payload is then appended to the original pdu via coap\_add\_data(pdu, ...), not to new, and the original is deleted. The duplicate contains options but no payload, so the retransmitted request silently loses its body.

#### Validation

The add target and free order are explicit. An independent strix run captured a wire trace showing the expanded options without the payload and a corrected build restoring the body.

Validation method: Static source review; independent comparator evidence

#### Dataflow

A client sends a body-bearing request with Uri-Path-Abbrev. The peer rejects the option, no\_path\_abbrev is set, and the retransmit path builds a duplicate but attaches the body to the old PDU before freeing it. The wire request has the expanded path and no payload marker/body.

#### Reachability

Client-side path; requires coap\_send with a body-bearing request containing Uri-Path-Abbrev and a peer known to reject the abbreviation.

#### Severity

**Low** — The impact is request-body loss for clients using Uri-Path-Abbrev against a peer that rejected it. It is a correctness/integrity issue, not a memory-safety issue.

Raise if the affected requests carry security-relevant commands or if the peer treats the empty body as a valid different request.

#### Remediation

Call coap\_add\_data(new, data\_len, data) and handle failure by deleting new and returning an error. If the duplicate helper is expected to preserve payload, extend it to copy data explicitly.

Tests:
- Send a PUT with Uri-Path-Abbrev and a body to a peer that rejects the option; assert the retransmitted datagram contains the payload marker and body.
- Add a regression test around coap\_pdu\_duplicate\_lkd with a body-bearing PDU.

Preventive controls:
- Make coap\_pdu\_duplicate\_lkd() copy data explicitly or document that callers must add it to the returned PDU.
