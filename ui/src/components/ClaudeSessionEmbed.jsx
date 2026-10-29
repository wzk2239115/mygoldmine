import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ExternalLink, Loader2, RefreshCw, ServerOff, Terminal } from 'lucide-react';
import { api } from '../api.js';
import { cx, formatDateTime } from '../utils.js';

const LIVE_POLL_MS = 15000;

function resolveEmbedUrl(url) {
  if (!url) return '';
  if (url.startsWith('/')) return `${window.location.origin}${url}`;
  return url;
}

export default function ClaudeSessionEmbed({ project, runId, live = false, tall = false }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState('');
  const [frameKey, setFrameKey] = useState(0);
  const requestSeq = useRef(0);
  const importedAtRef = useRef('');

  const load = useCallback(
    async (force = false) => {
      if (!project || !runId) return null;
      const seq = requestSeq.current + 1;
      requestSeq.current = seq;
      if (!force) setLoading(true);
      setError('');
      try {
        const payload = await api.runCcui(project, runId, { force });
        if (seq !== requestSeq.current) return null;
        importedAtRef.current = payload.importedAt || '';
        setSession(payload);
        if (force) setFrameKey((key) => key + 1);
        return payload;
      } catch (loadError) {
        if (seq === requestSeq.current) setError(loadError.message);
        return null;
      } finally {
        if (seq === requestSeq.current && !force) setLoading(false);
      }
    },
    [project, runId]
  );

  useEffect(() => {
    setSession(null);
    setStale(false);
    setFrameKey(0);
    importedAtRef.current = '';
    load(false);
  }, [load]);

  useEffect(() => {
    if (!live || !project || !runId) return undefined;
    const timer = window.setInterval(async () => {
      const payload = await api.runCcui(project, runId).catch(() => null);
      if (!payload?.importedAt) return;
      if (payload.importedAt !== importedAtRef.current) setStale(true);
    }, LIVE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [live, project, runId]);

  const sync = useCallback(async () => {
    setSyncing(true);
    setStale(false);
    await load(true);
    setSyncing(false);
  }, [load]);

  const embedUrl = useMemo(() => resolveEmbedUrl(session?.url), [session?.url]);
  const showFrame = Boolean(session?.available && session.reachable && embedUrl);
  const importedLabel = session?.importedAt ? formatDateTime(session.importedAt) : '';

  return (
    <section className={cx('ccui-embed', tall && 'ccui-embed-tall')} aria-label="Claude Code UI 会话">
      <div className="ccui-toolbar">
        <span className="ccui-title">
          {showFrame
            ? `Claude Code UI · ${session.messages || 0} 条消息${importedLabel ? ` · 导入于 ${importedLabel}` : ''}`
            : 'Claude Code UI'}
        </span>
        {stale ? <span className="ccui-stale">有新内容</span> : null}
        <div className="ccui-actions">
          {showFrame ? (
            <button type="button" className="traj-button" onClick={sync} disabled={syncing}>
              {syncing ? <Loader2 size={15} className="traj-spin" aria-hidden="true" /> : <RefreshCw size={15} aria-hidden="true" />}
              同步会话
            </button>
          ) : null}
          {showFrame ? (
            <a className="traj-button" href={embedUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={15} aria-hidden="true" />
              新窗口打开
            </a>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="ccui-state">
          <Loader2 size={16} className="traj-spin" aria-hidden="true" /> 正在导入 CC 会话…
        </div>
      ) : null}

      {!loading && error ? (
        <div className="ccui-state is-error">
          {error}
          <button type="button" className="traj-button" onClick={() => load(false)}>
            <RefreshCw size={15} aria-hidden="true" />
            重试
          </button>
        </div>
      ) : null}

      {!loading && !error && session && !session.available ? (
        <div className="ccui-state">
          <p>该 run 没有可导入的 CC 会话：{session.reason || '未知原因'}</p>
          <p className="ccui-hint">可改用 Trajectory 标签页浏览渲染日志。</p>
        </div>
      ) : null}

      {!loading && !error && session?.available && !session.reachable ? (
        <div className="ccui-state">
          <p>
            <ServerOff size={15} aria-hidden="true" /> CloudCLI 服务未启动（127.0.0.1:3001）
          </p>
          <p className="ccui-hint">在仓库根目录执行下面的命令启动，然后重试：</p>
          <code className="ccui-command">
            <Terminal size={13} aria-hidden="true" /> bash scripts/ccui/start.sh
          </code>
          <div className="ccui-state-actions">
            <button type="button" className="traj-button" onClick={() => load(false)}>
              <RefreshCw size={15} aria-hidden="true" />
              重新检测
            </button>
          </div>
        </div>
      ) : null}

      {showFrame ? (
        <div className="ccui-frame-wrap">
          <iframe
            key={frameKey}
            className="ccui-frame"
            src={embedUrl}
            title={`Claude Code UI session ${runId}`}
            allow="clipboard-read; clipboard-write"
          />
        </div>
      ) : null}
    </section>
  );
}
