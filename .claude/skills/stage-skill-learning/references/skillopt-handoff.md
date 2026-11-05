# SkillOpt 请求与候选约定

## 请求字段

`request_skillopt_optimization` 只接受本节点（`learner`）调用。请求写入运行目录的 `rsi/skillopt-requests/`，不会直接修改正式技能。

```json
{
  "target_stage": "verify",
  "scope": "project",
  "problem": "蓝队验证在环境缺失时仍把结果写成已确认；需要把受阻条件写入判断。",
  "suggestions": [
    {
      "type": "replace",
      "title": "受阻时先记录缺失能力",
      "instruction": "运行入口不可用或缺少最小能力时，结论写为受阻，并列出缺失能力和已尝试命令。"
    }
  ],
  "evidence": ["/path/to/run/verify/agent/summary.json"],
  "source_stages": ["verify", "judge"],
  "expected_improvement": "减少把环境故障写成已确认的情况。",
  "possible_regression": "可能增加受阻结论，需要保留原验证尝试。",
  "conditions": {"commit": "abc123"}
}
```

## 校验规则

- 每轮最多两个请求；每个请求 1—4 条建议；证据 1—5 份。
- 证据必须在本次运行目录内，单份不超过 2 MiB；提交时保存副本。
- 修改建议只允许新增、替换或删除，必须指向具体动作，不能只写“提高质量”。
- 适用条件只支持机器架构、Python 版本和源码提交号三个精确字符串。
- 不在技能正文写入随机标记、私有答案、评估表达式、凭据或完整攻击输出。
- 请求入队后由宿主机执行优化；优化任务带 `SKILLOPT_RUN=1`，不递归启动学习。

## 输出与现有契约

适配层调用 SkillOpt 核心重写入口，返回完整技能正文。只有同时满足以下条件才转换为候选：

- 返回正文非空、长度不超过 12000 字符；
- 与基线技能正文不同；
- 不包含随机标记或私钥；
- 证据文件仍存在且摘要可计算。

候选写入现有 `rsi/stage-skills/candidates/`，保留来源阶段、目标阶段、源码版本、原技能版本、证据、问题归因、修改、适用范围、预期改善、可能退化，以及 SkillOpt 版本、提交和模型。随后由现有评估入口决定是否发布；请求和重写结果保存在 `rsi/skillopt/`，供轨迹查看。
