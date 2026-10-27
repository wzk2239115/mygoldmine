# Experimental / optional

这些脚本**不参与默认审计流程**，只作为人工排障或 agent 的可选索引。

## `infra_surface_index.py`

早期尝试的规则扫描器。在 vLLM/SGLang/verl/codex/deepseek 上产出 4k-17k 条线索，
证明“纯规则检测”不适合作为 finding 来源。

保留原因：
- 快速列出入口/可疑 sink，帮助 agent 决定先读哪些文件。
- 输出只是 **lead/surface**，不是漏洞结论。

使用方式（可选）：

```bash
python3 scripts/experimental/infra_surface_index.py rpc targets/vllm --json
```

不要把它的 `findings` 直接写进报告；真正的判断交给 `infra-analyst` + `hypothesis-critic`。
