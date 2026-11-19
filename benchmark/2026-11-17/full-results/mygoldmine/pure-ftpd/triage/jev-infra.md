# Jev triage

- model: `typesafe/jev-latest` (returned: `typesafe/jev-1.14-20261014`)
- profile: `infra`
- units: 193
- requests: 193 (cached: 0)
- errors: 0
- input tokens: 440420
- cost: $0.018498
- elapsed: 35446 ms

| priority | unit | flags | mitigations |
|---|---|---|---|
| 0.965 | `gui/build.sh` | subprocess_exec=0.98 | - |
| 0.965 | `autogen.sh` | subprocess_exec=0.97 | - |
| 0.885 | `src/pure-authd.c` | subprocess_exec=0.94 | - |
| 0.885 | `src/pure-certd.c` | subprocess_exec=0.92, default_exposure=0.54 | - |
| 0.855 | `src/pure-uploadscript.c` | subprocess_exec=0.94 | - |
| 0.710 | `src/parser.c` | untrusted_model_input=0.72 | - |
| 0.700 | `src/log_ldap.c#L1-432` | untrusted_model_input=0.71 | - |
| 0.680 | `src/simpleconf.c#L398-742` | untrusted_model_input=0.69 | - |
| 0.650 | `src/ftpd.c#L5225-5654` | untrusted_model_input=0.67, default_exposure=0.65 | - |
| 0.645 | `src/ftpd.c#L5655-6057` | untrusted_model_input=0.67 | - |
| 0.645 | `src/log_puredb.c#L1-397` | untrusted_model_input=0.7 | - |
| 0.610 | `src/log_ldap_p.h` | untrusted_model_input=0.62 | - |
| 0.580 | `src/simpleconf_ftpd.h` | untrusted_model_input=0.59 | - |
| 0.580 | `src/tls.c#L1-363` | untrusted_model_input=0.6 | - |
| 0.570 | `src/tls.c#L364-609` | auth_boundary=0.56, default_exposure=0.58 | - |
| 0.565 | `src/pure-pw.c#L1186-1589` | untrusted_model_input=0.58 | - |
| 0.535 | `src/ftpd.c#L995-1406` | default_exposure=0.57 | - |
| 0.520 | `pureftpd-pgsql.conf` | untrusted_model_input=0.53 | - |
| 0.520 | `src/diraliases.c` | untrusted_model_input=0.54 | - |
| 0.515 | `src/globals.h` | default_exposure=0.53 | - |
| 0.490 | `src/ftpd.c#L4781-5224` | default_exposure=0.51 | - |
| 0.490 | `src/tls_extcert.h` | untrusted_model_input=0.5 | - |
| 0.480 | `src/ftpd.c#L6058-6364` | - | - |
| 0.475 | `src/log_extauth.c` | - | - |
| 0.475 | `src/log_mysql.c#L377-665` | - | - |
| 0.475 | `src/log_puredb.c#L398-476` | - | - |
| 0.470 | `src/log_pgsql_p.h` | - | - |
| 0.465 | `src/ftpd_p.h` | - | - |
| 0.445 | `src/bonjour.c` | - | - |
| 0.440 | `src/ftp_parser.c#L420-734` | - | - |
| 0.440 | `src/tls_extcert.c` | - | - |
| 0.430 | `pureftpd-mysql.conf` | - | - |
| 0.430 | `pureftpd-ldap.conf` | - | - |
| 0.430 | `src/log_mysql_p.h` | - | - |
| 0.420 | `src/pure-pw.c#L1-411` | - | - |
| 0.400 | `src/messages_check.pl` | - | - |
| 0.390 | `src/pure-ftpwho.c#L383-713` | - | - |
| 0.375 | `src/ftp_parser.c#L1-419` | - | - |
| 0.375 | `src/ftpd.c#L541-994` | - | - |
| 0.370 | `src/log_pgsql.c#L405-729` | - | - |
| 0.370 | `src/simpleconf.c#L1-397` | - | - |
| 0.365 | `src/ftpd.c#L1407-1834` | - | - |
| 0.360 | `src/ftpd.c#L1835-2256` | - | - |
| 0.360 | `src/pure-authd_p.h` | - | - |
| 0.360 | `src/simpleconf.h` | - | - |
| 0.355 | `src/ftpd.c#L1-540` | - | - |
| 0.350 | `src/log_ldap.c#L433-661` | - | - |
| 0.350 | `src/upload-pipe.c` | - | - |
| 0.340 | `src/bonjour.h` | - | - |
| 0.335 | `src/ftpd.c#L4338-4780` | - | - |

## 读取建议

- 优先检查分数（priority）≥ 0.70：优先用 Read/Grep 深入阅读。
- 0.40–0.70：人工或模型复核，尤其是风险信号（flags）命中但已有防护措施（mitigations）未命中的单元。
- < 0.40：可跳过；若涉及已知危险操作关键词，仍以 ripgrep 结果为准。
- Jev 只做召回初筛，不作为漏洞结论；最终必须读代码确认。
