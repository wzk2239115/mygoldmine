import { ArrowRight, BadgeCheck, Boxes, Filter, GitBranch, ShieldCheck } from 'lucide-react';

function Stage({ icon: Icon, label, value, hint, tone }) {
  return (
    <div className={`refinery-stage tone-${tone || 'ink'}`} title={hint}>
      <Icon size={13} aria-hidden="true" />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function RefineryStrip({ stats }) {
  if (!stats) return null;
  const status = stats.status || {};
  const raw = (status.inbox || 0) + (status.archived || 0);
  const stages = [
    { icon: Boxes, label: '原矿', value: raw, hint: `原始池 ${status.inbox || 0} · 已归档 ${status.archived || 0}`, tone: 'muted' },
    { icon: Filter, label: '分诊', value: status.triage || 0, hint: 'Critical/High 自动入队', tone: 'cool' },
    { icon: GitBranch, label: '复现', value: status.reproduce || 0, hint: '已有 verify 记录', tone: 'amber' },
    { icon: ShieldCheck, label: 'CVE 去重', value: status.cve || 0, hint: '去重、披露、CNA', tone: 'hot' },
    { icon: BadgeCheck, label: '验收', value: stats.reviewReady || 0, hint: '人工只看这一格', tone: 'green' }
  ];
  return (
    <section className="refinery-strip" aria-label="精炼管线">
      <img className="refinery-art" src="/refinery-hero.webp" alt="" aria-hidden="true" />
      <div className="refinery-shade" />
      <div className="refinery-copy">
        <span className="eyebrow">REFINERY / FINDINGS PIPELINE</span>
        <strong>把原始发现炼成可验收的 case</strong>
        <span className="refinery-sub">自动评分、去重、复现、CVE 去重；人只看最后的精品。</span>
      </div>
      <div className="refinery-track" aria-label="流程计数">
        {stages.map((stage, index) => (
          <div className="refinery-node" key={stage.label}>
            <Stage {...stage} />
            {index < stages.length - 1 ? <ArrowRight className="refinery-arrow" size={15} aria-hidden="true" /> : null}
          </div>
        ))}
      </div>
      <div className="refinery-flow" aria-hidden="true"><i /><i /><i /></div>
    </section>
  );
}
