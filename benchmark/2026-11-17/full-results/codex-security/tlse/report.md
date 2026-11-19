# Security Review: tlse

## Scope

Repository-wide review of all 16 files: tlse.c, tlse.h, libtomcrypt.c, x509.c, examples, build files, documentation, and test data.

- Scan mode: repository
- Target kind: git\_worktree
- Target ID: target\_sha256\_262c3bd2eecacfe3aa17f94aa955c7af79583c3e1ace7cea825e015292cebbb8
- Revision: 25be48a4f0176b7242d8c5955fc325e92b487838
- Snapshot digest: codex-security-snapshot/v1:sha256:242ce2c1abcccb1053600439d0f378cb8e3e7d3cc9548d4372d9d4bb8f8df073
- Included paths: .
- Excluded paths: none
- Artifacts reviewed: CMakeLists.txt, LICENSE, README.md, examples/CMakeLists.txt, examples/tlsclienthello.c, examples/tlshelloworld.c, examples/tlslayer.png, examples/tlssimple.c, examples/tlssimpleserver.c, libtomcrypt.c, root.pem, tls\_root\_ca.h, tlse.c, tlse.h, tlslayer\_ssltest.png, x509.c
- Scan context: Standard repository scan of the TLSe TLS/DTLS library, focused on pre-authentication memory-safety in network parsers.

Limitations and exclusions:
- Findings are source-confirmed but were not reproduced under ASan or a debugger.
- The bundled libtomcrypt.c was reviewed for call-site safety rather than exhaustively audited.
- x509.c is only compiled when TLS\_FULL\_X509 is defined and was reviewed for context, not as the default parser.

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 3 |
| Severity mix | high: 2, medium: 1 |
| Confidence mix | high: 3 |
| Validation mode | Static source review |

Canonical artifacts: `scan-manifest.json` and `findings.json`. This report is a deterministic projection of those files.

## Threat Model

TLSe is a single-file C TLS/DTLS 1.0-1.3 implementation with WebRTC, STUN, and SRTP helpers. Its attack surface is untrusted network bytes consumed by tls\_consume\_stream, tls\_peerconnection\_iterate, and the certificate ASN.1 parser. The primary boundary is the pre-authentication record/handshake parser: attacker-controlled lengths and offsets reach memory copies before peer authentication or certificate verification.

### Assets

- Process memory of the TLS/DTLS server or client
- TLS/DTLS session keys and peer credentials
- Availability of the service terminating TLS, DTLS, or WebRTC
- Certificate-derived trust decisions

### Trust Boundaries

- Untrusted network datagram and record bytes -\> tls\_consume\_stream
- Untrusted STUN datagrams -\> tls\_peerconnection\_iterate and tls\_stun\_parse
- Untrusted certificate DER -\> tls\_parse\_certificate and the ASN.1 parser
- Pre-authentication handshake state -\> authenticated session state

### Attacker Capabilities

- Send arbitrary TLS, DTLS, and STUN datagrams to a listening endpoint
- Control record lengths, handshake fragment headers, STUN attribute lengths, and certificate DER contents
- Act as the peer or as a malicious server/client before certificate verification

### Security Objectives

- Confine every network-derived length and offset to its allocated buffer
- Reject malformed records, fragments, attributes, and certificates without memory corruption
- Never perform length arithmetic or copies before validating attacker-controlled counts

### Assumptions

- The embedding application exposes TLSe parsing to network input
- The default build does not define TLS\_FULL\_X509, so the bundled ASN.1 parser is compiled
- Validation is source-level; no runtime exploit was executed

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [Overlapping DTLS fragments overflow the stack reassembly buffer](#finding-1) | high | high | inline below |
| [STUN USERNAME and REALM attributes overflow the credential key buffer](#finding-2) | high | high | inline below |
| [Zero-length certificate BIT STRING underflows into an unbounded memcpy](#finding-3) | medium | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] Overlapping DTLS fragments overflow the stack reassembly buffer

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The fragment header arithmetic, the unchecked written += fragment\_length, the stack array size, and the final memcpy are all visible in source. A concrete six-record sequence was traced arithmetically. No runtime crash was executed because the scan environment has no C compiler. |
| Category | memory-corruption |
| CWE | CWE-121, CWE-787 |
| Affected lines | tlse.c:12434, tlse.c:12524-12550, tlse.c:9801-9850, tlse.c:14006-14066 |

#### Summary

tls\_consume\_stream() accumulates each DTLS handshake fragment's fragment\_length into fragment-\>written without ever checking that written + fragment\_length still fits the declared data\_length. The backing heap buffer is allocated as data\_length \* sizeof(char \*), so repeated overlapping fragments (fragment\_offset = 0) keep the heap copies in bounds while written grows far past data\_length. A later DTLS record with data\_length == fragment\_length takes the non-fragmented path and reaches tls\_parse\_payload(), which copies fragment-\>written bytes into a 0x4000C-byte stack buffer. A remote sender can drive written to 0x4FB00 with five 0xFF00-byte fragments (each record fits in a UDP datagram) and overflow the stack by roughly 64 KB with attacker-controlled and uninitialized heap bytes.

#### Validation

Traced a concrete sequence: five records with data\_length=0x40000, fragment\_offset=0, fragment\_length=0xFF00 accumulate written=0x4FB00 without equalling len; a sixth 13-byte-payload record with data\_length=fragment\_length=1 and handshake length 1 enters tls\_parse\_payload, passes the CHECK\_SIZE(1, 0x4FB00) minimum check, and memcpys 0x4FB00 bytes into a 0x4000C-byte stack array, overflowing it by 64,256 bytes.

Validation method: Static source review

- **Status:** validated

#### Dataflow

Attacker-controlled 24-bit data\_length, fragment\_offset and fragment\_length fields drive an unchecked accumulation that is later copied into a fixed stack array.

- **Source:** DTLS record and handshake-fragment header bytes from an untrusted datagram

- **Sink:** memcpy(local\_buffer + 12, context-\>dtls\_data-\>fragment-\>buffer, context-\>dtls\_data-\>fragment-\>written) at tlse.c:9847

- **Outcome:** Stack buffer overflow of approximately 0xF000 bytes with attacker-controlled and uninitialized heap data

Transformations:
- record length = 16-bit DTLS length + 13-byte header
- data\_length = 24-bit handshake length
- fragment\_offset and fragment\_length = 24-bit fields
- fragment\_length + 12 \<= length - 13 and fragment\_offset + fragment\_length \<= data\_length are enforced
- written += fragment\_length is not bounded by data\_length
- written != len keeps the fragment pending across records

**The only bounds check compares offset+fragment\_length to data\_length and ignores the running written count** — `tlse.c:12524-12527`

data\_length is capped at 0x40000 and each fragment must fit inside data\_length, but nothing relates the accumulated written count to data\_length during later fragments.

```
                if ((data_length > DTLS_MAX_FRAGMENT_SIZE) || (fragment_offset + fragment_length > data_length)) {
                    DEBUG_PRINT3("INVALID PACKET SIZE: %i, FRAGMENT OFFSET: %i, FRAGMENT LENGTH: %i\n", data_length, fragment_offset, fragment_length);
                    return TLS_BROKEN_PACKET;
                }
```

**Fragment bytes are copied at an attacker offset and written grows by fragment\_length on every record** — `tlse.c:12543-12550`

The allocation is eight bytes per data\_length byte, so repeated copies at offset 0 stay in the heap allocation, while written can reach 0x4FB00 without ever equalling len == 0x40000 and therefore stays pending.

```
                    fragment_buffer = (char *)TLS_REALLOC(fragment_buffer, data_length * sizeof(char *));
                    if (!fragment_buffer)
                        return TLS_NO_MEMORY;

                    memcpy(fragment_buffer + fragment_offset, &buffer[12], fragment_length);
                    context->dtls_data->fragment->buffer = fragment_buffer;
                    context->dtls_data->fragment->len = data_length;
                    context->dtls_data->fragment->written += fragment_length;
```

**Reassembly target is a fixed 0x4000C-byte stack array** — `tlse.c:9801-9802`

DTLS\_MAX\_FRAGMENT\_SIZE is 0x40000, so local\_buffer holds 262156 bytes.

```
int tls_parse_payload(struct TLSContext *context, const unsigned char *buf, int buf_len, tls_validation_function certificate_verify) {
    unsigned char local_buffer[DTLS_MAX_FRAGMENT_SIZE + 12];
```

**The accumulated count is copied into the stack buffer without a size check** — `tlse.c:9847-9850`

CHECK\_SIZE at line 9832 only ensures written is at least the small final record's handshake length; it does not cap written at the destination size or at data\_length.

```
                memcpy(local_buffer + 12, context->dtls_data->fragment->buffer, context->dtls_data->fragment->written);

                buf = local_buffer;
                buf_len = context->dtls_data->fragment->written + 12;
```

#### Reachability

Any application that feeds untrusted DTLS records to tls\_consume\_stream is affected. The bundled WebRTC wrapper also forwards DTLS after a STUN binding has set remote\_state.

- **Attacker:** Remote unauthenticated network sender to a DTLS listener, or a WebRTC peer that can complete a STUN binding (holds the advertised ICE password)

- **Entry point:** tls\_consume\_stream (tlse.c:12434); tls\_peerconnection\_iterate (tlse.c:14006-14066)

- **Source:** Network datagram bytes

- **Sink:** tls\_parse\_payload stack memcpy

- **Outcome:** Remote stack memory corruption / crash with potential code execution

Preconditions:
- The application uses TLSe for DTLS (context-\>dtls is set) and parses attacker-reachable datagrams
- For the WebRTC wrapper, channel-\>remote\_state must be non-zero, normally after a successful STUN binding request
- cipher\_spec\_set is 0, which is true during the initial DTLS handshake

**Fragment handling runs before cipher\_spec\_set and the WebRTC wrapper forwards raw DTLS records** — `tlse.c:12505-12508`

Initial DTLS handshake records are parsed before any authenticated cipher state exists, and tls\_peerconnection\_iterate passes network datagrams to tls\_consume\_stream after the STUN association gate.

```
        if ((context->dtls) && (!context->cipher_spec_set)) {
            /*  check fragmented! */
            unsigned char *buffer = &context->message_buffer[index];
            if ((buffer[0] == TLS_HANDSHAKE) && (length > 13)) {
```

**The accumulated count is copied into the stack buffer without a size check** — `tlse.c:9847-9850`

CHECK\_SIZE at line 9832 only ensures written is at least the small final record's handshake length; it does not cap written at the destination size or at data\_length.

```
                memcpy(local_buffer + 12, context->dtls_data->fragment->buffer, context->dtls_data->fragment->written);

                buf = local_buffer;
                buf_len = context->dtls_data->fragment->written + 12;
```

#### Severity

**High** — The DTLS fragment accumulator is reached before any handshake authentication when cipher\_spec\_set is 0, and the final memcpy has an attacker-influenced length and attacker-influenced content. A stack out-of-bounds write of tens of kilobytes can overwrite saved state and return addresses, giving a repeatable remote crash and a plausible code-execution primitive. Full control-flow hijack was not demonstrated, so the finding is High rather than Critical.

Rejecting fragments whose accumulated written count exceeds data\_length, or refusing to expose tls\_consume\_stream to untrusted datagrams, removes the primitive. A stack-protector build would turn the overflow into a detected abort, leaving a remote DoS.

#### Remediation

Track filled bytes independently of the declared length, reject any fragment for which fragment\_offset + fragment\_length exceeds data\_length or for which written + fragment\_length would exceed data\_length, size the fragment allocation to data\_length (not data\_length \* sizeof(char \*)), and require written + 12 \<= sizeof(local\_buffer) before the stack copy. Prefer rejecting overlapping fragments entirely.

Tests:
- Send five overlapping 0xFF00-byte fragments with data\_length=0x40000 followed by a small data\_length==fragment\_length record; assert TLS\_BROKEN\_PACKET before the memcpy and no ASan report.
- Fuzz DTLS fragment\_offset/fragment\_length/data\_length combinations and assert written never exceeds data\_length.

<a id="finding-2"></a>

### [2] STUN USERNAME and REALM attributes overflow the credential key buffer

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The attribute length caps, the 1230-byte array, the concatenation order, and the 24-byte local\_pwd buffer are all explicit in source. The 47-byte maximum overflow was computed from those values. No runtime reproduction was performed. |
| Category | memory-corruption |
| CWE | CWE-121, CWE-787 |
| Affected lines | tlse.c:13070, tlse.c:13085, tlse.c:13201-13219, tlse.c:14000-14006 |

#### Summary

tls\_stun\_parse() accepts a USERNAME attribute of up to 513 bytes and a REALM attribute of up to 763 bytes, then concatenates username + ':' + realm + ':' + password into char key\[0x4CE\] (1230 bytes). Even before the 24-byte local password is appended, 513 + 1 + 763 = 1277 bytes overwrite the end of key by 47 bytes. The code also advances the pointer by username\_len instead of realm\_len after copying the realm. The overflow happens while processing MESSAGE-INTEGRITY, before the HMAC comparison, so a sender does not need valid credentials.

#### Validation

Confirmed that local\_pwd is a 25-byte array filled with 24 characters and NUL, that USERNAME and REALM each permit the maximum lengths above, and that the realm memcpy occurs inside the MESSAGE-INTEGRITY branch before the HMAC comparison at line 13240.

Validation method: Static source review

- **Status:** validated

#### Dataflow

Attacker-controlled STUN attribute lengths are copied into a fixed stack key buffer before the MESSAGE-INTEGRITY HMAC is verified.

- **Source:** STUN USERNAME and REALM attribute values in a binding request

- **Sink:** memcpy(ptr, realm, realm\_len) into char key\[0x4CE\] at tlse.c:13210

- **Outcome:** Stack out-of-bounds write of up to 47 bytes past key, followed by writes based on the wrong pointer advance

Transformations:
- tls\_is\_stun checks only the magic cookie
- USERNAME attr\_len \<= 513
- REALM attr\_len \<= 763
- key = username + ':' + realm + ':' + local\_pwd
- MESSAGE-INTEGRITY handling builds the key before memcmp of the HMAC

**The credential key is a fixed 1230-byte stack array** — `tlse.c:13078-13085`

0x4CE equals 1230, the maximum space available for username:realm:password.

```
    unsigned char hash[20];
    unsigned long hash_len;
    unsigned char md5_hash[16];
    hmac_state hmac;
    hash_state md5_state;
    int stun_message_len;
    unsigned char secret[16];
    char key[0x4CE];
```

**USERNAME may be 513 bytes** — `tlse.c:13182-13189`

The limit is one byte larger than the 512 bytes that would fit with other fields.

```
            case 0x0006:
                /*  USERNAME */
                if (attr_len > 513)
                    return TLS_BROKEN_PACKET;

                username = msg;
                username_len = attr_len;
                break;
```

**REALM may be 763 bytes** — `tlse.c:13252-13258`

513 + 1 + 763 = 1277 bytes is already 47 bytes past the 1230-byte key before the password is copied.

```
            case 0x0014:
                /*  REALM */
                if (attr_len > 763)
                    return TLS_BROKEN_PACKET;
                realm = msg;
                realm_len = attr_len;
                break;
```

**The realm copy overflows key and the pointer is advanced by the wrong length** — `tlse.c:13201-13219`

memcpy(ptr, realm, realm\_len) starts at key + username\_len + 1 and has no remaining-capacity check. The subsequent ptr += username\_len does not repair the overflow.

```
                if ((realm) && (realm_len > 0)) {
                    ptr = key;
                    memcpy(ptr, username, username_len);
                    ptr += username_len;

                    *ptr = ':';
                    ptr ++;

                    if ((realm) && (realm_len > 0)) {
                        memcpy(ptr, realm, realm_len);
                        ptr += username_len;
                        *ptr = ':';
                        ptr ++;
                    }

                    memcpy(ptr, pwd, pwd_len);
                    ptr += pwd_len;

                    *ptr = 0;
```

**The WebRTC ingest path reaches tls\_stun\_parse on a magic-cookie match** — `tlse.c:14000-14006`

tls\_is\_stun only checks that bytes 4-7 equal 0x2112A442, so an unauthenticated datagram reaches the credential build before the HMAC check at line 13240.

```
    if (tls_is_stun(buf, buf_len)) {
        unsigned char response_buffer[0x8000];
        int len;
        unsigned short type;
        DEBUG_PRINT0("RECEIVED STUN PACKET\n");

        len = tls_stun_parse(buf, buf_len, channel->local_pwd, strlen(channel->local_pwd), is_ipv6, addr, port, response_buffer);
```

#### Reachability

A single crafted STUN binding request to a TLSe WebRTC/STUN endpoint triggers the overflow without knowing the ICE password.

- **Attacker:** Remote unauthenticated UDP sender that can reach the peerconnection port

- **Entry point:** tls\_peerconnection\_iterate -\> tls\_stun\_parse

- **Source:** STUN attribute bytes

- **Sink:** key stack buffer

- **Outcome:** Pre-authentication stack memory corruption / crash in the STUN handler

Preconditions:
- The target uses tls\_peerconnection\_iterate (or calls tls\_stun\_parse directly)
- The request type is 0x0001 (binding request) and bytes 4-7 match the STUN magic cookie
- USERNAME precedes REALM, and MESSAGE-INTEGRITY (20 bytes) follows both

**The WebRTC ingest path reaches tls\_stun\_parse on a magic-cookie match** — `tlse.c:14000-14006`

tls\_is\_stun only checks that bytes 4-7 equal 0x2112A442, so an unauthenticated datagram reaches the credential build before the HMAC check at line 13240.

```
    if (tls_is_stun(buf, buf_len)) {
        unsigned char response_buffer[0x8000];
        int len;
        unsigned short type;
        DEBUG_PRINT0("RECEIVED STUN PACKET\n");

        len = tls_stun_parse(buf, buf_len, channel->local_pwd, strlen(channel->local_pwd), is_ipv6, addr, port, response_buffer);
```

**The realm copy overflows key and the pointer is advanced by the wrong length** — `tlse.c:13201-13219`

memcpy(ptr, realm, realm\_len) starts at key + username\_len + 1 and has no remaining-capacity check. The subsequent ptr += username\_len does not repair the overflow.

```
                if ((realm) && (realm_len > 0)) {
                    ptr = key;
                    memcpy(ptr, username, username_len);
                    ptr += username_len;

                    *ptr = ':';
                    ptr ++;

                    if ((realm) && (realm_len > 0)) {
                        memcpy(ptr, realm, realm_len);
                        ptr += username_len;
                        *ptr = ':';
                        ptr ++;
                    }

                    memcpy(ptr, pwd, pwd_len);
                    ptr += pwd_len;

                    *ptr = 0;
```

#### Severity

**High** — tls\_peerconnection\_iterate sends every datagram whose first bytes match the STUN magic cookie to tls\_stun\_parse, and the USERNAME/REALM values are fully attacker-controlled. The resulting stack out-of-bounds write occurs pre-authentication in a WebRTC-facing handler and can corrupt adjacent stack state, producing a repeatable remote crash or a control-flow corruption primitive. The 47-byte window bounds the attacker's direct control, and code execution was not demonstrated, so the finding is High rather than Critical.

Enforcing username\_len + realm\_len + pwd\_len + 2 \<= sizeof(key) and advancing the pointer by realm\_len removes the overflow. A build without TLS\_SRTP/WebRTC or with stack protector reduces the impact.

#### Remediation

Compute the total credential length first and reject unless username\_len + 1 + realm\_len + 1 + pwd\_len + 1 \<= sizeof(key). Advance ptr by realm\_len after the realm copy, cap both attributes to values that leave room for the password and separators, and avoid placing attacker-sized concatenations in a fixed stack buffer.

Tests:
- Send a binding request with a 513-byte USERNAME, a 763-byte REALM, and a 20-byte MESSAGE-INTEGRITY value; assert the parser rejects the credential build without writing past key.
- Repeat with a valid MESSAGE-INTEGRITY and assert the same bound holds.

<a id="finding-3"></a>

### [3] Zero-length certificate BIT STRING underflows into an unbounded memcpy

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | The exact level/idx/fields condition, the unchecked val\[0\] read, the len-- that produces -1, and the memcpy whose length is an int converted to size\_t are all explicit in source. glibc malloc(0) returning non-NULL is the documented allocator behavior. No runtime crash was executed. |
| Category | memory-corruption |
| CWE | CWE-191, CWE-787, CWE-125 |
| Affected lines | tlse.c:8637-8702, tlse.c:11580-11590, tlse.c:4597-4604, tlse.c:4546-4557 |

#### Summary

In the default build (TLS\_FULL\_X509 is not defined), the ASN.1 certificate parser passes the outer signatureValue BIT STRING to tls\_certificate\_set\_sign\_key(). For a zero-length BIT STRING (DER 03 00), length is 0; tls\_certificate\_set\_sign\_key reads val\[0\], the byte after the TLV, and when that byte is zero it decrements len to -1. tls\_certificate\_set\_copy then treats -1 as a non-zero length, calls TLS\_MALLOC(len + 1) == malloc(0), and on glibc receives a non-NULL pointer, after which memcpy(\*member, val, (size\_t)-1) and (\*member)\[-1\] = 0 corrupt memory far beyond the allocation. The certificate is parsed before the application certificate\_verify callback, so an untrusted TLS peer reaches this pre-verification.

#### Validation

Traced the DER path from tls\_parse\_certificate through \_private\_asn1\_parse to tls\_certificate\_set\_sign\_key and tls\_certificate\_set\_copy, confirming that a 03 00 BIT STRING at level 2/idx 3 with a zero following byte yields len -1, malloc(0), and a SIZE\_MAX memcpy before certificate\_verify is called.

Validation method: Static source review

- **Status:** validated

#### Dataflow

A crafted DER certificate with a zero-length outer BIT STRING drives an integer underflow that becomes an unbounded memcpy.

- **Source:** DER bytes of a certificate in a TLS Certificate handshake message

- **Sink:** memcpy(\*member, val, len) in tls\_certificate\_set\_copy at tlse.c:4553

- **Outcome:** Unbounded heap overwrite and one-byte heap underflow before certificate verification

Transformations:
- Certificate DER is parsed by tls\_parse\_certificate -\> asn1\_parse -\> \_private\_asn1\_parse
- outer SEQUENCE has tbsCertificate at level 2/idx 1, signatureAlgorithm at idx 2, signatureValue BIT STRING at idx 3
- BIT STRING length 0
- val\[0\] is the attacker-controlled byte after the TLV, set to 0
- len becomes -1
- malloc(len + 1) is malloc(0); glibc returns non-NULL
- memcpy length -1 converts to SIZE\_MAX

**A level-2 signatureValue BIT STRING is passed to set\_sign\_key with its declared length** — `tlse.c:11580-11590`

A zero-length BIT STRING reaches this branch with length == 0; level 2, idx 3 and fields\[0\] == 1 identify the outer certificate signatureValue.

```
                case 0x03:
                    if (_is_field(fields, pk_id)) {
                        if (has_key)
                            *has_key = 1;
                    }
                    /*  bitstream */
                    DEBUG_PRINT1("BITSTREAM(%i): ", length);
                    DEBUG_DUMP_HEX(&buffer[pos], length);
                    DEBUG_PRINT0("\n");
                    if ((level == 2) && (idx == 3) && (fields[0] == 1)) {
                        tls_certificate_set_sign_key(cert, &buffer[pos], length);
```

**set\_sign\_key decrements the length whenever the next byte is zero, including at length zero** — `tlse.c:4597-4605`

There is no len \> 0 guard before reading val\[0\], so a zero-length BIT STRING followed by a zero byte produces len == -1.

```
void tls_certificate_set_sign_key(struct TLSCertificate *cert, const unsigned char *val, int len) {
    if (!val[0]) {
        val++;
        len--;
    }
    tls_certificate_set_copy(&cert->sign_key, val, len);
    if (cert->sign_key)
        cert->sign_len = len;
}
```

**A non-zero negative length reaches malloc(len+1) and memcpy** — `tlse.c:4546-4558`

len == -1 is truthy, len + 1 == 0, and memcpy converts -1 to SIZE\_MAX; (\*member)\[-1\] is also written.

```
void tls_certificate_set_copy(unsigned char **member, const unsigned char *val, int len) {
    if (!member)
        return;
    TLS_FREE(*member);
    if (len) {
        *member = (unsigned char *)TLS_MALLOC(len + 1);
        if (*member) {
            memcpy(*member, val, len);
            (*member)[len] = 0;
        }
    } else
        *member = NULL;
}
```

**Certificate parsing happens before the verification callback** — `tlse.c:8702`

tls\_parse\_certificate calls asn1\_parse on each certificate and only invokes certificate\_verify after parsing returns.

```
            cert = asn1_parse(context, &buf[res2], certificate_size2, is_server);
```

#### Reachability

Any TLS peer that can present a certificate before verification triggers the parser. On the client this is the remote server's certificate; on the server this is a client certificate when client authentication is requested.

- **Attacker:** Malicious TLS server to a TLSe client, or an unauthenticated TLS client to a server that requests client authentication

- **Entry point:** tls\_parse\_certificate (tlse.c:8637) via the Certificate handshake message

- **Source:** Certificate handshake bytes

- **Sink:** tls\_certificate\_set\_copy

- **Outcome:** Pre-verification remote crash / heap corruption

Preconditions:
- The library is built without TLS\_FULL\_X509 (the default CMake and amalgamation builds)
- The handshake reaches a Certificate message (TLS 1.2 connection\_status 1, or TLS 1.3 connection\_status 2)
- The certificate contains a DER BIT STRING with length zero followed by a zero byte; a following zero-length certificate entry or trailing handshake byte supplies that byte

**Certificate parsing happens before the verification callback** — `tlse.c:8702`

tls\_parse\_certificate calls asn1\_parse on each certificate and only invokes certificate\_verify after parsing returns.

```
            cert = asn1_parse(context, &buf[res2], certificate_size2, is_server);
```

**A level-2 signatureValue BIT STRING is passed to set\_sign\_key with its declared length** — `tlse.c:11580-11590`

A zero-length BIT STRING reaches this branch with length == 0; level 2, idx 3 and fields\[0\] == 1 identify the outer certificate signatureValue.

```
                case 0x03:
                    if (_is_field(fields, pk_id)) {
                        if (has_key)
                            *has_key = 1;
                    }
                    /*  bitstream */
                    DEBUG_PRINT1("BITSTREAM(%i): ", length);
                    DEBUG_DUMP_HEX(&buffer[pos], length);
                    DEBUG_PRINT0("\n");
                    if ((level == 2) && (idx == 3) && (fields[0] == 1)) {
                        tls_certificate_set_sign_key(cert, &buffer[pos], length);
```

#### Severity

**Medium** — The parser is reachable by any TLS peer that supplies a certificate: a malicious server to a TLSe client, or a client to a server that requests client authentication. The size\_t conversion turns the copy into an effectively unbounded heap write that will fault after overwriting mapped memory, giving a reliable remote crash and a one-byte heap underflow. Code execution was not demonstrated and the overwrite is not attacker-steered beyond its start address, so impact is bounded to availability and limited heap corruption; this is Medium.

Rejecting zero-length signature BIT STRINGs or requiring len \>= 1 after the leading-zero adjustment removes the underflow. A build with TLS\_FULL\_X509 compiles a different parser and is not affected by this path.

#### Remediation

Require length \>= 1 before reading val\[0\] and reject zero-length signature BIT STRINGs. In tls\_certificate\_set\_copy, reject negative lengths explicitly instead of relying on the truthiness of an int. Do not allocate zero bytes for a non-empty logical value.

Tests:
- Feed a certificate whose outer signatureValue is 03 00 followed by 00 and assert TLS\_BROKEN\_PACKET or TLS\_UNSUPPORTED\_CERTIFICATE without a memcpy.
- Run the certificate parser under ASan and assert no heap-buffer-overflow for zero-length BIT STRING inputs.
