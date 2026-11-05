# 审阅手册：证据优先

每条候选问题（finding）必须能回答：

1. **入口**：哪个外部可控输入到达这里？例如 HTTP、gRPC、命令行、配置、模型文件、进程间通信、MCP 或环境变量。
2. **路径**：从输入来源到危险数据终点的调用链是什么？跨进程或跨文件也可以，但要写清。
3. **危险数据终点**：危险操作是什么？例如 `exec`、`eval`、`pickle`、`torch.load`、文件写入、网络访问、GPU 操作或权限变更。
4. **前置条件**：默认配置是否可达？需要哪些启动参数、模式或权限？
5. **证据**：`path:line`、配置片段和命令输出。没有证据的只能叫假设。
6. **影响**：远程代码执行、未授权访问、信息泄露、拒绝服务或沙箱逃逸。
7. **排除**：为什么不是误报？有没有白名单、真实路径校验、认证中间件、`weights_only` 或沙箱？

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

- 把没有 `file:line` 证据的问题定为严重。
- 把“可能”“也许”写成 `confirmed`。
- 同一个根因按端点或语言重复计数。
- 引用未核实 CVE 编号。
- 编写可直接武器化的利用代码。
