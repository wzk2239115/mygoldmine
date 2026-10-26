# 公开漏洞汇总（T01）

- 生成日期：2026-10-27
- 范围：Publicly disclosed vulnerabilities affecting codex, deepseek-harness, vLLM, SGLang and verl. Local source copies only; no exploits executed.
- 条目数：38（vLLM 7、SGLang 16、verl 3、codex 6、deepseek-harness 6）
- 方法：Primary sources: GitHub Advisory Database pages (fetched and parsed), CERT/CC VU#281278, NVD/CVE records and upstream issue/PR references. Entries without a CVE or CVSS are marked Unverified/Unverified (non-CVE issue).
- 机器可读版本：`research/disclosed-vulns.json`（字段 project, id, aliases, type, component, affected, severity, cvss, cwe, summary, source_url, fix_ref, verified）

> 说明：CERT/CC VU#281278 中的 SGLang CVE 未给出 CVSS，故 severity 标为 `Unverified`；verl issue #5331 不是 CVE，仅作为上游公开安全 issue 记录并明确标注。未核实或无法给出 URL 的条目未写入本清单。

## 汇总

| 项目 | 条目 | 主要漏洞类型 |
|---|---:|---|
| vLLM | 7 | 认证绕过、反序列化 RCE、内存破坏、SSRF、trust_remote_code 绕过 |
| SGLang | 16 | pickle/dill 反序列化 RCE、路径遍历写文件、SSRF/本地文件读取、凭据泄露、模型权重外泄、DoS |
| verl | 3 | unsafe eval、torch.load 反序列化、安全 issue |
| OpenAI Codex CLI / Desktop | 6 | MCP/配置注入、沙箱绕过、命令审批绕过、Git hook/filter/fsmonitor 执行 |
| DeepSeek Harness (dsh) | 6 | 认证绕过、搜索路径 RCE、提示注入、沙箱逃逸/隔离不足 |

## vLLM

### CVE-2026-48746 — authentication-bypass

- **组件**：`vllm/entrypoints/openai/api_server.py AuthenticationMiddleware`
- **影响版本**：`>= 0.3.0, < 0.22.0`
- **严重性**：Critical (CVSS 9.1)
- **CWE**：CWE-444, CWE-501
- **摘要**：Starlette/ASGI 重建 URL 时信任 Host 头，攻击者用特殊字符构造 Host 使 url_path 与路由不一致，从而绕过配置的 API Key 认证。
- **来源**：<https://github.com/advisories/GHSA-94f4-hr76-p5j6>
- **修复参考**：`https://github.com/vllm-project/vllm/pull/43426`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-47277 — rce-deserialization

- **组件**：`PyNcclPipe CPU 控制通道 send_obj/recv_obj`
- **影响版本**：`>= 0.6.5, < 0.8.5`
- **严重性**：Critical (CVSS 9.8)
- **CWE**：CWE-502
- **摘要**：PyNcclPipe 服务对收到的序列化数据直接反序列化，未认证攻击者可发送恶意对象在 vLLM 节点执行代码（仅 V0 引擎 + PyNcclPipe KV cache 传输受影响）。
- **来源**：<https://github.com/advisories/GHSA-hjq4-87xh-g4fv>
- **修复参考**：`https://github.com/vllm-project/vllm/pull/15988`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-62164 — memory-corruption-deserialization

- **组件**：`Completions API prompt_embeds / torch.load + to_dense`
- **影响版本**：`>= 0.10.2, < 0.11.1`
- **严重性**：High (CVSS 8.8)
- **CWE**：CWE-123, CWE-20, CWE-502, CWE-787
- **摘要**：Completions 接口用 torch.load 加载用户提供的 prompt embeddings；PyTorch 2.8 默认关闭稀疏张量完整性检查，构造张量可越界写并导致 DoS/潜在 RCE。
- **来源**：<https://github.com/advisories/GHSA-mrw7-hf4f-83pf>
- **修复参考**：`https://github.com/vllm-project/vllm/pull/27204`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-6242 — ssrf

- **组件**：`MediaConnector.load_from_url / load_from_url_async`
- **影响版本**：`>= 0.5.0, < 0.11.0`
- **严重性**：High (CVSS 7.1)
- **CWE**：CWE-601, CWE-918
- **摘要**：多模态 MediaConnector 对用户提供的 URL 缺少目标主机限制，可迫使 vLLM 请求内网资源、扫描集群或读取云元数据。
- **来源**：<https://github.com/advisories/GHSA-3f6c-7fw2-ppm4>
- **修复参考**：`vLLM >= 0.11.0 (patched version in advisory)`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-25960 — ssrf-bypass

- **组件**：`vllm/connections.py load_from_url_async`
- **影响版本**：`>= 0.15.1, < 0.17.0`
- **严重性**：Moderate (CVSS 5.4)
- **CWE**：CWE-918
- **摘要**：SSRF 修复使用 urllib3 解析 URL，而实际请求用 aiohttp/yarl；两者对反斜杠处理不一致导致校验绕过。
- **来源**：<https://github.com/advisories/GHSA-v359-jj2v-j536>
- **修复参考**：`https://github.com/vllm-project/vllm/pull/34743`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-27893 — rce-trust-remote-code

- **组件**：`vllm/model_executor/models/nemotron_vl.py, kimi_k25.py`
- **影响版本**：`>= 0.10.1, < 0.18.0`
- **严重性**：High (CVSS 8.8)
- **CWE**：CWE-693
- **摘要**：两个模型实现硬编码 trust_remote_code=True，绕过用户显式 --trust-remote-code=False，恶意模型仓库可执行代码。
- **来源**：<https://github.com/advisories/GHSA-7972-pg2x-xr59>
- **修复参考**：`https://github.com/vllm-project/vllm/pull/36192`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-66448 — rce-config-auto-map

- **组件**：`vllm.transformers_utils.config.get_config / Nemotron_Nano_VL_Config`
- **影响版本**：`< 0.11.1`
- **严重性**：High (CVSS 7.1)
- **CWE**：CWE-94
- **摘要**：加载含 auto_map 的 model config 时通过 get_class_from_dynamic_module 拉取并实例化远程类，即使调用方设置 trust_remote_code=False 仍执行。
- **来源**：<https://github.com/advisories/GHSA-8fr4-5q9j-m8gm>
- **修复参考**：`https://github.com/vllm-project/vllm/pull/28126`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

## SGLang

### CVE-2026-3059 — rce-deserialization

- **组件**：`multimodal_gen ZMQ broker scheduler_client.py`
- **影响版本**：`<= 0.5.9`
- **严重性**：Critical (CVSS 9.8)
- **CWE**：CWE-502
- **摘要**：多模态生成 ZMQ broker 对未认证消息直接 pickle.loads，暴露端口即可 RCE。
- **来源**：<https://github.com/advisories/GHSA-rgq9-fqf5-fv58>
- **修复参考**：`https://github.com/sgl-project/sglang/releases/tag/v0.5.10`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-3060 — rce-deserialization

- **组件**：`srt/disaggregation/encode_receiver.py`
- **影响版本**：`<= 0.5.9`
- **严重性**：Critical (CVSS 9.8)
- **CWE**：CWE-502
- **摘要**：encoder parallel disaggregation 模块对未认证数据直接 pickle.loads，导致未认证 RCE。
- **来源**：<https://github.com/advisories/GHSA-jx93-g359-86wm>
- **修复参考**：`https://github.com/sgl-project/sglang/releases/tag/v0.5.10`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-7301 — rce-deserialization

- **组件**：`multimodal_gen scheduler ROUTER socket`
- **影响版本**：`>= 0.5.5, <= 0.5.12`
- **严重性**：Critical (CVSS 9.8)
- **CWE**：CWE-502
- **摘要**：多模态 scheduler 的 ROUTER socket 默认绑定 0.0.0.0，收到的消息直接 pickle.loads，暴露公网即可 RCE。
- **来源**：<https://github.com/advisories/GHSA-gwv6-pq6m-p3rq>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-7302 — path-traversal-file-write

- **组件**：`multimodal generation upload filename`
- **影响版本**：`>= 0.5.5, <= 0.5.12`
- **严重性**：Critical (CVSS 9.1)
- **CWE**：CWE-35
- **摘要**：多模态生成运行时的上传接口未清理文件名中的 ../，可向服务进程有写权限的任意位置写文件。
- **来源**：<https://github.com/advisories/GHSA-qwrp-wghp-94q2>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-7304 — rce-dill-deserialization

- **组件**：`--enable-custom-logit-processor / dill.loads`
- **影响版本**：`>= 0.4.1.post7, <= 0.5.12`
- **严重性**：Critical (CVSS 9.8)
- **CWE**：CWE-502
- **摘要**：启用 --enable-custom-logit-processor 后对加载对象调用 dill.loads 且无校验，形成未认证 RCE。
- **来源**：<https://github.com/advisories/GHSA-36m8-w8qf-g76p>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-3989 — insecure-deserialization-script

- **组件**：`scripts/playground/replay_request_dump.py pickle.load`
- **影响版本**：`<= 0.5.9`
- **严重性**：High (CVSS 7.8)
- **CWE**：CWE-502
- **摘要**：replay_request_dump.py 对本地 .pkl 文件直接 pickle.load，打开恶意 dump 即执行攻击者代码。
- **来源**：<https://github.com/advisories/GHSA-hvwj-8w5g-28rg>
- **修复参考**：`https://github.com/sgl-project/sglang/releases/tag/v0.5.10`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-10164 — rce-deserialization

- **组件**：`/update_weights_from_tensor serialized_named_tensors`
- **影响版本**：`<= 0.5.3`
- **严重性**：Moderate (CVSS 5.5)
- **CWE**：CWE-20, CWE-502
- **摘要**：/update_weights_from_tensor 对 serialized_named_tensors 反序列化未校验，远程攻击者可利用。
- **来源**：<https://github.com/advisories/GHSA-9w53-xr52-mwgj>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-7669 — insecure-deserialization

- **组件**：`python/sglang/srt/utils/hf_transformers_utils.py get_tokenizer`
- **影响版本**：`<= 0.5.9`
- **严重性**：Moderate (CVSS 6.3)
- **CWE**：CWE-20, CWE-74
- **摘要**：HuggingFace tokenizer 加载路径存在反序列化问题，可远程触发（高复杂度）。
- **来源**：<https://github.com/advisories/GHSA-6m5f-673f-5vh7>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-10300 — reachable-assertion-dos

- **组件**：`python/sglang/srt/lora/lora_manager.py lora_path`
- **影响版本**：`<= 0.5.10.post1`
- **严重性**：Low (CVSS 2.9)
- **CWE**：CWE-617
- **摘要**：LoRAManager 对 lora_path 处理可触发可达断言，远程请求使推理服务崩溃。
- **来源**：<https://github.com/advisories/GHSA-m2jr-x4gq-5rmj>
- **修复参考**：`https://github.com/sgl-project/sglang/pull/25078`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-10775 — dos

- **组件**：`Cache Handler data_hash`
- **影响版本**：`<= 0.5.11`
- **严重性**：Low (CVSS 1.1)
- **CWE**：CWE-404
- **摘要**：data_hash 处理存在拒绝服务问题，本地高复杂度触发。
- **来源**：<https://github.com/advisories/GHSA-jrcc-j37m-v8fg>
- **修复参考**：`https://github.com/sgl-project/sglang/pull/25462`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-15969 — rce-deserialization

- **组件**：`/load_lora_adapter_from_tensors SafeUnpickler denylist bypass`
- **影响版本**：`CERT/CC VU#281278: no vendor patch at publication (2026-07-30)`
- **严重性**：Unverified (no CVSS in CERT note)
- **摘要**：SafeUnpickler 不完整 denylist 可被绕过，构造 base64 pickle 载荷实现未认证 RCE。
- **来源**：<https://www.kb.cert.org/vuls/id/281278>
- **修复参考**：无公开修复链接
- **核实**：CERT/CC VU#281278 note fetched 2026-10-27; CVE IDs and affected endpoints listed in the note

### CVE-2026-15971 — rce-dumper-sandbox-escape

- **组件**：`可选 dumper 子系统 / DUMPER_SERVER_PORT`
- **影响版本**：`CERT/CC VU#281278: no vendor patch at publication (2026-07-30)`
- **严重性**：Unverified (no CVSS in CERT note)
- **摘要**：启用 dumper 且设置 DUMPER_SERVER_PORT 时可沙箱逃逸并在推理请求中执行代码。
- **来源**：<https://www.kb.cert.org/vuls/id/281278>
- **修复参考**：无公开修复链接
- **核实**：CERT/CC VU#281278 note fetched 2026-10-27; CVE IDs and affected endpoints listed in the note

### CVE-2026-15974 — ssrf-local-file-read

- **组件**：`/v1/chat/completions image_url`
- **影响版本**：`CERT/CC VU#281278: no vendor patch at publication (2026-07-30)`
- **严重性**：Unverified (no CVSS in CERT note)
- **摘要**：image_url 未净化，可访问内部元数据、密钥和服务，并读取本地文件。
- **来源**：<https://www.kb.cert.org/vuls/id/281278>
- **修复参考**：无公开修复链接
- **核实**：CERT/CC VU#281278 note fetched 2026-10-27; CVE IDs and affected endpoints listed in the note

### CVE-2026-15976 — rce-deserialization

- **组件**：`/update_weights_from_disk HuggingFace 权重加载`
- **影响版本**：`CERT/CC VU#281278: no vendor patch at publication (2026-07-30)`
- **严重性**：Unverified (no CVSS in CERT note)
- **摘要**：torch.load(..., weights_only=False) 回退导致 .bin 文件 pickle 反序列化 RCE。
- **来源**：<https://www.kb.cert.org/vuls/id/281278>
- **修复参考**：无公开修复链接
- **核实**：CERT/CC VU#281278 note fetched 2026-10-27; CVE IDs and affected endpoints listed in the note

### CVE-2026-15977 — credential-disclosure

- **组件**：`/server_info`
- **影响版本**：`CERT/CC VU#281278: no vendor patch at publication (2026-07-30)`
- **严重性**：Unverified (no CVSS in CERT note)
- **摘要**：仅配置 --admin-api-key 时 /server_info 返回 API key 与 SSL keyfile 信息。
- **来源**：<https://www.kb.cert.org/vuls/id/281278>
- **修复参考**：无公开修复链接
- **核实**：CERT/CC VU#281278 note fetched 2026-10-27; CVE IDs and affected endpoints listed in the note

### CVE-2026-15978 — model-weight-exfiltration

- **组件**：`未配置 API key 时的分布式权重广播端点 (NCCL)`
- **影响版本**：`CERT/CC VU#281278: no vendor patch at publication (2026-07-30)`
- **严重性**：Unverified (no CVSS in CERT note)
- **摘要**：攻击者可触发 distributed weight broadcasting 并外传全部模型权重。
- **来源**：<https://www.kb.cert.org/vuls/id/281278>
- **修复参考**：无公开修复链接
- **核实**：CERT/CC VU#281278 note fetched 2026-10-27; CVE IDs and affected endpoints listed in the note

## verl

### CVE-2026-6878 — rce-unsafe-eval

- **组件**：`verl/utils/reward_score/prime_math/grader.py math_equal`
- **影响版本**：`<= 0.7.1`
- **严重性**：Low (CVSS 2.9)
- **CWE**：CWE-95
- **摘要**：math_equal 对模型输出使用 eval()，恶意/不可信内容可逃逸沙箱并执行任意代码（复杂度较高）。
- **来源**：<https://github.com/advisories/GHSA-h57c-v2v3-5v3v>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-50461 — rce-deserialization

- **组件**：`scripts/model_merger.py (fsdp backend) torch.load(weights_only=False)`
- **影响版本**：`3.0.0`
- **严重性**：Moderate (CVSS 6.5)
- **CWE**：CWE-77
- **摘要**：model_merger.py 使用 fsdp 后端时对用户提供的 .pt 文件调用 torch.load(weights_only=False)，加载恶意模型即 RCE。
- **来源**：<https://github.com/advisories/GHSA-xhf5-3r9v-mm67>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### verl-issue-5331 — security-issue-unsafe-eval-deserialization

- **组件**：`prime_math/grader.py, scripts/model_merger.py, shell eval`
- **影响版本**：`verl <= 0.7.1 / 3.0.0 (issue opened 2026-02-15, closed 2026-08-21)`
- **严重性**：Unverified (non-CVE issue)
- **CWE**：CWE-95, CWE-502
- **摘要**：上游公开安全 issue，汇总 math_equal 的 eval、pickle.load/torch.load(weights_only=False) 及 shell eval 三类不安全用法；issue 已关闭完成，但未分配独立 CVE。
- **来源**：<https://github.com/verl-project/verl/issues/5331>
- **修复参考**：`https://github.com/verl-project/verl/issues/5331`
- **核实**：GitHub issue #5331 fetched 2026-10-27; body and maintainer reply explicitly discuss eval/pickle.load/torch.load/shell eval

## OpenAI Codex CLI / Desktop

### CVE-2025-61260 — rce-mcp-config

- **组件**：`codex CLI project-local .env / .codex/config.toml`
- **影响版本**：`<= 0.23.0`
- **严重性**：Critical (CVSS 9.8)
- **CWE**：CWE-94
- **摘要**：在恶意仓库运行 codex 时自动加载项目级 .env 与 .codex/config.toml（无需确认），可植入命令立即执行。
- **来源**：<https://github.com/advisories/GHSA-xrxf-jgv3-qmrm>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-59532 — sandbox-bypass

- **组件**：`sandbox configuration / model-generated cwd`
- **影响版本**：`>= 0.2.0, <= 0.38.0`
- **严重性**：High (CVSS 8.6)
- **CWE**：CWE-20
- **摘要**：沙箱配置逻辑缺陷把模型生成的 cwd 当作可写根，可越过用户初始工作区边界写文件并执行命令。
- **来源**：<https://github.com/advisories/GHSA-w5fx-fh39-j5rw>
- **修复参考**：`https://github.com/openai/codex/releases/tag/rust-v0.39.0`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2025-54558 — command-approval-bypass

- **组件**：`ripgrep (rg) auto-approval`
- **影响版本**：`< 0.9.0`
- **严重性**：Moderate (CVSS 4.1)
- **CWE**：CWE-829
- **摘要**：Codex CLI 0.9.0 之前即使用 --pre/--hostname-bin/--search-zip/-z 也自动批准 rg 执行。
- **来源**：<https://github.com/advisories/GHSA-q6hp-29g8-7j6j>
- **修复参考**：`https://github.com/openai/codex/pull/1644`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-19590 — git-hook-rce

- **组件**：`Git core.hooksPath`
- **影响版本**：`Unknown`
- **严重性**：High (CVSS 7.3)
- **CWE**：CWE-427
- **摘要**：Codex Desktop 自动 Git 操作信任仓库本地 core.hooksPath，打开攻击者准备的仓库即执行沙箱外恶意 hook。
- **来源**：<https://github.com/advisories/GHSA-433v-pqvh-w4gj>
- **修复参考**：`https://github.com/openai/codex/pull/22843`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-19593 — git-filter-rce

- **组件**：`Git attr.tree + clean/process filter`
- **影响版本**：`Codex Desktop (Windows/macOS), patched per advisory`
- **严重性**：Critical (CVSS 9.8)
- **CWE**：CWE-15
- **摘要**：自动读取 Git 元数据时信任仓库 .git/config 的 attr.tree 与 clean/process filter，打开仓库即执行攻击者程序。
- **来源**：<https://github.com/advisories/GHSA-hcf6-9q9g-xx3c>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-19592 — git-fsmonitor-rce

- **组件**：`Git core.fsmonitor`
- **影响版本**：`Unknown`
- **严重性**：High (CVSS 7.3)
- **CWE**：CWE-15
- **摘要**：自动收集 Git 元数据时未禁用 core.fsmonitor，恶意仓库配置可让 Git 执行攻击者 helper，绕过命令沙箱与审批。
- **来源**：<https://github.com/advisories/GHSA-26wp-42v3-96xp>
- **修复参考**：`https://github.com/openai/codex/pull/22652`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

## DeepSeek Harness (dsh)

### CVE-2026-82533 — authentication-bypass

- **组件**：`local HTTP control-plane API Host header`
- **影响版本**：`< 0.1.2-alpha.1`
- **严重性**：Critical (CVSS 9.4)
- **CWE**：CWE-807
- **摘要**：本地 HTTP 控制面只校验客户端 Host 头而不校验 TCP 来源，伪造 Host 可完全控制 agent、以 danger-full-access 执行命令并读取全部会话。
- **来源**：<https://github.com/advisories/GHSA-8m2g-8cgm-3vcp>
- **修复参考**：`https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.1.2-alpha.1`
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-95182 — untrusted-search-path-rce

- **组件**：`dsh commit c291e796 executable lookup`
- **影响版本**：`commit c291e796`
- **严重性**：Critical (CVSS 10.0)
- **CWE**：CWE-426
- **摘要**：不受信任的搜索路径可被替换为恶意可执行文件，打开恶意内容即执行任意代码。
- **来源**：<https://github.com/advisories/GHSA-g5wx-c65h-w9px>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-95183 — prompt-injection

- **组件**：`context-compaction feature`
- **影响版本**：`commit c291e796`
- **严重性**：High (CVSS 8.8)
- **CWE**：CWE-94
- **摘要**：context-compaction 处理外部内容时可被提示注入，攻击者通过构造内容影响 agent 行为。
- **来源**：<https://github.com/advisories/GHSA-8rmg-g7v9-j8x6>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-101102 — sandbox-escape

- **组件**：`Code Mode Sandbox run_code`
- **影响版本**：`<= 0.1.0-rc.7`
- **严重性**：Moderate (CVSS 5.3)
- **摘要**：run_code 沙箱隔离不足；项目 SAFETY.md 明确 worker 仅为 containment 而非安全边界。
- **来源**：<https://github.com/advisories/GHSA-m9ww-cpfc-8cf2>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-101078 — sandbox-isolation

- **组件**：`packages/sandbox/sandbox-local/src/profiles.ts Landlock backend`
- **影响版本**：`<= 0.1.7-rc.2`
- **严重性**：Low (CVSS 1.9)
- **CWE**：CWE-653
- **摘要**：Landlock 后端配置不当导致隔离/分区不充分，本地攻击者可利用。
- **来源**：<https://github.com/advisories/GHSA-23q9-h232-4q79>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

### CVE-2026-108788 — sandbox-escape

- **组件**：`Sandbox spawn / Profile argument`
- **影响版本**：`<= 0.1.1-rc.2`
- **严重性**：Low (CVSS 1.9)
- **摘要**：Sandbox 组件的 spawn 对 Profile 参数处理不当导致沙箱问题，本地可利用。
- **来源**：<https://github.com/advisories/GHSA-5mvr-2xwh-9v9q>
- **修复参考**：无公开修复链接
- **核实**：GitHub Advisory Database page fetched; CVE/GHSA and version range confirmed

## 观察与使用限制

1. **反序列化是 AI 基础设施最集中的高危面**：vLLM 的 PyNcclPipe/prompt_embeds、SGLang 的 ZMQ/encoder disaggregation/权重加载都直接触发 RCE（CWE-502），且多处是未认证网络入口。
2. **模型加载链路反复出问题**：`trust_remote_code`、`auto_map`、`torch.load(weights_only=False)` 既出现在 vLLM，也出现在 SGLang 与 verl，说明需要专门的“模型/权重加载”检测规则。
3. **SSRF 与本地文件读取是第二大类**：vLLM MediaConnector（含修复绕过）与 SGLang `image_url` 都表明“远程 URL → 服务端请求”的路径需要统一 sink 建模。
4. **Agent/CLI 的信任边界问题突出**：Codex 的 MCP 配置、Git hook/filter/fsmonitor 与 DeepSeek Harness 的 Host 头认证绕过，都是“打开/处理不可信工作区”导致沙箱外执行。
5. **CERT/CC VU#281278 与 GitHub Advisory 的时间线不同**：CERT 条目在发布时无厂商补丁；GitHub 条目多数已给出补丁版本。两者都保留，便于后续区分“已知修复”与“无修复”风险。
6. **未写入的内容**：未在 NVD/GHSA/CERT/项目 issue 中找到可核实来源的传闻、无 URL 的 CVE 编号、以及需要运行 exploit 才能确认的细节均未记录；后续如需扩展，应补充 source_url 并更新本文件与 JSON。
