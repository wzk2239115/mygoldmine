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
  const status = stats.status || {};
  const severityTotal = Object.values(stats.severity).reduce((sum, value) => sum + value, 0) || 1;

  return (
    <section className="stats-strip" aria-label="流程统计">
      <div className="metrics">
        <Metric
          label="全部发现"
          value={stats.total}
          hint="所有最新报告中的原始 finding；不是已确认漏洞数"
        />
        <Metric
          label="原始池"
          value={status.inbox || 0}
          suffix={`已归档 ${status.archived || 0}`}
          hint="尚未晋级；后台精炼 worker 会把未达门槛的 finding 归档并从这里移走"
        />
        <Metric
          label="分诊中"
          value={status.triage || 0}
          tone="ink"
          hint="Critical/High 自动入队，等待人工判断可达性与设计意图"
        />
        <Metric
          label="复现中"
          value={status.reproduce || 0}
          tone="amber"
          hint="已有 verify 记录，等待版本映射或最小 PoC"
        />
        <Metric
          label="CVE 跟踪"
          value={stats.cveTrack}
          suffix={`/ ${stats.cveCandidates} 候选`}
          tone="red"
          hint="已进入 CVE 流程的条目；候选数包含尚未去重的 Tier 1/2"
        />
        <Metric
          label="待验收"
          value={stats.reviewReady || 0}
          tone="green"
          hint="已精炼的精品 case：CVE 候选或源码级已验证 finding"
        />
        <Metric
          label="目标运行"
          value={`${completed}/${total}`}
          suffix={stats.live ? `${stats.live} 运行中` : '已结束'}
          hint="最新一轮各目标运行状态"
        />
      </div>

      <div className="severity-summary">
        <div className="severity-summary-head">
          <span>严重度分布</span>
          <span>{stats.total} 条</span>
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
