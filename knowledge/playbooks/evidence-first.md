# Playbook：证据优先

每条 finding 必须能回答：

1. **入口**：哪个外部可控输入到达这里？（HTTP/gRPC/CLI/config/model file/IPC/MCP/env）
2. **路径**：从 source 到 sink 的调用链是什么？跨进程/跨文件也可以，但要写清。
3. **sink**：危险操作是什么？（exec/eval/pickle/torch.load/文件写/网络/GPU/权限变更）
4. **前置条件**：默认配置是否可达？需要哪些 flag/模式/权限？
5. **证据**：`path:line`、配置片段、命令输出。没有证据的只能叫 hypothesis。
6. **影响**：RCE / 未授权访问 / 信息泄露 / DoS / 沙箱逃逸。
7. **排除**：为什么不是误报？有没有 allowlist、realpath、auth middleware、weights_only、沙箱？

## 输出格式

```json
{
  "id": "VULN-001",
  "title": "...",
  "severity": "critical|high|medium|low",
  "confidence": "high|medium|low",
  "reachability": "default|opt-in|dev-only|requires-config|unknown",
  "cwe": "CWE-...",
  "files": [{"path": "...", "line_start": 1, "line_end": 1}],
  "source": "...",
  "sink": "...",
  "evidence": [{"type": "code|config|runtime", "path": "...", "line": 1, "snippet": "..."}],
  "preconditions": ["..."],
  "verification": {"status": "unverified", "method": "static", "report": ""},
  "remediation": "..."
}
```

## 禁止

- 没有 `file:line` 的 Critical。
- 把“可能”“也许”写成 confirmed。
- 同一个 root cause 按端点/语言重复计数。
- 引用未核实 CVE 编号。
- 写可直接武器化的 exploit。
