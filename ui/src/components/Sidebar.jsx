import {projectIsBusy} from '../project-activity.js';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Clock3, Filter, LoaderCircle, RotateCcw, Target, Trash2, X } from 'lucide-react';
import { SEVERITIES, VERDICTS } from '../constants.js';
import { cx } from '../utils.js';
import ProjectMark from './ProjectMark.jsx';
import ProjectImport from './ProjectImport.jsx';

function CountPill({ value }) {
  return <span className="filter-count">{value}</span>;
}

export default function Sidebar({ board, filters, setFilters, facets, onImported, onRemove, onRestart }) {
  const [restartBusy, setRestartBusy] = useState('');
  const [restartError, setRestartError] = useState(null);
  const restart = async (project) => {
    if (restartBusy) return;
    setRestartBusy(project.id); setRestartError(null);
    try { await onRestart(project); }
    catch (error) { setRestartError({project:project.id,message:error.message}); }
    finally { setRestartBusy(''); }
  };
  const [removing, setRemoving] = useState(null);
  const [removeBusy, setRemoveBusy] = useState(false);
  const [removeError, setRemoveError] = useState('');
  const confirmRemove = async () => {
    setRemoveBusy(true);
    setRemoveError('');
    try { await onRemove(removing); setRemoving(null); }
    catch (error) { setRemoveError(error.message); }
    finally { setRemoveBusy(false); }
  };
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
    <>
    {removing ? createPortal(<>
      <button type="button" className="project-import-backdrop" aria-label="关闭删除确认" disabled={removeBusy} onClick={() => setRemoving(null)} />
      <section className="project-import-dialog project-remove-dialog" role="dialog" aria-modal="true" aria-labelledby="project-remove-title">
        <header className="project-import-head"><h2 id="project-remove-title">删除项目 {removing.name}？</h2><button type="button" className="icon-button" aria-label="关闭删除确认" disabled={removeBusy} onClick={() => setRemoving(null)}><X size={16} /></button></header>
        <p>将删除项目登记、候选问题及审计运行记录，无法撤销。源码目录保留。</p>
        {removeError ? <p className="project-import-error" role="alert">{removeError}</p> : null}
        <footer className="project-import-actions"><button type="button" className="button" disabled={removeBusy} onClick={() => setRemoving(null)}>取消</button><button type="button" className="button project-remove-confirm" disabled={removeBusy} onClick={confirmRemove}>{removeBusy ? '正在删除…' : '删除项目'}</button></footer>
      </section>
    </>, document.body) : null}
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
        {!removing && removeError ? <p className="project-import-error" role="alert">{removeError}</p> : null}
        {projects.map((project) => (
          <div className="project-row-wrap" key={project.id}>
          <button
            type="button"
            className={cx('project-row', filters.project === project.id && 'is-active')}
            aria-pressed={filters.project === project.id}
            onClick={() => setProject(project.id)}
          >
            <ProjectMark project={project} />
            <span className="project-copy">
              <strong>{project.name}</strong>
              <span>
                {!projectIsBusy(project)?<i className={cx('run-dot', `state-${project.state}`)} />:null}
                {projectIsBusy(project) ? <span className={cx('project-activity-icon',project.activity?.status==='queued'?'is-queued':'is-running')} role="img" aria-label={project.activity?.status==='queued'?'排队中':'运行中'} title={project.activity?.status==='queued'?'排队中'+(project.activity.position?' · 第 '+project.activity.position+' 位':''):'审计运行中'}>
                  {project.activity?.status==='queued'?<Clock3 size={14} aria-hidden="true"/>:<LoaderCircle size={14} aria-hidden="true"/>}
                </span> : null}
                {projectIsBusy(project) && !project.hasReport ? (project.activity?.status==='queued'?'等待运行名额':'审计中…') : `${project.findingsCount} 条候选问题`}
              </span>
              <small className="project-branch" title={project.commit || ''}>
                {project.branch || '分支未知'}
                {project.commit ? ` · ${String(project.commit).slice(0, 8)}` : ''}
              </small>
            </span>
          </button>
          <div className="project-row-actions">
          <button type="button" className="project-restart" aria-label={`重新审计 ${project.name}`} title="使用当前源码重新运行完整审计，保留历史记录" disabled={projectIsBusy(project) || Boolean(restartBusy)} onClick={() => restart(project)}><RotateCcw size={13} aria-hidden="true" />{restartBusy === project.id ? '正在启动…' : projectIsBusy(project) ? (project.activity?.status==='queued'?'排队中':'审计进行中') : '重新审计'}</button>
          <button type="button" className="project-remove icon-button is-small" title={projectIsBusy(project) ? '审计进行中，停止后可删除' : `删除项目 ${project.name}`} aria-label={`删除项目 ${project.name}`} disabled={projectIsBusy(project) || Boolean(restartBusy)} onClick={() => { setRemoveError(''); setRemoving(project); }}><Trash2 size={14} aria-hidden="true" /></button>
          </div>
          {restartError?.project === project.id ? <p className="project-import-error" role="alert">{restartError.message}</p> : null}
          </div>
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
    </>
  );
}
