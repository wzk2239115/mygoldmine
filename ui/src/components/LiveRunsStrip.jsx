import { ChevronRight, Clock3, Loader2, Radio, Terminal } from 'lucide-react';
import { cx, formatDuration, relativeTime, truncate } from '../utils.js';

function stateLabel(run) {
  if (run.finished) return '已结束';
  if (run.state === 'starting') return '启动中';
  if (run.state === 'running') return '运行中';
  return '实时';

}

export default function LiveRunsStrip({ runs, onOpen }) {
  if (!runs?.length) return null;

  return (
    <section className="live-strip" aria-label="正在运行的挖掘任务">
      <div className="live-strip-head">
        <span className="live-pulse" aria-hidden="true" />
        <strong>实时挖掘</strong>
        <span className="live-count">{runs.length} 个任务</span>
        <span className="live-hint">日志每 4 秒刷新 · 报告生成后自动进入看板</span>
      </div>
      <div className="live-strip-list">
        {runs.map((run) => {
          const timeout = Number(run.timeoutSeconds) || 0;
          const elapsed = Number(run.elapsedSeconds) || 0;
          const progress = timeout ? Math.min(100, Math.round((elapsed / timeout) * 100)) : null;
          return (
            <button
              key={`${run.project}:${run.runId}`}
              type="button"
              className={cx('live-run-card', `state-${run.state}`, run.finished && 'is-finished')}
              onClick={() => onOpen(run)}
            >
              <div className="live-run-top">
                <span className="live-run-project">{run.projectName}</span>
                <span className={cx('live-state', `state-${run.state}`)}
                  role="status" aria-label={stateLabel(run)} title={stateLabel(run)}>
                  {!run.finished && run.state === 'running'
                    ? <><Loader2 size={13} className="is-spinning" aria-hidden="true" />{stateLabel(run)}</>
                    : <><Radio size={10} aria-hidden="true" />{stateLabel(run)}</>}
                </span>
                <span className="live-run-time" title={`${elapsed} / ${timeout || '?'} seconds`}>
                  <Clock3 size={11} aria-hidden="true" />
                  {formatDuration(elapsed)}
                  {timeout ? <small> / {formatDuration(timeout)}</small> : null}
                </span>
              </div>
              <div className="live-run-id">{run.runId}</div>
              {progress !== null ? (
                <span className="live-progress" aria-hidden="true">
                  <span style={{ width: `${progress}%` }} />
                </span>
              ) : null}
              <div className="live-run-line" title={run.lastLogLine || ''}>
                <Terminal size={11} aria-hidden="true" />
                <code>{truncate(run.lastLogLine || '等待 agent 输出…', 150)}</code>
              </div>
              <div className="live-run-foot">
                <span>{run.logMtime ? `最后输出 ${relativeTime(run.logMtime)}` : '日志尚未生成'}</span>
                <span className="live-open">
                  打开实时日志
                  <ChevronRight size={12} aria-hidden="true" />
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
