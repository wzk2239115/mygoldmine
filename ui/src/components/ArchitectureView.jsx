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
  Radar,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Workflow
} from 'lucide-react';
import { cx } from '../utils.js';
import AgenticPipeline from './AgenticPipeline.jsx';

const MINING_STAGES = [
  {
    code: '01',
    title: '选择项目并批量审计',
    icon: GitBranch,
    tone: 'ink',
    body: '看板左侧加号支持导入公开 GitHub 仓库或服务器本地目录；GitHub 地址校验通过后分页列出分支，每页只读取 10 个分支的提交对象并可继续加载，分别标记默认分支和本页最新分支；本地目录可通过服务器目录选择器逐层浏览并选择。登记项目后调用 run.sh 启动完整审计。批量模式从项目清单 targets/manifest.json 读取目标，parallel_mine.sh 控制同时运行的项目数和失败重试；overnight.sh 用于后台启动、查看进度、停止和恢复未完成项目。每个项目的日志与报告保存在独立目录中。',
    artifact: 'targets/manifest.json → runs/<project>/<run>/'
  },
  {
    code: '02',
    title: '隔离工作副本',
    icon: Boxes,
    tone: 'blue',
    body: '第 0 阶段默认直接启动 environment-builder 智能体，由它检查源码、选择构建方式、调用确定性工具、修复并验收环境；智能体没有产出可用环境时才执行备用方案。随后每次审计运行（run）使用独立持久沙箱，复用同一工作副本。',
    artifact: 'environment-builder → env-manifest.json → sandbox.sh → /workspace/repo'
  },
  {
    code: '03',
    title: '整理审计线索并拆分任务',
    icon: Bot,
    tone: 'violet',
    body: 'Jev 先给代码块打分，帮助决定优先检查哪里；这些分数和风险标记只是线索，不会直接记为候选问题。security-orchestrator 再结合项目结构、知识库和攻击面，把后续检查拆成具体任务。',
    artifact: 'triage/jev-*.json · raw.jsonl'
  },
  {
    code: '04',
    title: '持续更新报告与完整性检查',
    icon: FileCode2,
    tone: 'amber',
    body: '审计开始即创建报告骨架，子任务完成就增量保存；数据结构、必填字段和系统语言全部通过检查才算完整。',
    artifact: 'audit-report.{md,json} · reports_complete'
  },
  {
    code: '05',
    title: '时限与恢复',
    icon: Database,
    tone: 'hot',
    body: '所有尝试共享实际运行时间，按真实事件判断是否仍在推进；等待中的工具调用不算空闲，校验和匹配才复用成果。失败分支不阻塞汇总。',
    artifact: 'progress_guard.py · durable_recovery.py'
  },
  {
    code: '06',
    title: '发布到下游',
    icon: ShieldCheck,
    tone: 'green',
    body: '完整有效报告进入后续验证；红队直接读取本轮已校验报告及其摘要，不依赖只收录已结束运行的发现记录表。蓝队和红队全部受阻时记录受阻，部分受阻时记录降级，整次运行不会汇总为成功。',
    artifact: '发现记录表 → 第四阶段验证 → 自动分类'
  }
];

const STAGES = [
  {
    code: '01',
    title: '报告与发现记录表',
    icon: FileCode2,
    tone: 'ink',
    body: '只接收完整有效的审计报告；每次发现的候选问题都有单独编号，多轮审计中的同一问题会归并，草稿不会覆盖历史。',
    artifact: 'runs/*/*/audit-report.json → finding-ledger.json'
  },
  {
    code: '02',
    title: '自动分类',
    icon: ScanSearch,
    tone: 'blue',
    body: '后台任务负责评分、去重和证据完整性检查。低价值项归档，不等同于安全；高价值项进入分诊，随后由自动流转后台任务处理。',
    artifact: 'auto-state.json · refine-state.json · refine-queue.json · flow-state.json'
  },
  {
    code: '03',
    title: '验证 / 待验证',
    icon: ShieldCheck,
    tone: 'amber',
    body: '自动流转后台任务按候选问题（finding）调用验证智能体，生成最小验证程序（harness）；已确认的候选转入待验证，已排除的候选关闭，受阻或结果不确定时保留尝试记录。',
    artifact: 'verify/flow/.../verify-report.json · flow-queue.json'
  },
  {
    code: '04',
    title: 'CVE 去重',
    icon: GitBranch,
    tone: 'hot',
    body: '查询 NVD、GHSA 和项目公告，判断是否已被覆盖；重复项关闭，候选进入动态验收。',
    artifact: 'docs/cve-*.json · curated/state'
  },
  {
    code: '05',
    title: '在隔离环境验证漏洞',
    icon: Bot,
    tone: 'violet',
    body: '为每个候选问题单独创建目标容器和攻击容器。攻击容器只能通过内部网络访问目标服务；从工具输出中拿到目标容器里的随机标记（flag）后，才进入独立审核。目前只支持 HTTP 服务场景。',
    artifact: 'labs/<project>/<finding-id>/scenario.json · runs/redteam/*'
  },
  {
    code: '06',
    title: '独立审核与验收',
    icon: BadgeCheck,
    tone: 'green',
    body: '独立模型审核轨迹：是否命中目标漏洞、随机标记是否来自目标容器、是否作弊、是否可复现。',
    artifact: 'judge.json · report-illustrated.md · scene.webp'
  }
];

const COMPONENTS = [
  {
    icon: Layers3,
    title: '发现记录表',
    body: '扫描所有完整有效的审计报告，为每次发现的候选问题保留单独编号，并归并多轮审计中的同一问题；编号相同但含义不同的问题不共用状态，历史报告中独有的问题也会保留。',
    code: 'scripts/workflow/finding_ledger.py'
  },
  {
    icon: Braces,
    title: '状态编译器',
    body: '基于发现记录表合并验证结果、CVE 和人工状态，再次重算红队证据来源链与待人工验收条件。',
    code: 'scripts/workflow/build_state.py'
  },
  {
    icon: Workflow,
    title: '自动分类后台任务',
    body: '按来源内容哈希重算路由；已确认的结果可让归档项重新进入队列，高危弱指纹只进入重复候选而不直接归档。',
    code: 'scripts/workflow/refine_worker.py'
  },
  {
    icon: Workflow,
    title: '自动流转后台任务',
    body: '处理分诊和待验证候选：调用第四阶段验证智能体、补图文报告、触发第五阶段红队验证；只写真实报告结果，失败时保留受阻或结果不确定状态。',
    code: 'scripts/workflow/flow_worker.py'
  },
  {
    icon: Radar,
    title: '持续监控派发',
    body: '轮询仓库提交并按项目、分支、提交绑定身份；高风险事件自动派发到深度审计，同一提交不重复开挖。',
    code: 'scripts/watch/watch.py · daemon.sh'
  },
  {
    icon: Database,
    title: '持久化恢复',
    body: '所有尝试共享实际运行时间，根据环境准备、模型和工具的真实事件区分推进与空闲；每次尝试的成果保存后，恢复时继续完成第四阶段验证。',
    code: 'scripts/mine/durable_recovery.py'
  },
  {
    icon: Boxes,
    title: '隔离场景构建器',
    body: '按候选问题和来源绑定验证场景并校验执行约定；当前只有 HTTP 隔离场景能进入运行阶段。',
    code: '.claude/skills/redteam-lab-builder'
  },
  {
    icon: Network,
    title: '隔离环境攻击执行器',
    body: '攻击端在受限容器执行工具；随机标记只能来自真实工具输出，最终回答和宿主路径不算证据。',
    code: 'scripts/redteam/agent.py'
  },
  {
    icon: ShieldCheck,
    title: '独立审核器',
    body: '同时校验完整固定的数据结构和确定性的证据来源链，缺字段、字符串布尔或哈希不一致都拒绝。',
    code: 'scripts/redteam/judge.py'
  },
  {
    icon: Sparkles,
    title: '视觉报告',
    body: '展示结构树、覆盖树、攻击路径、攻击端与目标端步骤和叙事插图；插图不充当漏洞证据。',
    code: '.claude/skills/project-cartographer'
  }
];

const RSI_STAGES = [
  {
    code: '01',
    title: '真实轨迹',
    icon: Workflow,
    tone: 'blue',
    body: '把真实验证与红队行动整理成带身份、动作前上下文、成本和证据来源链的经验，不从最终报告反推探索过程。',
    artifact: 'rsi/verification-experience.jsonl · redteam-experience.jsonl'
  },
  {
    code: '02',
    title: '可信标签',
    icon: BadgeCheck,
    tone: 'green',
    body: '把实际运行、独立审核和人工结论作为高等级答案；静态分析只辅助学习，不知道就保留未知。',
    artifact: 'rsi/verification-label-plan.jsonl → labeled.jsonl'
  },
  {
    code: '03',
    title: '成本与收益评估',
    icon: Sparkles,
    tone: 'violet',
    body: '固定五动作词表；当前只有深入阅读和暂缓处理两个动作有样本，比较收益与成本，而不是模仿历史报告。',
    artifact: 'verify / deep_read / human_review / duplicate_candidate / defer'
  },
  {
    code: '04',
    title: '跨项目验证与前后结果对比',
    icon: ScanSearch,
    tone: 'amber',
    body: '使用未参与训练的项目检验效果，逐项检查修好了什么、改坏了什么；回放不等于因果证明。',
    artifact: 'verification-replay.json · verification-flips.json · 统计通过条件'
  },
  {
    code: '05',
    title: '只读建议（shadow）',
    icon: Bot,
    tone: 'violet',
    body: '只给建议，不改流程。可用于动作训练的可信样本（trusted）为 0 时仍然只读，不能进入生产。',
    artifact: 'ui/data/verification-shadow.json'
  },
  {
    code: '06',
    title: '挖掘修复发布',
    icon: ShieldCheck,
    tone: 'green',
    body: '智能体学习节点组合多个技能生成修复文档，再在独立上下文实际重跑挖掘与红蓝验证；接受项才写入加载目录并保留回滚。只读验证策略不会借此自动发布。',
    artifact: '.claude/skills/rsi-shared-experience · knowledge/project-rules'
  }
];

const RSI_BRANCH_COMPONENTS = [
  {
    icon: ScanSearch,
    title: '找出反复出现的执行失败',
    tone: 'hot',
    body: '红队验证失败后，系统会把相同类型的失败放在一起，统计出现次数和成本，帮助判断执行器的哪个环节最值得优先检查。',
    code: 'audit_rsi/weakness.py → rsi/redteam-weakness.json'
  },
  {
    icon: FileCode2,
    title: '验证程序候选',
    tone: 'amber',
    body: '只为白名单允许修改的范围生成带稳定身份的证据提案；经前后结果对比验证后仍需复核，绝不自动修改验证程序。',
    code: 'audit_rsi/harness.py → rsi/harness-candidates.json'
  }
];

const STAGE_SUMMARIES = {
  '选择项目并批量审计': '从项目清单选择目标，批量审计，中断后恢复未完成项目',
  '隔离工作副本': '一个沙箱，持续探索与验证',
  '整理审计线索并拆分任务': '先给代码检查线索排序，再拆分后续审计任务',
  '持续更新报告与完整性检查': '审计中持续保存报告，完成后检查内容和格式是否完整',
  '时限与恢复': '共享实际运行时间，校验后复用成果并继续处理',
  '发布到下游': '完整报告才进入后续处理流程',
  '报告与发现记录表': '给每次发现建立稳定身份',
  '自动分类': '去重、评分、归档与分诊',
  '验证 / 待验证': '用最小验证程序验证候选',
  'CVE 去重': '确认是否已知与受影响',
  '在隔离环境验证漏洞': '在隔离容器中实际验证，并检查随机标记是否来自真实工具输出',
  '独立审核与验收': '独立审核后才交给人工',
  '真实轨迹': '记录动作、上下文、结果与成本',
  '可信标签': '分清可信证据、静态证据与未知结果',
  '成本与收益评估': '比较每种处理方式的成本与收益',
  '跨项目验证与前后结果对比': '在未参与训练的项目上检查效果，逐项比较前后结果',
  '只读建议（shadow）': '只给建议，不改变生产状态',
  '挖掘修复发布': '独立评估后发布共享或仓库专属修复，下一轮挖掘实际加载'
};

const COMPONENT_SUMMARIES = {
  '发现记录表': '记录每次发现，归并多轮审计中的同一问题',
  '状态编译器': '把证据转换为流程状态',
  '自动分类后台任务': '持续执行自动路由',
  '自动流转后台任务': '处理分类结果，推进验证与红队检查',
  '持续监控派发': '绑定分支和提交，自动进入挖掘',
  '持久化恢复': '复用校验过的成果，继续处理中断任务',
  '隔离场景构建器': '构建与校验隔离场景',
  '隔离环境攻击执行器': '执行受限攻击并留痕',
  '独立审核器': '独立审核证据与作弊行为',
  '找出反复出现的执行失败': '统计哪些执行失败反复出现，帮助确定优先检查哪个环节',
  '验证程序候选': '只为白名单范围生成提案，不直接改代码',
  '视觉报告': '把证据变成易懂图文'
};

const ZONES = [
  {
    id: 'mining',
    title: '批量审计',
    subtitle: '从目标源码到可信报告',
    description: '目标调度、隔离副本、协同审计、报告完整性检查和恢复发布。',
    image: '/architecture/mining.webp',
    icon: Boxes,
    tone: 'blue',
    stages: MINING_STAGES,
    components: []
  },
  {
    id: 'pipeline',
    title: '自动分类与验证',
    subtitle: '从原始候选问题到可验证候选',
    description: '发现记录表、自动分类、验证和 CVE 去重如何逐步收敛候选。',
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
    description: '目标端与攻击端、真实随机标记、独立审核和人工验收条件。',
    image: '/architecture/redteam.webp',
    icon: ShieldCheck,
    tone: 'hot',
    stages: STAGES.slice(4),
    components: COMPONENTS.filter((item) => ['隔离场景构建器', '隔离环境攻击执行器', '独立审核器'].includes(item.title))
  },
  {
    id: 'components',
    title: '核心组件',
    subtitle: '数据、状态、路由、恢复与表达',
    description: '支撑整条处理流程的发现记录表、状态编译、自动分类与自动流转后台任务、持续监控派发、持久化恢复和视觉报告。',
    image: '/architecture/components.webp',
    icon: Layers3,
    tone: 'ink',
    stages: [],
    components: COMPONENTS.filter((item) => ['发现记录表', '状态编译器', '自动分类后台任务', '自动流转后台任务', '持续监控派发', '持久化恢复', '视觉报告'].includes(item.title))
  },
  {
    id: 'learning',
    title: 'RSI 学习流程',
    subtitle: '让每次验证成为下一次挖掘的经验',
    description: '验证动作保持只读建议；挖掘修复按共享或仓库专属作用域生成，经独立评估后发布、加载和回滚。',
    image: '/architecture/rsi-flywheel.webp',
    icon: Sparkles,
    tone: 'violet',
    stages: RSI_STAGES,
    components: RSI_BRANCH_COMPONENTS
  }
];

const DETAIL_GUIDES = {
  '选择项目并批量审计': {
    input: '看板导入的公开 GitHub 地址或本地绝对路径、项目清单（targets/manifest.json）、项目源码、模型配置、同时运行的项目数和超时时间',
    output: '登记后的项目与源码版本、每个项目独立的审计目录，以及完成、失败、超时和恢复状态',
    source: 'ui/server/project-import.mjs · run.sh · scripts/mine/parallel_mine.sh · scripts/mine/overnight.sh',
    checks: ['每个项目单独执行，日志和报告写入各自目录，不会互相覆盖。', '公开仓库按所选提交编号下载、检出并核对版本；提交列表通过 GitHub 接口分页读取。', '下载不设固定总时长上限，连续三分钟没有命令输出才停止。', '无有效提交且仅含同源 Git 元数据的未完成目录会备份后重试；完整源码保留。', '导入后调用 run.sh 完整流程，已有实时审计的项目不能重复启动。', '启动早期只有相邻状态目录时也会列入侧栏；主目录出现后同一次运行不会重复统计。', '侧栏删除项目登记、候选问题和审计运行记录，不提供撤销；保留源码，正在审计的项目不能删除。', '节点轨迹转换登记后展示；重复打开复用短期缓存，聚焦节点时提前准备，源日志更新自动同步，等待时可查看原始记录；蓝队默认最多 10 条候选并发，各自保留报告与轨迹，面板可逐项查看；节点显示实际候选数与部分受阻计数，日志份数单列，红队场景构建支持单独重跑，候选间默认最多 10 路并发，逐项显示状态、轨迹和交付；蓝红队先显示队员列表，选中队员后才打开个人轨迹，编号、标题和状态固定显示，可返回列表另选队员；查看交付报告独立于个人轨迹；完整流程等待所有场景构建结束后再执行与审核，单节点重跑完成后停止；不支持单独重跑的节点显示不可用说明；环境智能体正常交付可用沙箱显示已完成，能力范围和限制单独展示，备用方案或必要验收未通过仍显示降级。', '蓝队技能要求先写最小可执行脚本、通过真实入口和负向对照确认；红队技能先核对支持的攻击面，结构性受阻后交付并停止重复提交；当前非 HTTP 执行支持和受阻文件验收契约仍需工具实现。', '审计主会话尚未生成时展示启动日志，区分启动前失败和审计执行失败。', '看板按监督脚本记录的当前阶段显示运行中，后续阶段等待；任务中断后标明中断阶段及后续未执行状态；侧边栏可使用当前源码重新审计，保留历史并拦截重复启动；重新导入时自动使用已有的本地项目图片；打开轨迹时自动恢复本机查看服务；查看缓存写入相邻元数据目录，避免阻止审计启动；设置可选择各阶段模型，仅在新任务启动时生效；红队默认跟随安全审计模型并复用对应服务配置；新任务默认安全审计时限为 24 小时，已有任务保留原时限；红队内部按候选重复构建、执行和审核。', '导入弹窗实时显示排队、源码准备、项目登记、审计启动与命令输出；取消或断开导入连接会停止本次任务并撤回本次登记，已有源码保留。', '已有内容的审计目录不会被覆盖；已经有完整成功报告的项目默认跳过。', '恢复运行时只处理未完成项目；超时和普通失败分别记录。'],
    failure: '来源校验、克隆或启动失败会返回明确错误，已有目录不会被强制更新。批量启动前检查不通过时不会调用模型；项目失败会保留日志和状态，超时不会被当作普通失败自动重试。',
    optimize: '优先检查各项目是否按并发设置执行、中断后的状态是否准确、恢复是否只处理未完成项目，以及新增项目是否能通过项目清单接入。'
  },
  '隔离工作副本': {
    input: '只读目标目录、环境构建技能、确定性构建工具、独立审计运行和审计时的模型凭据',
    output: '智能体检收的环境镜像、可持续进入的项目沙箱、共享 /workspace/repo、离线验证与持久化产物',
    source: 'scripts/env/phase0_env.sh · build_env_agent.sh · .claude/agents/environment-builder.md · sandbox.sh',
    checks: ['默认直接启动 environment-builder 智能体，由它决定检测、构建、修复和验收步骤，确定性脚本不再抢先执行。', '智能体没有产出可用环境时才执行确定性备用方案；env-phase.json 分别记录智能体、备用方案和最终状态。', '每次审计运行使用一个沙箱，审计探索、交互式命令行和验证复用同一工作副本；验证前通过 isolate 命令断开网络。', '沙箱等待源码复制完成并写入就绪标记后才返回；审计入口复用副本，不再重复复制。缺少标记的旧沙箱需用新的运行目录重建。'],
    failure: '智能体不可用或没有可用镜像时保留明确原因并执行备用方案；备用方案也失败则环境受阻，不伪装成就绪。沙箱创建失败时改用一次性容器。',
    optimize: '优先检查智能体是否实际主导构建、是否根据日志灵活修复、镜像是否真实可用，以及工作副本复用和验证断网是否生效。',
    command: `bash scripts/env/phase0_env.sh <source> --meta-dir /tmp/phase0 --agent auto
bash scripts/env/sandbox.sh status --project <project> --run-dir <run>
bash scripts/env/sandbox.sh shell --project <project> --run-dir <run>
bash scripts/env/sandbox.sh isolate --project <project> --run-dir <run>
bash run.sh --verify-only <run>`
  },
  '整理审计线索并拆分任务': {
    input: '项目工作副本、已有知识库、审计计划，以及 Jev 为代码块生成的优先检查分数和风险标记',
    output: '按优先级排列的代码检查线索、项目结构摘要、拆分后的子任务和实际工具调用记录',
    source: 'scripts/mine/mine_one.sh · .claude/agents/security-orchestrator.md',
    checks: ['优先检查分数（priority）是 0 到 1 的优先检查分数，分数越高越先检查；风险信号（flags）是达到阈值的风险类型，例如认证边界、子进程执行或危险反序列化。', '已有防护措施（mitigations）记录路径白名单等防护，会降低优先级；这些信息只用于安排检查，不能直接确认漏洞。', 'security-orchestrator 按项目结构和攻击面拆分任务；raw.jsonl 记录实际工具调用，不能用最终报告反推探索过程。'],
    failure: 'Jev 失败时仍可按项目结构和已有知识继续审计，但会缺少这批初筛线索；模型瞬时错误只在总时限内有限重试。',
    optimize: '重点检查风险类型是否覆盖完整、子任务是否重复、模型名称是否一致和工具记录是否完整，而不是只统计候选问题数量。'
  },
  '持续更新报告与完整性检查': {
    input: '子任务结论、文件和行号证据、根因与修复建议',
    output: 'audit-report.md/json、report-quality.json、reports_complete',
    source: 'scripts/mine/mine_one.sh · check_report.py · report_quality.py',
    checks: ['审计开始即写骨架，子任务完成后增量更新。', '数据结构、必填字段和系统语言全部通过检查才完整。', '报告是静态候选，不能把未验证描述写成运行时事实。'],
    failure: '即使模型退出码为 0，报告质量不合格仍会失败，且不能发布到发现记录表。',
    optimize: '修改报告字段时同步 Python 和 JavaScript 数据约定、质量检查和界面；不要用补文案掩盖缺失证据。'
  },
  '时限与恢复': {
    input: '所有尝试共享的实际运行时间、原始事件、任务产物和历史恢复检查点',
    output: '每次尝试的健康状态、校验过的分支成果、可继续处理的任务与恢复摘要',
    source: 'scripts/mine/progress_guard.py · durable_recovery.py',
    checks: ['所有重试和等待共享同一实际运行时限，不重新计时。', '环境准备、模型和工具调用按真实事件判断是否仍在推进；等待中的工具调用不算空闲。', '只有校验和匹配的成果才会在恢复时复用，来源审计运行的证据保持原样，不被修改。'],
    failure: '实际运行时间耗尽后不再启动新尝试；单分支失败被隔离，不能阻塞其他成果和报告汇总。',
    optimize: '重点检查中断位置、产物校验和、部分失败是否可见，以及恢复后是否真正完成第四阶段验证。'
  },
  '发布到下游': {
    input: '完整有效报告、环境镜像和现有历史发现记录表',
    output: '发现记录表、第四阶段验证、视觉产物、自动状态与自动分类状态',
    source: 'run.sh · scripts/workflow/finding_ledger.py · build_state.py',
    checks: ['只有完整有效报告能替换最新发布状态。', '第四阶段验证与静态审计分离，环境受阻时不伪装成就绪。', '界面必须读取新发现记录表与状态产物，不能只重新构建静态页面。'],
    failure: '报告无效时不执行第四阶段验证；环境缺失、验证受阻或后端未加载新产物都保持明确状态。',
    optimize: '检查发布后的服务重载、后台任务是否存活和新数据是否触发重算，避免产物已推进而页面仍停留在旧流程。'
  },
  '报告与发现记录表': {
    input: '所有审计运行的报告、运行元数据、原始候选问题与历史身份',
    output: '第二版数据结构的发现记录表和各项目最新记录，保留单次观测编号与跨轮同一问题编号',
    source: 'scripts/workflow/finding_ledger.py · ui/server/finding-ledger.mjs',
    checks: ['单次观测身份（occurrence）是每次观测的单独编号，同一问题编号（semantic）用于归并多轮审计中的同一问题。', '历史报告中独有的候选问题会保留，新审计不会让它们消失。', '旧 project:id 只有确认指向同一问题时才继承状态。'],
    failure: '运行中、失败或质量不合格草稿不覆盖最新完整报告；编号含义有歧义时不猜测合并。',
    optimize: '调整问题归并规则时重点检查编号相同但含义不同、多轮审计改变证据路径、历史独有项和状态继承。'
  },
  '自动分类': {
    input: '最新发现记录表、验证和 CVE 证据、人工状态和已有自动分类来源内容哈希',
    output: '分诊、待验证和已归档路由、队列统计和决策轨迹',
    source: 'scripts/workflow/refine_worker.py · refine_worker.sh',
    checks: ['原始内容或证据变化会改变来源内容哈希并触发重算。', '已确认的结果可让归档项重新进入队列，高危弱指纹不直接归档。', '人工状态始终高于自动路由，已归档不代表安全。'],
    failure: '锁文件防止同时运行两个实例；循环模式在空队列时等待并继续扫描，新数据到达后自动处理，暂停和停止保留明确控制语义。',
    optimize: '优先检查后台任务是否存活、空队列后的重新扫描、状态与当前单次观测身份的匹配，再调整评分阈值。'
  },
  '验证 / 待验证': {
    input: '候选问题、对应源码提交、环境镜像和验证时限',
    output: '最小验证程序、已确认、受阻或结果不确定的验证结论和证据分类',
    source: 'scripts/verify/auto_verify.sh · run_verify.sh',
    checks: ['验证对象绑定具体候选问题与源码版本。', '已确认结论必须来自可检查的验证结果，静态成立不等于运行时成立。', '最小验证程序只用于验证，不交付武器化利用代码。'],
    failure: '环境或输入不足时保持受阻或结果不确定，不猜测成功，也不满足红队待人工验收条件。',
    optimize: '重点提升可执行环境覆盖、最小复现质量和可信标签比例，而不是放宽已确认结论的判定。'
  },
  'CVE 去重': {
    input: '候选根因、项目版本、NVD、GHSA、项目公告和人工裁定',
    output: 'CVE 等级和状态、已知漏洞关闭或动态验收候选',
    source: 'docs/cve-candidates.md · cve-adjudication.json · cve-handoff.json',
    checks: ['按根因和受影响版本判断，不只匹配标题相似度。', '无法核实的 CVE 编号保持未核实状态。', '重复关闭与进入动态验收都保留来源和人工优先级。'],
    failure: '外部来源缺失或版本关系不明时不编造编号，不把未去重候选当作新漏洞。',
    optimize: '检查来源新鲜度、版本区间和误去重风险，确保知识库更新不会覆盖人工结论。'
  },
  '在隔离环境验证漏洞': {
    input: '候选问题、与源码版本绑定的验证场景、目标服务镜像和随机标记',
    output: '隔离网络中的实际攻击步骤、工具输出和随机标记捕获记录',
    source: 'scripts/redteam/build_lab.py · lab.py · agent.py',
    checks: ['攻击端只能在攻击容器中执行命令，并通过隔离的内部网络向目标服务发送 HTTP 请求；不能读取宿主机文件、直接读取随机标记文件或操作 Docker。', '目标服务容器单独保存随机标记。只有工具实际返回该标记才算成功；模型在最终回答中写出标记，或报告宿主机上的标记路径，都不算证据。', '目前只执行 HTTP 服务场景。命令行、标准输入输出等其他类型暂不执行，并标记为“暂不支持（blocked）”；不会把它们包装成 HTTP 场景运行。'],
    failure: '没有可用验证环境、场景与源码版本不匹配或类型暂不支持时，不会执行；没有从工具输出中拿到随机标记时，不进入人工验收。',
    optimize: '新增协议时必须实现对应的执行器和隔离限制，不能把命令行或标准输入输出场景包装成 HTTP 来冒充支持。'
  },
  '独立审核与验收': {
    input: '完整执行轨迹、随机标记的证据来源链、目标候选问题和图文报告',
    output: '具有固定数据结构的 judge.json 与待人工验收条件',
    source: 'scripts/redteam/judge.py · scripts/workflow/build_state.py',
    checks: ['独立审核器与攻击端分离，轨迹内容只作为不可信数据。', '程序在审核前后和构建待人工验收条件时重复校验证据来源链。', '随机标记、审核通过和图文报告三者缺一不可。'],
    failure: '缺字段、字符串布尔、哈希不一致或证据不足均拒绝，旧审核文件不能绕过检查。',
    optimize: '重点检查提示注入鲁棒性、确定性证据校验和人工展示完整性，不降低通过条件换取通过率。'
  },
  '状态编译器': {
    input: '发现记录表、验证和 CVE 产物、人工状态和红队结果',
    output: 'auto-state.json、可信的待人工验收集合和路由原因',
    source: 'scripts/workflow/build_state.py',
    checks: ['自动状态不覆盖人工状态。', '构建待人工验收条件时重算确定性的随机标记证据来源链。', '每条路由保留来源、证据和产物路径。'],
    failure: '证据不合法或引用无法唯一解析时跳过，不继承给相似候选问题。',
    optimize: '修改优先级或通过条件时同步界面合并顺序、回归测试和架构说明。'
  },
  '自动分类后台任务': {
    input: '最新发现记录表、证据补丁、来源内容哈希和人工优先级',
    output: 'refine-state/queue 与 rsi/trajectories/refine.jsonl',
    source: 'scripts/workflow/refine_worker.py',
    checks: ['每条决策可回放并携带策略版本。', '新证据可触发已归档项重新评估，低分归档不删除原报告。', '批处理与锁文件控制资源消耗和并发。'],
    failure: '异常或暂停不伪造完成；空队列后的持续监听是新数据自动推进的关键。',
    optimize: '先看路由是否执行及生效，再看评分策略；同时检查队列统计与界面当前发现记录表是否一致。'
  },
  '自动流转后台任务': {
    input: '最新发现记录表、分诊和待验证状态、环境清单、图文报告和验证与红队时限',
    output: 'flow-state.json、flow-queue.json、verify/flow、redteam/flow 和 rsi/trajectories/flow.jsonl',
    source: 'scripts/workflow/flow_worker.py · flow_worker.sh · phase4_verify_agent.sh · phase5_redteam.sh',
    checks: ['只处理分诊和待验证候选，不越过验证、独立审核和人工验收的通过条件。', '已确认、已排除和独立审核通过必须来自真实报告，受阻或结果不确定时保持原状态并记录尝试。', '环境缺失或镜像不存在时只写受阻状态，不伪造产物。'],
    failure: '暂停、超时、环境受阻或达到最大尝试次数时停止推进；人工状态始终优先。',
    optimize: '先检查后台任务心跳、环境清单和失败原因，再调整批大小、超时和重试上限。'
  },
  '持续监控派发': {
    input: 'git 仓库、远端分支和提交、静态差异评分和已有运行记录',
    output: 'watch-state.json、dispatch-state.json、独立工作副本和深度审计运行',
    source: 'scripts/watch/watch.py · daemon.sh',
    checks: ['队列绑定项目、分支、提交和仓库路径。', '同一项目同一提交已有运行或成功报告时标记为复用，不重复开挖。', '派发使用独立工作副本固定提交，不移动用户当前分支。'],
    failure: '仓库不可用、工作副本创建失败或已有派发在运行时保留明确状态，不伪造挖掘结果。',
    optimize: '先检查监控心跳、分支和提交身份以及派发日志，再调整并发与重试上限。'
  },
  '隔离环境攻击执行器': {
    input: '受限攻击端工具、目标端地址、目标候选问题和验证场景',
    output: 'agent.jsonl、trace.jsonl、工具输出哈希和捕获结果',
    source: 'scripts/redteam/agent.py · contracts.py',
    checks: ['模型只能使用声明的受限工具。', '随机标记捕获与最终文本分离，来源可重算。', '执行轨迹是证据输入，同时也是不可信内容。'],
    failure: '工具失败、超时或未捕获都保留真实结果，不生成替代性成功叙述。',
    optimize: '增强协议能力时同步工具权限、网络隔离、执行轨迹数据约定和独立审核校验。'
  },
  '真实轨迹': {
    input: '发现记录表、自动分类和验证产物、真实流式事件与红队运行和步骤事件',
    output: '带单次观测编号与同一问题编号、动作前上下文、动作、历史动作被选中的概率、成本、结果与证据来源链的经验池',
    source: 'audit_rsi/experience.py · adapters/raw_trace.py · adapters/redteam.py',
    checks: ['只从真实动作与工具事件构建经验，不从最终报告反推探索路径。', '保留任务与智能体拓扑、实际成本与证据等级；历史动作被选中的概率未知时保持空值。', '红队运行结果与步骤工具事件分开记录，不复制随机标记或原始攻击输出。'],
    failure: '篡改轨迹、未捕获和未复核结果保持未知；缺失动作的记录不会凭空进入动作训练。',
    optimize: '先检查轨迹证据来源链、身份和动作前特征是否完整，再增加样本；不要用报告文本补造行动历史。'
  },
  '可信标签': {
    input: '经验池、分层抽样计划、实际运行、独立审核和人工结论，以及标签选择概率',
    output: '合并后的 verification-experience-labeled.jsonl 和可审计标签覆盖',
    source: 'audit_rsi/labeling.py · verification.py: merge_labels',
    checks: ['可信证据只包括实际运行、独立审核和人工结论；静态标签不能冒充这三类证据。', '智能体静态结论必须保留 evidence_class=static 与 adjudication.method=agent-static。', '未知不等于误报，标签合并不能改变单次观测身份、同一问题编号和历史动作被选中的概率。'],
    failure: '缺失或非法标签选择概率的样本不进入可信收益训练；只有静态证据时，可信样本支持数仍为 0。',
    optimize: '优先补齐完全缺少可信证据的项目和动作覆盖，不用放宽证据等级来提高支持度。'
  },
  '成本与收益评估': {
    input: '去重后的训练语义、动作前特征、已知结果、实际成本与合法标注选择概率',
    output: 'verification-policy.json：五个动作各自的岭回归（ridge）收益权重与支持度统计',
    source: 'audit_rsi/verification.py: train_policy / _solve_ridge',
    checks: ['动作词表（ACTIONS）固定为 verify、deep_read、human_review、duplicate_candidate、defer。', '每个动作分别回归实际动作收益，奖励扣除智能体、词元和人工审核等成本。', '按证据等级和历史动作被选中的概率加权，并限制概率权重，不模仿最终报告或历史动作频率。'],
    failure: '没有已知收益目标时，训练状态为证据不足；只有静态证据也可训练，但不构成可信的生产证据。',
    optimize: '检查各动作支持度、可信样本支持数、目标分布和成本口径，不用单一总分掩盖动作覆盖空洞。'
  },
  '跨项目验证与前后结果对比': {
    input: '未参与训练的留出验证集（holdout）、候选与基线方案的真实经验池、训练策略和统计通过条件配置',
    output: '按相同动作回放、按同源问题比较前后结果变化，以及通过、证据不足或拒绝的评估结果',
    source: 'audit_rsi/verification.py: replay_policies / outcome_flip_report · evaluation.py · release.py',
    checks: ['回放只比较策略与日志动作相同时的实际动作收益，明确不是因果离线策略评估。', '前后结果变化只观测两个真实经验池中由失败转为通过、由通过转为失败和保持稳定的项目，不构造反事实。', '候选默认要求 paired_coverage≥0.8、至少一项由失败转为通过且没有由通过转为失败，发布还需通过统计检查。'],
    failure: '项目、标签覆盖或支持不足时判定为证据不足；出现由通过转为失败的回归时拒绝，均不发布为生产策略。',
    optimize: '先检查留出验证集隔离、配对覆盖与表现最差的分组，再比较收益；不能把不同审计运行的差异解释为因果提升。'
  },
  '只读建议（shadow）': {
    input: '经验池、训练策略、基线方案、可信样本支持数和训练状态',
    output: '只读建议（recommendation_only=true）的 verification-shadow.json，逐条保留基线与候选方案、分数和原因',
    source: 'audit_rsi/verification.py: shadow_payload',
    checks: ['所有建议都是 recommendation_only=true（只读建议）且 state_change=none（不改变状态）。', '可信样本支持数为 0（trusted_support=0）时继续只读建议，状态为仅静态证据（static-only），原因是 no_trusted_utility_targets。', '训练不足时恢复基线方案；即使仅静态证据产生不同建议，也不代表已验证提升。'],
    failure: '没有可信样本支持时不发布为生产策略，不切换自动路由，也不宣称生产 RSI。',
    optimize: '先补独立可信标签与评估证据，再比较建议质量；不要通过隐藏仅静态证据状态制造就绪假象。'
  },
  '挖掘修复发布': {
    input: '正式基线运行、共享或仓库专属候选、独立候选上下文，以及批量流程自动选择的未参与训练留出项目',
    output: '学习节点生成的修复 Markdown、隔离候选挖掘与红蓝运行、driver.json、共享技能或当前项目规则、发布版本和回滚记录',
    source: '.claude/agents/mining-repair-learner.md · verification-experience-analyzer · repair-scope-analyzer · mining-repair-learning · audit_rsi/mining_driver.py',
    checks: ['学习节点由智能体执行框架驱动，组合验证经验、作用域、证据、项目知识和按类别选择的现有分析技能。', '候选必须实际参与独立重跑，不是只比较外部提供的两个经验池；候选产物不进入正式 runs/。', '误报修复必须至少抑制一个既有误报、降低误报率，且不得丢失正确结论或引入新误报。', '共享修复至少需要两个可信来源项目，并在未参与训练的留出项目上通过评估；项目修复只写入对应项目目录。', '发布重算候选身份、内容哈希和评估身份；下一轮挖掘同时加载共享规则与当前项目规则。'],
    failure: '静态证据、候选执行失败、正确结论丢失、新增误报、路径或哈希异常均拒绝发布；规则被后续修改后必须先回滚后续版本。',
    optimize: '按规则查看误报抑制、正确结论保留和跨项目表现；候选数量不等于发布数量，当前没有接受评估时保持候选状态。'
  },
  '找出反复出现的执行失败': {
    input: '每次红队验证的结果，以及模型超时、隔离环境异常、工具调用失败等真实执行记录',
    output: '一份失败统计：每类失败出现在多少次运行中、发生了多少个事件、平均调用模型多少次、耗时多久，以及可能对应哪个执行器环节',
    source: 'audit_rsi/weakness.py → rsi/redteam-weakness.json',
    checks: ['只统计真实执行记录，不根据最终报告猜测失败原因。', '按项目类型、攻击模型、失败原因和严重度分别统计，避免把不同场景混为一谈。', '统计结果只用于提出改进候选，不会自动修改执行器（mutation=none）；失败次数多也不等于已经找到根因。'],
    failure: '没有可统计的失败记录时，报告会明确显示“证据不足（insufficient）”；无法确定结果的记录不会被算作已成功验证的漏洞。',
    optimize: '先核对失败原因是否准确，再检查“失败运行数”和“失败事件数”是否混算；出现次数只能帮助安排检查顺序，不能证明修改后会更好。'
  },
  '验证程序候选': {
    input: '只提出提案、不直接修改的弱点报告，白名单允许修改的范围，以及配对后的前后结果变化记录',
    output: '具有稳定候选编号、仅包含提案的候选，以及验证通过、证据不足或拒绝的结果',
    source: 'audit_rsi/harness.py → rsi/harness-candidates.json · harness-validated.json',
    checks: ['提案只能指向允许修改的范围（ALLOWED_SURFACES），保留所有无关行为并记录证据哈希。', 'harness-validate 命令重算候选身份，并检查配对项的前后结果变化是否满足通过条件。', '全程不修改文件（mutation=none），不自动修改验证程序；验证通过后仍需后续候选与发布复核。'],
    failure: '修改范围不在白名单内、身份被篡改、覆盖不足或出现由通过转为失败的回归，均不能通过验证。',
    optimize: '先提高配对证据和失败复现质量，再评估提案；不能把生成提案当成已经修复验证程序。'
  },
  '视觉报告': {
    input: '审计报告、结构、覆盖和攻击模型，以及红队步骤',
    output: 'SVG、scene.webp、report-illustrated.md 和项目地图',
    source: '.claude/skills/project-cartographer',
    checks: ['结构树与攻击路径来自结构化模型。', '阶段智能体可多次调用结构化交付工具，获得修改意见与产物摘要；文件检查凭据不替代动态验证及人工验收。', '八阶段分别加载通用与仓库专属技能，记录本轮版本；候选须独立评估后发布，支持回退。', '连续迭代使用命令行入口，达到轮数或连续无改善即停止；页面尚无循环启停按钮。', '恢复汇总明确标注未重新扫描，并关联原始审计轨迹；报告交付仍须通过质量检查。', '场景设计智能体按技能执行，启动时配置模型服务连接与鉴权。', '攻击场景与蓝队节点可独立重跑，保留历史产物，不自动执行后续节点。', '人工智能插图明确标注非漏洞证据。', '视觉素材服务于人工理解，不能替代执行轨迹和独立审核。'],
    failure: '图片生成失败保留 SVG 和文本报告，不阻塞安全结论，也不伪造验收素材。',
    optimize: '优化信息层级和可读性时保持证据来源链，避免视觉叙事超出实际证据。'
  }
};

const GUIDE_ALIASES = {
  '发现记录表': '报告与发现记录表',
  '持久化恢复': '时限与恢复',
  '隔离场景构建器': '在隔离环境验证漏洞',
  '独立审核器': '独立审核与验收'
};

function ArchitectureDetail({ node, onBack }) {
  const Icon = node.icon;
  const guide = DETAIL_GUIDES[GUIDE_ALIASES[node.title] || node.title];
  const stepNumber = /^\d+$/.test(node.code || '') ? node.code : null;
  const artifact = node.artifact || node.code;
  return (
    <section className="arch-detail" aria-labelledby="arch-detail-title">
      <button type="button" className="arch-detail-back" onClick={onBack}>
        <ArrowLeft size={15} aria-hidden="true" /> 返回架构总览
      </button>
      <header className="arch-detail-hero">
        <div className={cx('arch-detail-icon', `tone-${node.tone || 'ink'}`)}><Icon size={24} aria-hidden="true" /></div>
        <div>
          <span className="arch-detail-group">{node.group} {stepNumber ? `/ ${stepNumber}` : ''}</span>
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
          <span className="arch-detail-label">执行规则</span>
          <ul>{guide.checks.map((item) => <li key={item}>{item}</li>)}</ul>
        </article>
        <article className="arch-detail-card">
          <span className="arch-detail-label">对应脚本与输出文件</span>
          <code>{guide.source}</code>
          {artifact && artifact !== guide.source ? <code>{artifact}</code> : null}
          {guide.command ? <pre className="arch-detail-command">{guide.command}</pre> : null}
        </article>
        <article className="arch-detail-card">
          <span className="arch-detail-label">失败时如何处理</span>
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
          <span className="arch-detail-group">学习依据</span>
          <h3 id="arch-rsi-why-title">为什么能形成 RSI 学习流程</h3>
          <p>每次验证都留下经验：当时看到什么、做了什么、结果是否可信、花费多少。系统据此学习怎样选择，再通过独立检验决定建议能否采用，而不是让模型直接改写自己。</p>
        </div>
        <aside className="arch-rsi-boundary" aria-label="当前 RSI 边界">
          <strong>验证动作只建议；挖掘修复经评估才发布</strong>
          <span>可用于动作训练的可信样本：<code>0</code></span>
          <span>回放只看真实结果，不证明因果</span>
          <span>共享修复必须使用未参与训练的留出项目</span>
        </aside>
      </section>

      <section className="arch-rsi-flywheel" aria-labelledby="arch-rsi-flywheel-title">
        <header className="arch-rsi-section-head">
          <div>
            <span className="arch-detail-group">主要流程 / 01—06</span>
            <h3 id="arch-rsi-flywheel-title">
              验证经验与挖掘修复学习循环
            </h3>
          </div>
          <p>前五步保留验证资源的只读建议；第六步是独立的挖掘修复支路，经真实前后运行评估后发布并加载。</p>
        </header>
        <div
          className="arch-rsi-loop"
          role="group"
          aria-label="六步 RSI 学习流程，按 01 到 06 展示；第六步发布挖掘修复"
        >
          <div className="arch-rsi-loop-row">
            {zone.stages.slice(0, 3).map((stage, index) => renderStage(stage, index, 'right'))}
          </div>
          <div className="arch-rsi-loop-links" aria-hidden="true">
            <span>
              <ArrowUp size={20} />
              06 发布后的新结果回到 01
            </span>
            <span>
              04 通过评估才进入建议或修复复核
              <ArrowDown size={20} />
            </span>
          </div>
          <div className="arch-rsi-loop-row is-reverse">
            {zone.stages.slice(3).map((stage, index) => renderStage(stage, index, 'left'))}
          </div>
        </div>
      </section>

      <section className="arch-rsi-branch" aria-labelledby="arch-rsi-branch-title">
        <header className="arch-rsi-section-head">
          <div>
            <span className="arch-detail-group">辅助流程 / 红队验证程序</span>
            <h3 id="arch-rsi-branch-title">第二条学习支路：从重复失败到最小修改候选</h3>
          </div>
          <p>主流程学习怎样选择；这条支路寻找执行器本身哪里经常出问题。</p>
        </header>
        <div className="arch-rsi-branch-track" role="group" aria-label="红队轨迹经过找出反复出现的执行失败形成验证程序候选，再接受独立回放与发布复核">
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
            <div><strong>独立检验与回归检查</strong><span>复核后才采用；这里不会自动改代码</span></div>
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
      <p className="arch-visual-note">人工智能漫画插图用于辅助理解；准确结构以这些可点击节点和实现详情为准。</p>
    </section>
  );
}

export default function ArchitectureView({ board }) {
  const [zone, setZone] = useState(null);
  const [selected, setSelected] = useState(null);
  const latest = [...(board?.projects || [])]
    .sort((a, b) => String(b.startedAt || '').localeCompare(String(a.startedAt || '')))[0];
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
            <span>MYGOLDMINE / 系统地图</span>
            <h2 id="arch-overview-title">从目标源码到可信证据</h2>
            <p>选择一个区域，逐层了解系统如何工作。</p>
          </div>
        </header>
        <AgenticPipeline
          project={latest?.id}
          projectName={latest?.name}
          runId={latest?.liveRunId || latest?.latestRunId}
          live={Boolean(latest?.isLive)}
        />
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
        <p className="arch-visual-note">漫画由人工智能生成，仅用于叙事；点击节点看到的层级与实现细节才是系统约定。</p>
      </section>
    </div>
  );
}
