import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowDown,
  Clock3,
  Copy,
  ExternalLink,
  FileText,
  Radio,
  RefreshCw,
  Terminal,
  X
} from 'lucide-react';
import { api } from '../api.js';
import { cx, formatDateTime, formatDuration, relativeTime } from '../utils.js';
import TrajectoryPanel from './TrajectoryPanel.jsx';

export default function LiveRunDrawer({ run, onClose, onToast }) {
  const [log, setLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [follow, setFollow] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [view, setView] = useState(run?.finished ? 'trajectory' : 'stream');
  const preRef = useRef(null);
  const closeRef = useRef(null);

  const loadLog = useCallback(
    async (silent = false) => {
      if (!run) return;
      if (!silent) setLoading(true);
      setError('');
      try {
        const payload = await api.log(run.project, run.runId, 1000);
        setLog(payload);
      } catch (loadError) {
        setError(loadError.message);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [run?.project, run?.runId]
  );

  useEffect(() => {
    setLog(null);
    setFollow(true);
    setError('');
    setLoading(true);
    setView('stream');
    loadLog();
    closeRef.current?.focus();
  }, [run?.project, run?.runId, loadLog]);

  useEffect(() => {
    if (!autoRefresh || run?.finished || view !== 'stream') return;
    const timer = window.setInterval(() => loadLog(true), 2000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, run?.finished, loadLog, view]);

  useEffect(() => {
    if (!follow) return;
    const el = preRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log, follow]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!run) return null;

  const timeout = Number(run.timeoutSeconds) || 0;
  const elapsed = Number(run.elapsedSeconds) || 0;
  const progress = timeout ? Math.min(100, Math.round((elapsed / timeout) * 100)) : null;
  const startLine = log ? Math.max(1, log.totalLines - log.lines.length + 1) : 1;
  const state = run.finished ? 'finished' : run.state;

  const copy = async (value, label = '已复制') => {
    const ok = await navigator.clipboard.writeText(value).then(() => true).catch(() => false);
    onToast?.(ok ? `${label}：${value}` : '复制失败，请手动选择文本');
  };

  return (
    <>
      <div className="drawer-backdrop live-backdrop" onClick={onClose} />
      <aside className="detail-drawer live-drawer" role="dialog" aria-modal="true" aria-label={`${run.projectName} 实时日志`}>
        <header className="drawer-head live-drawer-head">
          <div className="drawer-head-top">
            <div className="drawer-ident">
              <span className={cx('live-badge', `state-${state}`)}>
                <Radio size={11} aria-hidden="true" />
                {state === 'finished' ? 'FINISHED' : 'LIVE'}
              </span>
              <span className="drawer-project">{run.projectName}</span>
              <span className="drawer-id">{run.runId}</span>
            </div>
            <div className="drawer-actions">
              <span className="live-updated">{run.logMtime ? relativeTime(run.logMtime) : '等待输出'}</span>
              <button ref={closeRef} type="button" className="icon-button on-dark" title="关闭实时日志" aria-label="关闭实时日志" onClick={onClose}>
                <X size={18} />
              </button>
            </div>
          </div>
          <h2>{run.finished ? 'CC 运行轨迹' : '实时挖掘日志'}</h2>
          <div className="live-drawer-meta">
            <span>
              <Clock3 size={12} aria-hidden="true" />
              {formatDuration(elapsed)}
              {timeout ? ` / ${formatDuration(timeout)}` : ''}
            </span>
            <span>{run.model || 'unknown model'}</span>
            <span>{run.container || 'container pending'}</span>
            {run.hasReport ? <span className="report-ready">REPORT READY</span> : null}
          </div>
          {progress !== null ? (
            <div className="live-progress is-large" aria-label={`已运行 ${progress}%`}>
              <span style={{ width: `${progress}%` }} />
            </div>
          ) : null}
        </header>

        <div className="drawer-body live-drawer-body">
          <div className={cx('live-notice', run.finished && 'is-finished')}>
            {run.finished
              ? '运行已结束。关闭后刷新看板；如果报告尚未出现，请查看下方日志尾部。'
              : run.hasReport
                ? '报告已生成，关闭后刷新看板即可切换到 findings。'
                : '报告尚未生成时，看板先展示这条实时日志。完成后会自动刷新看板并载入 findings。'}
          </div>

          <div className="traj-switch" role="tablist" aria-label="实时日志视图">
            <button
              type="button"
              role="tab"
              aria-selected={view === 'stream'}
              className={cx(view === 'stream' && 'is-active')}
              onClick={() => setView('stream')}
            >
              Stream
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'trajectory'}
              className={cx(view === 'trajectory' && 'is-active')}
              onClick={() => setView('trajectory')}
            >
              Trajectory
            </button>
          </div>

          {view === 'stream' ? (
            <>
          <div className="agent-toolbar live-toolbar">
            <button type="button" className="button is-small" onClick={() => loadLog()} disabled={loading}>
              <RefreshCw size={13} className={cx(loading && 'is-spinning')} aria-hidden="true" />
              刷新
            </button>
            <label className="follow-toggle">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(event) => setAutoRefresh(event.target.checked)}
                disabled={run.finished}
              />
              自动刷新 2s
            </label>
            <button type="button" className="button is-small" onClick={() => copy(`tail -f ${run.logPath}`, '已复制 tail 命令')}>
              <Terminal size={13} aria-hidden="true" />
              复制 tail
            </button>
            <a className="button is-small" href={`/api/runs/${run.project}/${run.runId}/log.txt`} target="_blank" rel="noreferrer">
              <ExternalLink size={13} aria-hidden="true" />
              完整日志
            </a>
            {run.hasReport ? (
              <a className="button is-small" href={`/api/runs/${run.project}/${run.runId}/report.md`} target="_blank" rel="noreferrer">
                <FileText size={13} aria-hidden="true" />
                打开报告
              </a>
            ) : null}
          </div>

          <div className="log-meta">
            <span>{log?.path || run.logPath || 'claude.rendered.log'}</span>
            <span>{log ? `${log.totalLines} lines · ${formatDateTime(log.mtime)}` : ''}</span>
          </div>

          {error ? <div className="inline-error">{error}</div> : null}

          <div className="live-log-wrap">
            <pre ref={preRef} className="agent-log live-log" onScroll={(event) => {
              const el = event.currentTarget;
              const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
              setFollow(atBottom);
            }}>
              {loading && !log ? 'Connecting to live stream…\n' : null}
              {log?.lines?.map((line, index) => (
                <span className="log-line" key={`${startLine + index}-${line.slice(0, 24)}`}>
                  <span className="log-number">{startLine + index}</span>
                  <span className="log-text">{line || ' '}</span>
                </span>
              ))}
              {!loading && !log?.lines?.length ? <span className="log-empty">No log lines yet.</span> : null}
            </pre>
            {!follow ? (
              <button
                type="button"
                className="jump-latest"
                onClick={() => {
                  setFollow(true);
                  const el = preRef.current;
                  if (el) el.scrollTop = el.scrollHeight;
                }}
              >
                <ArrowDown size={13} aria-hidden="true" />
                跳到最新
              </button>
            ) : null}
          </div>
            </>
          ) : (
            <TrajectoryPanel project={run.project} runId={run.runId} finished={Boolean(run.finished)} fill />
          )}
        </div>

        <footer className="drawer-footer">
          <span className="footer-signal">
            <Radio size={13} aria-hidden="true" />
            {run.finished ? 'complete trajectory · CC session' : 'streaming · 2s refresh'}
          </span>
          <div className="footer-actions">
            <button type="button" className="button is-small" onClick={() => copy(run.runDir, '已复制 run 目录')}>
              <Copy size={13} aria-hidden="true" />
              Copy run
            </button>
            {run.hasReport ? (
              <button type="button" className="button is-small" onClick={() => copy(`bash run.sh --verify-only ${run.runDir}`, '已复制验证命令')}>
                <Terminal size={13} aria-hidden="true" />
                Copy verify
              </button>
            ) : null}
          </div>
        </footer>
      </aside>
    </>
  );
}
