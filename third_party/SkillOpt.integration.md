# SkillOpt 接入记录

- 上游：https://github.com/microsoft/SkillOpt
- 固定提交：`01e41dbcdf9ea6e20d6428c152c14178bd1c80f3`
- 固定版本：`0.2.0`
- 本地目录：`third_party/SkillOpt/`
- 许可证：MIT，保留上游 `LICENSE`。
- 依赖登记：`third_party/SkillOpt.pin.json` 和 `.gitmodules`；核心依赖见 `third_party/SkillOpt/requirements.txt`。
- 未启用上游 WebUI、插件、hook、定时任务或自动采用。

## 接入边界

01—08 节点、执行顺序和现有阶段状态保持不变。01—07 只执行和提交反馈；08 读取前面阶段的产物、轨迹、覆盖记录、验证结果和失败原因，选择证据最充分的目标阶段，再调用 SkillOpt 核心重写入口生成候选。正式版本、评估、发布和回退仍由现有 `scripts/stages/skill_bank.py` 管理，不建立第二套技能管理系统。

第一版只使用核心入口：

```text
skillopt.optimizer.rewrite.rewrite_skill_from_suggestions
```

选择理由：

- 现有项目已经有阶段反馈、候选契约、独立评估、版本指针、发布记录和回退接口；接入完整 SkillOpt-Sleep 会重复采集、回放、暂存和采用流程，产生第二套发布真值。
- 核心重写入口只需要当前技能正文和少量修改建议，适合 08 在归因后提交小幅改动。
- 不修改上游源码；适配代码位于 `scripts/stages/skillopt_adapter.py`，调用记录保存在运行目录的 `rsi/skillopt/`。

SkillOpt-Sleep 未接入。其完整夜间循环包含采集、挖掘、回放、合并、验证和采用，和现有八阶段学习循环重叠，本任务不同时叠加两套循环。

## 真实调用关系

```text
08 stage-skill-learner
  -> 读取 rsi/stage-feedback/index.json 和各阶段产物
  -> 选择目标阶段并提交 request_skillopt_optimization
  -> 请求写入 rsi/skillopt-requests/<编号>.json
  -> scripts/stages/learn_round.py
  -> scripts/stages/skillopt_adapter.py
  -> SkillOpt rewrite_skill_from_suggestions
  -> scripts/stages/skill_bank.py propose
  -> rsi/stage-skills/candidates/<候选编号>.json
  -> config/stage-evals/<目标阶段>.json 现有评估
  -> 通过后 publish，保留发布记录；必要时 rollback
```

请求只写候选，不直接覆盖正式 `SKILL.md`。没有可信评估套件时，候选保留并记录原因，不自动发布。SkillOpt 的内部评分不作为项目发布批准。

## 运行边界

- 每轮最多两个优化请求，每个请求 1—4 条建议；核心重写最多尝试两次；只有第一次没有返回可解析结果时才重试。
- 模型通过现有 Claude 兼容连接运行，设置 `CLAUDE_SETTING_SOURCES=project,local`，避免用户级 Claude 配置覆盖项目模型。
- 优化任务设置 `SKILLOPT_RUN=1`，学习入口检测到该标记后直接跳过，不递归启动新的学习循环。
- 优化过程和结果写入 `rsi/skillopt/`；不写入 `.stage-skill-proposals`，避免被再次当作独立成功经验导入。
- 学习数据、验证数据和最终留出测试分开；随机标记、私有答案和评估表达式不得进入技能。

## 验证状态

- 已做真实 08 调用：在临时运行 `demo/one` 中启动真实 `stage-skill-learner`，它读取八阶段反馈并提交两个 `request_skillopt_optimization` 请求；宿主机适配层调用本地 SkillOpt 提交 `01e41dbc` 的核心重写入口，生成 environment 和 verify 两个候选，候选来源说明包含提交、版本、模型和请求编号。
- 已做拒绝与保留验证：没有 `config/stage-evals/<stage>.json` 时，`skill_bank.py advance` 记录 `missing_evaluation_suite`，正式版本指针保持为空，没有自动发布。
- 已做接线验证：在临时仓库放入测试评估命令后，候选进入现有评估入口并显示 accepted；随后调用现有 publish 和 rollback，版本指针先写入后清空。该测试只证明候选契约、评估、发布和回退接线，不证明漏洞识别能力提高。
- 真实运行时曾出现一次模型返回内容无法解析；适配层只在没有可解析结果时再尝试一次，并在结果中保留尝试次数和错误。没有把失败重试写成成功。
- 仓库当前没有为阶段技能配置可信的生产评估套件；真实 08 运行产生的候选默认保留，不自动发布。
