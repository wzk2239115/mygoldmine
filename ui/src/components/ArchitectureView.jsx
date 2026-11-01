import {
  ArrowRight,
  BadgeCheck,
  Bot,
  Boxes,
  Braces,
  CircleAlert,
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

const STATE_ROWS = [
  ['人工状态', 'state.json', '最高优先级；永不自动覆盖'],
  ['人工种子', 'curated.json', '二次审计结论'],
  ['精炼 worker', 'refine-state.json', '分批归档/晋级'],
  ['自动路由', 'auto-state.json', 'CVE/verify/规则'],
  ['默认', 'inbox', '原始池']
];

const INVARIANTS = [
  ['网络', 'docker network create --internal，attacker 无外网'],
  ['Flag', '每轮随机，只挂载给 victim，attacker 无可见路径'],
  ['宿主', 'attacker 不挂载宿主、不挂载 Docker socket'],
  ['证据', 'trace / agent 输出是不可信数据，judge 不被其指令带偏'],
  ['验收', '必须 flag + judge approved + 图文报告，三者缺一不可'],
  ['归档', 'archived 不是“安全”，只是评分未晋级']
];

function Count({ value, label }) {
  return (
    <div className="arch-count">
      <strong>{value ?? '—'}</strong>
      <span>{label}</span>
    </div>
  );
}

function Stage({ stage }) {
  const Icon = stage.icon;
  return (
    <article className={cx('arch-stage', `tone-${stage.tone}`)}>
      <div className="arch-stage-top">
        <span className="arch-stage-code">{stage.code}</span>
        <Icon size={17} aria-hidden="true" />
      </div>
      <h3>{stage.title}</h3>
      <p>{stage.body}</p>
      <code>{stage.artifact}</code>
    </article>
  );
}

export default function ArchitectureView({ board }) {
  const stats = board?.stats || {};
  const status = stats.status || {};
  const review = stats.reviewReady || 0;
  return (
    <div className="arch-view">
      <header className="arch-head">
        <div>
                    <h2>一条 finding 如何变成可验收的 case</h2>
          <p>
            这不是一张“结果图”，而是系统的真实数据流、状态门和隔离边界。每一层都保留可回放证据；
            自动化负责收敛，红队负责证明，judge 负责人工前的最后一道审阅。
          </p>
        </div>
        <div className="arch-counts">
          <Count value={stats.total} label="原始 finding" />
          <Count value={status.triage} label="分诊" />
          <Count value={status.reproduce} label="复现" />
          <Count value={status.cve} label="CVE" />
          <Count value={review} label="待验收" />
        </div>
      </header>

      <section className="arch-flow arch-mining" aria-label="挖掘执行链">
        <div className="arch-flow-head">
          <span>挖掘过程：从目标源码到可信报告</span>
        </div>
        <div className="arch-stages">
          {MINING_STAGES.map((stage, index) => (
            <div className="arch-stage-wrap" key={stage.code}>
              <Stage stage={stage} />
              {index < MINING_STAGES.length - 1 ? <ArrowRight className="arch-stage-arrow" size={18} aria-hidden="true" /> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="arch-flow" aria-label="端到端流水线">
        <div className="arch-flow-head">
          <span>从原始报告到人工验收</span>
        </div>
        <div className="arch-stages">
          {STAGES.map((stage, index) => (
            <div className="arch-stage-wrap" key={stage.code}>
              <Stage stage={stage} />
              {index < STAGES.length - 1 ? <ArrowRight className="arch-stage-arrow" size={18} aria-hidden="true" /> : null}
            </div>
          ))}
        </div>
      </section>

      <div className="arch-columns">
        <section className="arch-panel">
          <div className="arch-panel-head">
                        <span>各司其职，不互相冒充</span>
          </div>
          <div className="arch-component-list">
            {COMPONENTS.map(({ icon: Icon, title, body, code }) => (
              <article className="arch-component" key={title}>
                <Icon size={16} aria-hidden="true" />
                <div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                  <code>{code}</code>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="arch-panel">
          <div className="arch-panel-head">
                        <span>人永远可以覆盖机器</span>
          </div>
          <div className="arch-state-list">
            {STATE_ROWS.map(([title, file, body], index) => (
              <div className="arch-state-row" key={file}>
                <span className="arch-state-rank">0{index + 1}</span>
                <div>
                  <strong>{title}</strong>
                  <p>{body}</p>
                </div>
                <code>{file}</code>
              </div>
            ))}
          </div>
          <div className="arch-callout">
            <CircleAlert size={15} aria-hidden="true" />
            <p>
              <code>archived</code> 不是安全结论。它只表示自动评分没有达到晋级门槛；报告仍在原始 run 中，
              未来可以重新捞回。
            </p>
          </div>
        </section>
      </div>

      <section className="arch-lab">
        <div className="arch-panel-head">
                    <span>flag 只能从漏洞路径出来</span>
        </div>
        <div className="lab-map">
          <div className="lab-zone attacker-zone">
            <div className="lab-zone-head"><Bot size={16} /> attacker container</div>
            <p>只有 shell / curl / python；无 host、无 flag、无 Docker socket。</p>
            <code>runs/redteam/.../agent.jsonl</code>
          </div>
          <div className="lab-boundary">
            <span>INTERNAL NETWORK</span>
            <div className="lab-arrow"><ArrowRight size={18} /></div>
            <small>finding 只作为数据</small>
          </div>
          <div className="lab-zone victim-zone">
            <div className="lab-zone-head"><ShieldCheck size={16} /> victim container</div>
            <p>真实服务 + 随机 flag；health check 不泄露 flag。</p>
            <code>/flag · trace.jsonl</code>
          </div>
          <div className="lab-verdict">
            <div className="lab-zone-head"><BadgeCheck size={16} /> independent judge</div>
            <p>检查目标漏洞、flag provenance、作弊路径、可复现性和证据完整性。</p>
            <code>judge.json → review</code>
          </div>
        </div>
        <div className="arch-invariants">
          {INVARIANTS.map(([title, body]) => (
            <div key={title}>
              <strong>{title}</strong>
              <span>{body}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="arch-bottom-grid">
        <article className="arch-panel">
          <div className="arch-panel-head">
                        <span>决策也变成训练数据</span>
          </div>
          <div className="arch-loop">
            <span>experience</span><ArrowRight size={14} /><span>trusted labels</span><ArrowRight size={14} /><span>holdout + gates</span><ArrowRight size={14} /><span>release</span>
          </div>
          <p>
            经验记录动作前上下文、倾向、证据等级、成本与结果；模型学习 verify / deep_read / human_review 等动作效用。
            static 标签不能冒充人工或运行时真值；支持不足时只给只读 shadow，不发布生产策略。
          </p>
          <code>audit_rsi/experience.py → evaluation.py → release.py</code>
        </article>
        <article className="arch-panel">
          <div className="arch-panel-head">
                        <span>从看板到动态验收</span>
          </div>
          <pre className="arch-code">{`bash scripts/ui/start.sh
bash scripts/workflow/refine_worker.sh start
python3 scripts/redteam/build_lab.py --project <p> --finding <f>
python3 scripts/redteam/agent.py --finding <f> --victim-image <img>
python3 scripts/redteam/judge.py --run-dir runs/redteam/<p>/<run>`}</pre>
          <p className="arch-footnote">
            没有 lab 时 fail-closed 到 <code>blocked_no_lab</code>；没有 flag 不进入 review；
            没有图文报告也不进入 review。
          </p>
        </article>
      </section>
    </div>
  );
}
