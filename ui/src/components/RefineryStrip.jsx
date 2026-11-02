import { Archive, ArrowRight, BadgeCheck, Boxes, Filter, GitBranch, ShieldCheck } from 'lucide-react';
import { stageCount } from '../stage-model.js';
import { SEVERITIES, VERDICTS } from '../constants.js';
import { cx } from '../utils.js';

function Stage({ icon: Icon, label, value, hint, tone, active, onClick }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      className={`refinery-stage tone-${tone || 'ink'}${active ? ' is-active' : ''}`}
      title={onClick ? `${hint} · 点击进入` : hint}
      aria-pressed={onClick ? active : undefined}
      onClick={onClick}
    >
      <Icon size={13} aria-hidden="true" />
      <span>{label}</span>
      <strong>{value}</strong>
    </Tag>
  );
}

export default function RefineryStrip({ stats, stageStats = stats, activeStage, onSelectStage, landing, filters, setFilters }) {
  if (!stats) return null;
  const status = stageStats.status || {};
  const raw = stageCount(stageStats, 'raw');
  const stages = [
    { id: 'raw', icon: Boxes, label: '未处理候选', value: raw, hint: `未处理候选（inbox） ${status.inbox || 0} · 已归档 ${status.archived || 0} 仅统计`, tone: 'muted' },
    { id: 'triage', icon: Filter, label: '分诊', value: status.triage || 0, hint: 'Critical/High 自动入队', tone: 'cool' },
    { id: 'reproduce', icon: GitBranch, label: '待验证', value: status.reproduce || 0, hint: 'CVE Tier 候选或 confirmed verify；等待验证（尚未复现）', tone: 'amber' },
    { id: 'cve', icon: ShieldCheck, label: 'CVE 跟踪', value: status.cve || 0, hint: '去重、披露、CNA', tone: 'hot' },
    { id: 'review', icon: BadgeCheck, label: '待验收', value: stageStats.reviewReady || 0, hint: '红队 flag + judge + 图文报告', tone: 'green' },
    { id: 'closed', icon: Archive, label: '已关闭', value: status.closed || 0, hint: '误报、重复、已知 CVE 或设计限制', tone: 'muted' }
  ];
  return (
    <section className={landing ? "refinery-strip is-landing" : "refinery-strip"} aria-label="自动分类管线">
      <img className="refinery-art" src="/refinery-hero.webp" alt="" aria-hidden="true" />
      <div className="refinery-shade" />
      <div className="refinery-track" aria-label="流程计数">
        {stages.map((stage, index) => (
          <div className="refinery-node" key={stage.label}>
            <Stage {...stage} active={activeStage === stage.id} onClick={onSelectStage ? () => onSelectStage(stage.id) : undefined} />
            {index < stages.length - 1 ? <ArrowRight className="refinery-arrow" size={15} aria-hidden="true" /> : null}
          </div>
        ))}
      </div>
      {filters && setFilters ? (
        <div className="refinery-distribution">
          <div className="refinery-dist-row">
            <span className="refinery-dist-label">严重度</span>
            {SEVERITIES.map((severity) => {
              const selected = filters.severities.includes(severity.id);
              return (
                <button
                  key={severity.id}
                  type="button"
                  className={cx('refinery-dist-chip', `severity-${severity.id}`, selected && 'is-selected')}
                  aria-pressed={selected}
                  onClick={() => setFilters((current) => ({
                    ...current,
                    severities: current.severities.includes(severity.id)
                      ? current.severities.filter((item) => item !== severity.id)
                      : [...current.severities, severity.id]
                  }))}
                >
                  <i />
                  {severity.full}
                  <strong>{stats.severity?.[severity.id] ?? 0}</strong>
                </button>
              );
            })}
          </div>
          <div className="refinery-dist-row">
            <span className="refinery-dist-label">判定</span>
            {VERDICTS.filter((verdict) => verdict.id !== 'untriaged').map((verdict) => {
              const selected = filters.verdicts.includes(verdict.id);
              return (
                <button
                  key={verdict.id}
                  type="button"
                  className={cx('refinery-dist-chip', `verdict-chip-${verdict.id}`, selected && 'is-selected')}
                  aria-pressed={selected}
                  onClick={() => setFilters((current) => ({
                    ...current,
                    verdicts: current.verdicts.includes(verdict.id)
                      ? current.verdicts.filter((item) => item !== verdict.id)
                      : [...current.verdicts, verdict.id]
                  }))}
                >
                  {verdict.full}
                  <strong>{stats.verdict?.[verdict.id] ?? 0}</strong>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
      <div className="refinery-flow" aria-hidden="true"><i /><i /><i /></div>
    </section>
  );
}
