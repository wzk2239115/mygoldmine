# 知识库索引

> 由 `knowledge-scribe` 维护。新增知识卡或案例后在这里登记，方便智能体按需加载。

## 项目类型

- [agent-harness](project-types/agent-harness.md) — codex / deepseek-harness / MCP / 工具执行
- [inference-engine](project-types/inference-engine.md) — vLLM / SGLang / TGI / 模型服务
- [training-framework](project-types/training-framework.md) — verl / DeepSpeed / Ray RL
- [model-serving](project-types/model-serving.md) — Triton / 模型网关

## 具体项目

- [vllm](projects/vllm.md)
- [sglang](projects/sglang.md)
- [codex](projects/codex.md)
- [deepseek-harness](projects/deepseek-harness.md)
- [agentscope-runtime](projects/agentscope-runtime.md) — FastAPI 引擎、沙箱管理器和训练沙箱

## 审阅手册

- [evidence-first](playbooks/evidence-first.md)
- [reachability](playbooks/reachability.md)

## CVE 与案例

- [CVE 卡片格式](cves/README.md)
- [误报模式](false-positives/README.md)
- `cases/<project>/` — 每次审计的 confirmed/rejected 记录（由 knowledge-scribe 追加）
  - [agentscope-runtime/2026-10-27-infra-control-plane](cases/agentscope-runtime/2026-10-27-infra-control-plane.md) — manager fail-open / env_service 无鉴权 / AgentApp shutdown / 默认 token / CORS
  - [deepseek-harness/2026-11-02-static-audit](cases/deepseek-harness/2026-11-02-static-audit.md) — 11 findings（GIT_CONFIG_PARAMETERS / 读路径无围栏 / MCP 无标注无界 / auto-review fail-open）+ 5 hypotheses + 21 rejected（全 unverified）

## 使用顺序

1. `knowledge/project-types/<type>.md`
2. `knowledge/projects/<project>.md`
3. 按类别和根因读 `.claude/skills/rsi-shared-experience/rules/` 中的共享修复
4. `knowledge/project-rules/<project>/` 中当前项目的专属修复
5. `false-positives/README.md` 中相关误报排除条件，再按信任边界读 `playbooks/` 或 `cves/`
6. 审计后由 `knowledge-scribe` 回写 `cases/`、`false-positives/`、`projects/`；挖掘修复经独立评估后由发布命令写入，不靠智能体直接改生产规则
