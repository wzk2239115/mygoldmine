# 审计案例

每次审计后由 `knowledge-scribe` 在这里追加：

```text
knowledge/cases/<project>/<date>-<finding-id>.md
```

## 模板

```markdown
# <project> / <finding-id> / <date>

- verdict: confirmed|rejected|inconclusive|blocked
- severity: critical|high|medium|low
- reachability: default|opt-in|dev-only|requires-config|unknown
- files: path:line
- root cause: ...
- trigger: ...
- evidence: ...
- verification: command / harness / report
- false-positive notes: ...
- reusable lesson: 下次应该先看哪里、怎么判断
```

## 规则

- 只写与本次审计运行相关的事实，不大规模重写知识库。
- `rejected` 也要写：它是最有价值的误报样本。
- 不写密钥、令牌、内部 URL 和可直接武器化的利用代码。
- 写完后更新 `knowledge/index.md` 或对应 `knowledge/projects/<project>.md`。
