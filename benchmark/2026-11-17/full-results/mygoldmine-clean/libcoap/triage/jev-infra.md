# Jev triage

- model: `typesafe/jev-latest` (returned: `typesafe/jev-1.14-20261014`)
- profile: `infra`
- units: 485
- requests: 484 (cached: 0)
- errors: 1
- input tokens: 1332415
- cost: $0.055961
- elapsed: 88811 ms

| priority | unit | flags | mitigations |
|---|---|---|---|
| 0.970 | `.travis.yml` | subprocess_exec=0.98 | - |
| 0.970 | `build-env/build.sh` | subprocess_exec=0.98 | - |
| 0.970 | `get_config.sh` | subprocess_exec=0.98 | - |
| 0.970 | `autogen.sh` | subprocess_exec=0.98 | - |
| 0.970 | `examples/etsi_testcases.sh#L1-420` | subprocess_exec=0.98 | - |
| 0.970 | `examples/oscore_testcases.sh` | untrusted_model_input=0.58, subprocess_exec=0.98 | - |
| 0.970 | `scripts/build.sh` | subprocess_exec=0.98 | - |
| 0.970 | `scripts/dist.sh` | subprocess_exec=0.98 | - |
| 0.970 | `scripts/fix-cunit.sh` | subprocess_exec=0.98 | - |
| 0.970 | `scripts/check_examples.sh` | subprocess_exec=0.98 | - |
| 0.970 | `scripts/api-version-bump.sh` | subprocess_exec=0.98 | - |
| 0.970 | `scripts/github_dist.sh` | subprocess_exec=0.98 | - |
| 0.970 | `scripts/mingw-cmake.sh` | subprocess_exec=0.98 | - |
| 0.965 | `man/examples-code-check.c#L1-457` | subprocess_exec=0.98 | - |
| 0.965 | `scripts/format_cmake.sh` | subprocess_exec=0.98 | - |
| 0.960 | `CMakeLists.txt#L385-754` | subprocess_exec=0.97 | - |
| 0.960 | `examples/etsi_coaptest.sh` | subprocess_exec=0.97 | - |
| 0.960 | `scripts/check-missing-updates.sh` | subprocess_exec=0.97 | - |
| 0.960 | `scripts/check_have_.sh` | subprocess_exec=0.97 | - |
| 0.955 | `examples/tls_backend_testcases.sh#L510-817` | subprocess_exec=0.97, default_exposure=0.55 | - |
| 0.950 | `man/examples-code-check.c#L458-818` | subprocess_exec=0.97 | - |
| 0.945 | `examples/tls_backend_testcases.sh#L1-509` | subprocess_exec=0.96 | - |
| 0.940 | `examples/etsi_testcases.sh#L421-765` | subprocess_exec=0.95 | - |
| 0.940 | `examples/tls_backend_testcases.sh#L818-1196` | subprocess_exec=0.95 | - |
| 0.910 | `CMakeLists.txt#L986-1173` | subprocess_exec=0.92 | - |
| 0.860 | `examples/contiki/server.c` | default_exposure=0.87 | - |
| 0.850 | `examples/lwip/server-coap.c` | default_exposure=0.86 | - |
| 0.845 | `examples/tls_backend_testcases.sh#L1197-1529` | subprocess_exec=0.86 | - |
| 0.840 | `examples/oscore-interop-server.c#L345-724` | untrusted_model_input=0.82, default_exposure=0.85 | - |
| 0.835 | `examples/etsi_iot_01.c#L412-639` | default_exposure=0.85 | - |
| 0.815 | `examples/etsi_iot_01.c#L1-411` | default_exposure=0.83 | - |
| 0.795 | `examples/tls_backend_testcases.sh#L1530-1866` | subprocess_exec=0.81 | - |
| 0.790 | `examples/coap-rd.c#L766-908` | default_exposure=0.8 | - |
| 0.790 | `examples/coap-server.c#L1464-1795` | untrusted_model_input=0.81, default_exposure=0.62 | - |
| 0.785 | `examples/coap-rd.c#L446-765` | default_exposure=0.8 | - |
| 0.780 | `examples/coap-client.c#L702-1024` | untrusted_model_input=0.79 | - |
| 0.780 | `examples/tls_backend_testcases.sh#L1867-1952` | subprocess_exec=0.79 | - |
| 0.770 | `examples/coap-server.c#L2262-2668` | untrusted_model_input=0.79 | - |
| 0.770 | `examples/riot/tests_pkg_libcoap/tests/01-run.py` | subprocess_exec=0.78 | - |
| 0.750 | `examples/coap-server.c#L1-402` | untrusted_model_input=0.75, default_exposure=0.77 | - |
| 0.745 | `examples/oscore-interop-server.c#L1-344` | default_exposure=0.76 | - |
| 0.745 | `examples/lwip/server.c` | default_exposure=0.75 | - |
| 0.740 | `examples/coap-server.c#L2669-3130` | untrusted_model_input=0.76, default_exposure=0.74 | - |
| 0.740 | `examples/riot/examples_libcoap_server/server_coap.c` | default_exposure=0.75 | - |
| 0.740 | `src/coap_dgrm_lwip.c#L1-408` | default_exposure=0.75 | - |
| 0.725 | `examples/coap-server.c#L1116-1463` | default_exposure=0.74 | - |
| 0.720 | `man/examples-code-check.c#L819-857` | subprocess_exec=0.74 | - |
| 0.720 | `src/coap_openhitls.c#L1496-1777` | untrusted_model_input=0.74 | - |
| 0.710 | `examples/coap-client.c#L1467-1793` | untrusted_model_input=0.73, default_exposure=0.52 | - |
| 0.705 | `src/coap_dgrm_posix.c#L1-369` | default_exposure=0.71 | - |

## 读取建议

- 优先检查分数（priority）≥ 0.70：优先用 Read/Grep 深入阅读。
- 0.40–0.70：人工或模型复核，尤其是风险信号（flags）命中但已有防护措施（mitigations）未命中的单元。
- < 0.40：可跳过；若涉及已知危险操作关键词，仍以 ripgrep 结果为准。
- Jev 只做召回初筛，不作为漏洞结论；最终必须读代码确认。
