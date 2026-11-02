import { useState } from 'react';
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  BadgeCheck,
  Bot,
  Boxes,
  Braces,
  Database,
  FileCode2,
  GitBranch,
  Layers3,
  Network,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Workflow
} from 'lucide-react';
import { cx } from '../utils.js';

const MINING_STAGES = [
  {
    code: '01',
    title: '目标与调度',
    icon: GitBranch,
    tone: 'ink',
    body: '从 manifest 选择目标；parallel_mine / overnight 控制并发、失败重试和断点续跑，每个项目使用独立 run。',
    artifact: 'targets/manifest.json → runs/<project>/<run>/'
  },
  {
    code: '02',
    title: '隔离工作副本',
    icon: Boxes,
    tone: 'blue',
    body: '每个 run 使用独立持久沙箱：原始源码只读，挖掘、verify 和交互 shell 复用同一工作副本。',
    artifact: 'sandbox.sh → /workspace/repo → verify / shell'
  },
  {
    code: '03',
    title: '召回与协同审计',
    icon: Bot,
    tone: 'violet',
    body: 'Jev 初筛只提供审计线索，不直接成为 finding；security-orchestrator 组织项目画像、攻击面和分任务审计。',
    artifact: 'triage/jev-*.json · raw.jsonl'
  },
  {
    code: '04',
    title: '增量报告与质量门',
    icon: FileCode2,
    tone: 'amber',
    body: '审计开始即创建报告骨架，子任务完成就增量落盘；schema、必填字段和系统语言全部通过才算完整。',
    artifact: 'audit-report.{md,json} · reports_complete'
  },
  {
    code: '05',
    title: 'Deadline 与恢复',
    icon: Database,
    tone: 'hot',
    body: '所有尝试共享墙钟预算，按 setup/model/tool 真实进展判活；恢复复用校验过的成果，失败分支不阻塞汇总。',
    artifact: 'progress_guard.py · durable_recovery.py'
  },
  {
    code: '06',
    title: '发布到下游',
    icon: ShieldCheck,
    tone: 'green',
    body: '只有完整有效报告才进入 Finding Ledger；随后接入 Phase 4 验证、视觉报告、自动状态和精炼，而不是直接推给人工。',
    artifact: 'Finding Ledger → Phase 4 → refine'
  }
];

const STAGES = [
  {
    code: '01',
    title: '报告与台账',
    icon: FileCode2,
    tone: 'ink',
    body: '只接收完整有效的审计报告；occurrence 定位单次观测，semantic 汇聚跨 run 的同一语义，草稿不会覆盖历史。',
    artifact: 'runs/*/*/audit-report.json → finding-ledger.json'
  },
  {
    code: '02',
    title: '自动精炼',
    icon: ScanSearch,
    tone: 'blue',
    body: '评分、去重、证据门槛和批量 worker。低价值项归档，不等同于安全；高价值项进入分诊。',
    artifact: 'auto-state.json · refine-state.json · refine-queue.json'
  },
  {
    code: '03',
    title: '验证 / 复现',
    icon: ShieldCheck,
    tone: 'amber',
    body: 'verify-agent 生成最小 harness，记录 confirmed / blocked / inconclusive，并保留证据与限制。',
    artifact: 'verify/.../verify-report.json'
  },
  {
    code: '04',
    title: 'CVE 去重',
    icon: GitBranch,
    tone: 'hot',
    body: '查 NVD / GHSA / 项目公告，判断是否已被覆盖；重复项关闭，候选进入动态验收。',
    artifact: 'docs/cve-*.json · curated/state'
  },
  {
    code: '05',
    title: '红队 lab',
    icon: Bot,
    tone: 'violet',
    body: 'scenario 按 finding 隔离并绑定 source hash；当前执行器只支持 HTTP，其他形态明确 blocked，不做伪装包装。',
    artifact: 'labs/<project>/<finding-id>/scenario.json · runs/redteam/*'
  },
  {
    code: '06',
    title: 'Judge / 验收',
    icon: BadgeCheck,
    tone: 'green',
    body: '独立模型审核轨迹：是否命中目标漏洞、flag 是否来自 victim、是否作弊、是否可复现。',
    artifact: 'judge.json · report-illustrated.md · scene.webp'
  }
];

const COMPONENTS = [
  {
    icon: Layers3,
    title: 'Finding Ledger',
    body: '扫描全部完整有效 run，保留 occurrence/semantic 双层身份；同 ID 异义不串状态，历史独有项不消失。',
    code: 'scripts/workflow/finding_ledger.py'
  },
  {
    icon: Braces,
    title: '状态编译器',
    body: '基于台账合并 verify、CVE 和人工状态，再次重算红队 provenance 与 review 门槛。',
    code: 'scripts/workflow/build_state.py'
  },
  {
    icon: Workflow,
    title: '精炼 worker',
    body: '按 source hash 重算路由；confirmed 可唤醒归档，高危弱指纹只进入重复候选而不直接归档。',
    code: 'scripts/workflow/refine_worker.py'
  },
  {
    icon: Database,
    title: '持久化恢复',
    body: '全 run 共享 deadline，区分 setup/model/tool idle；attempt 成果落盘，恢复后继续完成 Phase 4。',
    code: 'scripts/mine/durable_recovery.py'
  },
  {
    icon: Boxes,
    title: 'Lab builder',
    body: '按 finding/source 绑定 scenario 并校验执行契约；当前只有 HTTP lab 能进入运行阶段。',
    code: '.claude/skills/redteam-lab-builder'
  },
  {
    icon: Network,
    title: 'Red-team runner',
    body: 'attacker 在受限容器执行工具；flag 只能来自真实工具输出，最终回答和宿主路径不算证据。',
    code: 'scripts/redteam/agent.py'
  },
  {
    icon: ShieldCheck,
    title: 'Independent judge',
    body: '完整固定 schema + 确定性 provenance 双重校验，缺字段、字符串布尔或哈希不一致都拒绝。',
    code: 'scripts/redteam/judge.py'
  },
  {
    icon: Sparkles,
    title: '视觉报告',
    body: '结构树、覆盖树、攻击路径、attacker/victim 步骤和叙事插图；插图不充当漏洞证据。',
    code: '.claude/skills/project-cartographer'
  }
];

const RSI_STAGES = [
  {
    code: '01',
    title: '真实轨迹',
    icon: Workflow,
    tone: 'blue',
    body: '把真实验证与红队行动整理成带身份、动作前上下文、成本和血缘的经验，不从最终报告反推探索过程。',
    artifact: 'rsi/verification-experience.jsonl · redteam-experience.jsonl'
  },
  {
    code: '02',
    title: '可信标签',
    icon: BadgeCheck,
    tone: 'green',
    body: '分层抽样并合并 runtime、judge、manual 证据；static 只能辅助 shadow，unknown 不会被当成误报。',
    artifact: 'rsi/verification-label-plan.jsonl → labeled.jsonl'
  },
  {
    code: '03',
    title: '效用学习',
    icon: Sparkles,
    tone: 'violet',
    body: '对五种验证动作分别训练 ridge 效用模型，学习收益与成本，而不是模仿历史动作或最终报告。',
    artifact: 'verify / deep_read / human_review / duplicate_candidate / defer'
  },
  {
    code: '04',
    title: 'Holdout + Flips 评估',
    icon: ScanSearch,
    tone: 'amber',
    body: '按项目留出 holdout，对照 baseline 回放并观测 semantic outcome flips；只评估真实已发生结果，不做因果宣称。',
    artifact: 'verification-replay.json · verification-flips.json · statistical gate'
  },
  {
    code: '05',
    title: 'Shadow 建议',
    icon: Bot,
    tone: 'violet',
    body: '生成 recommendation-only 建议且 state_change=none；trusted_support=0 时仍以 static-only 继续 shadow，不进入生产。',
    artifact: 'ui/data/verification-shadow.json'
  },
  {
    code: '06',
    title: '受控执行回流',
    icon: ShieldCheck,
    tone: 'green',
    body: '只有通过统计与发布复核的候选才可进入既有受控流程；执行产生的新真实结果再回流，shadow 本身不触发执行。',
    artifact: '不可变候选 → 发布复核 → 新轨迹'
  }
];

const RSI_BRANCH_COMPONENTS = [
  {
    icon: ScanSearch,
    title: '弱点聚类',
    tone: 'hot',
    body: '按项目类型、攻击模型、失败类别和严重度确定性聚类，定位高支持度的 harness 失败表面。',
    code: 'audit_rsi/weakness.py → rsi/redteam-weakness.json'
  },
  {
    icon: FileCode2,
    title: 'Harness 候选',
    tone: 'amber',
    body: '只为白名单 editable surface 生成带稳定身份的证据提案；经 flips 验证后仍需复核，绝不自动修改 harness。',
    code: 'audit_rsi/harness.py → rsi/harness-candidates.json'
  }
];

const STAGE_SUMMARIES = {
  '目标与调度': '选目标、控并发、可续跑',
  '隔离工作副本': '一个沙箱，持续探索与验证',
  '召回与协同审计': '先广召回，再分任务审计',
  '增量报告与质量门': '边审计边落盘，过质量门',
  'Deadline 与恢复': '统一预算，复用成果续跑',
  '发布到下游': '完整报告才进入流水线',
  '报告与台账': '给每次发现建立稳定身份',
  '自动精炼': '去重、评分、归档与分诊',
  '验证 / 复现': '用最小 harness 验证候选',
  'CVE 去重': '确认是否已知与受影响',
  '红队 lab': '隔离环境捕获真实 flag',
  'Judge / 验收': '独立审核后才交给人工',
  '真实轨迹': '记录动作、上下文、结果与成本',
  '可信标签': '分清 trusted、static 与 unknown',
  '效用学习': '按动作学习收益减去成本',
  'Holdout + Flips 评估': '独立对照与非回归观测',
  'Shadow 建议': '只给建议，不改变生产状态',
  '受控执行回流': '过门后执行，新结果再学习'
};

const COMPONENT_SUMMARIES = {
  'Finding Ledger': '跨 run 的发现身份与历史',
  '状态编译器': '把证据编译为流程状态',
  '精炼 worker': '持续执行自动路由',
  '持久化恢复': '复用成果，恢复中断',
  'Lab builder': '构建与校验隔离场景',
  'Red-team runner': '执行受限攻击并留痕',
  'Independent judge': '独立审核证据与作弊',
  '弱点聚类': '从真实失败中定位改进表面',
  'Harness 候选': '白名单提案，不直接改代码',
  '视觉报告': '把证据变成易懂图文'
};

const ZONES = [
  {
    id: 'mining',
    title: '挖掘工厂',
    subtitle: '从目标源码到可信报告',
    description: '目标调度、隔离副本、协同审计、质量门和恢复发布。',
    image: '/architecture/mining.webp',
    icon: Boxes,
    tone: 'blue',
    stages: MINING_STAGES,
    components: []
  },
  {
    id: 'pipeline',
    title: '精炼与验证',
    subtitle: '从原始 finding 到可验证候选',
    description: '台账、自动精炼、verify 和 CVE 去重如何逐步收敛候选。',
    image: '/architecture/refinery.webp',
    icon: ScanSearch,
    tone: 'amber',
    stages: STAGES.slice(0, 4),
    components: []
  },
  {
    id: 'redteam',
    title: '红队与验收',
    subtitle: '在隔离环境里证明，而不是猜',
    description: 'victim / attacker、真实 flag、独立 judge 和人工验收门。',
    image: '/architecture/redteam.webp',
    icon: ShieldCheck,
    tone: 'hot',
    stages: STAGES.slice(4),
    components: COMPONENTS.filter((item) => ['Lab builder', 'Red-team runner', 'Independent judge'].includes(item.title))
  },
  {
    id: 'components',
    title: '核心组件',
    subtitle: '数据、状态、路由、恢复与表达',
    description: '支撑整条流水线的台账、状态编译、精炼 worker、持久化恢复和视觉报告。',
    image: '/architecture/components.webp',
    icon: Layers3,
    tone: 'ink',
    stages: [],
    components: COMPONENTS.filter((item) => ['Finding Ledger', '状态编译器', '精炼 worker', '持久化恢复', '视觉报告'].includes(item.title))
  },
  {
    id: 'learning',
    title: 'RSI 学习闭环',
    subtitle: '真实经验驱动建议，门禁控制回流',
    description: '把验证与红队经验变成可评估的效用策略；当前只运行 shadow 学习，不把建议称作生产 RSI。',
    image: '/architecture/learning.webp',
    icon: Sparkles,
    tone: 'violet',
    stages: RSI_STAGES,
    components: RSI_BRANCH_COMPONENTS
  }
];

const DETAIL_GUIDES = {
  '目标与调度': {
    input: 'targets/manifest.json、目标源码、模型与并发/超时预算',
    output: '每项目独立 run、编排状态、可恢复的完成/失败记录',
    source: 'scripts/mine/parallel_mine.sh · overnight.sh',
    checks: ['并发只作用于项目级 worker，不共享产物目录。', '非空 run 拒绝覆盖，完整成功报告默认跳过。', 'resume 只补未完成项目，超时与失败保持可辨识。'],
    failure: '启动前检查失败不会调用模型；worker 失败保留日志和状态，超时不错误重试。',
    optimize: '优先检查队列公平性、陈旧 running 状态、恢复语义，以及新目标接入是否需要修改调度器。'
  },
  '隔离工作副本': {
    input: '只读目标目录、Phase 0 环境镜像、独立 run 和挖掘时的模型凭据',
    output: '可持续进入的项目沙箱、共享 /workspace/repo、离线 verify 与持久化产物',
    source: 'scripts/env/sandbox.sh · mine_one_docker.sh · run_verify.sh',
    checks: ['每个 run 一个沙箱，挖掘、shell 和 verify 复用同一工作副本。', '原始 /target 只读；不挂 Docker socket，cap-drop ALL，密钥不写入沙箱状态。', 'verify 前 isolate 断开网络；stop 保留工作副本，remove 才删除容器。'],
    failure: '沙箱创建失败回退一次性容器；联网沙箱拒绝离线 verify；恢复 run 无法共享挂载时回退独立验证容器。',
    optimize: '优先检查工作副本是否真正复用、验证是否断网、产物挂载是否覆盖，以及 stop/remove 是否混淆。',
    command: `bash scripts/env/sandbox.sh status --project <project> --run-dir <run>
bash scripts/env/sandbox.sh shell --project <project> --run-dir <run>
bash scripts/env/sandbox.sh isolate --project <project> --run-dir <run>
bash run.sh --verify-only <run>`
  },
  '召回与协同审计': {
    input: '工作副本、知识库、Jev priority/flags 和审计计划',
    output: 'jev 初筛、项目画像、子任务发现、真实 stream-json 动作轨迹',
    source: 'scripts/mine/mine_one.sh · .claude/agents/security-orchestrator.md',
    checks: ['Jev 只负责召回，初筛单元不直接成为 finding。', 'orchestrator 按项目画像和攻击面组织子任务。', 'raw.jsonl 记录真实工具调用，不能用最终报告反推探索过程。'],
    failure: 'Jev 失败可降级继续审计；模型瞬时错误只在共享预算内有限重试。',
    optimize: '重点看攻击面覆盖、重复子任务、模型别名一致性和轨迹完整性，而不是只看最终 finding 数。'
  },
  '增量报告与质量门': {
    input: '子任务结论、文件/行号证据、根因与修复建议',
    output: 'audit-report.md/json、report-quality.json、reports_complete',
    source: 'scripts/mine/mine_one.sh · check_report.py · report_quality.py',
    checks: ['审计开始即写骨架，子任务完成后增量更新。', 'schema、必填字段和系统语言全部通过才完整。', '报告是静态候选，不能把未验证描述写成运行时事实。'],
    failure: '即使模型退出码为 0，报告质量不合格仍会失败，且不能发布到 Finding Ledger。',
    optimize: '修改报告字段时同步 Python/JS 合同、质量检查和 UI；不要用补文案掩盖缺失证据。'
  },
  'Deadline 与恢复': {
    input: '共享墙钟预算、raw 事件、task artifacts、历史 recovery checkpoint',
    output: 'attempt health、校验过的分支成果、可续跑任务与恢复摘要',
    source: 'scripts/mine/progress_guard.py · durable_recovery.py',
    checks: ['重试和等待共享同一 deadline，不重置预算。', 'setup/model/tool 按真实事件判活，pending tool 不算 idle。', '恢复复用 checksum 匹配成果，源 run 证据保持不可变。'],
    failure: '预算耗尽不再启动新尝试；单分支失败被隔离，不能阻塞其他成果和报告汇总。',
    optimize: '重点验证中断点、产物 checksum、部分失败可见性，以及恢复后是否真正完成 Phase 4。'
  },
  '发布到下游': {
    input: '完整有效报告、环境镜像和现有历史台账',
    output: 'Finding Ledger、Phase 4 验证、视觉产物、自动/精炼状态',
    source: 'run.sh · scripts/workflow/finding_ledger.py · build_state.py',
    checks: ['只有完整有效报告能替换最新发布状态。', 'Phase 4 验证与静态挖掘分离，env blocked 不伪装 ready。', 'UI 必须读取新台账与状态产物，不能只重新构建静态页面。'],
    failure: '报告无效不执行 Phase 4；环境缺失、verify blocked 或后端未加载新产物都保持明确状态。',
    optimize: '检查发布后的服务重载、worker 存活和新数据唤醒，避免产物已推进而页面仍停留在旧流程。'
  },
  '报告与台账': {
    input: '所有 run 的报告、run-meta、原始 finding 与历史身份',
    output: 'schema v2 occurrence/semantic 台账和 latest_by_project',
    source: 'scripts/workflow/finding_ledger.py · ui/server/finding-ledger.mjs',
    checks: ['occurrence 精确定位一次观测，semantic 汇聚跨 run 语义。', '历史独有 finding 保留，新 run 不会让它们消失。', '旧 project:id 只有语义唯一时才继承状态。'],
    failure: '运行中、失败或质量不合格草稿不覆盖最新完整报告；歧义旧 ID 不猜测合并。',
    optimize: '调整语义指纹时重点回归同 ID 异义、跨 run 改路径、历史独有项和状态继承。'
  },
  '自动精炼': {
    input: '最新台账、verify/CVE 证据、人工状态和已有 refine source hash',
    output: 'triage/reproduce/archived 路由、队列统计和决策轨迹',
    source: 'scripts/workflow/refine_worker.py · refine_worker.sh',
    checks: ['raw 或证据变化会改变 source hash 并触发重算。', 'confirmed 可唤醒归档，高危弱指纹不直接归档。', '人工状态始终高于自动路由，archived 不代表安全。'],
    failure: 'lock 防止双实例；--loop 在空队列时等待并继续扫描，新数据到达后自动处理，pause/stop 保留明确控制语义。',
    optimize: '优先检查 worker 存活、空队列后的唤醒、状态与当前 occurrence 的匹配，再调整评分阈值。'
  },
  '验证 / 复现': {
    input: '候选 finding、对应源码 commit、环境镜像和验证预算',
    output: '最小 harness、confirmed/blocked/inconclusive 和证据分类',
    source: 'scripts/verify/auto_verify.sh · run_verify.sh',
    checks: ['验证对象绑定具体 finding 与源码版本。', 'confirmed 必须来自可检查的验证结果，静态成立不等于运行时成立。', '最小 harness 只用于验证，不交付武器化 exploit。'],
    failure: '环境或输入不足保持 blocked/inconclusive，不猜测成功，也不满足红队 review 门槛。',
    optimize: '重点提升可执行环境覆盖、最小复现质量和可信标签比例，而不是放宽 confirmed 判定。'
  },
  'CVE 去重': {
    input: '候选根因、项目版本、NVD/GHSA/公告和人工 adjudication',
    output: 'CVE tier/status、已知漏洞关闭或动态验收候选',
    source: 'docs/cve-candidates.md · cve-adjudication.json · cve-handoff.json',
    checks: ['按根因和受影响版本判断，不只匹配标题相似度。', '无法核实的 CVE 编号保持 unverified。', '重复关闭与进入动态验收都保留来源和人工优先级。'],
    failure: '外部来源缺失或版本关系不明时不编造编号，不把未去重候选当作新漏洞。',
    optimize: '检查来源新鲜度、版本区间和误去重风险，确保知识库更新不会覆盖人工结论。'
  },
  '红队 lab': {
    input: 'finding、绑定 source hash 的 scenario、victim image 和随机 flag',
    output: '内部网络中的真实攻击轨迹、工具输出和 flag 捕获事件',
    source: 'scripts/redteam/build_lab.py · lab.py · agent.py',
    checks: ['attacker 无宿主、flag 和 Docker socket 访问。', 'flag 只能来自真实工具输出，最终回答和宿主路径不算证据。', '当前只支持 HTTP 执行契约，其他形态必须 blocked。'],
    failure: '无 lab、scenario 失效或 mode 不支持时 fail-closed；拿不到 flag 不进入 review。',
    optimize: '新增协议时实现真实执行器和安全边界，不能用 HTTP 包装冒充 stdio/cli 支持。'
  },
  'Judge / 验收': {
    input: '完整 trace、flag provenance、目标 finding 和图文报告',
    output: '固定 schema judge.json 与人工 review 资格',
    source: 'scripts/redteam/judge.py · scripts/workflow/build_state.py',
    checks: ['judge 独立于 attacker，轨迹内容只作为不可信数据。', '程序在审核前后和 review 构建时重复校验 provenance。', 'flag + approved + 图文报告三者缺一不可。'],
    failure: '缺字段、字符串布尔、哈希不一致或证据不足均拒绝，旧 judge 文件不能绕过。',
    optimize: '重点检查提示注入鲁棒性、确定性证据校验和人工展示完整性，不降低门禁换取通过率。'
  },
  '状态编译器': {
    input: 'Finding Ledger、verify/CVE 产物、人工状态和红队结果',
    output: 'auto-state.json、可信 review 集合和路由原因',
    source: 'scripts/workflow/build_state.py',
    checks: ['自动状态不覆盖人工状态。', 'review 重算确定性 flag provenance。', '每条路由保留来源、证据和产物路径。'],
    failure: '证据不合法或引用无法唯一解析时跳过，不继承给相似 finding。',
    optimize: '修改优先级或门禁时同步 UI 合并顺序、回归测试和架构说明。'
  },
  '精炼 worker': {
    input: '最新台账、证据 patch、source hash 和人工优先级',
    output: 'refine-state/queue 与 rsi/trajectories/refine.jsonl',
    source: 'scripts/workflow/refine_worker.py',
    checks: ['每条决策可回放并携带策略版本。', '新证据可唤醒归档，低分归档不删除原报告。', '批处理与 lock 控制资源消耗和并发。'],
    failure: '异常或暂停不伪造完成；空队列后的持续监听是新数据自动推进的关键。',
    optimize: '先看路由是否执行及生效，再看评分策略；同时检查队列统计与 UI 当前台账是否一致。'
  },
  'Red-team runner': {
    input: '受限 attacker 工具、victim 地址、目标 finding 和 scenario',
    output: 'agent.jsonl、trace.jsonl、工具输出哈希和捕获结果',
    source: 'scripts/redteam/agent.py · contracts.py',
    checks: ['模型只能使用声明的受限工具。', 'flag 捕获与最终文本分离，来源可重算。', 'trace 是证据输入，同时也是不可信内容。'],
    failure: '工具失败、超时或未捕获都保留真实结果，不生成替代性成功叙述。',
    optimize: '增强协议能力时同步工具权限、网络隔离、trace 合同和 judge 校验。'
  },
  '真实轨迹': {
    input: 'Finding Ledger、refine/verify 产物、真实 stream-json 与红队 run/step 事件',
    output: '带 occurrence/semantic 身份、pre-action context、动作、倾向、成本、结果与血缘的经验池',
    source: 'audit_rsi/experience.py · adapters/raw_trace.py · adapters/redteam.py',
    checks: ['只从真实动作与工具事件构建经验，不从最终报告反推探索路径。', '保留 Task/Agent 拓扑、实际成本与证据等级，未知 propensity 保持 null。', '红队 run 结果与 step 工具事件分开记录，不复制 flag 或原始攻击输出。'],
    failure: '篡改轨迹、not_captured 和未复核结果保持 unknown；缺失动作的记录不会凭空进入动作训练。',
    optimize: '先检查轨迹血缘、身份和动作前特征是否完整，再增加样本；不要用报告文本补造行动历史。'
  },
  '可信标签': {
    input: '经验池、分层抽样计划、runtime/judge/manual 审核结论与 label propensity',
    output: '合并后的 verification-experience-labeled.jsonl 和可审计标签覆盖',
    source: 'audit_rsi/labeling.py · verification.py: merge_labels',
    checks: ['trusted 只包括 runtime、judge、manual；static 标签不能冒充这三类证据。', 'agent-static 必须保留 evidence_class=static 与 adjudication.method=agent-static。', 'unknown 不等于 FP，标签合并不能改变 occurrence/semantic 身份和动作倾向。'],
    failure: '缺失或非法 label propensity 的样本不进入可信效用训练；只有 static 时 trusted_support 仍为 0。',
    optimize: '优先补齐完全缺少 trusted 的项目和动作覆盖，不用放宽证据等级来提高支持度。'
  },
  '效用学习': {
    input: '去重后的训练语义、动作前特征、已知结果、实际成本与合法标注倾向',
    output: 'verification-policy.json：五个动作各自的 ridge 效用权重与支持度统计',
    source: 'audit_rsi/verification.py: train_policy / _solve_ridge',
    checks: ['ACTIONS 固定为 verify、deep_read、human_review、duplicate_candidate、defer。', '每个动作分别回归 realized utility，奖励扣除 agent/token/review 等成本。', '按 evidence class 和 bounded propensity 加权，不模仿最终报告或历史动作频率。'],
    failure: '没有已知效用目标时 training.status=insufficient；static-only 可训练但不构成 trusted 生产证据。',
    optimize: '检查各动作支持度、trusted_support、目标分布和成本口径，不用单一总分掩盖动作覆盖空洞。'
  },
  'Holdout + Flips 评估': {
    input: '独立项目 holdout、候选与 baseline 真实经验池、训练策略和统计门禁配置',
    output: 'matched-action replay、per-semantic outcome flips、accepted/insufficient/rejected 评估',
    source: 'audit_rsi/verification.py: replay_policies / outcome_flip_report · evaluation.py · release.py',
    checks: ['replay 只比较策略与日志动作相同时的 realized utility，明确不是 causal OPE。', 'flips 只观测两个真实经验池的 F→P/P→F 与稳定项，不构造反事实。', '候选默认要求 paired_coverage≥0.8、至少一个 F→P 且零 P→F，发布还需 accepted statistical gate。'],
    failure: '项目、标签覆盖或支持不足为 insufficient；出现 P→F 回归为 rejected，均不能生产 promote。',
    optimize: '先检查 holdout 隔离、配对覆盖与 worst slice，再比较效用；不能把不同 run 差异解释为因果提升。'
  },
  'Shadow 建议': {
    input: '经验池、训练策略、baseline 和 trusted_support / training.status',
    output: 'recommendation-only 的 verification-shadow.json，逐条保留 baseline/candidate、分数和原因',
    source: 'audit_rsi/verification.py: shadow_payload',
    checks: ['所有建议都是 recommendation_only=true 且 state_change=none。', 'trusted_support=0 时继续 shadow，状态为 static-only，原因是 no_trusted_utility_targets。', '训练不足时回退 baseline；即使 static-only 产生不同建议，也不代表已验证提升。'],
    failure: '无 trusted support 不生产 promote，不切换自动路由，也不宣称生产 RSI。',
    optimize: '先补独立 trusted 标签与评估证据，再比较建议质量；不要通过隐藏 static-only 状态制造就绪假象。'
  },
  '受控执行回流': {
    input: 'accepted 评估、不可变候选、产物哈希、发布复核和既有受控执行流程',
    output: '经复核的策略版本，以及执行后产生的新真实轨迹和下一轮经验',
    source: 'audit_rsi/release.py · rsi_version/store.py',
    checks: ['只有 gate 与 evaluation 均 accepted 且无回归，候选才具备 promote 条件。', '发布复核重算候选完整性和 gate；shadow 建议自身不会调用执行或修改状态。', '回流数据必须来自受控执行后的真实结果，不能拿 replay 预测冒充新经验。'],
    failure: '门禁不足、身份或哈希不一致均拒绝发布；当前 static-only/shadow 停在学习支路，不进入生产执行。',
    optimize: '保持候选不可变、执行边界和轨迹血缘可审计；新增自动化前必须先实现明确的人工发布与控制点。'
  },
  '弱点聚类': {
    input: '红队 run 级经验、step 级非零返回码、失败分类、项目类型与成本',
    output: '按支持度排序的 deterministic weakness groups、平均成本和候选 editable surface',
    source: 'audit_rsi/weakness.py → rsi/redteam-weakness.json',
    checks: ['按项目类型、攻击模型、失败类别、严重度和 surface 确定性聚类。', '区分 model_timeout、lab_unhealthy、not_captured、工具失败与结构化输出失败。', '只输出 candidate_only 证据包，mutation=none，不作因果归因。'],
    failure: '没有失败分组时为 insufficient；unknown 或 not_captured 不会被转换成可信漏洞奖励。',
    optimize: '检查 occurrence 与 event 支持度是否混淆、失败分类是否准确，以及聚类是否指向真实可改进表面。'
  },
  'Harness 候选': {
    input: '非变更型 weakness report、白名单 editable surface 和配对 outcome flips',
    output: '稳定 candidate_id 的 proposal-only 候选及 validated/insufficient/rejected 验证结果',
    source: 'audit_rsi/harness.py → rsi/harness-candidates.json · harness-validated.json',
    checks: ['proposal 只能指向 ALLOWED_SURFACES，保留所有无关行为并记录证据哈希。', 'harness-validate 重算候选身份并应用 paired outcome flip gate。', '全程 mutation=none，不自动修改 harness；validated 仍需后续候选与发布复核。'],
    failure: '非白名单 surface、身份篡改、覆盖不足或 P→F 回归均不能通过验证。',
    optimize: '先提高配对证据和失败复现质量，再评估提案；不能把生成提案当成已经修复 harness。'
  },
  '视觉报告': {
    input: '审计报告、结构/覆盖/攻击模型和红队步骤',
    output: 'SVG、scene.webp、report-illustrated.md 和项目地图',
    source: '.claude/skills/project-cartographer',
    checks: ['结构树与攻击路径来自结构化模型。', 'AI 插图明确标注非漏洞证据。', '视觉素材服务于人工理解，不能替代 trace/judge。'],
    failure: '图片生成失败保留 SVG 和文本报告，不阻塞安全结论，也不伪造验收素材。',
    optimize: '优化信息层级和可读性时保持数据血缘，避免视觉叙事超出实际证据。'
  }
};

const GUIDE_ALIASES = {
  'Finding Ledger': '报告与台账',
  '持久化恢复': 'Deadline 与恢复',
  'Lab builder': '红队 lab',
  'Independent judge': 'Judge / 验收'
};

function ArchitectureDetail({ node, onBack }) {
  const Icon = node.icon;
  const guide = DETAIL_GUIDES[GUIDE_ALIASES[node.title] || node.title];
  return (
    <section className="arch-detail" aria-labelledby="arch-detail-title">
      <button type="button" className="arch-detail-back" onClick={onBack}>
        <ArrowLeft size={15} aria-hidden="true" /> 返回架构总览
      </button>
      <header className="arch-detail-hero">
        <div className={cx('arch-detail-icon', `tone-${node.tone || 'ink'}`)}><Icon size={24} aria-hidden="true" /></div>
        <div>
          <span className="arch-detail-group">{node.group} {node.code ? `/ ${node.code}` : ''}</span>
          <h2 id="arch-detail-title">{node.title}</h2>
          <p>{node.body}</p>
        </div>
      </header>
      <div className="arch-detail-io">
        <article><span>输入</span><strong>{guide.input}</strong></article>
        <article><span>输出</span><strong>{guide.output}</strong></article>
      </div>
      <div className="arch-detail-grid">
        <article className="arch-detail-card">
          <span className="arch-detail-label">设计与契约</span>
          <ul>{guide.checks.map((item) => <li key={item}>{item}</li>)}</ul>
        </article>
        <article className="arch-detail-card">
          <span className="arch-detail-label">实现入口与产物</span>
          <code>{guide.source}</code>
          <code>{node.artifact || node.code}</code>
          {guide.command ? <pre className="arch-detail-command">{guide.command}</pre> : null}
        </article>
        <article className="arch-detail-card">
          <span className="arch-detail-label">失败语义</span>
          <p>{guide.failure}</p>
        </article>
        <article className="arch-detail-card is-optimization">
          <span className="arch-detail-label">优化时重点检查</span>
          <p>{guide.optimize}</p>
        </article>
      </div>
    </section>
  );
}

function Stage({ stage, onSelect }) {
  const Icon = stage.icon;
  return (
    <button
      type="button"
      className={cx('arch-stage', `tone-${stage.tone}`)}
      onClick={onSelect}
      aria-label={`查看${stage.title}的实现细节`}
    >
      <div className="arch-stage-top">
        <span className="arch-stage-code">{stage.code}</span>
        <Icon size={20} aria-hidden="true" />
      </div>
      <h3>{stage.title}</h3>
      <p>{STAGE_SUMMARIES[stage.title]}</p>
      <span className="arch-stage-cta">查看实现细节 <ArrowRight size={13} aria-hidden="true" /></span>
    </button>
  );
}

function ComponentCard({ component, onSelect }) {
  const Icon = component.icon;
  return (
    <button type="button" className="arch-component" onClick={onSelect} aria-label={`查看${component.title}的实现细节`}>
      <Icon size={20} aria-hidden="true" />
      <div>
        <h3>{component.title}</h3>
        <p>{COMPONENT_SUMMARIES[component.title]}</p>
        <span className="arch-stage-cta">查看实现细节 <ArrowRight size={13} aria-hidden="true" /></span>
      </div>
    </button>
  );
}

function RsiLearningLoop({ zone, onSelect }) {
  const renderStage = (stage, index, direction) => (
    <div className="arch-rsi-step" key={stage.code}>
      <Stage stage={stage} onSelect={() => onSelect({ ...stage, group: zone.title })} />
      {index < 2 ? direction === 'right'
        ? <ArrowRight size={24} aria-hidden="true" />
        : <ArrowLeft size={24} aria-hidden="true" /> : null}
    </div>
  );
  return (
    <>
      <section className="arch-rsi-why" aria-labelledby="arch-rsi-why-title">
        <div>
          <span className="arch-detail-group">WHY THIS CAN LEARN</span>
          <h3 id="arch-rsi-why-title">为什么能形成 RSI 学习闭环</h3>
          <p>每次验证都留下可学习的经验：动作前看到什么、做了什么、结果是否可信、花费多少。模型学习的是验证动作的效用，独立评估决定建议能否受控回流，而不是让模型直接改写自己。</p>
        </div>
        <aside className="arch-rsi-boundary" aria-label="当前 RSI 边界">
          <strong>当前：shadow 学习，不是生产 RSI</strong>
          <span><code>trusted_support=0</code> → 继续 static-only shadow</span>
          <span>Replay → matched-action 观测，非因果</span>
          <span>Harness → 只产候选，不自动修改</span>
        </aside>
      </section>

      <section className="arch-rsi-flywheel" aria-labelledby="arch-rsi-flywheel-title">
        <header className="arch-rsi-section-head">
          <div>
            <span className="arch-detail-group">PRIMARY LOOP / 01—06</span>
            <h3 id="arch-rsi-flywheel-title">验证策略飞轮</h3>
          </div>
          <p>沿箭头从真实经验到受控回流；点击任一步查看实现契约。</p>
        </header>
        <div className="arch-rsi-loop" role="group" aria-label="六步 RSI 学习飞轮，按 01 到 06 执行，再回流到 01">
          <div className="arch-rsi-loop-row">
            {zone.stages.slice(0, 3).map((stage, index) => renderStage(stage, index, 'right'))}
          </div>
          <div className="arch-rsi-loop-links" aria-hidden="true">
            <span><ArrowUp size={20} /> 06 的真实结果回流到 01</span>
            <span>04 通过评估才进入建议 <ArrowDown size={20} /></span>
          </div>
          <div className="arch-rsi-loop-row is-reverse">
            {zone.stages.slice(3).map((stage, index) => renderStage(stage, index, 'left'))}
          </div>
        </div>
      </section>

      <section className="arch-rsi-branch" aria-labelledby="arch-rsi-branch-title">
        <header className="arch-rsi-section-head">
          <div>
            <span className="arch-detail-group">SECONDARY LOOP / RED-TEAM HARNESS</span>
            <h3 id="arch-rsi-branch-title">第二条学习支路：从失败到 Harness 候选</h3>
          </div>
          <p>主飞轮优化验证动作；这条支路定位执行器自身的失败模式。</p>
        </header>
        <div className="arch-rsi-branch-track" role="group" aria-label="红队轨迹经过弱点聚类形成 Harness 候选，再接受独立回放与发布复核">
          <div className="arch-rsi-branch-endpoint">
            <Bot size={23} aria-hidden="true" />
            <div><strong>红队真实轨迹</strong><span>失败类别 · 工具事件 · 成本</span></div>
          </div>
          <ArrowRight size={23} aria-hidden="true" />
          {zone.components.map((component, index) => (
            <div className="arch-rsi-branch-node" key={component.title}>
              <ComponentCard component={component} onSelect={() => onSelect({ ...component, group: zone.title })} />
              {index === 0 ? <ArrowRight size={23} aria-hidden="true" /> : null}
            </div>
          ))}
          <ArrowRight size={23} aria-hidden="true" />
          <div className="arch-rsi-branch-endpoint is-gate">
            <ShieldCheck size={23} aria-hidden="true" />
            <div><strong>独立回放 + Flips</strong><span>候选复核后受控回流，mutation=none</span></div>
          </div>
        </div>
      </section>
    </>
  );
}

function ArchitectureZone({ zone, onBack, onSelect }) {
  return (
    <section className="arch-zone" aria-labelledby="arch-zone-title">
      <button type="button" className="arch-detail-back" onClick={onBack}>
        <ArrowLeft size={15} aria-hidden="true" /> 返回整体架构
      </button>
      <header className="arch-zone-hero">
        <img src={zone.image} alt="" aria-hidden="true" />
        <div>
          <span className="arch-detail-group">中层架构 / {zone.id}</span>
          <h2 id="arch-zone-title">{zone.title}</h2>
          <p>{zone.description}</p>
          <span className="arch-zone-hint">选择阶段或组件，继续查看实现细节</span>
        </div>
      </header>
      {zone.id === 'learning' ? <RsiLearningLoop zone={zone} onSelect={onSelect} /> : (
        <>
          {zone.stages.length ? (
            <div className="arch-zone-stages" aria-label={`${zone.title}阶段`}>
              {zone.stages.map((stage) => (
                <div className="arch-stage-wrap" key={stage.code}>
                  <Stage stage={stage} onSelect={() => onSelect({ ...stage, group: zone.title })} />
                </div>
              ))}
            </div>
          ) : null}
          {zone.components.length ? (
            <div className="arch-component-list arch-zone-components" aria-label={`${zone.title}组件`}>
              {zone.components.map((component) => (
                <ComponentCard key={component.title} component={component} onSelect={() => onSelect({ ...component, group: zone.title })} />
              ))}
            </div>
          ) : null}
        </>
      )}
      <p className="arch-visual-note">AI 漫画插图用于辅助理解；准确结构以这些可点击节点和实现详情为准。</p>
    </section>
  );
}

export default function ArchitectureView() {
  const [zone, setZone] = useState(null);
  const [selected, setSelected] = useState(null);
  if (selected) {
    return <div className="arch-view"><ArchitectureDetail node={selected} onBack={() => setSelected(null)} /></div>;
  }
  if (zone) {
    return <div className="arch-view"><ArchitectureZone zone={zone} onBack={() => setZone(null)} onSelect={setSelected} /></div>;
  }
  return (
    <div className="arch-view">
      <section className="arch-overview" aria-labelledby="arch-overview-title">
        <header className="arch-overview-hero">
          <img src="/architecture/overview.webp" alt="" aria-hidden="true" />
          <div className="arch-overview-copy">
            <span>MYGOLDMINE / SYSTEM MAP</span>
            <h2 id="arch-overview-title">从一座矿，到一份可信证据</h2>
            <p>选择一个区域，逐层了解系统如何工作。</p>
          </div>
        </header>
        <div className="arch-zone-grid" aria-label="整体架构区域">
          {ZONES.map((item) => {
            const Icon = item.icon;
            return (
              <button
                type="button"
                className={cx('arch-zone-card', `tone-${item.tone}`)}
                key={item.id}
                onClick={() => setZone(item)}
                aria-label={`进入${item.title}中层架构`}
              >
                <img src={item.image} alt="" aria-hidden="true" />
                <span className="arch-zone-card-body">
                  <span className="arch-zone-card-icon"><Icon size={20} aria-hidden="true" /></span>
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.subtitle}</small>
                  </span>
                  <ArrowRight size={18} aria-hidden="true" />
                </span>
              </button>
            );
          })}
        </div>
        <p className="arch-visual-note">漫画由 AI 生成，仅用于叙事；点击节点看到的层级与实现细节才是系统契约。</p>
      </section>
    </div>
  );
}
