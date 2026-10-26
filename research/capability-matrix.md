# mygoldmine 现有能力盘点（T02）

- 盘点时间：2026-10-27
- 输入：`research/disclosed-vulns.json`（T01，38 条，5 个项目，29 个 type 取值）
- 范围：`.claude/skills/`、`.claude/agents/`、各 skill 的 `quick-scan.py` 与 `scripts/`
- 方法：逐个读取 SKILL/脚本，按 T01 的 type 逐项对照；对“无覆盖”结论同时记录关键词检索结果
- 约束：本文件只做能力盘点，不做漏洞复现；T01 的 CVE/GHSA 与 URL 以 `research/disclosed-vulns.json` 为准

## 0. 覆盖度判定口径

| 覆盖度 | 判定标准 |
|--------|----------|
| 强 | 有专用 skill，且具备该机制的 source/sink 清单、语言特定参考或 tree-sitter/正则规则；能独立定位该类型的 sink，剩余工作是人工确认数据流 |
| 弱 | 只有相邻 skill 或通用章节；缺少该框架/机制的关键 sink，或只能靠 LLM 自由发挥，结果高度依赖模型 |
| 无 | 在 `.claude/skills` 中找不到对应机制，且关键词检索无命中 |

> “强”不等于“无漏报”。例如 pickle 的 sink 能扫到，但“数据是否从网络来”仍要 LLM 追踪。

## 1. 资产清单（先纠正数量口径）

| 项目 | 实测 | 证据 |
|------|------|------|
| skills 目录 | 83 个目录 + 1 个 `README.md`，共 84 个条目 | `ls -d .claude/skills/*/ \| wc -l` = 83；`.claude/skills/README.md` |
| 可被发现的 skill | 82 个目录含 `SKILL.md` | `find .claude/skills -maxdepth 2 -name SKILL.md \| wc -l` = 82 |
| 不可被发现的 skill | `case-studies-analyzer/` 没有 `SKILL.md`，只有案例 Markdown | `ls .claude/skills/case-studies-analyzer/` |
| agents | 3 个可执行 agent + 1 个 README | `security-orchestrator.md`、`skill-runner.md`、`report-generator.md`、`README.md` |
| 顶层 `quick-scan.py` | 7 个 | `normal-route-scanner` 的脚本是指向 `unauth-route-scanner/quick-scan.py` 的软链 |
| 其中真正使用 tree-sitter 的顶层 quick-scan | 4 个 | `unauth-route-scanner`、`normal-route-scanner`（同脚本）、`web-auth-analyzer`、`sensitive-info-scanner` |
| 不使用 tree-sitter 的顶层 quick-scan | 3 个 | `workspace-scanner`（文件布局/子进程）、`project-profiler`（正则+子进程）、`blockchain-goldmine-analyzer`（扩展名启发式） |
| 带 `scripts/` 的 skill | 10 个 | `authentication-jwt`、`command-injection`、`csrf`、`insecure-deserialization`、`insecure-file-uploads`、`mass-assignment`、`sql-injection`、`ssrf`、`xss`、`insecure-deserialization` 等 |

### 1.1 本机可运行性（重要）

当前环境缺少 `tree_sitter_language_pack`：

```text
$ python3 -c "import tree_sitter_language_pack"
ModuleNotFoundError: No module named 'tree_sitter_language_pack'

$ python3 .claude/skills/unauth-route-scanner/quick-scan.py . --output /tmp/routes.md
ModuleNotFoundError: No module named 'tree_sitter_language_pack'
exit=1
```

- `check-dependencies.sh:254-293` 把 `tree_sitter_language_pack` 标为 required，但没有自动安装。本机运行该脚本时先在必需工具阶段因缺 `cloc` 退出（exit 1），没有走到 Python 模块检查；上面的 `ModuleNotFoundError` 是用 `python3 -c` 单独确认的。
- 因此“文档里写了 4 个 tree-sitter quick-scan”不等于“当前机器能跑”；T07 的 Docker 镜像必须显式安装该依赖，否则 Phase 1 的 route/auth/sensitive 扫描会直接失败。
- 使用独立 parser 模块的脚本仍可运行（本机已验证）：
  - `insecure-deserialization-analyzer/scripts/cli.py --lang python` 能输出 `pickle.loads`、`pickle.load`、`dill.loads`、`cloudpickle.loads`、`yaml.load` 命中。
  - `ssrf-analyzer/scripts/cli.py --lang python .` 能输出 sink；但缺失 `tree_sitter_typescript`、`tree_sitter_rust` 时会打印 warning 并降级。
  - `authentication-jwt-analyzer/scripts/cli.py --lang python .` 能输出命中；对部分 Java fixture 会报语法 warning。

## 2. tree-sitter quick-scan 实际检测范围

| skill/脚本 | 语言/框架 | 实际能力 | 不能做什么 | 证据 |
|------------|----------|----------|------------|------|
| `unauth-route-scanner/quick-scan.py` | JS/TS、Python、Go、Java、PHP、Ruby、Rust、C/C++ 等（`LANGUAGE_MAP`） | 提取路由注册：Express、NestJS、Flask、FastAPI、gorilla/mux 等；输出方法/路径/handler/行号 | 不判断是否真的未授权；认证判定交给 `web-auth-analyzer` | `unauth-route-scanner/quick-scan.py:75`（LANGUAGE_MAP）、`unauth-route-scanner/quick-scan.py:555-628`（路由 Query） |
| `normal-route-scanner` | 同上 | 软链复用同一脚本，定位普通用户可访问路由 | 同上 | `ls -l` 显示 `normal-route-scanner/quick-scan.py -> ../unauth-route-scanner/quick-scan.py` |
| `web-auth-analyzer/quick-scan.py` | JS/TS、Python、Go、Java、PHP、Ruby、Rust、C/C++ 等 | 识别 JWT/Session/OAuth/API Key、认证豁免、角色模型、JWT 密钥/会话固定等风险 | 明确声明“认证绕过验证、权限提升路径”需人工；Host→路由重建这类逻辑不在脚本内 | `web-auth-analyzer/SKILL.md:62-69`、`web-auth-analyzer/quick-scan.py:198`（LANGUAGE_MAP） |
| `sensitive-info-scanner/quick-scan.py` | JS/TS、Python、Go、Java、PHP、Ruby、Rust、C/C++ 等 | 硬编码 AWS/GitHub/数据库/私钥/JWT Secret/API Key/PII；环境变量导出、配置对象返回 | 不判断“接口是否真的把敏感字段返回给低权限用户”；不做端点级数据流 | `sensitive-info-scanner/SKILL.md:8-21`、`sensitive-info-scanner/SKILL.md:41-46`、`sensitive-info-scanner/quick-scan.py:94`、`sensitive-info-scanner/quick-scan.py:128-166` |
| `project-profiler/quick-scan.py` | 依赖文件+目录启发式 | 技术栈、文件数、入口、项目分类辅助 | 不做 AST/漏洞检测；不使用 tree-sitter | `project-profiler/quick-scan.py:15-16`（import re/subprocess） |
| `workspace-scanner/quick-scan.py` | 目录/包管理器配置 | 单工程 vs Monorepo 判定 | 不做漏洞检测 | `workspace-scanner/quick-scan.py:15-16` |
| `blockchain-goldmine-analyzer/quick-scan.py` | `.sol/.rs/.move/.vy/.go` | 合约语言识别与应用场景建议 | 不做深度合约审计 | `blockchain-goldmine-analyzer/quick-scan.py:89-105` |

### 2.1 带 tree-sitter 的 scripts 级检测器

| detector | 语言 | 检测方式 | 证据 |
|----------|------|----------|------|
| `insecure-deserialization-analyzer` | PHP/Python/Java/JS/TS/C/C++/Go/Rust | tree-sitter query + 纯文本正则 fallback；Python 覆盖 pickle/dill/cloudpickle、yaml、marshal、shelve | `insecure-deserialization-analyzer/scripts/core/scanner.py:50-55`、`insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm:4-21`、`insecure-deserialization-analyzer/scripts/config/languages.yaml:2-9` |
| `ssrf-analyzer` | PHP/Python/Java/JS/TS/C/C++/Go/Rust | tree-sitter sink query；Python 覆盖 requests/urlopen 等 | `ssrf-analyzer/scripts/core/scanner.py:6-19`、`ssrf-analyzer/scripts/config/languages.yaml:2-9`、`ssrf-analyzer/scripts/languages/python/queries/sinks.scm:1-20` |
| `authentication-jwt-analyzer` | Python/PHP/JS/Java | tree-sitter query + JWT patterns | `authentication-jwt-analyzer/scripts/core/scanner.py:92-166`、`authentication-jwt-analyzer/scripts/config/languages.yaml:2-34` |
| `command-injection-analyzer` | PHP/Python/Java/JS/Go/Rust | README 自称“tree-sitter based”，但实际主路径是正则；tree-sitter 仅预留 | `command-injection-analyzer/scripts/README.md:22`、`command-injection-analyzer/scripts/README.md:250-265`、`command-injection-analyzer/scripts/cli.py:111`、`command-injection-analyzer/scripts/cli.py:127` |
| `insecure-file-uploads-analyzer` | PHP/Python（实际主路径） | 逐行字符串匹配；parser_manager 存在但不作为主检测路径 | `insecure-file-uploads-analyzer/scripts/cli.py:27-54`、`insecure-file-uploads-analyzer/scripts/core/parser_manager.py` |
| `sql-injection` / `xss` / `csrf` / `mass-assignment` | 多语言 | 各自 `scripts/core/scanner.py` 使用 tree-sitter/parser | 本次未逐条展开；它们在 T01 的 AI 基础设施类型中优先级低 |

## 3. T01 漏洞类型 × 现有能力矩阵

> 表中“T01 例”只列代表条目，完整字段见 `research/disclosed-vulns.json`。
> 同一 type 下机制差异大的，拆成多行，避免“部分覆盖”被误读为“全覆盖”。

### 3.1 反序列化、代码执行与内存安全

| T01 type | T01 例 | 最接近的 skill / 脚本 | 检测方式 | 覆盖度 | 证据与说明 |
|----------|--------|----------------------|----------|--------|------------|
| `rce-deserialization`（pickle/dill/cloudpickle、ZMQ/控制通道） | CVE-2025-47277、CVE-2026-3059、CVE-2026-3060、CVE-2026-7301、CVE-2026-10164 | `insecure-deserialization-analyzer`、`code-injection-analyzer` | tree-sitter query + 正则 + LLM | 强 | `insecure-deserialization-analyzer/SKILL.md:17`、`insecure-deserialization-analyzer/SKILL.md:27`；`insecure-deserialization-analyzer/scripts/core/scanner.py:50-55`；`insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm:4-21`；`code-injection-analyzer/SKILL.md:27` |
| `rce-deserialization`（torch.load、HF 权重、`from_pretrained`） | CVE-2025-62164、CVE-2025-50461、CVE-2026-15976 | 同上 | 只有关键词清单，没有 `weights_only`/`from_pretrained` 的规则或 AST | 弱 | `insecure-deserialization-analyzer/Python_Pickle_RCE.md:40` 只列了 `torch.load()`；全仓 `grep -rniI "weights_only\|safetensors\|from_pretrained" .claude/skills` 无命中；`insecure-deserialization-analyzer/scripts/languages/python` 的 query 不含 `torch.*` |
| `rce-dill-deserialization` | CVE-2026-7304 | `insecure-deserialization-analyzer` | tree-sitter query + 正则 | 强 | `insecure-deserialization-analyzer/scripts/core/scanner.py:54`（`dill.loads` critical）；`insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm:10` |
| `insecure-deserialization-script` | CVE-2026-3989 | `insecure-deserialization-analyzer` | tree-sitter query + 正则 | 强 | 与 pickle 共用 sink；`insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm:4-12`、`insecure-deserialization-analyzer/scripts/core/scanner.py:50-54` |
| `insecure-deserialization`（HF tokenizer/权重加载链） | CVE-2026-7669 | `insecure-deserialization-analyzer` | 通用反序列化指南，未覆盖 HuggingFace 加载链 | 弱 | `insecure-deserialization-analyzer/SKILL.md:17` 只有通用 pickle/yaml 等；全仓无 `from_pretrained`/`get_tokenizer` 规则 |
| `memory-corruption-deserialization`（torch 稀疏张量越界） | CVE-2025-62164 | `insecure-deserialization-analyzer` 的 C/C++ 章节、`integer-overflow-analyzer`、`error-boundary-analyzer` | LLM 审计内存安全；无 PyTorch tensor 语义 | 弱 | `insecure-deserialization-analyzer/general.md:135-136` 只覆盖“memcpy/fread 填充结构体”；`insecure-deserialization-analyzer/scripts/languages/c/queries/deserialization_sinks.scm:4-19`；没有 `torch`/`to_dense`/稀疏张量规则 |
| `rce-trust-remote-code` | CVE-2026-27893 | 无专用 skill；`code-injection-analyzer` 仅有“动态代码加载”概述 | LLM | 无 | 全仓 `grep -rniI "trust_remote_code" .claude/skills` 无命中；`code-injection-analyzer/SKILL.md:10` 只泛化提到“远程代码加载” |
| `rce-config-auto-map` | CVE-2025-66448 | `config-env-analyzer`、`code-injection-analyzer` | 配置→sink 的通用模式 | 弱 | `config-env-analyzer/SKILL.md:164-291` 覆盖 config→command/SQL/path/SSRF；无 `auto_map`/`get_class_from_dynamic_module`/`transformers` 规则 |
| `rce-unsafe-eval` | CVE-2026-6878 | `code-injection-analyzer`、`expression-injection-analyzer` | LLM + 语言特定 eval/exec 清单 | 强 | `code-injection-analyzer/SKILL.md:10`、`:27`；`expression-injection-analyzer/SKILL.md:10`、`:15`、`:31`（Python eval/exec） |
| `security-issue-unsafe-eval-deserialization` | verl-issue-5331 | 同上 + `insecure-deserialization-analyzer` | eval 部分强，deser 部分弱 | 弱 | eval 证据同上；torch/权重部分见本表第 2 行；`HuggingFace`/`torch.load(weights_only=False)` 无规则 |
| `rce-dumper-sandbox-escape` | CVE-2026-15971 | `code-injection-analyzer` 的沙箱章节 | LLM | 弱 | `code-injection-analyzer/SKILL.md:10`、`:113-121` 只讨论 eval/exec/vm 沙箱；无 dumper、`DUMPER_SERVER_PORT` 或进程边界分析 |
| `sandbox-bypass` | CVE-2025-59532 | `code-injection-analyzer`、`insecure-deserialization-analyzer` 的沙箱绕过文档 | LLM | 弱 | `code-injection-analyzer/SKILL.md:113-121`；`JS_V8_Serialization_Bypass.md` 只覆盖 JS vm；无“model-generated cwd / 可写根目录”边界检查 |
| `sandbox-escape` | CVE-2026-101102、CVE-2026-108788 | 同上 | LLM | 弱 | 同上；无 `run_code`/`Profile`/spawn 参数的系统级沙箱模型 |
| `sandbox-isolation` | CVE-2026-101078 | 无专用 skill；仅在修复建议里出现 `landlock/seccomp` 关键词 | 无规则 | 无 | 全仓 `grep -rniI "landlock" .claude/skills` 仅出现在 deserialization 文档的“安全实现/缓解”段落；没有 Landlock/seccomp 配置审计 skill |

### 3.2 网络请求、文件与认证

| T01 type | T01 例 | 最接近的 skill / 脚本 | 检测方式 | 覆盖度 | 证据与说明 |
|----------|--------|----------------------|----------|--------|------------|
| `ssrf` | CVE-2025-6242 | `ssrf-analyzer` | tree-sitter + LLM | 强 | `ssrf-analyzer/SKILL.md:13`、`ssrf-analyzer/SKILL.md:21`；`ssrf-analyzer/scripts/config/languages.yaml:2-9`；`ssrf-analyzer/scripts/core/scanner.py:6-19` |
| `ssrf-bypass`（解析器差异：urllib3 vs aiohttp/yarl） | CVE-2026-25960 | `ssrf-analyzer` 的 bypassTricks | 常见协议/IP/重定向绕过；无解析器差异分析 | 弱 | `ssrf-analyzer/bypassTricks.md:14-21`（file://）、`:216-229`（协议/重定向）；没有“校验用 A 库、请求用 B 库”的规则 |
| `ssrf-local-file-read` | CVE-2026-15974 | `ssrf-analyzer` | tree-sitter + `file://` 绕过指南 | 强 | `ssrf-analyzer/SKILL.md:13`、`ssrf-analyzer/SKILL.md:21`；`ssrf-analyzer/general.md:19-21`；`ssrf-analyzer/bypassTricks.md:14-21` |
| `path-traversal-file-write` | CVE-2026-7302 | `path-traversal-analyzer`、`insecure-file-uploads-analyzer` | LLM + 手写 grep/正则；无专用脚本 | 强 | `path-traversal-analyzer/SKILL.md:7`、`:18`、`:47`；上传写入/落盘见 `:278`（Zip Slip）；`insecure-file-uploads-analyzer/SKILL.md:31`、`:83` |
| `authentication-bypass`（Host 头 → 路由/URL 不一致） | CVE-2026-48746、CVE-2026-82533 | `web-auth-analyzer`、`http-header-injection-analyzer` | tree-sitter quick-scan + Host 头 LLM 指南 | 弱 | 两个 skill 各自覆盖一半：`web-auth-analyzer/SKILL.md:13-19`、`:62-69`（认证分析与 Host 无关）；`http-header-injection-analyzer/SKILL.md:10`、`:27`、`:239`（Host 未验证）。没有“Host 重建 URL→与路由比较”的检测步骤 |
| `credential-disclosure`（`/server_info` 返回 API key/SSL keyfile） | CVE-2026-15977 | `sensitive-info-scanner`、`security-configuration-analyzer` | tree-sitter/正则 + LLM | 弱 | `sensitive-info-scanner/SKILL.md:8-21` 面向硬编码密钥和泄露函数；`:41-46` 明确“实际泄露风险需人工”。没有“管理端点响应字段”清单；`security-configuration-analyzer/SKILL.md:19` 只泛化“敏感信息硬编码/明文” |
| `model-weight-exfiltration` | CVE-2026-15978 | `access-control-analyzer` 仅有通用资源访问章节 | LLM | 无 | `access-control-analyzer/SKILL.md:56` 是链上/资源访问泛化描述；无“分布式权重广播/NCCL/模型权重端点”模型；全仓无 `weight broadcast`/`NCCL` 专用规则 |

### 3.3 DoS、Agent 与 Git/工具链

| T01 type | T01 例 | 最接近的 skill / 脚本 | 检测方式 | 覆盖度 | 证据与说明 |
|----------|--------|----------------------|----------|--------|------------|
| `reachable-assertion-dos` | CVE-2026-10300 | `dos-attacks-analyzer`、`error-boundary-analyzer` | LLM | 弱 | `dos-attacks-analyzer/SKILL.md:7-8`、`:15-33` 以智能合约 Gas/循环为主；`error-boundary-analyzer/SKILL.md:335-402` 只覆盖 ReDoS/无限循环/文件大小/Zip Bomb，没有 Python `assert` 可达性分析 |
| `dos`（`data_hash` 高复杂度） | CVE-2026-10775 | 同上 | LLM | 弱 | 同上；没有“攻击者可控输入 → 高复杂度哈希/缓存计算”的规则或复杂度检查 |
| `rce-mcp-config`（项目级 `.env`/`.codex/config.toml`） | CVE-2025-61260 | 无专用 skill | 无 | 无 | 全仓 `grep -rniI "mcp" .claude/skills` 的 64 处命中均为 `memcpy` 等无关子串，没有 MCP 协议/配置审计内容 |
| `command-approval-bypass`（自动批准 rg） | CVE-2025-54558 | 无专用 skill | 无 | 无 | 全仓无“命令审批/auto-approval/ripgrep 参数”检测；`command-injection-analyzer` 只审计命令拼接 |
| `git-hook-rce`（`core.hooksPath`） | CVE-2026-19590 | `security-configuration-analyzer` 的 Git 配置注入章节 | LLM/手写 grep | 弱 | `security-configuration-analyzer/general_Git_Configuration_Injection.md:1-7`、`:80-84`、`:153-184` 覆盖 `core.hooksPath`；但它是 Web 配置注入视角，没有“Agent 打开恶意仓库即执行 hook”的触发链；无脚本 |
| `git-filter-rce`（`attr.tree` + clean/process filter） | CVE-2026-19593 | 同上 | LLM | 无 | 该 Git 章节只列 `core.hooksPath`（`:80-84`）；全仓无 `attr.tree`/`clean filter`/`process filter` 检测 |
| `git-fsmonitor-rce`（`core.fsmonitor`） | CVE-2026-19592 | 同上 | LLM | 无 | 全仓 `grep -rniI "fsmonitor" .claude/skills` 无命中 |
| `untrusted-search-path-rce`（可执行文件查找路径） | CVE-2026-95182 | `command-injection-analyzer` 的 PATH 污染章节 | LLM | 弱 | `command-injection-analyzer/command_env_pollution.md:1-30`（PATH/LD_PRELOAD/LD_LIBRARY_PATH）、`command-injection-analyzer/go_command_env_inherit.md:1-60`；只覆盖“进程继承被污染 PATH”，没有“从不可信目录解析可执行文件/当前目录优先”检测 |
| `prompt-injection`（context-compaction 注入） | CVE-2026-95183 | `llm-security-analyzer` | LLM + 语言特定参考 | 强 | `llm-security-analyzer/SKILL.md:10`、`llm-security-analyzer/SKILL.md:20`；`llm-security-analyzer/general.md:8`（间接注入）、`llm-security-analyzer/general.md:15`（上下文污染）；有 `Python_LLM_Indirect_Prompt_Injection_LangChain.md` 等专用参考 |

### 3.4 覆盖度汇总（按 29 个 type 去重）

| 覆盖度 | 数量 | type 列表 |
|--------|------|-----------|
| 强 | 8 | `rce-deserialization`、`rce-dill-deserialization`、`insecure-deserialization-script`、`ssrf`、`ssrf-local-file-read`、`path-traversal-file-write`、`rce-unsafe-eval`、`prompt-injection` |
| 弱 | 14 | `authentication-bypass`、`memory-corruption-deserialization`、`ssrf-bypass`、`rce-config-auto-map`、`insecure-deserialization`、`rce-dumper-sandbox-escape`、`sandbox-bypass`、`sandbox-escape`、`credential-disclosure`、`reachable-assertion-dos`、`dos`、`git-hook-rce`、`untrusted-search-path-rce`、`security-issue-unsafe-eval-deserialization` |
| 无 | 7 | `rce-trust-remote-code`、`model-weight-exfiltration`、`rce-mcp-config`、`command-approval-bypass`、`git-filter-rce`、`git-fsmonitor-rce`、`sandbox-isolation` |

> 统计的是 T01 的 29 个 type，不是 38 条条目；同一 type 的多条条目见第 3 节拆行。

## 4. 强覆盖能力（可直接复用）

1. **pickle/dill/cloudpickle 反序列化 sink**
   - tree-sitter 查询覆盖 `pickle|dill|cloudpickle` 的 `load/loads`，正则兜底覆盖 `yaml.load`、`marshal`、`shelve`。
   - 证据：`insecure-deserialization-analyzer/scripts/languages/python/queries/deserialization_sinks.scm:4-21`、`insecure-deserialization-analyzer/scripts/core/scanner.py:50-55`。
   - 本机实测：对 `insecure-deserialization-analyzer/scripts/tests/fixtures/python` 能输出 `pickle.loads`、`pickle.load`、`dill.loads`、`cloudpickle.loads`、`yaml.load` 命中。
2. **SSRF sink + file:// 本地读取**
   - tree-sitter query 覆盖 `requests.*`、`urlopen`、`urlretrieve` 等；`file://`、gopher、重定向绕过有专门 bypass 文档。
   - 证据：`ssrf-analyzer/scripts/config/languages.yaml:2-9`、`ssrf-analyzer/scripts/languages/python/queries/sinks.scm:1-20`、`ssrf-analyzer/bypassTricks.md:14-21`。
   - 本机实测：`ssrf-analyzer/scripts/cli.py --lang python .` 输出 68 条 sink（同时因缺 TS/Rust parser 打 warning）。
3. **路径遍历/上传写入**
   - 覆盖下载、预览、日志、上传文件名、归档解压（Zip Slip）和写入落盘，含 Java/Python/Go/JS/C/C++ 参考。
   - 证据：`path-traversal-analyzer/SKILL.md:7`、`:18`、`:47`、`:278`；`insecure-file-uploads-analyzer/SKILL.md:31`、`:83`。
4. **eval/exec 类代码注入**
   - Python/Java/JS/PHP/Go/Rust 的 eval/exec/动态编译/反射清单，含沙箱绕过提示。
   - 证据：`code-injection-analyzer/SKILL.md:10`、`:27`；`expression-injection-analyzer/SKILL.md:10`、`:15`、`:31`。
5. **LLM 提示注入与上下文隔离**
   - 直接/间接提示注入、上下文污染、工具调用越权、输出 XSS/代码注入等，有 Python/Node/Java/Go/PHP/Rust 参考文件。
   - 证据：`llm-security-analyzer/SKILL.md:10`、`llm-security-analyzer/SKILL.md:20`；`llm-security-analyzer/general.md:8`、`llm-security-analyzer/general.md:15`。

## 5. 结构性发现（会影响“真实覆盖率”，供 T03 使用）

1. **有 skill ≠ 会被编排到**
   - `project-profiler` 对后端 HTTP 服务只允许返回两个任务：`web-auth-analyzer` 与 `sensitive-info-scanner`，并明确“禁止添加其他技能”。
   - 证据：`project-profiler/SKILL.md:36-38`、`:165`。
   - 结果：`ssrf-analyzer`、`insecure-deserialization-analyzer`、`code-injection-analyzer`、`path-traversal-analyzer` 等不会因为“项目是 Python HTTP 服务”被自动调度；只有用户显式指定扫描器、走 `vtr-scanner` 靶场路径，或经 `code-security-analyzer` 的风险点映射才会被激活。
2. **README/agent 的扫描器清单与 profiler 的约束不一致**
   - README 列出 18 个“支持的扫描器”（`README.md:127-148`），并画出 `code-security-analyzer -> 漏洞分析器`（`README.md:309-314`）。
   - 但 profiler 的实际任务列表只有 2 个（见上），`security-orchestrator` 只在示例中提到 `ssrf-analyzer`（`.claude/agents/security-orchestrator.md:259`），没有强制“每个漏洞类型都要跑”。
3. **quick-scan 依赖未锁定**
   - `check-dependencies.sh:254-293` 要求 `tree_sitter_language_pack`，当前环境缺失；四个 tree-sitter quick-scan 全部启动失败。
   - 这是 T07 Docker 镜像的硬依赖，也是 T10 冒烟的前置条件。
4. **`case-studies-analyzer` 不是可执行 skill**
   - 目录只有案例 Markdown，没有 `SKILL.md`；orchestrator 的命名过滤虽然接受 `-analyzer`，但 skill-runner 无法加载它。
   - 证据：`ls .claude/skills/case-studies-analyzer/`；`.claude/agents/security-orchestrator.md:28-32`。
5. **AI 基础设施专用机制缺口集中在“平台层”**
   - 无 `trust_remote_code`、`auto_map`、MCP、safetensors、`torch.load(weights_only=...)`、Landlock/seccomp、Git filter/fsmonitor、命令审批、模型权重端点等专用规则。
   - 这些不是“再加一个 Web analyzer”能解决的，更像 T04 的候选：模型加载安全、Agent/沙箱边界审计。

## 6. 对 T03 的输入

- 可直接扩展的强项：pickle/dill sink、SSRF sink、路径遍历、eval/exec、提示注入。
- 优先补齐的“无覆盖”类型（P0 候选）：`rce-trust-remote-code`、`rce-config-auto-map`、`rce-mcp-config`、`model-weight-exfiltration`、`sandbox-isolation`、`git-filter-rce`、`git-fsmonitor-rce`、`command-approval-bypass`。
- 需要“扩展现有 skill”而不是新建的弱项：`torch.load`/HF 权重（扩 `insecure-deserialization-analyzer`）、Host→路由认证绕过（扩 `web-auth-analyzer` + `http-header-injection-analyzer`）、assertion/DoS（扩 `error-boundary-analyzer`）、Git filter/fsmonitor（扩 `security-configuration-analyzer` 的 Git 章节）。
- 需要先修编排的项：把 `code-security-analyzer` 的风险点映射接入 HTTP 工作流，或在 profiler 中按语言/框架增加条件任务；否则新增 skill 也不会被自动调用。
