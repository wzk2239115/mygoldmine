import { SEVERITIES } from '../constants.js';
import { cx } from '../utils.js';

function Metric({ label, value, suffix, tone, hint }) {
  return (
    <div className={cx('metric', tone && `metric-${tone}`)} title={hint}>
      <span className="metric-label">{label}</span>
      <span className="metric-value">
        {value}
        {suffix ? <small>{suffix}</small> : null}
      </span>
    </div>
  );
}

export default function StatsStrip({ stats, projects }) {
  if (!stats) {
    return <div className="stats-strip is-loading" aria-hidden="true" />;
  }
  const completed = projects?.filter((project) => project.state === 'completed').length || 0;
  const total = projects?.length || 0;
  const severityTotal = Object.values(stats.severity).reduce((sum, value) => sum + value, 0) || 1;

  return (
    <section className="stats-strip" aria-label="统计">
      <div className="metrics">
        <Metric label="RAW FINDINGS" value={stats.total} hint="所有报告中的原始 finding 数" />
        <Metric label="CURATED" value={stats.curated} tone="ink" hint="二次审计抽样的 25 条 + 手工移动的条目" />
        <Metric label="CODE-LEVEL TP" value={stats.tp} tone="green" hint="二次审计判定为代码级成立" />
        <Metric label="CVE CANDIDATES" value={stats.cveCandidates} tone="amber" hint="Tier 1 / Tier 2 候选" />
        <Metric label="CVE TRACK" value={stats.cveTrack} tone="red" hint="当前在 CVE 跟踪列" />
        <Metric label="RUNS" value={`${completed}/${total}`} suffix={stats.live ? `${stats.live} live` : 'done'} hint="最新一轮各目标运行状态" />
      </div>

      <div className="severity-summary">
        <div className="severity-summary-head">
          <span>SEVERITY MIX</span>
          <span>{stats.total} findings</span>
        </div>
        <div className="severity-summary-bar">
          {SEVERITIES.map((severity) => {
            const count = stats.severity[severity.id] || 0;
            if (!count) return null;
            return (
              <span
                key={severity.id}
                className={cx('severity-summary-segment', `severity-${severity.id}`)}
                style={{ width: `${(count / severityTotal) * 100}%` }}
                title={`${severity.full}: ${count}`}
              />
            );
          })}
        </div>
        <div className="severity-summary-legend">
          {SEVERITIES.map((severity) => (
            <span key={severity.id} className={cx('severity-legend-item', `severity-${severity.id}`)}>
              <i />
              {severity.label} {stats.severity[severity.id] || 0}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
