# Jev triage

- model: `typesafe/jev-latest` (returned: `typesafe/jev-1.14-20261014`)
- profile: `infra`
- units: 192
- requests: 192 (cached: 0)
- errors: 0
- input tokens: 941745
- cost: $0.039553
- elapsed: 38593 ms

| priority | unit | flags | mitigations |
|---|---|---|---|
| 0.930 | `examples/tlssimpleserver.c` | default_exposure=0.94 | - |
| 0.920 | `examples/tlshelloworld.c` | default_exposure=0.93 | - |
| 0.765 | `examples/tlsclienthello.c` | auth_boundary=0.55, outbound_url=0.77 | - |
| 0.750 | `examples/tlssimple.c` | outbound_url=0.76 | - |
| 0.640 | `tlse.c#L2414-2765` | default_exposure=0.65 | - |
| 0.530 | `tlse.c#L10841-11233` | default_exposure=0.54 | - |
| 0.530 | `tlse.c#L14202-14548` | default_exposure=0.54 | - |
| 0.515 | `tlse.h#L1-292` | default_exposure=0.52 | - |
| 0.485 | `tlse.c#L7041-7331` | - | - |
| 0.475 | `tlse.c#L13811-14201` | - | - |
| 0.430 | `x509.c#L1-428` | - | - |
| 0.390 | `tlse.c#L8511-8812` | - | - |
| 0.380 | `tlse.c#L7332-7585` | - | - |
| 0.375 | `tlse.c#L7887-8238` | - | - |
| 0.375 | `tlse.c#L9789-10035` | - | - |
| 0.375 | `tlse.c#L12745-13069` | - | - |
| 0.370 | `tlse.c#L3167-3522` | - | - |
| 0.370 | `tlse.c#L8239-8510` | - | - |
| 0.370 | `tlse.c#L14549-14920` | - | - |
| 0.370 | `x509.c#L10673-11192` | - | - |
| 0.360 | `tlse.c#L6052-6374` | - | - |
| 0.350 | `README.md` | - | - |
| 0.345 | `tlse.c#L5675-6051` | - | - |
| 0.340 | `libtomcrypt.c#L13117-13591` | - | - |
| 0.340 | `tlse.c#L7586-7886` | - | - |
| 0.340 | `tlse.c#L13070-13514` | - | - |
| 0.330 | `tlse.c#L10036-10260` | - | - |
| 0.330 | `tlse.c#L13515-13810` | - | - |
| 0.320 | `tlse.c#L11234-11555` | - | - |
| 0.310 | `tlse.c#L6713-7040` | - | - |
| 0.310 | `tlse.c#L10261-10568` | - | - |
| 0.305 | `tlse.c#L12450-12744` | - | - |
| 0.300 | `libtomcrypt.c#L17346-17807` | - | - |
| 0.300 | `libtomcrypt.c#L28578-28979` | - | - |
| 0.300 | `tlse.c#L8813-9169` | - | - |
| 0.290 | `libtomcrypt.c#L29295-29734` | - | - |
| 0.290 | `tlse.c#L9497-9788` | - | - |
| 0.290 | `tlse.c#L11810-12130` | - | - |
| 0.290 | `tlse.h#L293-479` | - | - |
| 0.290 | `x509.c#L7901-8482` | - | - |
| 0.285 | `tlse.c#L14921-15009` | - | - |
| 0.280 | `tlse.c#L1778-2117` | - | - |
| 0.280 | `tlse.c#L4747-5088` | - | - |
| 0.280 | `tlse.c#L4464-4746` | - | - |
| 0.280 | `tlse.c#L5294-5674` | - | - |
| 0.270 | `tlse.c#L2118-2413` | - | - |
| 0.265 | `libtomcrypt.c#L17808-18260` | - | - |
| 0.260 | `tlse.c#L10569-10840` | - | - |
| 0.260 | `tlse.c#L12131-12449` | - | - |
| 0.260 | `x509.c#L3644-4214` | - | - |

## 读取建议

- 优先检查分数（priority）≥ 0.70：优先用 Read/Grep 深入阅读。
- 0.40–0.70：人工或模型复核，尤其是风险信号（flags）命中但已有防护措施（mitigations）未命中的单元。
- < 0.40：可跳过；若涉及已知危险操作关键词，仍以 ripgrep 结果为准。
- Jev 只做召回初筛，不作为漏洞结论；最终必须读代码确认。
