# Knowledge Index

> 由 knowledge-scribe 维护。新增知识卡/case 后在这里登记，方便 agent 渐进加载。

## Project Types

- [agent-harness](project-types/agent-harness.md) — codex / deepseek-harness / MCP / 工具执行
- [inference-engine](project-types/inference-engine.md) — vLLM / SGLang / TGI / serving
- [training-framework](project-types/training-framework.md) — verl / DeepSpeed / Ray RL
- [model-serving](project-types/model-serving.md) — Triton / 模型网关

## Projects

- [vllm](projects/vllm.md)
- [sglang](projects/sglang.md)
- [verl](projects/verl.md)
- [codex](projects/codex.md)
- [deepseek-harness](projects/deepseek-harness.md)

## Playbooks

- [evidence-first](playbooks/evidence-first.md)
- [reachability](playbooks/reachability.md)

## CVE / Cases

- [CVE 卡片格式](cves/README.md)
- [误报模式](false-positives/README.md)
- `cases/<project>/` — 每次审计的 confirmed/rejected 记录（由 knowledge-scribe 追加）

## 使用顺序

1. `knowledge/project-types/<type>.md`
2. `knowledge/projects/<project>.md`
3. 按 boundary 读 `playbooks/` 或 `cves/`
4. 审计后由 `knowledge-scribe` 回写 `cases/`、`false-positives/`、`projects/`
