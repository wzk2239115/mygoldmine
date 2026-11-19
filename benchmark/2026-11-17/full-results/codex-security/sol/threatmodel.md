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

---

## Saved Model Context

- Source: scan
- Scan: e2734f35-14d6-4012-968e-66758e9463d2
- Target: sol
- Revision: 373d84877d22031b45a7f3599297f691eab09230
- Snapshot: codex-security-snapshot/v1:sha256:90a9aaf0853034ca9c071ef712b2764bb7029ccab11863cb27f966f728f30f92
- Result status: completed
- Model origin: not recorded
- Model scope: not recorded
- Scan scope: .
