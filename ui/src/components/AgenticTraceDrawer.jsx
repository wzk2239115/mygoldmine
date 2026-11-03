import { useEffect, useState } from 'react';
import { FileText, MessageSquare, X } from 'lucide-react';
import { api } from '../api.js';
import ClaudeSessionEmbed from './ClaudeSessionEmbed.jsx';

export default function AgenticTraceDrawer({ project, runId, node, traces, live, onClose }) {
  const [traceId, setTraceId] = useState(traces[0]?.id || '');
  const [text, setText] = useState(null);
  const [error, setError] = useState('');
  const selected = traces.find((trace) => trace.id === traceId) || traces[0] || null;

  useEffect(() => {
    if (!selected || selected.kind === 'claude') {
      setText(null);
      setError('');
      return;
    }
    let cancelled = false;
    setText(null);
    setError('');
    api.traceText(project, runId, node.id, selected.id)
      .then((payload) => {
        if (!cancelled) setText(payload);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      });
    return () => { cancelled = true; };
  }, [project, runId, node.id, selected?.id, selected?.kind]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="detail-drawer agentic-trace-drawer" role="dialog" aria-modal="true" aria-label={`${node.title}轨迹`}>
        <header className="drawer-head">
          <div className="drawer-head-top">
            <div>
              <span className="drawer-kicker">{node.agent}</span>
              <h2>{node.title} · 执行轨迹</h2>
            </div>
            <button type="button" className="icon-button" title="关闭轨迹" aria-label="关闭轨迹" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
          <p className="agentic-trace-subtitle">{project}/{runId} · 只读记录，不会启动新的智能体</p>
          {traces.length > 1 ? (
            <label className="agentic-trace-picker">
              <span>选择本次节点调用</span>
              <select value={selected?.id || ''} onChange={(event) => setTraceId(event.target.value)}>
                {traces.map((trace) => <option value={trace.id} key={trace.id}>{trace.label}</option>)}
              </select>
            </label>
          ) : null}
        </header>
        <div className="drawer-body agentic-trace-body">
          {selected?.kind === 'claude' ? (
            <ClaudeSessionEmbed
              key={selected.id}
              project={project}
              runId={runId}
              node={node.id}
              trace={selected.id}
              live={live}
              tall
              chrome={false}
            />
          ) : selected ? (
            <section className="agentic-text-trace" aria-label={`${selected.label}文本轨迹`}>
              <div className="agentic-text-trace-head">
                <FileText size={15} aria-hidden="true" />
                <strong>{selected.label}</strong>
                <span>{selected.kind === 'execution' ? '红队结构化执行轨迹' : '旧格式文本日志'}</span>
              </div>
              {error ? <div className="inline-error" role="alert">{error}</div> : null}
              <pre>{text ? text.lines.join('\n') : '正在读取轨迹…'}</pre>
            </section>
          ) : (
            <div className="agentic-trace-empty">
              <MessageSquare size={22} aria-hidden="true" />
              <strong>这个节点还没有执行轨迹</strong>
              <p>当前状态为“{node.detail}”。只有实际启动节点后，才会在这里出现对应的会话或执行记录。</p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
