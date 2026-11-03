import { Check, Filter, RotateCcw, Target } from 'lucide-react';
import { SEVERITIES, VERDICTS } from '../constants.js';
import { cx } from '../utils.js';
import ProjectMark from './ProjectMark.jsx';
import ProjectImport from './ProjectImport.jsx';

function CountPill({ value }) {
  return <span className="filter-count">{value}</span>;
}

export default function Sidebar({ board, filters, setFilters, facets, onImported }) {
  const projects = board?.projects || [];
  const stats = board?.stats;
  const active = Boolean(
    filters.project !== 'all' ||
      filters.severities.length ||
      filters.verdicts.length ||
      filters.cveOnly ||
      filters.reviewOnly ||
      !filters.hideInbox ||
      filters.query
  );

  const setProject = (project) => {
    setFilters((current) => ({ ...current, project: current.project === project ? 'all' : project }));
  };

  const toggleSeverity = (severity) => {
    setFilters((current) => ({
      ...current,
      severities: current.severities.includes(severity)
        ? current.severities.filter((item) => item !== severity)
        : [...current.severities, severity]
    }));
  };

  const toggleVerdict = (verdict) => {
    setFilters((current) => ({
      ...current,
      verdicts: current.verdicts.includes(verdict)
        ? current.verdicts.filter((item) => item !== verdict)
        : [...current.verdicts, verdict]
    }));
  };

  return (
    <aside className="sidebar" id="finding-filters" aria-label="筛选与目标">
      <div className="sidebar-head">
        <div>
          <h2>漏洞审计</h2>
        </div>
        <div className="sidebar-head-actions">
          <ProjectImport onImported={onImported} />
          {active ? (
            <button
              type="button"
              className="icon-button is-small"
              title="重置筛选"
              aria-label="重置筛选"
              onClick={() =>
                setFilters((current) => ({
                  ...current,
                  project: 'all',
                  severities: [],
                  verdicts: [],
                  cveOnly: false,
                  reviewOnly: false,
                  hideInbox: true,
                  query: ''
                }))
              }
            >
              <RotateCcw size={14} />
            </button>
          ) : null}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <Target size={13} aria-hidden="true" />
          <span>目标</span>
          <span className="section-count">{projects.length}</span>
        </div>
        <button
          type="button"
          className={cx('project-row', filters.project === 'all' && 'is-active')}
          aria-pressed={filters.project === 'all'}
          onClick={() => setFilters((current) => ({ ...current, project: 'all' }))}
        >
          <span className="project-mark is-all">全部</span>
          <span className="project-copy">
            <strong>全部目标</strong>
            <span>{stats?.total ?? 0} 条候选问题</span>
          </span>
          <span className="project-total">{stats?.total ?? 0}</span>
        </button>
        {projects.map((project) => (
          <button
            key={project.id}
            type="button"
            className={cx('project-row', filters.project === project.id && 'is-active')}
            aria-pressed={filters.project === project.id}
            onClick={() => setProject(project.id)}
          >
            <ProjectMark project={project} />
            <span className="project-copy">
              <strong>{project.name}</strong>
              <span>
                <i className={cx('run-dot', `state-${project.state}`)} />
                {project.isLive ? <em className="live-project-badge">实时</em> : null}
                {project.isLive && !project.hasReport ? '审计中…' : `${project.findingsCount} 条候选问题`}
              </span>
              <small className="project-branch" title={project.commit || ''}>
                {project.branch || '分支未知'}
                {project.commit ? ` · ${String(project.commit).slice(0, 8)}` : ''}
              </small>
            </span>
            <span className="project-total">{project.curatedCount || 0}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <Filter size={13} aria-hidden="true" />
          <span>严重度</span>
        </div>
        <div className="filter-grid">
          {SEVERITIES.map((severity) => {
            const selected = filters.severities.includes(severity.id);
            return (
              <button
                key={severity.id}
                type="button"
                className={cx('filter-chip', `severity-${severity.id}`, selected && 'is-selected')}
                aria-pressed={selected}
                onClick={() => toggleSeverity(severity.id)}
              >
                <span className="filter-dot" />
                <span>{severity.full}</span>
                <CountPill value={facets?.severity?.[severity.id] ?? stats?.severity?.[severity.id] ?? 0} />
              </button>
            );
          })}
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>判定</span>
        </div>
        <div className="filter-grid">
          {VERDICTS.filter((verdict) => verdict.id !== 'untriaged').map((verdict) => {
            const selected = filters.verdicts.includes(verdict.id);
            return (
              <button
                key={verdict.id}
                type="button"
                className={cx('filter-chip', `verdict-chip-${verdict.id}`, selected && 'is-selected')}
                aria-pressed={selected}
                onClick={() => toggleVerdict(verdict.id)}
              >
                <span>{verdict.label}</span>
                <CountPill value={facets?.verdict?.[verdict.id] ?? stats?.verdict?.[verdict.id] ?? 0} />
              </button>
            );
          })}
        </div>
      </div>

      <div className="sidebar-section">
        <button
          type="button"
          className={cx('toggle-row', filters.cveOnly && 'is-active')}
          aria-pressed={filters.cveOnly}
          onClick={() => setFilters((current) => ({ ...current, cveOnly: !current.cveOnly }))}
        >
          <span className={cx('toggle-box', filters.cveOnly && 'is-checked')}>
            {filters.cveOnly ? <Check size={12} aria-hidden="true" /> : null}
          </span>
          <span>
            <strong>只看 CVE 候选</strong>
            <small>Tier 1 / Tier 2</small>
          </span>
        </button>
        <button
          type="button"
          className={cx('toggle-row', filters.reviewOnly && 'is-active')}
          aria-pressed={filters.reviewOnly}
          onClick={() => setFilters((current) => ({ ...current, reviewOnly: !current.reviewOnly }))}
        >
          <span className={cx('toggle-box', filters.reviewOnly && 'is-checked')}>
            {filters.reviewOnly ? <Check size={12} aria-hidden="true" /> : null}
          </span>
          <span>
            <strong>只看待验收</strong>
            <small>通过红队验证和独立审核，且图文报告齐全的候选</small>
          </span>
        </button>
        <button
          type="button"
          className={cx('toggle-row', filters.hideInbox && 'is-active')}
          aria-pressed={filters.hideInbox}
          onClick={() => setFilters((current) => ({ ...current, hideInbox: !current.hideInbox }))}
        >
          <span className={cx('toggle-box', filters.hideInbox && 'is-checked')}>
            {filters.hideInbox ? <Check size={12} aria-hidden="true" /> : null}
          </span>
          <span>
            <strong>隐藏未处理候选</strong>
            <small>已自动评分、尚未进入下一阶段的不占主视图</small>
          </span>
        </button>
      </div>

      <div className="sidebar-foot">
        <span className="data-pulse" />
        <div>
          <strong>静态审计报告</strong>
          <p>未做运行时验证。CVE 判断以人工复核为准。</p>
        </div>
      </div>
    </aside>
  );
}
