# Security Review: pure-ftpd

## Scope

Repository-wide Standard scan of pure-ftpd 1.0.54 source snapshot. Focused review covered FTP control/data parsing, filesystem policy enforcement, PureDB/IP access rules, TLS/SNI helpers, authentication backends, quotas, upload notification, and local parsing utilities.

- Scan mode: repository
- Target kind: git\_worktree
- Target ID: target\_sha256\_842d551aeee2890af95a1fa77db8001fc2141dff5911f86adc004876eb72056b
- Revision: b64c56dc81bc4a7fa5d09d76afa59012ca5509a6
- Snapshot digest: codex-security-snapshot/v1:sha256:dde2c6b218b6b149b8492d93c4fd5db7e5d34594fbe5f5bef68006afbd6c559e
- Included paths: .
- Excluded paths: none
- Artifacts reviewed: src/ftpd.c, src/ftp\_parser.c, src/ls.c, src/log\_puredb.c, puredb/src/puredb\_read.c, puredb/src/puredb\_write.c, src/quotas.c, src/quotas.h, src/log\_pam.c, src/log\_ldap.c, src/log\_extauth.c, src/log\_mysql.c, src/log\_pgsql.c, src/log\_unix.c, src/tls.c, src/tls\_extcert.c, src/pure-certd.c, src/pure-authd.c, src/privsep.c, src/upload-pipe.c, src/pure-uploadscript.c, src/altlog.c, src/pure-pwconvert.c, src/ipstack.c, src/safe\_rw.c, src/crypto.c, src/main.c, src/simpleconf.c, src/parser.c, src/pure-pw.c, src/pure-pw.h, src/pure-quotacheck.c, src/ftpwho-read.c, src/pure-ftpwho.c, src/utils.c
- Scan context: Repository-wide Standard scan of pure-ftpd 1.0.54 source snapshot; runtime configuration and compiled binaries are not supplied.

Limitations and exclusions:
- No compiler or runnable server binary was available for dynamic reproduction
- Optional authentication and TLS paths depend on deployment-specific configuration
- Local administrative utilities were reviewed for remote reachability, not exhaustively fuzzed

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 3 |
| Severity mix | low: 3 |
| Confidence mix | high: 3 |
| Validation mode | source-backed static validation with local libc behavior checks |

Canonical artifacts: `scan-manifest.json` and `findings.json`. This report is a deterministic projection of those files.

## Threat Model

Pure-FTPd 1.0.54 is a network-facing FTP server. Untrusted remote clients speak FTP over cleartext or TLS and can authenticate as anonymous or virtual/real users. After authentication, the server exposes filesystem operations constrained by chroot/jail and per-user permissions; optional backends (PureDB, PAM, LDAP, SQL, external auth), TLS SNI helpers, upload scripts, quotas, logging, and local admin utilities create additional trust boundaries. The primary assets are host files outside the FTP jail, credentials and authentication decisions, user files and quotas, helper process integrity, and service availability.

### Assets

- host filesystem and files outside chroot
- user credentials and authentication backend data
- FTP user files and quota accounting
- TLS private keys and certificate selection
- service availability and privileged helper processes
- audit logs and session metadata

### Trust Boundaries

- unauthenticated network client to FTP control parser
- authenticated FTP user to chrooted filesystem namespace
- FTP daemon to root-owned configuration, PureDB and quota files
- FTP daemon to external auth/cert helper processes
- TLS client SNI to certificate selection
- upload notification pipe to external upload script

### Attacker Capabilities

- send arbitrary FTP commands and arguments over the network
- choose PORT/EPRT/PASV/EPSV data connection parameters
- authenticate if anonymous access is enabled or valid credentials are available
- create files and directories within permitted FTP namespace
- supply TLS SNI names and client certificates when TLS is enabled
- race concurrent uploads and quota operations

### Security Objectives

- prevent memory corruption and command injection from network input
- enforce authentication and authorization before filesystem operations
- prevent escape from chroot or access to files outside the user namespace
- preserve credential secrecy and authentication backend integrity
- keep quota accounting and upload notifications trustworthy
- prevent denial of service of the FTP service or privileged helpers

### Assumptions

- The repository is the authorized current source and is reviewed read-only.
- Runtime deployment configuration is not supplied; optional features are assessed where reachable under documented configuration.
- No SECURITY.md policy was found at the repository root.

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [NLST/MLSD/MLST/MDTM/SIZE bypass the -X dot-file read policy](#finding-1) | low | high | inline below |
| [PureDB IPv6 deny rules are silently discarded by colon-delimited record parsing](#finding-2) | low | high | inline below |
| [IPv6 EPRT error reply discloses uninitialized stack memory](#finding-3) | low | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] NLST/MLSD/MLST/MDTM/SIZE bypass the -X dot-file read policy

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The relevant command dispatch and listing/stat routines are visible, and none of the identified paths calls checknamesanity() with dot\_read\_ok. RETR and CWD show the expected control for comparison. |
| Category | authorization-policy-bypass |
| CWE | CWE-863, CWE-200 |
| Affected lines | src/ftp\_parser.c:626-658, src/ls.c:981-1046, src/ls.c:1062-1110, src/ftpd.c:4469-4512, src/ftpd.c:761-836 |

#### Summary

When the server is started with -X (dot\_read\_ok = 0), RETR and CWD call checknamesanity(), but NLST, MLSD, MLST, MDTM, and SIZE do not. An authenticated user can therefore list dot-directories, enumerate their entries, and stat dot-files even though the administrator prohibited reading them.

#### Root Cause

The dot-file read policy is enforced in some command handlers (CWD and RETR) but not in the listing and stat handlers. The check is endpoint-specific rather than applied at the protocol dispatch or shared path-resolution layer.

**Existing dot-read control** — `src/ftpd.c:761-814`

This is the control that rejects dot-file path components when dot\_read\_ok is zero.

```c
static int checknamesanity(const char *name, int dot_ok)
{
    const char *namepnt;

    if (name == NULL || *name == 0) {
        return -1;
    }
    /* optimize . and .. */
    if (name[0] == '.' && (name[1] == 0 || (name[1] == '.' && name[2] == 0))) {
        return 0;
    }
    namepnt = name;
    while (*namepnt != 0) {
        if (ISCTRLCODE(*namepnt) || *namepnt == '\\') {
            return -1;
        }
        if (dot_ok == 0) {
            if (*namepnt == '/') {
                namepnt++;
            } else if (namepnt != name) {
                namepnt++;
                continue;
            }
            if (namepnt[0] == 0) {
                return 0;
            }
            if (namepnt[0] == '.') {
                if (namepnt[1] == 0) {
                    return 0;
                }
                if (namepnt[1] == '.') {
                    if (namepnt[2] == 0) {
                        return 0;
                    }
                    if (namepnt[2] != '/') {
                        return -1;
                    }
                } else if (namepnt[1] != '/') {
                    return -1;
                }
            }
            if (namepnt != name) {
                continue;
            }
        }
        namepnt++;
    }
    return 0;
}
```

**NLST lists without the policy check** — `src/ls.c:981-1046`

donlst() changes into the requested directory and sends every printable entry, including dot entries.

```c
void donlst(const char *base)
{
    char           line[PATH_MAX + 3U];
    DIR           *dir;
    void          *tls_fd = NULL;
    struct dirent *de;
    size_t         name_len;
    unsigned int   matches = 0;
    int            c;
    int            base_has_trailing_slash = 0;

    if (*base != 0 && chdir(base) != 0) {
        if (*base++ == '-') {
            while (*base != 0 && !isspace((unsigned char) *base++));
            while (*base != 0 && isspace((unsigned char) *base++));
            if (*base != 0 && chdir(base) != 0) {
                addreply_noformat(550, MSG_STAT_FAILURE2);
                return;
            }
        } else {
            addreply_noformat(550, MSG_STAT_FAILURE2);
            return;
        }
    }
    if ((dir = opendir(".")) == NULL) {
        addreply_noformat(550, MSG_STAT_FAILURE2);
        goto bye;
    }
    while ((de = readdir(dir)) != NULL) {
        if (checkprintable(de->d_name) != 0) {
            continue;
        }
        name_len = strlen(de->d_name);
        if (name_len > sizeof line - 3U) {
            continue;
        }
        memcpy(line, de->d_name, name_len);
        line[name_len] = '\r';
        line[name_len + 1] = '\n';
        line[name_len + 2] = 0;
        wrstr(c, tls_fd, line);
        matches++;
        if (matches >= max_ls_files) {
            break;
        }
    }
```

**MLSD lists without the policy check** — `src/ls.c:1062-1110`

domlsd() has no checknamesanity() call and formats every entry as a machine-readable listing record.

```c
void domlsd(const char *base)
{
    char           line[PATH_MAX + 1];
    DIR           *dir = NULL;
    void          *tls_fd = NULL;
    struct dirent *de;
    unsigned int   matches = 0;
    int            c;

    if (*base != 0 && chdir(base) != 0) {
        if (*base++ == '-') {
            while (*base != 0 && !isspace((unsigned char) *base++));
            while (*base != 0 && isspace((unsigned char) *base++));
            if (*base != 0 && chdir(base) != 0) {
                addreply_noformat(550, MSG_STAT_FAILURE2);
                return;
            }
        } else {
            addreply_noformat(550, MSG_STAT_FAILURE2);
            return;
        }
    }
    if ((dir = opendir(".")) == NULL) {
        addreply_noformat(550, MSG_STAT_FAILURE2);
        goto bye;
    }
    while ((de = readdir(dir)) != NULL) {
        if (checkprintable(de->d_name) != 0 ||
            modernformat(de->d_name, line, sizeof line, "") < 0) {
            continue;
        }
        wrstr(c, tls_fd, line);
        wrstr(c, tls_fd, "\r\n");
        matches++;
        if (matches >= max_ls_files) {
            break;
        }
    }
```

**MDTM and SIZE stat without the policy check** — `src/ftpd.c:4469-4512`

Both commands call stat() directly on the client-supplied name without a dot-file policy check.

```c
void domdtm(const char *name)
{
    struct stat st;
    struct tm *t;

    if (!name || !*name) {
        addreply_noformat(501, MSG_MISSING_ARG);
    } else if (stat(name, &st)) {
        addreply_noformat(550, MSG_STAT_FAILURE2);
    } else if (!S_ISREG(st.st_mode)) {
        addreply_noformat(550, MSG_NOT_REGULAR_FILE);
    } else {
        t = gmtime((time_t *) &(st.st_mtime));
        if (!t) {
            addreply_noformat(451, MSG_GMTIME_FAILURE);
        } else {
            addreply(213, "%04d%02d%02d%02d%02d%02d",
                     t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
                     t->tm_hour, t->tm_min, t->tm_sec);
        }
    }
}

void dosize(const char *name)
{
    struct stat st;

    if (!name || !*name) {
        addreply_noformat(501, MSG_MISSING_ARG);
    } else if (stat(name, &st)) {
        addreply_noformat(550, MSG_STAT_FAILURE2);
    } else if (!S_ISREG(st.st_mode)) {
        addreply_noformat(550, MSG_NOT_REGULAR_FILE);
    } else {
        addreply(213, "%llu", (unsigned long long) st.st_size);
    }
}
```

#### Validation

With -X, dot\_read\_ok is zero. CWD and RETR call checknamesanity(..., dot\_read\_ok), while NLST/MLSD call chdir()/readdir() directly and MLST/MDTM/SIZE call stat() directly. The bypass is therefore reachable by any authenticated user.

Validation method: Static source review

- **Status:** validated

Evidence:
- src/ftp\_parser.c:626-658 routes NLST and MLSD to donlst()/domlsd()
- src/ls.c:992 and 1071 call chdir(base) without checknamesanity()
- src/ftpd.c:4476 and 4503 call stat(name) without checknamesanity()
- src/ftpd.c:3293 shows RETR does call checknamesanity(name, dot\_read\_ok)

Counterevidence and remaining uncertainty:
- The FTP chroot and normal filesystem permissions still constrain which entries are visible.
- RETR rejects dot-file content because it calls checknamesanity() at src/ftpd.c:3293.
- LIST without -a skips dot entries in listdir(), so the clearest bypass is NLST/MLSD and the stat commands.

Limitations:
- Requires the administrator to enable -X
- No runtime server build was available to exercise the commands

#### Dataflow

A client-supplied path such as .ssh is passed to chdir()/readdir() or stat() without the dot\_read\_ok check. The resulting names and metadata are sent to the client.

Attack steps:
- Authenticate to an instance running with -X.
- Send NLST .ssh or MLSD .ssh and read the data connection.
- Send MLST .ssh/known\_hosts, SIZE .ssh/known\_hosts, or MDTM .ssh/known\_hosts to obtain metadata.
- Compare with RETR or CWD .ssh, which is rejected by checknamesanity().

- **Source:** NLST/MLSD/MLST/MDTM/SIZE command argument

- **Sink:** donlst(), domlsd(), domdtm(), and dosize()

- **Outcome:** Dot-directory entries and dot-file metadata are disclosed despite -X

#### Reachability

Reachability was not recorded beyond the canonical finding summary and affected locations.

- **Attacker:** Authenticated FTP user

- **Entry point:** NLST .ssh, MLSD .ssh, MLST .ssh/known\_hosts, SIZE .ssh/known\_hosts, or MDTM .ssh/known\_hosts

- **Source:** src/ftp\_parser.c:626-658 and 788-791

- **Sink:** src/ls.c:981-1110 and src/ftpd.c:4469-4512

- **Outcome:** The client receives names or metadata that -X was intended to hide

Preconditions:
- The server is started with -X (dot\_read\_ok = 0)
- The user is authenticated
- A dot-file or dot-directory exists in the permitted namespace

#### Severity

**Low** — The bypass exposes names and metadata, not file contents, and the user must already be authenticated. It is a concrete but bounded violation of the -X policy.

Raise if the disclosed names or metadata are high-value (for example, they reveal an otherwise hidden credential or key identifier) or if another flaw turns the metadata into content access. Lower if the deployment does not rely on -X for sensitive dot-files.

#### Remediation

Apply the same checknamesanity(path, dot\_read\_ok) gate to NLST, MLSD, MLST, MDTM, and SIZE, or move the dot-file check into a shared path-resolution helper used by every filesystem command. Keep RETR and CWD behavior unchanged.

Tests:
- With -X enabled, assert NLST, MLSD, MLST, MDTM, and SIZE reject .ssh and .ssh/known\_hosts with the same policy error as CWD/RETR.
- With -X disabled, assert the same commands continue to work.
- Add a regression test that verifies a dot-directory cannot be traversed through a listing command.

Preventive controls:
- Centralize command-path validation so new filesystem commands cannot omit the dot-read policy.
- Add protocol-level tests for every filesystem command against a dot-file fixture.

<a id="finding-2"></a>

### [2] PureDB IPv6 deny rules are silently discarded by colon-delimited record parsing

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The record separator, the verbatim deny-rule write, the single-character tokenizer, the positional parser, and the empty-field allow behavior are all directly visible. The emitted field layout was reproduced with the exact separator sequence. |
| Category | authorization-policy-bypass |
| CWE | CWE-863 |
| Affected lines | src/pure-pw.h:36-38, src/pure-pw.c:710-731, src/utils.c:59-79, src/log\_puredb.c:412-437, src/log\_puredb.c:219-249 |

#### Summary

pure-pw writes deny-client and deny-local IP rules verbatim into a colon-delimited PureDB record. An IPv6 literal contains colons, so the parser splits the rule into extra fields before access\_ip\_check(). For -R '::1/128' and -I '::1/128', the deny fields become empty and login is permitted; the intended deny policy is never enforced.

#### Root Cause

The PureDB wire format uses an unescaped colon separator while IPv6 literals themselves contain colons. deny\_local\_ip and deny\_client\_ip are written verbatim, so their colons create empty positional fields; access\_ip\_check() sees no rule and permits the login.

**PureDB record delimiter** — `src/pure-pw.h:36-38`

The record format uses a colon as its field separator.

```c
#ifndef PW_LINE_SEP
# define PW_LINE_SEP ":"
#endif
```

**Deny rule written verbatim** — `src/pure-pw.c:710-731`

IPv6 literals are not escaped or rejected, and the record separator is emitted immediately after each rule.

```c
    if (pwinfo->allow_local_ip != NULL) {
        fprintf(fp2, "%s", pwinfo->allow_local_ip);   /* allowed local ip */
    }
    if (fprintf(fp2, PW_LINE_SEP) < 0) {
        return -1;
    }
    if (pwinfo->deny_local_ip != NULL) {
        fprintf(fp2, "%s", pwinfo->deny_local_ip);    /* denied local ip */
    }
    if (fprintf(fp2, PW_LINE_SEP) < 0) {
        return -1;
    }
    if (pwinfo->allow_client_ip != NULL) {
        fprintf(fp2, "%s", pwinfo->allow_client_ip);  /* allowed client ip */
    }
    if (fprintf(fp2, PW_LINE_SEP) < 0) {
        return -1;
    }
    if (pwinfo->deny_client_ip != NULL) {
        fprintf(fp2, "%s", pwinfo->deny_client_ip);   /* denied client IP */
    }
```

**Single-character tokenization** — `src/utils.c:59-79`

Every colon in an IPv6 literal terminates a field; there is no quoting or escaping.

```c
char *pure_strtok2(char **cursor, const char delim)
{
    char *str;
    char *end;

    if (cursor == NULL || (str = *cursor) == NULL) {
        return NULL;
    }
    end = str;
    while (*end != 0 && *end != delim) {
        end++;
    }
    if (*end == delim) {
        *end = 0;
        *cursor = end + 1;
    } else {
        *cursor = NULL;
    }

    return str;
}
```

**Positional IP-rule parse** — `src/log_puredb.c:412-437`

The parser assigns deny fields positionally and stops after the time field; a shifted IPv6 fragment is ignored.

```c
    if ((line = pure_strtok2(&cursor, *PW_LINE_SEP)) == NULL) {   /* allowed local ip */
        return 0;
    }
    allow_local_ip = line;
    if ((line = pure_strtok2(&cursor, *PW_LINE_SEP)) == NULL) {   /* denied local ip */
        return 0;
    }
    deny_local_ip = line;
    if ((line = pure_strtok2(&cursor, *PW_LINE_SEP)) == NULL) {   /* allowed remote ip */
        return 0;
    }
    allow_remote_ip = line;
    if ((line = pure_strtok2(&cursor, *PW_LINE_SEP)) == NULL) {   /* denied remote ip */
        return 0;
    }
    deny_remote_ip = line;
    if (access_ip_check(sa, allow_local_ip, deny_local_ip) != 0 ||
        access_ip_check(peer, allow_remote_ip, deny_remote_ip) != 0) {
        return -1;
    }
    if ((line = pure_strtok2(&cursor, *PW_LINE_SEP)) == NULL) {   /* time restrictions */
        return 0;
    }
    time_restrictions = line;
    if (time_restrictions_check(time_restrictions) != 0) {
        return -1;
    }
```

**Empty rules permit access** — `src/log_puredb.c:225-237`

When both parsed fields are empty, access\_ip\_check() immediately allows the address.

```c
    if (*allow == 0) {
        if (*deny == 0) {
            return 0;
        }
        if (access_ip_match(sa, deny) != 0) {
            return -1;
        }
        return 0;
    }
    if (*deny == 0) {
        if (access_ip_match(sa, allow) == 1) {
            return 0;
        }
        return -1;
    }
```

#### Validation

For -R '::1/128', the emitted record places '::1/128' after four empty IP fields. Tokenization yields empty allow/deny fields and a trailing '1/128' fragment after the parser's time field; access\_ip\_check() therefore allows the address. The -I path is equivalent for the local-IP deny field.

Validation method: Static source review and field-layout reproduction

- **Status:** validated

Evidence:
- Exact separator layout for -R '::1/128' produces ':::::::::::::1/128:' after the quota fields.
- src/log\_puredb.c:412-431 reads allow\_local, deny\_local, allow\_remote, deny\_remote positionally.
- src/log\_puredb.c:225-232 returns 0, allowing access, when both allow and deny are empty.

Counterevidence and remaining uncertainty:
- The user must already know a valid virtual-user password.
- IPv4 rules and hostname rules do not contain the separator and work normally.
- The -r/-i allow variants are not bypasses; their shifted value reaches the time field and can fail closed.
- No compiler was available to run the full pure-pw/pure-ftpd reproduction.

Limitations:
- Deployment must use the PureDB backend and an IPv6 literal deny rule
- No runtime server build was available

#### Dataflow

An IPv6 deny rule is serialized with unescaped colons into a colon-delimited record. The PureDB parser maps the fragments to empty fields, and access\_ip\_check() permits the connection.

Attack steps:
- Create a PureDB virtual user with pure-pw useradd user ... -R '::1/128'.
- Build the database with pure-pw mkdb and start pure-ftpd with -l puredb:\<db\>.
- Connect from ::1 with the valid account and password.
- Observe login success even though the deny rule was intended to reject ::1.

- **Source:** Administrator-configured pure-pw -R '::1/128' or -I '::1/128'

- **Sink:** pw\_puredb\_parseline() and access\_ip\_check()

- **Outcome:** The virtual user authenticates from the denied IPv6 address

#### Reachability

Reachability was not recorded beyond the canonical finding summary and affected locations.

- **Attacker:** Remote FTP client that has valid credentials for the affected virtual user

- **Entry point:** USER/PASS login from the denied IPv6 address

- **Source:** PureDB record created by pure-pw and loaded with -l puredb:\<db\>

- **Sink:** src/log\_puredb.c:412-437

- **Outcome:** Login succeeds despite the configured IPv6 deny rule

Preconditions:
- The daemon uses the PureDB authentication backend
- A virtual user was created with a literal IPv6 -R or -I deny rule
- The attacker knows that user's password

#### Severity

**Low** — The configuration boundary is real: an administrator's IPv6 deny rule is bypassed. The attacker still needs valid credentials, and the reviewed evidence does not show a privileged account or a sole control protecting highly sensitive data.

Raise to Medium or High if the affected virtual account is administrative, can access sensitive data, or the IPv6 deny rule is the only compensating control. Lower if an independent firewall or upstream ACL enforces the same restriction.

#### Remediation

Do not store unescaped IP-rule text in a single-character-delimited record. Reject colons in IPv4/IPv6 rule fields, encode each field (for example base64 or a length prefix), or split the record with a parser that understands bracketed IPv6 literals. Make the parser fail closed when extra fields or malformed CIDR widths appear, and validate IPv6 CIDRs before writing the PureDB record.

Tests:
- Add a regression test that creates a user with -R '::1/128', rebuilds the database, and verifies a login from ::1 is denied.
- Add equivalent tests for -I '::1/128', -r '::1/128', and -i '::1/128'.
- Assert that records containing an unexpected extra field are rejected rather than silently treated as unrestricted.

Preventive controls:
- Use one serializer/parser pair for PureDB records and reject any field value containing the separator.
- Prefer an unambiguous encoding for network-policy fields and validate CIDR syntax before persistence.

<a id="finding-3"></a>

### [3] IPv6 EPRT error reply discloses uninitialized stack memory

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The uninitialized declaration, the partial initializer, and the getnameinfo reply path are all visible in the source. Local glibc behavior check shows a nonzero sin6\_scope\_id appears as a %N suffix. |
| Category | uninitialized-memory-disclosure |
| CWE | CWE-457, CWE-200 |
| Affected lines | src/ftpd.c:838-866, src/ftpd.c:575-588, src/ftpd.c:2305-2352 |

#### Summary

An authenticated FTP client can send an IPv6 EPRT for an address different from its control connection. do\_ipv6\_port() passes an uninitialized sockaddr\_storage to generic\_aton(), which initializes only the family and address bytes. doport2() then formats the structure with getnameinfo() in the FXP-denial reply; glibc appends the uninitialized sin6\_scope\_id as a %N suffix, leaking four bytes of stale stack per request.

#### Root Cause

The IPv6 EPRT path serializes a sockaddr\_storage without initializing fields that getnameinfo reads. The successful generic\_aton() branch never clears the structure, unlike the IPv4 paths that call memset first.

**Uninitialized IPv6 address storage** — `src/ftpd.c:838-842`

The local sockaddr\_storage is not zeroed before the IPv6 address is parsed.

```c
static void do_ipv6_port(char *p, char delim)
{
    char *deb;
    struct sockaddr_storage a;
```

**Partial sockaddr initialization** — `src/ftpd.c:575-588`

Successful parsing sets only the address family and address bytes; sin6\_flowinfo and sin6\_scope\_id remain untouched.

```c
static int generic_aton(const char *src, struct sockaddr_storage *a)
{
    if (inet_pton(AF_INET6, src, &STORAGE_SIN_ADDR6(*a)) > 0) {
        STORAGE_FAMILY(*a) = AF_INET6;
        return 0;
    }
    if (inet_pton(AF_INET, src, &STORAGE_SIN_ADDR(*a)) > 0) {
        STORAGE_FAMILY(*a) = AF_INET;
        return 0;
    }
    memset(a, 0, sizeof *a);

    return -1;
}
```

**Scope ID reaches the numeric-host response** — `src/ftpd.c:2335-2347`

When the supplied address differs from the peer, getnameinfo formats it and the 500 reply sends the result to the client.

```c
        if (getnameinfo((struct sockaddr *) &a, STORAGE_LEN(a),
                        hbuf, sizeof hbuf, NULL,
                        (size_t) 0U, NI_NUMERICHOST) != 0 ||
            getnameinfo((struct sockaddr *) &peer, STORAGE_LEN(peer),
                        peerbuf, sizeof peerbuf, NULL,
                        (size_t) 0U, NI_NUMERICHOST) != 0) {
            goto hu;
        }
        if (allowfxp == 0 || (allowfxp == 1 && guest != 0)) {
            hu:
            (void) close(datafd);
            datafd = -1;
            addreply(500, MSG_NO_FXP, hbuf, peerbuf);
```

#### Validation

Source review confirms the uninitialized field reaches getnameinfo. A local Python socket.getnameinfo call with a nonzero scope ID returned the host name with a %N suffix, matching the disclosed bytes' rendering.

Validation method: Static source review plus a local glibc getnameinfo behavior check

- **Status:** validated

Evidence:
- python3 socket.getnameinfo(('2001:db8::1', 0, 0, 3724148534), socket.NI\_NUMERICHOST) returns ('2001:db8::1%3724148534', '0')
- src/ftpd.c:842 declares struct sockaddr\_storage a without memset
- src/ftpd.c:577-579 sets only the IPv6 address and family on success
- src/ftpd.c:2335-2347 passes the structure to getnameinfo and formats the 500 reply

Counterevidence and remaining uncertainty:
- The reply only exposes the suffix on libc implementations that render a nonzero IPv6 scope ID.
- The value is not guaranteed to contain a pointer or credential; its security value depends on the stale stack contents.
- No compiled server was available to run the full EPRT exchange.

Limitations:
- No runtime server build was available
- The exact leaked word varies with process history and compiler layout

#### Dataflow

The client-controlled EPRT address is parsed into a partially initialized sockaddr\_storage. The FXP mismatch branch formats that structure and returns the formatted host in the 500 reply.

Attack steps:
- Authenticate to the FTP service.
- Send EPRT |2|2001:db8::1|1025| (or another address different from the peer).
- Observe the 500 I won't open a connection reply.
- Repeat the request, optionally after shaping the command buffer, and compare the synthetic %N scope suffixes.

- **Source:** EPRT command argument

- **Sink:** getnameinfo() and addreply(500, MSG\_NO\_FXP, hbuf, peerbuf)

- **Outcome:** Four bytes of stale stack are rendered in the client-visible reply

#### Reachability

Reachability was not recorded beyond the canonical finding summary and affected locations.

- **Attacker:** Authenticated FTP client, including an anonymous client when anonymous access is enabled

- **Entry point:** EPRT |2|\<IPv6 address\>|\<port\>|

- **Source:** src/ftp\_parser.c:465 dispatches eprt to doeprt()

- **Sink:** src/ftpd.c:2335-2347

- **Outcome:** The client receives a 500 response containing the formatted address and uninitialized scope suffix

Preconditions:
- The server is built with IPv6 support (v6ready is true)
- The client is logged in
- The supplied IPv6 address differs from the control-connection peer so the mismatch branch runs

#### Severity

**Low** — The attacker must authenticate and can read only four bytes of uninitialized stack per EPRT. That crosses a memory-confidentiality boundary, but no direct access to credentials or host data is established.

Raise to Medium or High if the leaked words are shown to contain ASLR-relevant pointers, credentials, or other sensitive data, or if repeated disclosure enables a practical memory-corruption bypass. Lower if the platform does not format scope IDs or the storage is initialized by the compiler.

#### Remediation

Zero the sockaddr\_storage before generic\_aton() in do\_ipv6\_port(), as the IPv4 EPRT and PORT paths already do: memset(&a, 0, sizeof a). More generally, initialize every stack sockaddr structure at declaration and keep address construction in one helper that initializes the complete structure.

Tests:
- Build with a nonzero sin6\_scope\_id left in a poisoned stack and verify EPRT mismatch replies contain no %N suffix.
- Send EPRT |2|2001:db8::1|1025| after stack-shaping commands and confirm the reply is identical to the plain numeric address.

Preventive controls:
- Use a single address-construction helper that always zeroes sockaddr\_storage before filling it.
- Add a source-level regression test or compiler sanitizer run for EPRT IPv6 mismatch handling.
