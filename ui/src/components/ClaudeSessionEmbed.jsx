import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ExternalLink, Loader2, RefreshCw, ServerOff, Terminal } from 'lucide-react';
import { api } from '../api.js';
import { cx, formatDateTime } from '../utils.js';

const LIVE_POLL_MS = 4000;

function resolveEmbedUrl(url) {
  if (!url) return '';
  if (url.startsWith('/')) return `${window.location.origin}${url}`;
  return url;
}

const EMBED_CSS = `
  header.pwa-header-safe,
  .chat-composer-shell { display: none !important; }
  #root > div.fixed.inset-0 > div.relative.h-full.flex-shrink-0 { display: none !important; }
  #root > div.fixed.inset-0 { left: 0 !important; }
  .chat-messages-pane { padding-top: 0 !important; }
`;

export default function ClaudeSessionEmbed({ project, runId, live = false, tall = false, chrome = true }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const requestSeq = useRef(0);
  const importedAtRef = useRef('');
  const frameRef = useRef(null);

  // Keep the iframe document and its React tree alive; the inner app merges history.
  const notifyFrame = useCallback((payload) => {
    if (!payload?.sessionId) return;
    frameRef.current?.contentWindow?.postMessage({
      type: 'mygoldmine:history-updated', sessionId: payload.sessionId
    }, window.location.origin);
  }, []);

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
        if (force) notifyFrame(payload);
        return payload;
      } catch (loadError) {
        if (seq === requestSeq.current) setError(loadError.message);
        return null;
      } finally {
        if (seq === requestSeq.current && !force) setLoading(false);
      }
    },
    [project, runId, notifyFrame]
  );

  useEffect(() => {
    setSession(null);
    importedAtRef.current = '';
    load(false);
  }, [load]);

  useEffect(() => {
    if (!live || !project || !runId) return undefined;
    let cancelled = false;
    let pending = false;
    const timer = window.setInterval(async () => {
      if (pending) return;
      pending = true;
      try {
        const payload = await api.runCcui(project, runId);
        if (cancelled || !payload?.importedAt) return;
        if (payload.importedAt !== importedAtRef.current) {
          importedAtRef.current = payload.importedAt;
          setSession(payload);
          notifyFrame(payload);
        }
      } catch {
        // A failed poll keeps the existing readable transcript on screen.
      } finally {
        pending = false;
      }
    }, LIVE_POLL_MS);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [live, project, runId, notifyFrame]);

  const sync = useCallback(async () => {
    setSyncing(true);
    await load(true);
    setSyncing(false);
  }, [load]);

  const applyEmbedCss = useCallback((event) => {
    try {
      const doc = event?.currentTarget?.contentDocument || frameRef.current?.contentDocument;
      if (!doc?.head) return;
      let style = doc.getElementById('mygoldmine-embed-style');
      if (!style) {
        style = doc.createElement('style');
        style.id = 'mygoldmine-embed-style';
        doc.head.appendChild(style);
      }
      style.textContent = EMBED_CSS;
    } catch {
      // The iframe is same-origin through the board proxy; ignore transient access failures.
    }
  }, []);

  useEffect(() => {
    const ready = (event) => {
      if (event.origin !== window.location.origin || event.source !== frameRef.current?.contentWindow) return;
      if (event.data?.type !== 'mygoldmine:history-ready') return;
      // React can be ready before window.load (for example while a font request stalls).
      applyEmbedCss();
      notifyFrame({ sessionId: event.data.sessionId });
    };
    window.addEventListener('message', ready);
    return () => window.removeEventListener('message', ready);
  }, [applyEmbedCss, notifyFrame]);

  const embedUrl = useMemo(() => resolveEmbedUrl(session?.url), [session?.url]);
  const showFrame = Boolean(session?.available && session.reachable && embedUrl);
  const importedLabel = session?.importedAt ? formatDateTime(session.importedAt) : '';

  return (
    <section className={cx('ccui-embed', tall && 'ccui-embed-tall', !chrome && 'is-bare')} aria-label="Claude Code UI 会话">
      {chrome ? <div className="ccui-toolbar">
        <span className="ccui-title">
          {showFrame
            ? `Claude Code UI · ${session.messages || 0} 条消息${importedLabel ? ` · 导入于 ${importedLabel}` : ''}`
            : 'Claude Code UI'}
        </span>
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
      </div> : null}

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
            ref={frameRef}
            className="ccui-frame"
            src={embedUrl}
            title={`Claude Code UI session ${runId}`}
            allow="clipboard-read; clipboard-write"
            onLoad={applyEmbedCss}
          />
        </div>
      ) : null}
    </section>
  );
}
