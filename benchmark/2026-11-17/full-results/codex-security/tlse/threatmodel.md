# Threat Model

TLSe is a single-file C TLS/DTLS 1.0-1.3 implementation with WebRTC, STUN, and SRTP helpers. Its attack surface is untrusted network bytes consumed by tls_consume_stream, tls_peerconnection_iterate, and the certificate ASN.1 parser. The primary boundary is the pre-authentication record/handshake parser: attacker-controlled lengths and offsets reach memory copies before peer authentication or certificate verification.

## Assets

- Process memory of the TLS/DTLS server or client
- TLS/DTLS session keys and peer credentials
- Availability of the service terminating TLS, DTLS, or WebRTC
- Certificate-derived trust decisions

## Trust Boundaries

- Untrusted network datagram and record bytes -> tls_consume_stream
- Untrusted STUN datagrams -> tls_peerconnection_iterate and tls_stun_parse
- Untrusted certificate DER -> tls_parse_certificate and the ASN.1 parser
- Pre-authentication handshake state -> authenticated session state

## Attacker Capabilities

- Send arbitrary TLS, DTLS, and STUN datagrams to a listening endpoint
- Control record lengths, handshake fragment headers, STUN attribute lengths, and certificate DER contents
- Act as the peer or as a malicious server/client before certificate verification

## Security Objectives

- Confine every network-derived length and offset to its allocated buffer
- Reject malformed records, fragments, attributes, and certificates without memory corruption
- Never perform length arithmetic or copies before validating attacker-controlled counts

## Assumptions

- The embedding application exposes TLSe parsing to network input
- The default build does not define TLS_FULL_X509, so the bundled ASN.1 parser is compiled
- Validation is source-level; no runtime exploit was executed

---

## Saved Model Context

- Source: scan
- Scan: 49339c8b-6c5a-48f0-82ce-21caa9ee8c8c
- Target: tlse
- Revision: 25be48a4f0176b7242d8c5955fc325e92b487838
- Snapshot: codex-security-snapshot/v1:sha256:242ce2c1abcccb1053600439d0f378cb8e3e7d3cc9548d4372d9d4bb8f8df073
- Result status: completed
- Model origin: not recorded
- Model scope: not recorded
- Scan scope: .
- Scan scope description: Repository-wide review of all 16 files: tlse.c, tlse.h, libtomcrypt.c, x509.c, examples, build files, documentation, and test data.
