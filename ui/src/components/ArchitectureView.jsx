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

const STAGES = [
  {
    code: '01',
    title: '原始报告',
    icon: FileCode2,
    tone: 'ink',
    body: '审计容器输出 audit-report.json。此时只有 finding、证据路径和攻击面描述，没有“已确认”结论。',
    artifact: 'runs/<project>/<run>/audit-report.json'
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
    body: 'lab-builder 自动判断 http/stdio/cli/library/ipc/model 形态，构建 victim、随机 flag 和 attacker。',
    artifact: 'labs/<project>/scenario.json · runs/redteam/*'
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
    icon: Workflow,
    title: '精炼 worker',
    body: '后台分批消费原始池。人工/curated/auto 已处理项跳过；精确重复归档；Critical/High 进入分诊。',
    code: 'scripts/workflow/refine_worker.py'
  },
  {
    icon: Braces,
    title: '状态编译器',
    body: '聚合报告、verify、红队结果和人工状态，生成 UI 需要的 finding 字段与 review 门槛。',
    code: 'scripts/workflow/build_state.py'
  },
  {
    icon: Boxes,
    title: 'Lab builder',
    body: 'agentic skill：读 finding + 源码，选择 lab 形态，构建 victim/attacker，设计 flag 暴露路径。',
    code: '.claude/skills/redteam-lab-builder'
  },
  {
    icon: Network,
    title: 'Red-team runner',
    body: 'OpenAI-compatible 模型在 attacker 容器里循环执行 shell；每步记录 trace，不接触宿主。',
    code: 'scripts/redteam/agent.py'
  },
  {
    icon: ShieldCheck,
    title: 'Independent judge',
    body: '不同模型实例审核红队轨迹，拒绝捷径、伪造 flag、调试后门和不可复现路径。',
    code: 'scripts/redteam/judge.py'
  },
  {
    icon: Sparkles,
    title: '视觉报告',
    body: '结构树、覆盖树、攻击路径、attacker/victim 步骤和 image2 叙事插图；插图不充当证据。',
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
          <span className="eyebrow">SYSTEM ARCHITECTURE / FOR DEVELOPERS</span>
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

      <section className="arch-flow" aria-label="端到端流水线">
        <div className="arch-flow-head">
          <span className="eyebrow">01 / PIPELINE</span>
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
            <span className="eyebrow">02 / COMPONENTS</span>
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
            <span className="eyebrow">03 / STATE PRIORITY</span>
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
          <span className="eyebrow">04 / RED-TEAM BOUNDARY</span>
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
            <span className="eyebrow">05 / RSI LOOP</span>
            <span>决策也变成训练数据</span>
          </div>
          <div className="arch-loop">
            <span>refine.jsonl</span><ArrowRight size={14} /><span>validation.jsonl</span><ArrowRight size={14} /><span>RSI policy</span>
          </div>
          <p>
            自动路由记录 features / decision / score；红队通过记录 finding / trace / judge。
            后续用人工验收和 verify 结果补标签，回放历史策略，调整阈值和排序。
          </p>
          <code>rsi/trajectories/*.jsonl</code>
        </article>
        <article className="arch-panel">
          <div className="arch-panel-head">
            <span className="eyebrow">06 / RUNBOOK</span>
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
