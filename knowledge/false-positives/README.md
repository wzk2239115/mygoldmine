# 误报模式库

按项目/类型积累“看起来像、实际不是”的模式。

## 通用

- `torch.load(..., weights_only=True)` 且检查点受信：不是远程代码执行。
- `yaml.load(..., Loader=SafeLoader)`：不是反序列化远程代码执行。
- 只绑定 `127.0.0.1` 或 Unix 套接字的管理端点：网络不可达，应降级。
- 危险启动参数只在显式 `--dangerously-*` 或用户确认后生效：可达性为 `opt-in`，不是默认漏洞。
- 下载或文件路径同时具备白名单、真实路径和重定向校验：需要具体绕过证据。
- 测试、示例和文档中的不安全写法：不算产品默认行为。

## vLLM

- `torch.load` 全部设置 `weights_only=True`。
- 媒体抓取具备出站白名单和私网过滤。
- 开发与强化学习端点需要显式启动参数。

## SGLang

- 配置了 `--api-key` 或 `--admin-api-key`，且中间件覆盖。
- SafeUnpickler 使用白名单。
- 管理端点只绑定回环地址。

## verl

- `exec` 和 `eval` 只处理受信本地脚本。
- 训练集群完全受信、无跨租户边界。
- `torch.load(weights_only=True)`。

## codex

- 控制面只绑定回环地址且限同一用户。
- 危险配置需显式确认。
- 沙箱和审批默认开启。

## deepseek-harness

- ~~文件读取有工作区前缀校验。~~ **更正 2026-11-02**：与代码不符，不能作为误报理由。`fs-sandbox` 只围栏写（“Reads pass through untouched”），`workspace-files.read` JSDoc 明确 “files outside it are allowed”；读路径无前缀校验，见 INFRA-FS-001。
- 沙箱默认开启；danger-full-access 需显式选择 profile（`sdk-minimal` 为文档化 opt-in）或在运行时卸载安全插件（见 INFRA-SB-004，那是真 fail-open，不算误报）。
- 控制面**默认**只绑定回环（`127.0.0.1:3080`），非回环需显式 `--host`；回环端口不按 OS 用户隔离。
- 工具输出/会话日志明文持久化是既定设计；spill 文件在 0700 mkdtemp、0o600 `wx` 打开 → 不单列。

### 2026-11-02 静态审计确认的误报模式（commit `22ddee37`）

来源：`/home/wzk/mygoldmine/runs/deepseek-harness/20261102T170623Z/`（21 条 rejected）。

- **ACP trusted controller**（INFRA-MCP-003）：ACP README 明确 “ACP clients are trusted controllers”；`session/new|resume` 声明的 stdio MCP command/env 是受信控制器授权，不是未授权输入。
- **owner 选择的 cwd**（INFRA-SB-002）：`session.create` 的 cwd 由已认证本地 owner 选择，模型无法改 header cwd，无向非 owner 授予 create 的 policy；不要把“cwd 即可写根”当越权。
- **OAuth PKCE/state**（CP-H1/CP-H2）：state 32 字节随机 + timingSafeEqual + 单次使用（重放 410），callbackOrigin 由 owner 提供且用 S256 PKCE、verifier 仅存服务端；仅防御纵深/DoS。
- **webhook HMAC**（CP-H6）：webhook-github 先校验 method/content-type，再用 `X-Hub-Signature-256` + secret HMAC（伪造 401），且默认未挂载；未见 Host/Origin fence 不等于可伪造。
- **MCP URL/URI 来自操作者或服务器**（MCP-H2/H3/H4）：streamable-http 的 URL/header、resource URI、browser/computer-use command 均来自操作者 overlay 或受信服务器；URI 不映射为主机路径。
- **Windows ACL partial**（SB-H1）：windows-acl 后端只限制写/删，是 README 记录的平台边界，不是实现缺陷；不要把平台差异当逃逸。
- **fs-sandbox TOCTOU**（FS-H2）：模块自述 “containment, not a security boundary”，TOCTOU 为接受风险且检查后重新 canonicalize；需稳定利用证据才升级。
- **PTC 实际有界**（PE-NOTE-PTC，原 VULN-006）：`maxPendingCalls`（默认 128）/`maxMessageBytes` 背压 + `Promise.race`，未发现无界队列；不要把“有队列”直接当 OOM。
- **媒体引用无出站抓取**（FS-VULN-003，原 VULN-003）：media-references 只接受本地绝对路径并 fs.resolve/stat/readBytes，不存在按 `image_url` 下载的逻辑。
- **会话日志路径已修复**（FS-VULN-004，原 VULN-004）：`session-persistence-jsonl` 的 `encodeSegment` 已中和 `../`、绝对路径、NUL、分隔符与 `.`/`..`。
- **旧条目归并**：VULN-001/002 → INFRA-FS-001（读路径确实无围栏，不属误报）；VULN-005 → INFRA-CONFIG-001（`GIT_CONFIG_PARAMETERS` 残留面，不属误报）。

## 维护

每次 `hypothesis-critic` 或 `verify-agent` 判定 `rejected`，由 `knowledge-scribe` 把模式追加到这里。

## 2026-10-27 二次审计新增

- codex F-01 / F-36：exec-server 默认 `ws://127.0.0.1:0`；只有显式 `--listen 0.0.0.0` 且无 ws-auth 才成立 → opt-in。
- codex F-02 / F-25：app-server 默认 stdio/回环或已认证 WS，本地信任模型；不是未授权远程 → opt-in。
- deepseek VULN-004：session log 发往同一模型提供方，属既定功能/隐私设计；`.env` 禁止改 baseURL，无攻击者通道。
- deepseek VULN-006：无 turn budget 是设计限制，可取消/扩展；重试有上限，不是漏洞。
- deepseek VULN-001：与 VULN-002 同 `locateFile` 根因，合并。
- sglang VULN-001：与 VULN-002 同 `/server_info` 根因，合并。
- sglang VULN-025：标题/描述不一致，evidence 空、line 0 → UNCLEAR，重写或删除。
- verl CI-01 / CI-02：`custom_cls.path`/`router_config_path` 默认 null，来源是操作者 Hydra 配置；
  默认不可达、无跨信任边界 → FP（只有多租户/配置注入场景才重新评估）。
- verl AC-001 / AC-002：与 ROUTE-01/WEB-01、ROUTE-02/WEB-03 同根因，合并别名。

## agentscope-runtime（2026-10-27，静态审计）

- 沙箱内 `run_shell_command` / `run_ipython_cell`（`box/shared/routers/generic.py:121-138`）是**设计能力**，不是独立漏洞；
  只有在拿到沙箱 token、绕过 manager 或容器逃逸（MOBILE `privileged=True`）时才升级。generic 路由编译进 FILESYSTEM 镜像只算加固提示。
- `tools/mcp_wrapper.py` 的 `exec(code, namespace)`（`:137-184`）由**受信静态工具元数据**（类名/方法名/参数名/类型名）生成，
  非模型/用户可控；除非存在不可信插件或外部 FQN 注册工具元数据的入口，否则不报代码注入。
- Manager 默认 `HOST=127.0.0.1`（`sandbox/manager/server/config.py:15`）：默认配置类 finding 要写清
  “loopback 默认；远程需 `HOST=0.0.0.0` 或浏览器跨站”，不要直接按公网 Critical。
- 训练沙箱 `env_service` 与共享 box 的 `verify_secret_token` 是两套入口，不能因为共享 box 有 token 就认为训练面已认证。
- 同一根因的端点/脚本/Dockerfile 变体要合并（本次 8 条源 finding → 5 个 cluster），不要按出现次数重复计数。
- `/admin/status` 信息泄露、SSE 错误回显、完整请求体日志属低危，与 high 认证缺失合并评估，不重复计漏洞。


## 工具层误报（2026-10-28，batch 1）

这些不是目标仓库的漏洞模式，而是 mygoldmine 自身验证流程的误报来源：

- `auto_verify.sh` 把 `exec_module` 关键词命中判成 confirmed → verl CI-01 实际是默认 null、操作者 Hydra 配置的 FP。**关键词命中不是漏洞证明。**
- `auto_verify.sh` 把“关键词没搜到”判成 rejected → 关键词缺失同样不是反证。现在只允许 `inconclusive`。
- 源码链存在、但环境缺失/无法启动时，应标 `blocked` 或 `source-supported`，不能写 confirmed。
- 默认 HITL / 人工审批 / 回环绑定 / opt-in flag / 测试与示例代码，必须先在 `false_positive_checks` 里排除。
- `confirmed` 必须有 `evidence/` 文件；没有证据的 confirmed 由 `run_verify.sh` 自动降级。
- 只做单行 grep 的 harness 必须标 `evidence_class=static-pattern`，只能产出 `inconclusive`。

这些模式用于反向优化：
1. 先问“默认配置是否可达”；
2. 再问“有没有反向对照”；
3. 最后才问“sink 是否存在”。
缺少前两项时，不进入人工研判优先队列。
