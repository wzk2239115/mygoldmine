# Threat Model

libcoap is a C implementation of CoAP used as a library and through example clients and servers. It parses UDP, TCP, TLS/DTLS, and WebSocket traffic; decodes options and bodies; implements block-wise transfer, observe, caching, proxying, persistence, and OSCORE. Network peers control packets and metadata, while applications choose resources, authentication, and deployment exposure. The critical invariant is that untrusted wire data must be length-checked and bounded before it reaches indexes, arithmetic, copies, allocations, formatting, or protocol state transitions.

## Assets

- Integrity and confidentiality of CoAP resources, request and response bodies, and OSCORE or DTLS/TLS-protected content
- Process memory and control flow of applications embedding libcoap
- Availability of CoAP servers, clients, proxies, and resource-directory services
- Credentials and key material used by DTLS/TLS, OSCORE, PSK, PKI, and configuration paths
- CoAP endpoint identity, token and request correlation, block-wise reassembly, observe state, and proxy routing decisions

## Trust Boundaries

- Unauthenticated or authenticated network peers to UDP/TCP/WS listeners and client response processing
- DTLS/TLS/OSCORE authenticated content versus plaintext parsing and error-reporting paths
- CoAP wire message and option encoding to internal parsed PDU structures and application callbacks
- Client, server, and proxy application layer to filesystem persistence, resource-directory records, and configured credentials
- Test and fuzz harnesses from production library paths; fixtures demonstrate parser behavior but are not themselves deployed services

## Attacker Capabilities

- Send arbitrary CoAP datagrams or streams, including malformed headers, options, token lengths, block options, observe operations, and bodies
- Control message size, option repetition and order, extended option widths and deltas, URI paths, content-format values, and block-wise state
- Potentially hold a valid DTLS/TLS/PSK/OSCORE identity and send authenticated but otherwise adversarial messages
- Supply malicious responses to clients, or interact with proxies and resource-directory endpoints where enabled
- Cannot assume operator-level configuration changes, local filesystem access, or access to private keys unless source evidence establishes them

## Security Objectives

- Reject malformed or oversized wire input without out-of-bounds access, integer overflow, uncontrolled allocation, or persistent resource exhaustion
- Preserve message parsing and protocol state isolation across peers and concurrent requests
- Enforce authenticated-message integrity and the intended scope of OSCORE, DTLS, and TLS protections
- Prevent untrusted URIs, proxy targets, persistence input, or cache keys from escaping expected resource boundaries
- Avoid disclosing usable credentials or private keys through source-distributed files

## Assumptions

- Network-facing library code is reachable wherever an application exposes a CoAP listener; endpoint configuration and credentials are application policy.
- The current snapshot is the authorized release source; previous commits are not available for comparison because the checkout is grafted.
- A denial-of-service finding requires a source-backed repeatable trigger with meaningful service impact, not merely an error path.

---

## Saved Model Context

- Source: scan
- Scan: 7b3d1e49-deec-4915-bb10-983e5c2b9711
- Target: libcoap
- Revision: a4de0faea54d3d548924c8b9f6e67b72a36cbac3
- Snapshot: codex-security-snapshot/v1:sha256:868747fbdfeec18f41a2ef392ede1963b4708eed591631e4cc97641062afea81
- Result status: completed
- Model origin: not recorded
- Model scope: not recorded
- Scan scope: .
- Scan scope description: Repository-wide static review of libcoap 4.3.5 (revision a4de0fae) covering CoAP PDU and option parsing, WebSocket framing and close, block-wise Block1/Q-Block reassembly, OSCORE decryption and external credential lookup, Appendix B.1.2/B.2 state, and URI/proxy handling. Six source-backed findings identify the attacker path and the deployment conditions required for impact.
