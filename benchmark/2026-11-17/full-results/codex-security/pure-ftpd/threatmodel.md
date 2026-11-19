# Threat Model

Pure-FTPd 1.0.54 is a network-facing FTP server. Untrusted remote clients speak FTP over cleartext or TLS and can authenticate as anonymous or virtual/real users. After authentication, the server exposes filesystem operations constrained by chroot/jail and per-user permissions; optional backends (PureDB, PAM, LDAP, SQL, external auth), TLS SNI helpers, upload scripts, quotas, logging, and local admin utilities create additional trust boundaries. The primary assets are host files outside the FTP jail, credentials and authentication decisions, user files and quotas, helper process integrity, and service availability.

## Assets

- host filesystem and files outside chroot
- user credentials and authentication backend data
- FTP user files and quota accounting
- TLS private keys and certificate selection
- service availability and privileged helper processes
- audit logs and session metadata

## Trust Boundaries

- unauthenticated network client to FTP control parser
- authenticated FTP user to chrooted filesystem namespace
- FTP daemon to root-owned configuration, PureDB and quota files
- FTP daemon to external auth/cert helper processes
- TLS client SNI to certificate selection
- upload notification pipe to external upload script

## Attacker Capabilities

- send arbitrary FTP commands and arguments over the network
- choose PORT/EPRT/PASV/EPSV data connection parameters
- authenticate if anonymous access is enabled or valid credentials are available
- create files and directories within permitted FTP namespace
- supply TLS SNI names and client certificates when TLS is enabled
- race concurrent uploads and quota operations

## Security Objectives

- prevent memory corruption and command injection from network input
- enforce authentication and authorization before filesystem operations
- prevent escape from chroot or access to files outside the user namespace
- preserve credential secrecy and authentication backend integrity
- keep quota accounting and upload notifications trustworthy
- prevent denial of service of the FTP service or privileged helpers

## Assumptions

- The repository is the authorized current source and is reviewed read-only.
- Runtime deployment configuration is not supplied; optional features are assessed where reachable under documented configuration.
- No SECURITY.md policy was found at the repository root.

---

## Saved Model Context

- Source: scan
- Scan: 4149d915-b8f5-452a-bb55-55a7a18223b6
- Target: pure-ftpd
- Revision: b64c56dc81bc4a7fa5d09d76afa59012ca5509a6
- Snapshot: codex-security-snapshot/v1:sha256:dde2c6b218b6b149b8492d93c4fd5db7e5d34594fbe5f5bef68006afbd6c559e
- Result status: completed
- Model origin: not recorded
- Model scope: not recorded
- Scan scope: .
- Scan scope description: Repository-wide Standard scan of pure-ftpd 1.0.54 source snapshot. Focused review covered FTP control/data parsing, filesystem policy enforcement, PureDB/IP access rules, TLS/SNI helpers, authentication backends, quotas, upload notification, and local parsing utilities.
