# Jev triage

- model: `typesafe/jev-latest` (returned: `typesafe/jev-1.14-20261014`)
- profile: `infra`
- units: 71
- requests: 71 (cached: 0)
- errors: 0
- input tokens: 133785
- cost: $0.005619
- elapsed: 13496 ms

| priority | unit | flags | mitigations |
|---|---|---|---|
| 0.975 | `changelog.sh` | subprocess_exec=0.98 | - |
| 0.950 | `tests/integration/sol_test.py` | subprocess_exec=0.96, default_exposure=0.51 | - |
| 0.940 | `.travis.yml` | subprocess_exec=0.95 | - |
| 0.890 | `CMakeLists.txt` | subprocess_exec=0.9 | - |
| 0.890 | `src/sol.c` | untrusted_model_input=0.9, default_exposure=0.82 | - |
| 0.800 | `src/config.c#L1-372` | untrusted_model_input=0.78, default_exposure=0.81 | - |
| 0.790 | `src/network.c#L1-479` | default_exposure=0.8 | - |
| 0.740 | `src/server.c#L694-1062` | default_exposure=0.75 | - |
| 0.720 | `README.md` | untrusted_model_input=0.74, default_exposure=0.55 | - |
| 0.695 | `src/server.c#L318-693` | default_exposure=0.7 | - |
| 0.600 | `src/server.c#L1-317` | default_exposure=0.61 | - |
| 0.580 | `src/handlers.c#L341-690` | default_exposure=0.59 | - |
| 0.570 | `src/config.h` | untrusted_model_input=0.58 | - |
| 0.565 | `conf/sol.conf` | untrusted_model_input=0.52, default_exposure=0.58 | - |
| 0.550 | `src/config.c#L373-471` | untrusted_model_input=0.56 | - |
| 0.540 | `src/handlers.c#L1-340` | default_exposure=0.55 | - |
| 0.530 | `tests/integration/run.py` | subprocess_exec=0.54 | - |
| 0.515 | `src/server.h` | default_exposure=0.52 | - |
| 0.495 | `src/handlers.c#L691-880` | default_exposure=0.5 | - |
| 0.450 | `src/network.h` | - | - |
| 0.435 | `src/network.c#L480-583` | - | - |
| 0.415 | `src/sol_internal.h#L1-276` | - | - |
| 0.345 | `passwd.py` | - | - |
| 0.280 | `src/mqtt.c#L1-279` | - | - |
| 0.245 | `src/mqtt.c#L280-684` | - | - |
| 0.215 | `tests/integration/test_connect.py` | - | - |
| 0.205 | `tests/integration/base_testcase.py` | - | - |
| 0.200 | `src/logging.c` | - | - |
| 0.190 | `tests/integration/test_subscribe.py` | - | - |
| 0.175 | `src/pack.c` | - | - |
| 0.170 | `src/util.c` | - | - |
| 0.165 | `src/ev.c#L1-386` | - | - |
| 0.155 | `src/topic_store.c` | - | - |
| 0.150 | `src/sol_internal.h#L277-389` | - | - |
| 0.140 | `src/handlers.h` | - | - |
| 0.125 | `src/ev.c#L387-781` | - | - |
| 0.125 | `src/ev.c#L782-879` | - | - |
| 0.120 | `src/pack.h` | - | - |
| 0.115 | `src/ev.h` | - | - |
| 0.115 | `src/mqtt.h` | - | - |
| 0.115 | `src/topic.c` | - | - |
| 0.115 | `src/subscriber.c` | - | - |
| 0.085 | `src/uthash.h#L780-954` | - | - |
| 0.080 | `src/logging.h` | - | - |
| 0.080 | `src/trie.c#L420-443` | - | - |
| 0.075 | `src/memory.c` | - | - |
| 0.075 | `src/memorypool.c` | - | - |
| 0.075 | `src/trie.c#L1-419` | - | - |
| 0.070 | `src/util.h` | - | - |
| 0.065 | `src/list.c` | - | - |

## 读取建议

- 优先检查分数（priority）≥ 0.70：优先用 Read/Grep 深入阅读。
- 0.40–0.70：人工或模型复核，尤其是风险信号（flags）命中但已有防护措施（mitigations）未命中的单元。
- < 0.40：可跳过；若涉及已知危险操作关键词，仍以 ripgrep 结果为准。
- Jev 只做召回初筛，不作为漏洞结论；最终必须读代码确认。
