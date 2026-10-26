# mygoldmine 能力差距分析与优先级（T03）

- 生成时间：2026-10-27
- 输入：`research/disclosed-vulns.json`（T01，38 条 / 29 个 type）、`research/capability-matrix.md`（T02）
- 方法：以 T02 的 type 级覆盖度为起点，逐条回查 T01 的具体条目；只把「现有 skill 缺少该机制的 source/sink 或检测步骤」计为缺口，不为凑数拆条目
- 约束：本文件只做差距分析，不新增/修改 skill；不运行真实挖矿；T01 中严重度为 `Unverified`（无 CVSS）的条目在优先级上按影响面而非 CVSS 处理，并在表中显式标记

## 0. 判定口径

| 字段 | 含义 |
|------|------|
| 缺口 | T02 判为「无」，或「弱」且缺少该框架特有的 sink / 检测步骤 |
| P0 | 与 AI 推理/Agent 主链路直接相关，可导致 RCE、认证绕过或模型资产外泄；现有覆盖为「无」或仅泛化描述 |
| P1 | 需要特定运行环境（Agent 打开恶意仓库、启用沙箱、管理端点）才触发，但一旦触发影响大；可先补检测步骤 |
| P2 | 低危 / 需要组合条件 / 现有相邻 skill 已能给出线索，补规则即可 |
| 实现方式 | 新 skill / 扩展现有 skill / tree-sitter 或正则规则 / agent 编排 |

> 优先级不直接等于 CVSS。`CVE-2026-15978`、`CVE-2026-15971`、`CVE-2026-15977` 等 SGLang 条目在 T01 中无 CVSS（CERT note 未给出），本文件按其组件重要性与可利用前置条件定级。

## 1. 结论摘要

- T01 的 29 个 type 中，T02 判定：强覆盖 8、弱覆盖 14、无覆盖 7。
- 归并后共 **15 个缺口**，覆盖 **26 / 38 条** T01 条目：
  - P0：5 个缺口，10 条条目；
  - P1：7 个缺口，13 条条目；
  - P2：3 个缺口，3 条条目。
- 剩余 12 条落在 T02 已判「强」的 8 个 type 内，不需要新建 skill，只需在 T04/T05 保持现有 sink 规则可用（见 §8）。
- 真正的瓶颈不只是「缺 skill」，还有 **编排不会自动调度这些 skill**：`project-profiler` 对后端 HTTP 服务只允许 `web-auth-analyzer` + `sensitive-info-scanner` 两个后续任务（`.claude/skills/project-profiler/SKILL.md:36-38`），因此即使 T04 新增模型加载/Agent 配置 skill，也不会在普通 Python 服务项目上被自动触发（见 §6 O01）。
- 建议 T04 先落地 2 个 P0 skill：`model-loading-analyzer`、`agent-config-analyzer`；T05 再把它们接入 orchestrator 的条件任务与白名单。

## 2. 差距总表

### 2.1 P0

| 缺口 | T01 类型 | T01 条目（项目 / ID） | 现状 | 建议实现 | 目标文件 |
|------|----------|----------------------|------|----------|----------|
| G01 模型加载信任边界 | `rce-trust-remote-code`、`rce-config-auto-map` | vLLM `CVE-2026-27893`、`CVE-2025-66448` | 无 / 弱 | 新 skill：识别 `trust_remote_code`、`auto_map`、`get_class_from_dynamic_module` 的不可信模型源 → 动态导入链 | `.claude/skills/model-loading-analyzer/` |
| G02 权重与张量反序列化 | `rce-deserialization`、`insecure-deserialization`、`memory-corruption-deserialization` | verl `CVE-2025-50461`；SGLang `CVE-2026-15976`、`CVE-2026-7669`；vLLM `CVE-2025-62164` | 弱 | 扩展现有反序列化 skill：补 `torch.load` / `weights_only` / `from_pretrained` / `get_tokenizer` / 稀疏张量规则 | `insecure-deserialization-analyzer/scripts/languages/python/` |
| G03 Host 头 → 路由认证绕过 | `authentication-bypass` | vLLM `CVE-2026-48746`；deepseek-harness `CVE-2026-82533` | 弱（两个 skill 各覆盖一半） | 扩展 `web-auth-analyzer` + `http-header-injection-analyzer`：增加「Host 重建 URL → 与路由比较」检测步骤 | 两个 skill 的 `SKILL.md` / `quick-scan.py` |
| G04 Agent 项目级配置信任 | `rce-mcp-config` | codex `CVE-2025-61260` | 无 | 新 skill：MCP / `.env` / `.codex/config.toml` 等项目级配置在无确认下被信任 | `.claude/skills/agent-config-analyzer/` |
| G05 模型权重/管理端点外泄 | `model-weight-exfiltration` | SGLang `CVE-2026-15978`（T01 Unverified） | 无 | 扩展 `access-control-analyzer` + `sensitive-info-scanner`：管理端点响应字段清单、权重广播端点鉴权 | 两个 skill 的 `SKILL.md` |

### 2.2 P1

| 缺口 | T01 类型 | T01 条目（项目 / ID） | 现状 | 建议实现 | 目标文件 |
|------|----------|----------------------|------|----------|----------|
| G06 沙箱边界与逃逸 | `sandbox-isolation`、`sandbox-bypass`、`sandbox-escape`、`rce-dumper-sandbox-escape` | deepseek-harness `CVE-2026-101078`、`CVE-2025-59532`、`CVE-2026-101102`、`CVE-2026-108788`；SGLang `CVE-2026-15971`（Unverified） | 无 / 弱 | 新 skill 或大幅扩展 `code-injection-analyzer`：进程/文件系统/网络/权限四类边界与 profile 参数审计 | `.claude/skills/agent-sandbox-analyzer/` |
| G07 命令审批绕过 | `command-approval-bypass` | codex `CVE-2025-54558` | 无 | 并入 G04 的 `agent-config-analyzer`：审批白名单、`rg` 参数/别名、shell 展开 | `.claude/skills/agent-config-analyzer/` |
| G08 Git 仓库信任链 | `git-hook-rce`、`git-filter-rce`、`git-fsmonitor-rce` | codex `CVE-2026-19590`、`CVE-2026-19593`、`CVE-2026-19592` | 弱 / 无 | 扩展 `security-configuration-analyzer` 的 Git 章节，并加 `quick-scan` 规则；或并入 G04 | `security-configuration-analyzer/general_Git_Configuration_Injection.md` |
| G09 可执行文件搜索路径 | `untrusted-search-path-rce` | deepseek-harness `CVE-2026-95182` | 弱 | 扩展 `command-injection-analyzer`：可执行文件解析、当前目录优先、`PATH` 继承 | `command-injection-analyzer/` |
| G10 SSRF 解析器差异 | `ssrf-bypass` | vLLM `CVE-2026-25960` | 弱 | 扩展 `ssrf-analyzer`：校验库与请求库不一致、URL 规范化差异 | `ssrf-analyzer/SKILL.md`、`bypassTricks.md` |
| G11 管理端点凭据泄露 | `credential-disclosure` | SGLang `CVE-2026-15977`（Unverified） | 弱 | 扩展 `sensitive-info-scanner`：`/server_info` 等管理端点的响应字段与鉴权前置 | `sensitive-info-scanner/` |
| G15 SafeUnpickler 允许列表绕过 | `rce-deserialization` | SGLang `CVE-2026-15969`（Unverified） | 弱（只能定位 sink，不能判断 denylist 是否可绕） | 扩展 `insecure-deserialization-analyzer`：分析 Unpickler 子类的 `find_class` / allowlist / denylist / `persistent_load` | `insecure-deserialization-analyzer/SKILL.md`、Python query |

### 2.3 P2

| 缺口 | T01 类型 | T01 条目（项目 / ID） | 现状 | 建议实现 | 目标文件 |
|------|----------|----------------------|------|----------|----------|
| G12 可达 assert DoS | `reachable-assertion-dos` | SGLang `CVE-2026-10300` | 弱 | 扩展 `error-boundary-analyzer`：远程输入 → `assert` / 不可恢复异常的可达性 | `error-boundary-analyzer/SKILL.md` |
| G13 高复杂度 data_hash DoS | `dos` | SGLang `CVE-2026-10775` | 弱 | 扩展 `dos-attacks-analyzer`：攻击者可控结构/大小 → 哈希或缓存计算 | `dos-attacks-analyzer/SKILL.md` |
| G14 eval + 反序列化组合复核 | `security-issue-unsafe-eval-deserialization` | verl `verl-issue-5331`（非 CVE） | 弱 | 不新建 skill；由 G02 规则 + `code-injection-analyzer` 的 eval 清单组合覆盖，并在测试用例中回归 | G02 目标文件 + `code-injection-analyzer/SKILL.md` |

## 3. P0 缺口详述

### G01 模型加载信任边界（`rce-trust-remote-code`、`rce-config-auto-map`）

- **T01 条目**
  - vLLM `CVE-2026-27893`（High）：`vllm/model_executor/models/nemotron_vl.py`、`kimi_k25.py`，模型仓库可携带远程代码并在加载时执行。
  - vLLM `CVE-2025-66448`（High）：`vllm.transformers_utils.config.get_config` / `Nemotron_Nano_VL_Config`，配置中的 `auto_map` 指向动态模块。
- **现状证据**
  - 全仓检索 `trust_remote_code|auto_map|get_class_from_dynamic_module` 在 `.claude/skills` 下 0 命中（命令见 §10.2 复核记录）。
  - `code-injection-analyzer/SKILL.md:10` 只有「远程代码加载」的泛化描述，没有 transformers/vLLM 的 sink 清单；`config-env-analyzer/SKILL.md` 覆盖 config→command/SQL/path/SSRF（T02 §3.1），不含模型配置键。
- **缺口**
  - 不知道哪些配置键会把「模型仓库内容」变成可执行代码：`auto_map`、`architectures`、`trust_remote_code=True`、`get_class_from_dynamic_module`、`importlib.import_module`。
  - 不区分「官方硬编码模型」与「用户/请求传入的模型 ID」。
- **实现方式（新 skill `model-loading-analyzer`）**
  - Source：HTTP 请求里的 `model` 字段、CLI `--model`、环境变量（`HF_HOME`、`TRUST_REMOTE_CODE`）、`config.json` 的 `auto_map` / `architectures`。
  - Sink：`AutoConfig.from_pretrained(..., trust_remote_code=True)`、`AutoModel*.from_pretrained`、`get_class_from_dynamic_module`、`transformers.dynamic_module_utils`、`importlib.import_module`、`exec` 加载动态模块。
  - 检测步骤：① 找模型加载入口；② 回溯模型 ID 是否请求可控；③ 检查 `trust_remote_code` 默认值与显式开关；④ 检查是否固定 revision/commit；⑤ 检查是否只允许本地目录/白名单。
  - 误报排除：`trust_remote_code=False`、模型路径硬编码且来自官方目录、`revision` 固定到受信 commit 时降级为提示。
- **可执行下一步**
  1. 新建 `.claude/skills/model-loading-analyzer/SKILL.md` + `quick-scan.py` + `patterns/transformers.yaml`。
  2. 在 T04 用 `targets/vllm` 的 `nemotron_vl.py` / `kimi_k25.py` 与 `transformers_utils/config.py` 作为 2 个真实位置示例。
  3. 在 `config-env-analyzer` 增加一段「模型配置键」交叉引用，不复制规则。

### G02 权重与张量反序列化（`rce-deserialization`、`insecure-deserialization`、`memory-corruption-deserialization`）

- **T01 条目**
  - verl `CVE-2025-50461`（Moderate）：`scripts/model_merger.py`（fsdp backend）`torch.load(weights_only=False)`。
  - SGLang `CVE-2026-15976`（Unverified）：`/update_weights_from_disk` HuggingFace 权重加载。
  - SGLang `CVE-2026-7669`（Moderate）：`python/sglang/srt/utils/hf_transformers_utils.py get_tokenizer`。
  - vLLM `CVE-2025-62164`（High）：Completions API `prompt_embeds` / `torch.load` + `to_dense`，稀疏张量越界。
- **现状证据**
  - Python sink 查询只覆盖 `pickle|dill|cloudpickle` 的 `load/loads`，正则兜底覆盖 `yaml.load`、`marshal`、`shelve`（`insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm:4-21`、`scripts/core/scanner.py:50-55`）。
  - `Python_Pickle_RCE.md:40` 仅把 `torch.load()` 列为关键词，没有 `weights_only` 判定；全仓无 `from_pretrained` / `safetensors` 规则（T02 §3.1 已用 grep 证实）。
- **缺口**
  - 无法区分 `torch.load(weights_only=True)` 与 `weights_only=False`/缺省（旧版本默认 False），会把安全加载误报，也会漏掉真正的危险加载。
  - 没有 HuggingFace 加载链（`from_pretrained` → 自定义模块 / tokenizer → `pickle`）的串联分析。
  - 没有 PyTorch 稀疏张量/`to_dense` 这类「数据形状导致内存越界」的检查。
- **实现方式（扩展现有 skill，不新建）**
  - 在 Python query 增加：`torch.load`、`torch.jit.load`、`numpy.load`（`allow_pickle=True`）、`joblib.load`、`pandas.read_pickle`。
  - 在 `scanner.py` 增加参数判定：`weights_only` 缺失或 `False` → critical；`True` → 记录但不报。
  - 把 `safetensors.torch.load_file` / `load_model` 加入安全白名单，避免误报。
  - 新增 `huggingface_loading.scm`：`from_pretrained`、`get_tokenizer`、`AutoTokenizer`，并与 G01 的 `trust_remote_code` 结果关联。
  - `memory-corruption-deserialization` 作为 C/C++ 参考补充：不在 Python query 里硬塞，改为在 SKILL 的 PyTorch 章节给出 `to_dense`/稀疏张量检查清单。
- **可执行下一步**
  1. 改 `deserialization_sinks.scm` + `scanner.py`，加 fixture `torch_load_weights_only_{true,false,absent}.py`。
  2. 用 `targets/verl/scripts/model_merger.py`、`targets/sglang/python/sglang/srt/utils/hf_transformers_utils.py` 做真实位置示例。
  3. 把 `CVE-2025-62164` 的 `prompt_embeds` 输入链写成 SKILL 中的 TODO 检查项，不虚构行号。

### G03 Host 头 → 路由认证绕过（`authentication-bypass`）

- **T01 条目**
  - vLLM `CVE-2026-48746`（Critical，CWE-444/501）：`vllm/entrypoints/openai/api_server.py AuthenticationMiddleware`，Starlette/ASGI 重建 URL 时信任 Host，导致 `url_path` 与路由不一致而绕过 API Key。
  - deepseek-harness `CVE-2026-82533`（Critical）：本地 HTTP 控制面 API 的 Host 头。
- **现状证据**
  - `web-auth-analyzer/SKILL.md:13-19` 覆盖认证机制/绕过/会话/角色，但没有 Host→路由的检测步骤；`quick-scan.py` 只识别认证方式与豁免（T02 §2）。
  - `http-header-injection-analyzer/SKILL.md:10` 提到「Host 头攻击（未验证、用于业务逻辑）」，`:239` 给出 Host 白名单建议；但没有「认证中间件从 Host 重建 path」的联合分析。
- **缺口**
  - 两个 skill 各覆盖一半，缺少「反向代理是否规范化 Host」「框架是否用 Host 构造 `base_url`/`root_path`」「认证中间件比较的是哪个 path」这三步。
- **实现方式（扩展现有 2 个 skill）**
  - 在 `web-auth-analyzer` 增加检测步骤：定位 `AuthenticationMiddleware`、`request.url.path`、`request.base_url`、`root_path`、`url_for`；检查鉴权判定使用的 path 与路由派发使用的 path 是否同源。
  - 在 `http-header-injection-analyzer` 增加：`TrustedHostMiddleware`、`allowed_hosts`、Nginx `server_name`、`proxy_set_header Host` 的配置检查；给出「Host 含特殊字符 → URL 重建差异」的验证思路（不写武器化 payload）。
  - `quick-scan.py` 增加正则：`headers\[['\"]host`、`request.host`、`base_url`、`root_path`、`TrustedHostMiddleware`。
- **可执行下一步**
  1. 先改两个 `SKILL.md` 的检测清单，再给 `web-auth-analyzer/quick-scan.py` 加 3-5 条 sink。
  2. T04 用 `targets/vllm/vllm/entrypoints/openai/api_server.py` 与 deepseek-harness 的 control-plane 路由文件做真实位置示例（以 T11 克隆结果为准）。
  3. 不为该缺口新建 skill，避免与现有两个 skill 重复。

### G04 Agent 项目级配置信任（`rce-mcp-config`）

- **T01 条目**
  - codex `CVE-2025-61260`（Critical）：项目本地 `.env` / `.codex/config.toml` 被自动信任，导致 MCP/命令配置注入。
- **现状证据**
  - 全仓检索 `\bmcp\b` 在 `.claude/skills` 下 0 命中（T02 §3.3 记录 64 处 `memcpy` 误命中，本轮用词边界复核为 0）。
  - `security-configuration-analyzer/SKILL.md:19` 只泛化提到敏感信息硬编码/明文，没有 Agent 配置加载顺序。
- **缺口**
  - 不理解「项目级配置 > 用户级配置」的覆盖关系；不检查配置文件是否在打开仓库时自动加载；不检查 MCP server 命令是否可来自仓库。
- **实现方式（新 skill `agent-config-analyzer`）**
  - Source：仓库内 `.env`、`.codex/config.toml`、`.mcp.json`、`.vscode/`、`AGENTS.md`、项目级 settings。
  - Sink：配置加载器、MCP server spawn、`command`/`args` 字段、环境变量覆盖、审批白名单。
  - 检测步骤：① 列配置发现顺序；② 判断仓库内配置是否无需用户确认即生效；③ 检查 MCP `command`/`args` 是否可执行任意程序；④ 检查审批规则是否被项目配置放宽。
  - 误报排除：配置仅从用户主目录读取、或首次加载有显式交互确认时降级。
- **可执行下一步**
  1. 新建 `.claude/skills/agent-config-analyzer/SKILL.md` + `quick-scan.py`（先覆盖 `.mcp.json`、`.codex/config.toml`、`.env` 的解析与危险键）。
  2. 把 G07（命令审批）并入同一 skill，避免两个 skill 都解析 Agent 配置。
  3. T04 用 `targets/codex` 的配置加载代码与 T11 克隆后的 `deepseek-harness` 做真实位置示例。

### G05 模型权重/管理端点外泄（`model-weight-exfiltration`）

- **T01 条目**
  - SGLang `CVE-2026-15978`（T01 Unverified）：未配置 API key 时的分布式权重广播端点（NCCL）。
- **现状证据**
  - `access-control-analyzer/SKILL.md:56` 只有链上/资源访问的泛化描述；全仓无 `weight broadcast` / `NCCL` 专用规则（T02 §3.2）。
- **缺口**
  - 缺少「管理/内部端点清单」和「端点默认鉴权状态」的检查；模型权重被当作普通文件，不区分「可下载」与「可被内部广播窃取」。
- **实现方式（扩展现有 skill，暂不新建）**
  - `access-control-analyzer`：增加「高价值端点」清单（权重下载、权重更新、权重广播、`/server_info`、调试端点），要求逐项标注鉴权中间件与默认值。
  - `sensitive-info-scanner`：增加管理端点响应字段检查（与 G11 共用）。
  - 与 G03 联动：如果认证中间件可被 Host 绕过，则权重端点同样暴露。
- **可执行下一步**
  1. 在 `access-control-analyzer/SKILL.md` 加一节「模型资产端点」；在 `sensitive-info-scanner` 加「管理端点响应」检查项。
  2. 因 T01 条目为 Unverified，T04 不把它作为新 skill 的主要验收样例，避免基于未核实信息写死规则。

## 4. P1 缺口详述

### G06 沙箱边界与逃逸（`sandbox-isolation`、`sandbox-bypass`、`sandbox-escape`、`rce-dumper-sandbox-escape`）

- **T01 条目**
  - deepseek-harness `CVE-2026-101078`（Low）：`packages/sandbox/sandbox-local/src/profiles.ts` Landlock backend。
  - deepseek-harness `CVE-2025-59532`（High）：sandbox configuration / model-generated cwd。
  - deepseek-harness `CVE-2026-101102`（Moderate）：Code Mode Sandbox `run_code`。
  - deepseek-harness `CVE-2026-108788`（Low）：Sandbox spawn / `Profile` 参数。
  - SGLang `CVE-2026-15971`（Unverified）：可选 dumper 子系统 / `DUMPER_SERVER_PORT`。
- **现状证据**
  - `code-injection-analyzer/SKILL.md:113-121` 只讨论 eval/exec/vm 沙箱（RestrictedPython、PHP 黑名单、Java ScriptEngine、Node vm），没有进程级文件系统/网络/权限边界。
  - `sandbox-isolation` 关键词 `landlock` 只出现在反序列化文档的缓解段落（T02 §3.1），无配置审计。
- **缺口**
  - 不会检查「沙箱 profile 参数是否可被模型/请求控制」「cwd 是否可写」「是否允许网络/子进程」「seccomp/landlock 是否真正启用」。
- **实现方式（新 skill `agent-sandbox-analyzer`，P1）**
  - 四类边界：文件系统（可写根目录、`cwd`）、网络（出站白名单）、进程（spawn/子进程/信号）、权限（uid/gid、capabilities、landlock/seccomp）。
  - Source：模型生成的命令、工具调用参数、`Profile`/`SandboxConfig` 结构、请求里的 `cwd`/`path`。
  - Sink：`spawn`、`exec`、`run_code`、`chroot`、landlock rules、`seccomp` filter、`setuid`。
  - 误报排除：仅当边界参数来自不可信输入，或 profile 明确放宽（可写根、无网络限制、允许任意 spawn）时报告；普通 `subprocess` 调用不单独算沙箱漏洞。
- **可执行下一步**
  1. 新建 `.claude/skills/agent-sandbox-analyzer/SKILL.md`，先写四类边界检查表与 profile 字段映射。
  2. T04 用 deepseek-harness 的 `profiles.ts`、`run_code` 实现文件作为真实位置示例（T11 克隆后定位）。
  3. 暂不加 `quick-scan.py`，等有 2 个以上真实目标再抽象规则，避免误报。

### G07 命令审批绕过（`command-approval-bypass`）

- **T01 条目**
  - codex `CVE-2025-54558`（Moderate）：ripgrep（`rg`）自动批准，参数可被构造以执行非预期操作。
- **现状证据**
  - 全仓无「命令审批 / auto-approval / ripgrep 参数」检测；`command-injection-analyzer` 只审计命令拼接（T02 §3.3）。
- **缺口**
  - 不理解「审批按命令名前缀匹配」与「shell 解析/别名/参数展开」的差异；不检查审批列表是否覆盖 `rg --pre`、`--hostname-bin` 等参数。
- **实现方式**：并入 G04 的 `agent-config-analyzer`，增加「审批规则」章节与危险参数表。
- **可执行下一步**：在 `agent-config-analyzer/patterns/approval.yaml` 列出 `rg`、`git`、`find`、`curl` 等易被参数绕过的命令；T04 示例用 codex 的审批实现文件。

### G08 Git 仓库信任链（`git-hook-rce`、`git-filter-rce`、`git-fsmonitor-rce`）

- **T01 条目**
  - codex `CVE-2026-19590`（High）：Git `core.hooksPath`。
  - codex `CVE-2026-19593`（Critical）：Git `attr.tree` + clean/process filter。
  - codex `CVE-2026-19592`（High）：Git `core.fsmonitor`。
- **现状证据**
  - `security-configuration-analyzer/general_Git_Configuration_Injection.md:7`、`:84`、`:97`、`:154` 覆盖 `core.hooksPath`、`core.editor`、`core.pager`，但视角是「应用把用户输入传给 git config」。
  - 该文件无 `attr.tree`、clean filter、process filter、`fsmonitor`；全仓 `fsmonitor` 0 命中。
- **缺口**
  - 缺少「Agent 打开不可信仓库 → 仓库/本地配置触发 hook/filter/fsmonitor」的触发链；缺少 `git config --local` 与 `--global` 的优先级分析。
- **实现方式（扩展现有 Git 章节 + 加规则）**
  - 在 `general_Git_Configuration_Injection.md` 增加一节「不可信仓库自动执行」：`core.hooksPath`、`core.fsmonitor`、`attr.tree`、`filter.*.clean`、`filter.*.process`、`core.sshCommand`。
  - 增加 `quick-scan` 正则：`hooksPath`、`fsmonitor`、`attr.tree`、`filter\..*\.(clean|process)`、`sshCommand`。
  - 与 G04 联动：项目级配置是否在打开仓库时自动写入/读取。
- **可执行下一步**
  1. 扩展该 Git 文档与 `security-configuration-analyzer` 的扫描规则。
  2. T04 用 codex 的 Git 配置加载/仓库打开代码做真实位置示例。
  3. 明确误报：仓库内 `.git/hooks` 默认不随 clone 生效；只有 `core.hooksPath` 被设置或本地配置被写入时才报告。

### G09 可执行文件搜索路径（`untrusted-search-path-rce`）

- **T01 条目**
  - deepseek-harness `CVE-2026-95182`（Critical）：`dsh` commit `c291e796` 的 executable lookup。
- **现状证据**
  - `command-injection-analyzer/command_env_pollution.md:1-30` 覆盖 PATH/LD_PRELOAD/LD_LIBRARY_PATH；`go_command_env_inherit.md` 覆盖进程继承。
  - 没有「从不可信目录解析可执行文件 / 当前目录优先 / 空 PATH 段」的检测。
- **缺口**
  - 只审计「命令字符串拼接」，不审计「命令名 → 可执行文件」的解析过程。
- **实现方式（扩展现有 skill）**
  - 在 `command-injection-analyzer` 增加：`exec.LookPath`、`shutil.which`、`subprocess` 的 `PATH` 继承、`os.Getenv("PATH")`、当前目录 `.`/空段、Windows `PATHEXT`。
  - 规则：命令名来自不可信输入且未用绝对路径/白名单 → 报告。
- **可执行下一步**：加 `command-injection-analyzer/PATH_Resolution_RCE.md` 与 2-3 条 grep 规则；T04 用 deepseek-harness 的 executable lookup 代码做示例。

### G10 SSRF 解析器差异（`ssrf-bypass`）

- **T01 条目**
  - vLLM `CVE-2026-25960`（Moderate）：`vllm/connections.py load_from_url_async`，urllib3 与 aiohttp/yarl 对 URL 解析不一致。
- **现状证据**
  - `ssrf-analyzer/bypassTricks.md:14-21`（`file://`）、`:216-229`（协议/重定向）覆盖常见绕过；没有「校验用 A 库、请求用 B 库」的规则（T02 §3.2）。
- **缺口**
  - 不理解同一 URL 在两个库中的 host/path 解析差异；不检查校验与请求是否使用同一解析器。
- **实现方式（扩展现有 skill）**
  - 在 `ssrf-analyzer/SKILL.md` 增加检测步骤：找出「校验 URL」与「发起请求」的库；若不同，标记为需人工验证；列出 urllib3/aiohttp/yarl/requests 的差异点（不写绕过 payload）。
  - `bypassTricks.md` 增加「解析器差异」章节与安全实现建议（统一解析、连接时校验 IP）。
- **可执行下一步**：改 `SKILL.md` + `bypassTricks.md`；T04 用 `targets/vllm/vllm/connections.py` 做真实位置示例。

### G11 管理端点凭据泄露（`credential-disclosure`）

- **T01 条目**
  - SGLang `CVE-2026-15977`（Unverified）：`/server_info` 返回 API key / SSL keyfile 等。
- **现状证据**
  - `sensitive-info-scanner/SKILL.md:8-21` 面向硬编码密钥和泄露函数；`:41-46` 明确「实际泄露风险需人工」。没有「管理端点响应字段」清单。
- **缺口**
  - 不检查「端点是否返回配置对象 / 服务器信息」；不区分「已鉴权端点」与「默认无鉴权」。
- **实现方式（扩展 `sensitive-info-scanner` + `access-control-analyzer`）**
  - 增加「管理端点响应清单」：`/server_info`、`/metrics`、`/config`、`/health`、`/debug`；检查响应字段是否包含 `api_key`、`ssl_keyfile`、`token`、`password`、`secret`。
  - 与 G05 共用「高价值端点 + 鉴权状态」表。
- **可执行下一步**：改 `sensitive-info-scanner/SKILL.md` 与 `quick-scan.py` 的端点响应规则；T04 用 SGLang 的 `/server_info` 实现做示例（T11 克隆后定位）。

### G15 SafeUnpickler 允许列表绕过（`rce-deserialization`）

- **T01 条目**
  - SGLang `CVE-2026-15969`（T01 严重度为 Unverified）：`/load_lora_adapter_from_tensors` 的 `SafeUnpickler` denylist 可被绕过。
- **现状证据**
  - 现有 Python query 能定位 `pickle.loads` / `pickle.load`（`deserialization_sinks.scm:4-21`），但对「自定义 `Unpickler` 子类的 `find_class` 允许/拒绝逻辑」没有分析。
  - T02 把 `rce-deserialization` 判为强，指的是主路径 sink 可定位；本条属于「有安全封装但封装可绕」，不应当直接算全覆盖。
- **缺口**
  - 只报「使用了 pickle」会把安全封装也当成同一风险；只依赖 LLM 又会漏掉 denylist 维护不全、`persistent_load` 未限制、允许 `builtins.eval` 等模式。
- **实现方式（扩展现有 skill，不新建）**
  - 在 `insecure-deserialization-analyzer` 增加「自定义 Unpickler」检查项：`class .*Unpickler`、`find_class`、`persistent_load`、`allowlist`/`denylist` 变量；规则优先级低于普通 `pickle.loads`，但要在报告中单列「封装是否可绕」。
  - 给出安全基线：默认拒绝 + 完整 allowlist + 禁止 `builtins`/`os`/`subprocess`，而不是维护 denylist。
- **可执行下一步**
  1. 在 SKILL 增加一节「SafeUnpickler 反模式」，不改 Python sink query 的主规则。
  2. T04 用 SGLang `/load_lora_adapter_from_tensors` 的实现做真实位置示例（T11 克隆后定位）。
  3. 因该条 CVSS 未核实，只作为 P1 的补充规则，不作为新 skill 的主要验收样例。

## 5. P2 缺口详述

### G12 可达 assert DoS

- **T01 条目**：SGLang `CVE-2026-10300`（Low）：`python/sglang/srt/lora/lora_manager.py lora_path`。
- **现状证据**：`error-boundary-analyzer/SKILL.md:335-402` 覆盖 ReDoS/无限循环/文件大小/Zip Bomb，没有 Python `assert` 可达性（T02 §3.3）。
- **实现方式**：在 `error-boundary-analyzer` 增加「远程输入 → assert/不可恢复异常」检查项；规则只在输入来自请求/文件/网络时报告。
- **下一步**：加一节检测清单 + fixture；不影响 P0/P1 进度。

### G13 高复杂度 data_hash DoS

- **T01 条目**：SGLang `CVE-2026-10775`（Low）：Cache Handler `data_hash`。
- **现状证据**：`dos-attacks-analyzer/SKILL.md:1-35` 以 Solidity/Rust/Move 的 Gas/循环为主，没有 Python 哈希/缓存复杂度（T02 §3.3）。
- **实现方式**：在 `dos-attacks-analyzer` 增加「攻击者可控结构/大小 → 哈希/序列化/缓存键计算」检查项。
- **下一步**：加 Python 章节；与 G12 合并成一个小 PR，避免频繁改 skill。

### G14 eval + 反序列化组合复核

- **T01 条目**：verl `verl-issue-5331`（非 CVE）：`prime_math/grader.py`、`scripts/model_merger.py`、shell eval。
- **现状证据**：eval 部分强（`code-injection-analyzer/SKILL.md:10`、`:27`；`expression-injection-analyzer/SKILL.md:31`）；torch 部分弱（见 G02）。
- **实现方式**：不新建 skill；G02 落地后用该 issue 作为回归用例，验证「eval 清单 + torch.load 规则」能否覆盖。
- **下一步**：在 G02 的 fixture 中加一个 `eval` + `torch.load` 组合样例，标注来源为 verl issue（不作为 CVE）。

## 6. 横向编排差距（不直接对应单一 T01 type，但决定真实覆盖率）

### O01 `project-profiler` 只调度 2 个 skill

- **证据**：`.claude/skills/project-profiler/SKILL.md:36-38` 对后端 HTTP 服务只允许 `web-auth-analyzer` 与 `sensitive-info-scanner`，并写明「禁止添加其他技能」。
- **影响**：G01-G05、G08、G10-G11、G15 等即使有规则，也不会在普通 Python 服务项目上自动运行；只有用户显式指定扫描器、走 `vtr-scanner`，或经 `code-security-analyzer` 的风险点映射才会触发。
- **建议**：T05 在 `project-profiler` 增加「按依赖/文件特征的条件任务」：
  - 检测到 `transformers` / `torch` / `vllm` / `sglang` → 追加 `model-loading-analyzer`；
  - 检测到 `.mcp.json` / `.codex/` / `AGENTS.md` → 追加 `agent-config-analyzer`；
  - 检测到 `sandbox` / `seccomp` / `landlock` → 追加 `agent-sandbox-analyzer`。
- **验收**：orchestrator 的 `-scanner`/`-analyzer` 命名过滤仍成立（`.claude/agents/security-orchestrator.md:28-32`）。

### O02 tree-sitter 依赖未锁定

- **证据**：`check-dependencies.sh:254-293` 把 `tree_sitter_language_pack` 标为 required；本机缺失，4 个 tree-sitter quick-scan 启动即失败（`research/capability-matrix.md` §1.1）。
- **影响**：新增 skill 若依赖 tree-sitter，T10 冒烟会直接失败；现有 `web-auth` / `sensitive-info` / 路由扫描也无法运行。
- **建议**：T07 Dockerfile 显式安装 `tree_sitter_language_pack` 及语言包；T05 文档写明本机需先装依赖。
- **验收**：容器内 `python3 -c "import tree_sitter_language_pack"` 无报错，且 `unauth-route-scanner/quick-scan.py` 能对 fixture 输出。

### O03 `case-studies-analyzer` 不可加载

- **证据**：该目录无 `SKILL.md`，只有案例 Markdown；orchestrator 的命名过滤虽接受 `-analyzer`，但 skill-runner 无法加载（T02 §1、§5）。
- **影响**：无法把已披露漏洞的修复 diff 作为案例喂给新 skill。
- **建议**：T04 新建 skill 时自带 `references/`，不依赖 `case-studies-analyzer`；或在 T05 给它补一个最小 `SKILL.md`（非本任务范围）。

### O04 README 扫描器清单与 profiler 不一致

- **证据**：`README.md:127-148` 列出 18 个扫描器，但 profiler 实际只推荐 2 个（O01）；orchestrator 只在示例中提到 `ssrf-analyzer`（`.claude/agents/security-orchestrator.md:259`）。
- **建议**：T05 更新 README 时，把「支持的扫描器」改为「可被显式调用的扫描器」，并单列「自动调度路径」，避免读者误以为全部自动运行。

## 7. 误报风险与排除规则（必须在 T04 落地）

| 缺口 | 高风险误报 | 排除/降级规则 |
|------|------------|----------------|
| G01 | 所有 `from_pretrained` 都报 | `trust_remote_code=False` 或未启用自定义模块 → 不报；官方硬编码模型 → 降级 |
| G02 | `torch.load` 全报 | `weights_only=True` → 不报；`safetensors` → 白名单；`torch.load` 只加载本地受信文件且无外部输入 → 降级 |
| G03 | 所有 Host 使用都报 | 有 `TrustedHostMiddleware`/反代 `server_name` 且鉴权与路由同源 → 不报 |
| G04 | 仓库内任意 `.env` 都报 | 仅用户目录读取、或加载前有显式确认 → 降级；`.env` 不含可执行配置 → 不报 |
| G05/G11 | 所有管理端点都报 | 端点有鉴权且响应字段已脱敏 → 不报；仅本地回环且无外部暴露 → 降级 |
| G06 | 所有 `subprocess` 都报 | 仅当边界参数来自不可信输入或 profile 明确放宽 → 报 |
| G07 | 所有审批列表都报 | 仅当审批按前缀匹配且命令有危险参数/别名展开 → 报 |
| G08 | 所有 Git 仓库都报 | `.git/hooks` 不随 clone 生效；仅 `core.hooksPath`/`fsmonitor`/filter 被设置 → 报 |
| G09 | 所有 `which` 都报 | 命令名硬编码且 PATH 受控 → 不报；仅不可信命令名 → 报 |
| G10 | 所有 SSRF 都报 | 校验与请求使用同一解析器且连接时校验 IP → 不报 |
| G12/G13 | 所有 assert/哈希都报 | 仅输入来自网络/文件/请求且可放大 → 报 |

## 8. 非缺口：可直接复用的强项

以下 8 个 type 已由现有 skill 强覆盖，T04 **不要**重复造 skill，只做回归验证：

1. `rce-deserialization`（pickle/dill/cloudpickle 主路径）：`CVE-2025-47277`、`CVE-2026-3059`、`CVE-2026-3060`、`CVE-2026-7301`、`CVE-2025-10164`；证据 `insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm:4-21`。
2. `rce-dill-deserialization`：`CVE-2026-7304`；证据 `scripts/core/scanner.py:54`。
3. `insecure-deserialization-script`：`CVE-2026-3989`；证据同上 query。
4. `ssrf`：`CVE-2025-6242`；证据 `ssrf-analyzer/scripts/languages/python/queries/sinks.scm:1-20`。
5. `ssrf-local-file-read`：`CVE-2026-15974`；证据 `ssrf-analyzer/bypassTricks.md:14-21`。
6. `path-traversal-file-write`：`CVE-2026-7302`；证据 `path-traversal-analyzer/SKILL.md:7`、`:47`、`:278`。
7. `rce-unsafe-eval`：`CVE-2026-6878`；证据 `code-injection-analyzer/SKILL.md:10`、`:27`；`expression-injection-analyzer/SKILL.md:31`。
8. `prompt-injection`：`CVE-2026-95183`；证据 `llm-security-analyzer/SKILL.md:10`、`:23-24`；`general.md:3`、`:16`。

> 注意：强覆盖不等于「自动被调度」，仍受 O01 影响。

## 9. T04 / T05 落地建议（按依赖顺序）

### T04 建议范围（至少 2 个 P0 skill）

| 顺序 | skill | 覆盖缺口 | 最小产物 | 真实位置示例（T04 前需最小克隆或用上游原文核对） |
|------|-------|----------|----------|--------------------------------------------------|
| 1 | `model-loading-analyzer` | G01、G02 的 HF 链、G14 的 eval 组合 | `SKILL.md` + `quick-scan.py` + `patterns/transformers.yaml` | vLLM `vllm/model_executor/models/nemotron_vl.py`、`vllm/transformers_utils/config.py`；SGLang `hf_transformers_utils.py`；verl `scripts/model_merger.py` |
| 2 | `agent-config-analyzer` | G04、G07、G08 的触发链 | `SKILL.md` + `quick-scan.py` + `patterns/mcp.yaml`、`patterns/approval.yaml`、`patterns/git.yaml` | codex `.codex/config.toml` 加载代码、审批实现；deepseek-harness control-plane 配置 |

> T04 在 T11 之前执行，`targets/` 可能还不存在。若未克隆，T04 必须先用 `git clone --depth 1` 或 GitHub raw 原文核对路径与行号；只写「预期路径」不满足 T04 的「真实代码位置」验收。

T04 验收对应：
- 每个 skill 目录含结构完整的 `SKILL.md`（适用场景、检测步骤、source/sink、误报排除、输出格式）。
- 每个 skill 至少 2 个目标仓库真实代码位置示例（用 `grep -n` 输出佐证，不写虚构行号）。
- 不修改无关 skill；G02/G03/G10/G11 的扩展留到后续或与 T04 同期的小改动，避免一个任务铺太大。

### T05 接入点

1. `.claude/agents/security-orchestrator.md`：在「子任务 Skill 过滤规则」后增加「AI 基础设施条件任务」段，引用两个新 skill；保持 `-scanner`/`-analyzer` 命名过滤（`:28-32`）。
2. `.claude/skills/README.md`：新增两个 skill 条目与适用项目特征。
3. 根 `README.md:127-148`：把扫描器表拆成「显式调用」与「自动调度」两列，避免 O04 的误导。
4. `project-profiler`：按 O01 增加条件任务（若 T05 时间不够，至少写入 README 作为已知限制）。
5. `research/phase1-summary.md`：一页结论，引用本文件的 15 个缺口与落地 2 个 P0 skill 的结果。

## 10. 验收对照与复核记录

### 10.1 对照 T03 验收标准

| 验收项 | 满足方式 |
|--------|----------|
| `research/gap-analysis.md` 存在 | 本文件 |
| 每个缺口对应 T01 具体条目 | §2 总表 + §3-§5 每条目列出项目/ID；15 个缺口覆盖 26 条 |
| 给出 P0/P1/P2 与实现方式 | §2 三张表 + §9 落地顺序 |
| 可执行下一步，不泛泛而谈 | 每个缺口有「可执行下一步」，含目标文件、示例仓库路径、验收方式 |

### 10.2 本轮复核命令

```bash
# 1. T01/T02 计数与 type 去重
python3 -c "import json;d=json.load(open('research/disclosed-vulns.json'));print(len(d['entries']),len(set(e['type'] for e in d['entries'])))"
# 输出：38 29

# 2. 关键“无覆盖”结论复核（0 命中）
grep -rniI "trust_remote_code\|from_pretrained\|weights_only\|safetensors\|auto_map\|get_class_from_dynamic_module" .claude/skills
grep -rniI "\bmcp\b" .claude/skills
grep -rniI "fsmonitor" .claude/skills

# 3. 强项证据文件存在性
test -f .claude/skills/insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm
test -f .claude/skills/ssrf-analyzer/bypassTricks.md
test -f .claude/skills/project-profiler/SKILL.md

# 4. 编排限制证据
sed -n '36,38p' .claude/skills/project-profiler/SKILL.md
sed -n '28,32p' .claude/agents/security-orchestrator.md
```

> 以上命令在本轮执行时均返回预期结果；`grep` 的 0 命中即 T02 所述「无覆盖」的直接证据。

## 11. 风险与未决项

1. **T01 部分条目的严重度为 Unverified**：`CVE-2026-15969/15971/15974/15976/15977/15978` 的 CVE 编号已由 CERT note 核实，但没有 CVSS（T01 `severity` 字段为 `Unverified (no CVSS in CERT note)`）；`verl-issue-5331` 是非 CVE issue。本文件不据此写死正则或行号；T04 优先用有明确 CVSS 的条目做验收样例。
2. **目标仓库尚未克隆**：真实代码位置示例以 T01 的 `component` 字段为线索，T04 执行前需先完成 T11 的克隆或用上游 GitHub 原文核对；否则只能给「预期路径」，不能算「真实位置」。
3. **新增 skill 的调度依赖 O01**：若 T05 不修 `project-profiler`，新 skill 只能被显式调用；这不影响 T04 验收，但会影响 Phase 3 的实际覆盖率。
4. **tree-sitter 依赖**：O02 未解决前，任何依赖 `tree_sitter_language_pack` 的 quick-scan 在宿主机不可运行；T04 的 `quick-scan.py` 应优先用标准库 `ast`/`re` 实现，tree-sitter 作为可选增强。
