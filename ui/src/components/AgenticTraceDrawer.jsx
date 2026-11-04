import { createPortal } from 'react-dom';
import { useEffect, useRef, useState } from 'react';
import { FileText, MessageSquare, X } from 'lucide-react';
import { api } from '../api.js';
import { traceVersion } from '../ccui-cache.js';
import ClaudeSessionEmbed from './ClaudeSessionEmbed.jsx';
import VerifyTasks from './VerifyTasks.jsx';
import TeamAgentIcon from './TeamAgentIcon.jsx';

export default function AgenticTraceDrawer({ project, runId, node: initialNode, traces: initialTraces, live, onClose }) {
  const [node, setNode] = useState(initialNode);
  const [traces, setTraces] = useState(initialTraces);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
  const pickedTrace = useRef(false);
  const [traceId, setTraceId] = useState(initialTraces[0]?.id || '');
  useEffect(() => {
    let cancelled = false;
    const refresh = () => api.pipeline(project, runId).then(payload => {
      const fresh = payload.nodes?.find(item => item.id === initialNode.id);
      if (!cancelled && fresh) { setNode(fresh); setTraces(fresh.traces || []); }
    }).catch(() => {});
    refresh();
    const timer = setInterval(refresh, 4000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [project, runId, initialNode.id]);
  async function restartNode() {
    setRetrying(true); setRetryError('');
    try {
      const result = await api.restartNode(project, runId, node.id);
      const payload = await api.pipeline(project, runId);
      const fresh = payload.nodes.find(item => item.id === node.id);
      pickedTrace.current = false;
      if (fresh) { setNode(fresh); setTraces(fresh.traces || []); setTraceId(`${result.id}-worker`); }
    } catch (error) { setRetryError(error.message); }
    finally { setRetrying(false); }
  }
  const [showRaw, setShowRaw] = useState(false);
  const [text, setText] = useState(null);
  const [error, setError] = useState('');
  const selected = traces.find((trace) => trace.id === traceId) || traces[0] || null;

  useEffect(() => {
    if (node.id !== 'verify' || pickedTrace.current) return;
    const tasks = node.verification?.tasks || [];
    const first = tasks.find(task => task.state === 'running' && traces.some(trace => trace.id === task.traceId))
      || tasks.find(task => traces.some(trace => trace.id === task.traceId));
    if (first) { pickedTrace.current = true; setTraceId(first.traceId); }
  }, [node.verification, traces]);

  useEffect(() => { setShowRaw(false); }, [selected?.id]);

  useEffect(() => {
    if (!selected || (selected.kind === 'claude' && !showRaw)) {
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
  }, [project, runId, node.id, selected?.id, selected?.kind, selected?.size, showRaw]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return createPortal(
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="detail-drawer agentic-trace-drawer" role="dialog" aria-modal="true" aria-label={`${node.title}轨迹`}>
        <header className="drawer-head">
          <div className="drawer-head-top">
            <div>
              <span className="drawer-kicker">{node.agent}</span>
              <h2 className="agentic-trace-heading"><TeamAgentIcon node={node.id} active={node.status==='running'} size={26} />{node.title} · 执行轨迹</h2>
            </div>
            <button type="button" className="icon-button" title="关闭轨迹" aria-label="关闭轨迹" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
          <p className="agentic-trace-subtitle">{project}/{runId} · 历史执行记录</p>
          {node.environment ? (
            <details className="agentic-environment-info">
              <summary>环境能力：{node.environment.scope} · {node.environment.coverage}</summary>
              {node.environment.checksPassed || node.environment.checksFailed ? <p>{node.environment.checksPassed} 项验收通过{node.environment.checksFailed ? `，${node.environment.checksFailed} 项必要验收未通过` : ''}</p> : null}
              {node.environment.limitations.length ? <ul>{node.environment.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>具体能力范围请查看本次环境构建记录。</p>}
            </details>
          ) : null}
          {node.retrySupported === false ? <div className="agentic-retry-unavailable" role="note">
            <strong>此节点暂不支持单独重跑</strong><span>请使用项目的“重新审计”入口。</span>
          </div> : <div className="agentic-trace-picker">
            <button type="button" className="button" disabled={retrying || Boolean(node.retryReason) || node.retryReason === undefined} title={node.retryReason || '复用已有输入，仅重新执行当前节点'} onClick={restartNode}>
              {retrying ? '正在提交…' : node.retryReason === '此节点正在重跑' ? '正在重跑…' : node.retryReason ? '暂时无法重跑' : '重新运行此节点'}
            </button>
            <span>{node.retryReason || '保留历史结果，仅重跑此节点；后续节点不会自动执行'}</span>
          </div>}
          {node.recoveryNotice ? <p className="agentic-trace-subtitle">{node.recoveryNotice}</p> : null}
          {node.learning ? <p className="agentic-trace-subtitle">下次运行技能：通用 {node.learning.general ? node.learning.general.slice(0, 8) : '基础规则'} · 仓库专属 {node.learning.project ? node.learning.project.slice(0, 8) : '暂无已验证版本'} · {node.learning.candidates} 个候选待评估</p> : null}
          {retryError ? <p className="inline-error" role="alert">{retryError}</p> : null}
          {traces.some((trace) => trace.label.includes('恢复汇总')) ? <p className="agentic-trace-subtitle">本次为已有结果的恢复汇总，未重新扫描；可切换查看原始完整审计。</p> : null}
          {traces.length > 1 ? (node.id === 'verify' ? (
            <details className="verify-other-traces"><summary>日志与历史记录（{traces.length} 份）</summary>
            <label className="agentic-trace-picker">
              <span>选择执行记录</span>
              <select value={selected?.id || ''} onChange={(event) => { pickedTrace.current = true; setTraceId(event.target.value); }}>
                {traces.map((trace) => <option value={trace.id} key={trace.id}>{trace.label}</option>)}
              </select>
            </label>
            </details>
          ) : (
            <label className="agentic-trace-picker">
              <span>选择执行记录</span>
              <select value={selected?.id || ''} onChange={(event) => { pickedTrace.current = true; setTraceId(event.target.value); }}>
                {traces.map((trace) => <option value={trace.id} key={trace.id}>{trace.label}</option>)}
              </select>
            </label>
          )) : null}
          {node.id === 'verify' ? <VerifyTasks key={node.verification?.attemptId || 'original'} project={project} runId={runId} verification={node.verification} traces={traces} selectedId={selected?.id} onSelect={id=>{pickedTrace.current=true;setTraceId(id);}} /> : null}
        </header>
        <div className="drawer-body agentic-trace-body">
          {selected?.kind === 'claude' && !showRaw ? (
            <ClaudeSessionEmbed
              key={selected.id}
              project={project}
              runId={runId}
              node={node.id}
              trace={selected.id}
              version={traceVersion(selected)}
              onShowRaw={() => setShowRaw(true)}
              live={live || node.status === 'running'}
              tall
              chrome
            />
          ) : selected ? (
            <section className="agentic-text-trace" aria-label={`${selected.label}文本轨迹`}>
              <div className="agentic-text-trace-head">
                <FileText size={15} aria-hidden="true" />
                <strong>{selected.label}</strong>
                {showRaw ? <button type="button" className="traj-button" onClick={() => setShowRaw(false)}>返回会话视图</button> : null}
                <span>{selected.kind === 'execution' ? '红队结构化执行轨迹' : '执行日志'}</span>
              </div>
              {error ? <div className="inline-error" role="alert">{error}</div> : null}
              {selected.id === 'startup' ? <p className="agentic-startup-reason">{node.detail}。这是本次历史运行的启动日志。</p> : null}
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
    </>, document.body
  );
}
