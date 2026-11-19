# pure-ftpd 安全审计报告

- 项目: pure-ftpd
- 源码版本: b64c56d（1.0.54）
- 源码根: /target（只读），工作副本 /workspace/repo
- 审计模式: 静态审计（原生内存安全 + 协议解析 + 权限边界）
- 状态: **进行中（增量更新，以下结论均为阶段性静态结论，未经验证）**

> 说明：本报告中的所有条目均为静态源码级候选或待核实假设。未运行目标程序、未使用 ASan/Valgrind，未执行任何动态验证。凡标注 `unverified` 的条目不得视为已确认漏洞。

## 1. 项目画像

- 语言与规模：C 语言，`src/` 下 48 个 `.c` 文件，约 32,279 行（含头文件统计见 `project-profile.json`）。
- 构建系统：GNU Autotools（`configure.ac` + `Makefile.am`）；无包管理器。
- 项目类型：`network-service` / `native-c-daemon`（非 Web、非智能合约、非 AI 基础设施）。
- 网络入口：
  - FTP 控制连接：`src/ftpd.c:5320`（accept 循环，每连接 fork 后进入 `doit()`），输入为 FTP 命令/参数、用户名口令、路径、PORT/EPRT/PASV、上传数据、TLS 握手。
  - FTP 数据连接：`src/ftpd.c:2416`。
  - 外部辅助进程（需配置启用）：`src/pure-authd.c:6`（Unix socket / 标准输入认证记录）、`src/pure-certd.c:6`（TLS 客户端证书映射）。
- 协议解析：`src/ftp_parser.c:66`（`sfgets()`），分派于 `src/ftp_parser.c:326`；命令缓冲区 `cmd[PATH_MAX+32]`，`cmdsize=PATH_MAX+16`（`src/globals.h:34-35`）。
- 提权/降权边界：`src/ftpd.c:1433`（setuid/seteuid）、`src/ftpd.c:1392`（chroot）、`src/ftpd.c:5203`（`privsep_init()`）、`src/privsep.c`（特权辅助进程）。
- 子进程：`src/pure-uploadscript.c:402`（`execl(script, script, file, NULL)`，需配置启用）。
- 配置解析：`src/simpleconf.c:715`、`src/parser.c:20`（LDAP/MySQL/PGSQL 后端配置）、`src/diraliases.c:23`、`src/quotas.c:28`。
- 编译开关：所有高风险特性（TLS、QUOTAS、THROTTLING、PUREDB、EXTAUTH、VIRTUAL_CHROOT、DIRALIASES、PER_USER_LIMITS）在 `configure.ac` 中均为 opt-in，默认构建不含这些路径。

## 2. 覆盖范围（阶段性）

已进行的覆盖（详见 `.workspace/findings/coverage-ledger.json`）：

| 覆盖编号 | 区域 | 技能 | 状态 |
|----------|------|------|------|
| COV-PROFILE-001 | 项目画像 | project-profiler | analyzed |
| COV-EXEC-001 | 命令执行 / 子进程 | command-injection-analyzer | analyzed（findings 为空，2 条假设） |
| COV-TLS-001 | TLS、回复缓冲、辅助进程 | memory-safety-analyzer | analyzed（1 条低危候选） |
| COV-LS-001 | 目录列表 / MLSD / 格式缓冲区 | memory-safety-analyzer | analyzed（findings 为空，3 条假设） |
| COV-PATH-001 | 路径规范化 / chroot / 链接 | path-traversal-analyzer | analyzed（1 条低危候选，6 条假设） |
| COV-CMD-001 | 控制连接命令处理 | memory-safety-analyzer | 进行中（后台任务） |
| COV-INT-001 | 整数溢出 / 尺寸运算 | integer-overflow-analyzer | analyzed（1 条低危候选，7 条假设） |
| COV-MERGE-001 | 候选归一化 / 去重 | hypothesis-critic | analyzed（3 findings、21 hypotheses，1 blocked） |
| COV-VCHROOT-001 | 虚拟 chroot / realpath / glob | memory-safety-analyzer | analyzed（0 findings、3 假设，1 条潜在 1 字节越界写） |
| COV-AUTH-001 | 认证后端链 | session-and-auth-analyzer | analyzed（1 条低危候选 AUTH-001，3 条假设） |
| COV-TLSDATA-001 | TLS 数据会话 / SIGALRM 可达性 | audit-hypothesis-tracer | needs_evidence（HYP-TLS-001 counterevidence；HYP-TLS-004 待时序证据） |
| COV-GROUPS-001 | `check_trustedgroup` 负索引 | audit-hypothesis-tracer | 进行中（wave 2） |

编排器人工阅读并核对的区域（非独立任务，仅作为覆盖记录与复核依据）：

- `src/ftp_parser.c`（`sfgets()` 行读取、控制字符过滤、全部命令分派）
- `src/ftpd.c`（`simplify`、`checkprintable`、`client_printf`/`addreply`/`doreply`、`checknamesanity`、PORT/EPRT/PASV 系列、认证流程 `douser`/`dopass`/`pw_check`、`create_home_and_chdir`、`docwd`/`dochmod`/`doutime`/`dodele`/`dornfr`/`dornto`、`get_atomic_file`、`doretr`、数据连接与上传/下载缓冲、`_dlmap_remap`、`dl_dowrite` 的 ASCII 缓冲区、`doit()`）
- `src/ls.c`（`wrstr`、`addfile`、`listfile`、`outputfiles`、`sreaddir`、`listdir`、`donlst` 的 `line[PATH_MAX+3]` 边界、`domlsd`、`unescape_and_return_next_file`）
- `src/log_puredb.c`、`src/log_ldap.c`、`src/log_pam.c`、`src/log_extauth.c`、`src/log_mysql.c`、`src/log_pgsql.c`（认证后端与转义）
- `src/puredb/src/puredb_read.c`、`src/dynamic.c`、`src/privsep.c`、`src/upload-pipe.c`、`src/altlog.c`、`src/diraliases.c`、`src/quotas.c`、`src/crypto.c`、`src/ipstack.c`、`src/parser.c`
- `src/bsd-glob.c`（`glob_`/`glob0`/`globexp2`/`glob3`/`match`/`globextend` 的 `patbuf[PATH_MAX]` 边界与展开长度）
- `src/fakechroot.c`（`fakexlate` 的 `..`/`/` 处理与 `chroot_base` 前缀校验、`fakegetcwd` 的截断与尾部斜杠折叠、各 `fake*` 包装的命令参数重写）
- `src/pure-uploadscript.c`、`src/pure-certd.c`、`src/ftpwho-update.c`、`src/ftpwho-read.c`
- `configure.ac`（可选特性开关确认）

未覆盖或覆盖不足：`src/caps.c`、`src/daemons.c`、`src/simpleconf.c`、`src/ftpwho-*.c` 的部分分支、`src/bsd-realpath.c`、`pure-pw` 等本地管理工具。上述区域尚未分配独立分析任务（多为本地管理面，非网络可达）。

### Jev 初筛（仅用于安排阅读顺序，不作为候选问题）

已读取 `.../pure-ftpd/triage/jev-infra.json`（193 个单元，0 错误）。`priority>=0.6` 的 12 个单元为：`gui/build.sh`、`autogen.sh`、`src/pure-authd.c`、`src/pure-certd.c`、`src/pure-uploadscript.c`（均因 `subprocess_exec` 高分），`src/parser.c`、`src/log_ldap.c`、`src/simpleconf.c:398-742`、`src/ftpd.c:5225-6057`、`src/log_puredb.c`、`src/log_ldap_p.h`（`untrusted_model_input`）。低置信度（0.4–0.6）单元集中在 `src/tls.c`、`src/diraliases.c`、`src/log_extauth.c`、`src/log_mysql.c:377-665`、`src/log_puredb.c:398-476`、`src/ftpd.c:995-1406/4781-5224`；未发现 `flags` 与 `mitigations` 冲突的单元。上述高分单元映射到已有覆盖：辅助进程执行 → COV-EXEC-001，TLS → COV-TLS-001，认证后端 → COV-AUTH-001；`ftpd.c:5225-6057` 为 `main()` 启动参数/权限设置（本地管理员配置面），`gui/build.sh`、`autogen.sh` 为构建脚本，均未构成客户端可达入口，未单独派发任务。

## 3. 候选问题

### NORM-TLS-001（原 MEM-TLS-001；low / requires-config / unverified）

- 标题: SNI 扩展证书路径的 `CertResult` 文件名在 `ssl_servername_cb` 中未释放（每次握手泄漏）
- 位置: `src/tls.c:72-121`、`src/tls_extcert.c:60-88`、`src/tls_extcert.c:141-142`
- 根因: `tls_extcert_get()` 通过 `callback_reply_cert_file()` / `callback_reply_key_file()` 对 `cert_file` / `key_file` 执行 `strdup()`（`src/tls_extcert.c:67`、`:82`）；`ssl_servername_cb()` 在 `tls_create_new_context()` 之后直接 `return SSL_TLSEXT_ERR_OK`（`src/tls.c:121`），从未释放这两个指针。
- 可达性: 需构建启用 `WITH_TLS` 且启用 `-E`（extcert）并配置外部证书服务；客户端在 TLS 握手中发送合法 SNI 即可触发。
- 影响: 每次握手泄漏少量堆内存（约数百字节）。pure-ftpd 通常每连接 fork 子进程，泄漏随子进程退出回收，实际影响有限，故定级 low。
- 修复建议: 在 `ssl_servername_cb()` 所有返回路径释放 `result.cert_file` / `result.key_file`，或实现统一的 `tls_extcert_result_free()`；注意 `key_file` 可能等于 `cert_file`，释放前需判等。
- 验证状态: unverified（仅源码生命周期追踪，未运行）

### NORM-PATH-001（原 PATH-001；low / requires-config / unverified）

- 标题: `NLST`/`MLSD`/`MLST`/`MDTM`/`SIZE` 路径未调用 `checknamesanity()` / `simplify()`，仅依赖底层 `chdir`/`stat`
- 位置: `src/ls.c:992`、`src/ls.c:1008`、`src/ls.c:1071`、`src/ls.c:1084`、`src/ftpd.c:1172`、`src/ftpd.c:4476`、`src/ftpd.c:4503`
- 根因: 与 `LIST`/`RETR`/`STOR` 路径不同，这些命令把用户参数直接交给 `chdir(base)` 或 `stat`，未经过 `checknamesanity()` 的 `..`/控制字符检查。
- 影响: 属策略不一致：在启用 `-X`（`dot_read_ok=0`，`src/globals.h:58`、`src/ftpd.c:5769-5770`）时，`NLST`/`MLSD`/`MLST`/`MDTM`/`SIZE` 仍可列出/stat 点文件，构成策略绕过（元数据泄露）；`..` 仍受 chroot/权限边界约束，不构成 chroot 逃逸。
- 验证状态: unverified（静态阅读）

### NORM-INT-001（原 INT-001；low / requires-config / unverified）

- 标题: 仅配置文件数配额时，`user_quota_size` 的无符号哨兵值经减法转换误判为超配额，合法上传被拒
- 位置: `src/ftpd.c:4299-4307`、`src/ftpd.c:1203-1207`、`src/globals.h:151-152`、`src/ftpd.h:689-690`、`src/log_puredb.c:399-411`
- 根因: `user_quota_size` 默认值为 `ULONG_LONG_MAX`（`1ULL << 63`，即 2^63）作为“未配置大小配额”的哨兵；当账户只配置文件数配额时，`log_puredb` 保持该默认值（`src/log_puredb.c:406` 仅在字段非空时覆盖）。`src/ftpd.c:4303` 执行 `(max_filesize = user_quota_size - quota.size) < (off_t) 0`，`quota.size == 0` 时无符号减法结果恰为 2^63，转为 `off_t` 为实现定义负值，命中 `< 0` 分支并置 `overflow = 1`，`STOR`/`APPE` 在初始化数据连接前以 552 `MSG_QUOTA_EXCEEDED` 拒绝。同一配置下 `doallo()`（`src/ftpd.c:1203-1207`）的无符号比较不会命中，造成 `ALLO` 成功而 `STOR` 失败的不一致。
- 可达性: 需编译启用 `QUOTAS`、会话已 chroot、账户仅设置文件数配额（如 `pure-pw useradd -n <n>` 不带 `-N`）、且 `/.ftpquota` 中 size 计数为 0（新账户常态）。
- 影响: 合法用户无法上传（可用性/功能缺陷），不构成配额绕过、越界或提权。
- 修复建议: 在减法前先判定哨兵值，例如 `if (user_quota_size >= ULONG_LONG_MAX) max_filesize = (off_t) -1; else if (quota.size >= user_quota_size) { 超限 } else max_filesize = (off_t) (user_quota_size - quota.size);`；或将哨兵值改为 `LLONG_MAX` 并统一按有符号比较。
- 验证状态: unverified（静态推导，未编译运行；`(off_t)` 转换的具体结果依赖 ABI）

### AUTH-001（low / requires-config / unverified）

- 标题: 未配置 `MYSQLCrypt`/`PGSQLCrypt` 时 `crypto` 为 `NULL`，`strcasecmp(NULL, ...)` 使认证子进程崩溃（fail-closed DoS）
- 位置: `src/log_mysql.c:423-424`、`src/log_pgsql.c:500-501`、`src/log_mysql_p.h:19,50`、`src/log_pgsql_p.h:12,39`
- 根因: 两个后端的 `crypto` 均为文件作用域 `static char *crypto;`（零初始化），仅当配置出现 `MYSQLCrypt`/`PGSQLCrypt` 时由 `generic_parser()` 赋值；`pw_mysql_parse()` / `pw_pgsql_parse()` 只校验 `server`/`socket_path`（`src/log_mysql.c:601-606`），不校验 `crypto`。`pw_mysql_check()` 在 4 条查询（`getpw`/`getuid`/`getgid`/`getdir`）均返回单行后才执行 `result->auth_ok--;`，随后无判空调用 `strcasecmp(crypto, PASSWD_SQL_ANY)`（`src/log_mysql.c:424`、`src/log_pgsql.c:501`）。
- 可达性: 需编译启用 `WITH_MYSQL`/`WITH_PGSQL` 并配置该后端，且配置文件省略 `MYSQLCrypt`/`PGSQLCrypt`（示例 conf 均包含，属部署错误前提）；攻击者提供数据库中已存在的账户名并发送 `PASS` 即可触发。口令内容不影响崩溃点。
- 影响: 该次连接的认证子进程 `SIGSEGV`，连接中断；父进程与其他会话不受影响，属 fail-closed 可用性缺陷，不产生认证绕过或身份混淆。可重复触发消耗子进程资源。
- 修复建议: 在 `pw_mysql_parse()`/`pw_pgsql_parse()` 中为 `crypto` 设置安全默认或在缺失时拒绝启动；同时在 `pw_mysql_check()`/`pw_pgsql_check()` 中对 `crypto == NULL` 显式 `goto bye`。
- 验证状态: unverified（静态源码与配置解析路径核对，未编译运行）

## 4. 验证状态

- 当前没有任何 `confirmed` 条目。NORM-TLS-001、NORM-PATH-001、NORM-INT-001 为 `unverified` 静态候选；`hypothesis-critic` 已合并产出 `.workspace/findings/findings.normalized.json`（3 findings、21 hypotheses、COV-CMD-001 记为 blocked）。
- 待核实假设（未进入候选）：
  1. `src/tls.c:531-538` 的 `else-if` 在 `tls_close_session()` 置空后未 `SSL_new`，随后 `SSL_set_fd(NULL)` 潜在空指针解引用：`audit-hypothesis-tracer`（COV-TLSDATA-001）已判定为 `counterevidence`（不可达，confidence high）——危险前置状态需 `xferfd==-1` 且 `tls_data_cnx!=NULL`，但 `closedata()` 同步置空二者（`src/ftpd.c:2365-2368`），`opendata()` 仅在 `xferfd!=-1` 时先 `closedata()`（`:2378-2380`），5 个 `tls_init_data_session` 调用点均在返回前到达 `closedata()` 或经 `die/_EXIT` 终止；保留为潜伏结构缺陷，不进入候选。
  2. `src/fakesnprintf.c:243-250` 对 `LLONG_MIN` 取负溢出并以负余数索引数字表，潜在越界读；仅在缺少 `vsnprintf` 的平台编译，未找到外部可控的 `LLONG_MIN` 输入。
  3. `src/ftpd.c:590-606` 在 `no_syslog` 分支对未初始化的 `va_list` 调用 `va_end`（未定义行为）。
  4. `src/ftpd.c:358-363` 的 SIGALRM 处理器经 `die()`→`addreply()`/`doreply()` 在信号上下文调用 `malloc`/`free`/`syslog`：静态链成立（`src/ftpd.c:4841-4845` 注册、`:4860` 解除阻塞、`:4946` 由 `doit` 安装；触发点 `src/ftp_parser.c:257`、`src/ftpd.c:2400/2489/4244`、`src/ls.c:876-881`；处理器 `:358-363`→`:337-351`→`addreply_newline` 的 `malloc(:658-674)`/`doreply` 的 `free(:719-755)`/`logfile` 的 `syslog(:590-637)`），潜在单会话 DoS（default 可达性，潜在 medium），但缺 SIGALRM 命中分配器临界区的时序与运行时证据，保持 `needs_evidence`。
  5. altlog `STATS` 格式对含空格/控制字符的文件名未转义（`src/altlog.c:54-91`），CWE-117 日志注入；仅影响日志消费者。
  6. `pure-authd` / `pure-certd` 协议与子进程环境注入：`src/ftp_parser.c` 已在前置阶段替换控制字符，当前输入无法包含换行，判定不可达。
  7. `src/ftpd.c:1571-1612` `check_trustedgroup()`：`n = getgroups(0, NULL) > 0` 成功分配后，第二次 `getgroups(n, ...)` 若失败返回 -1，则 `n = -1`，`while (n != 0) { n--; ... }` 对 `alloca_suppgroups` 做负索引越界读并近似长循环（有符号溢出 UB）。触发需两次调用间进程组列表异常变化，实际可达性很低；且该调用发生在 `setgid()` 之后（`src/ftpd.c:1802` 之后 `:1806`），进程已降权。
  8. `src/fakechroot.c:57-111` `fakegetcwd()` 在虚拟 chroot 根目录（`curdir == chroot_base`）时因 `s == 0` 返回 `NULL`，`docwd()` 走 `getcwd` 失败分支；仅影响回复内容正确性，未见内存破坏。
  9. `docwd()` 中 `getcwd` 失败分支用 `dir` 而非 `where` 拼回复（`src/ftpd.c:2061-2076`），属逻辑缺陷，不影响文件系统边界。
  10. 整数方向的 7 条假设见 `.workspace/findings/integer.json`，其中包括 `pure-pw -t/-T` 带宽乘法回绕为 0 后经 puredb 触发 ftpd 在 `src/ftpd.c:1527` 除零（`SIGFPE`）的可能性；均需管理员配置前提，尚无攻击者可控路径。

## 5. 编排器已核对并排除（示例）

以下位置经逐行核对未发现可确证缺陷（不构成“安全”结论，仅记录已读范围）：

- `src/ftp_parser.c` `sfgets()`：控制字符（含 `\001`、`\r`）替换为 `_`，行尾处理与 `readnbd > cmdsize` 退出条件正确，命令/参数 token 在小写化后 NUL 终止。
- `src/ls.c` `donlst()`：`line[PATH_MAX+3]` 先检查 `name_len > sizeof line - 3` 再 `memcpy`，尾随 `\r\n\0` 写入在界内；`outputfiles()` 的 `pad[6]` 索引上界为 4/5。
- `src/bsd-glob.c`：`patbuf[PATH_MAX]` 写入受 `bufend`/`pathend_last` 限制，`glob0` 元字符与 `globexp2` 花括号展开不会增长输出总长，`glob3` 在 `dc >= pathend_last` 时截断置 EOS 并置 `err`，`match()` 的 `M_SET`/`M_RNG`/`M_END` 与 `stars <= 3` 递归限制正确。
- `src/fakechroot.c` `fakexlate()`：`..` 逐级回退后再做 `chroot_base` 前缀与 `chroot_base[chroot_len] == '/'` 校验，越界回退会被重置回 `chroot_base/`；绝对路径被重写为 `chroot_base/...`；`strstr(dir, "/../")` 与尾部 `/..` 检查覆盖相对路径逃逸。
- `src/upload-pipe.c`：`upload_pipe_open()` 对锁文件/管道做 `O_NOFOLLOW` + 权限/属主/类型校验；`upload_pipe_push()` 的 `sizeof_buf = 1 + strlen(vuser) + strlen(file) + 1` 与 `memcpy` 布局一致。
- `src/log_puredb.c`：IPv6 CIDR `prefix > 128` 返回 0，IPv4 `netbits == 0 || > 32` 记日志并返回 -1（fail closed），`access_ip_check()` 对 -1 一律拒绝；`uid`/`gid` 数字校验；`hostname` 用 `getaddrinfo` 限定 `sa_family`。
- `src/log_mysql.c` / `src/log_pgsql.c`：转义 helper 的 `to_len = from_len * 2 + 1`、哨兵字节校验、`escaped_len >= to_len` 时归零死循环保护正确；口令在本地比较，不进入 SQL 文本。
- `src/ftpd.c` `_dlmap_remap()` / `dl_dowrite()`：`chunk_size <= 0` 提前返回，`size > chunk_size` 拒绝，`asciibuf = ALLOCA(chunk_size * 2U)` 与实际最多插入 `size` 个 `'\r'` 的上界匹配；页对齐 `(dlmap_size + page_size - 1) & ~(page_size - 1)` 与 `dlmap_size > remaining` 校验一致。
- `src/ftpd.c` `dornfr()`/`dornto()`：两侧均调用 `checknamesanity()`（`dot_write_ok`），quota 分支对 `stat()` 失败与 `ENOENT` 区分处理。
- `src/ftpd.c` `pw_check()` / `dopass()`：任一后端返回 `< 0` 即 break 并最终 `auth_ok != 1` 拒绝；`uid < useruid` 账号禁用检查、`PER_USER_LIMITS` 计数在认证成功后执行。

## 6. 限制

- 全部为静态分析；未编译、未运行，未使用 ASan/Valgrind 或运行时插桩。
- 未对上游历史做 diff（仓库为 shallow clone，单 commit `b64c56d`），无法据此判断是否存在人为回退修复。
- 已核对 `ChangeLog` 1.0.54 声明的加固项在当前代码中均已实现（IPv6 访问规则、CIDR fail-closed、LDAP 多条目拒绝、quota 畸形文件不清零、PureDB uid/gid 数字校验、pure-pwconvert 字符过滤、quota 文件加锁），因此未将仓库视为“回退修复”型注入目标；仍不排除未覆盖区域存在缺陷。
- 未进行动态验证，未产生任何可直接武器化的利用代码。
- 未发现明文密钥/口令；如后续发现，仅报告位置与类型。
