import { Clock3, Terminal, X } from 'lucide-react';
import { cx, formatDateTime, formatDuration } from '../utils.js';

function stateLabel(run) {
  if (run.isLive) return '实时';
  if (run.state === 'partial') return '部分完成';
  const state = String(run.state || '').toLowerCase();
  if (state === 'completed' || state === 'finished' || run.hasReport) return '已有报告';
  return state ? state.toUpperCase() : '运行';
}

export default function RunsDrawer({ runs, loading, error, onClose, onOpen }) {
  const ordered = [...(runs || [])].sort((left, right) => {
    const a = String(left.startedAt || left.updatedAt || '');
    const b = String(right.startedAt || right.updatedAt || '');
    return b.localeCompare(a);
  });

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="detail-drawer runs-drawer" role="dialog" aria-modal="true" aria-label="CC 运行轨迹">
        <header className="drawer-head">
          <div className="drawer-head-top">
            <div className="drawer-ident">
            </div>
            <button type="button" className="icon-button on-dark" title="关闭" aria-label="关闭运行轨迹" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
          <h2>CC 运行轨迹</h2>
          <p className="runs-subtitle">
            选择一次审计运行，查看完整的 Claude Code 审计轨迹；进入后可切换原始日志或结构化轨迹。
          </p>
        </header>

        <div className="drawer-body runs-body">
          {loading ? <div className="runs-empty">正在读取审计运行…</div> : null}
          {error ? <div className="inline-error">{error}</div> : null}
          {!loading && !error && !ordered.length ? <div className="runs-empty">没有可读取的审计运行。</div> : null}
          {ordered.map((run) => (
            <button
              key={`${run.project}:${run.runId}`}
              type="button"
              className={cx('runs-row', run.isLive && 'is-live')}
              onClick={() => onOpen(run)}
              disabled={!run.hasLog}
              title={run.hasLog ? `打开 ${run.projectName || run.project} ${run.runId} 的轨迹` : '该审计运行没有 claude.rendered.log'}
            >
              <span className={cx('runs-state', `runs-state-${String(run.state || 'unknown').toLowerCase()}`)}>
                {stateLabel(run)}
              </span>
              <span className="runs-main">
                <strong>{run.projectName || run.project}</strong>
                <span>
                  <code>{run.runId}</code>
                  <i>·</i>
                  {run.model || '模型未知'}
                  <i>·</i>
                  <Clock3 size={13} aria-hidden="true" />
                  {formatDuration(Number(run.durationSeconds) || 0)}
                </span>
                <small>
                  {run.findingsCount ?? 0} 条候选问题
                  <i>·</i>
                  {run.commit ? run.commit.slice(0, 8) : '提交未知'}
                  <i>·</i>
                  {formatDateTime(run.startedAt || run.updatedAt)}
                </small>
              </span>
              <span className="runs-action">
                <Terminal size={15} aria-hidden="true" />
                {run.hasLog ? '轨迹' : '无日志'}
              </span>
            </button>
          ))}
        </div>

        <footer className="drawer-footer">
          <span className="footer-signal">
            <Terminal size={13} aria-hidden="true" />
            CC 会话 · 结构化轨迹 / 原始日志
          </span>
          <span className="runs-count">{ordered.length} 次运行</span>
        </footer>
      </aside>
    </>
  );
}
