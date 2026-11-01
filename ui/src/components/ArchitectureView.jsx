import { useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
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
    body: '目标源码只读挂载到 /target，再复制到可写工作区；容器不挂 Docker socket，并移除 capabilities。',
    artifact: 'mine_one_docker.sh → entrypoint.sh'
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
    icon: ScanSearch,
    title: 'Verification-RSI',
    body: '学习验证动作的效用而非模仿历史；trusted 标签、holdout 和统计门禁不足时只允许 shadow。',
    code: 'audit_rsi/verification.py · evaluation.py · release.py'
  },
  {
    icon: Sparkles,
    title: '视觉报告',
    body: '结构树、覆盖树、攻击路径、attacker/victim 步骤和叙事插图；插图不充当漏洞证据。',
    code: '.claude/skills/project-cartographer'
  }
];

const STAGE_SUMMARIES = {
  '目标与调度': '选目标、控并发、可续跑',
  '隔离工作副本': '只读源码，隔离执行',
  '召回与协同审计': '先广召回，再分任务审计',
  '增量报告与质量门': '边审计边落盘，过质量门',
  'Deadline 与恢复': '统一预算，复用成果续跑',
  '发布到下游': '完整报告才进入流水线',
  '报告与台账': '给每次发现建立稳定身份',
  '自动精炼': '去重、评分、归档与分诊',
  '验证 / 复现': '用最小 harness 验证候选',
  'CVE 去重': '确认是否已知与受影响',
  '红队 lab': '隔离环境捕获真实 flag',
  'Judge / 验收': '独立审核后才交给人工'
};

const COMPONENT_SUMMARIES = {
  'Finding Ledger': '跨 run 的发现身份与历史',
  '状态编译器': '把证据编译为流程状态',
  '精炼 worker': '持续执行自动路由',
  '持久化恢复': '复用成果，恢复中断',
  'Lab builder': '构建与校验隔离场景',
  'Red-team runner': '执行受限攻击并留痕',
  'Independent judge': '独立审核证据与作弊',
  'Verification-RSI': '从可信标签学习验证策略',
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
    subtitle: '数据、状态、路由与恢复',
    description: '支撑整条流水线的台账、状态编译、精炼 worker 和持久化恢复。',
    image: '/architecture/components.webp',
    icon: Layers3,
    tone: 'ink',
    stages: [],
    components: COMPONENTS.filter((item) => ['Finding Ledger', '状态编译器', '精炼 worker', '持久化恢复'].includes(item.title))
  },
  {
    id: 'learning',
    title: '学习与视觉',
    subtitle: '让经验可学习，让证据易理解',
    description: 'Verification-RSI 的严格发布门，以及服务人类理解的视觉报告。',
    image: '/architecture/learning.webp',
    icon: Sparkles,
    tone: 'violet',
    stages: [],
    components: COMPONENTS.filter((item) => ['Verification-RSI', '视觉报告'].includes(item.title))
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
    input: '只读目标目录、审计镜像、空 run 目录和模型凭据',
    output: '/workspace/repo 可写副本、隔离审计进程、宿主持久化产物',
    source: 'scripts/mine/mine_one_docker.sh · entrypoint.sh',
    checks: ['/target 只读挂载，模型只能修改工作副本。', '不挂 Docker socket，cap-drop ALL + no-new-privileges。', '密钥只经环境传递，run-meta 写入前做泄漏扫描。'],
    failure: '缺镜像、缺鉴权、目标不存在或 run 非空时，在模型执行前明确失败。',
    optimize: '调整挂载、网络或权限时，先确认最小权限边界没有被便利性的宿主访问打破。'
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
    failure: 'lock 防止双实例；队列暂时清空后仍需能发现新数据，不能把一次性退出当作常驻成功。',
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
  'Verification-RSI': {
    input: '动作前上下文、真实轨迹、trusted labels、成本和验证结果',
    output: '效用策略、holdout 回放、统计门禁、shadow 或不可变候选',
    source: 'audit_rsi/verification.py · evaluation.py · release.py',
    checks: ['学习验证动作效用，不模仿最终报告。', 'static 标签不能冒充 human/runtime/judge 真值。', '支持不足只输出 shadow，不宣称因果 uplift。'],
    failure: '无 trusted support、holdout 或统计显著性时拒绝生产发布。',
    optimize: '优先补独立 trusted 标签与覆盖，再评估模型；不要通过放松门禁制造提升。'
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
