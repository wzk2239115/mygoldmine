import CandidateFlow from './CandidateFlow.jsx';
import NodeArtifacts from './NodeArtifacts.jsx';
import { createPortal } from 'react-dom';
import { useEffect, useState } from 'react';
import { FileText, MessageSquare, X } from 'lucide-react';
import { api } from '../api.js';
import { traceVersion } from '../ccui-cache.js';
import ClaudeSessionEmbed from './ClaudeSessionEmbed.jsx';
import VerifyTasks from './VerifyTasks.jsx';
import JevTriage from './JevTriage.jsx';
import LabTasks from './LabTasks.jsx';
import SceneTasks from './SceneTasks.jsx';
import JudgeTasks from './JudgeTasks.jsx';
import AgentTasks from './AgentTasks.jsx';
import TeamAgentIcon from './TeamAgentIcon.jsx';
import {initialTaskSelection, resolveTaskSelection, taskStateLabel, candidateTasks, isCandidateNode} from '../task-selection.js';

export default function AgenticTraceDrawer({ project, runId, node: initialNode, traces: initialTraces, live, onClose, onStarted }) {
  const [node, setNode] = useState(initialNode);
  const [traces, setTraces] = useState(initialTraces);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
  const [selection, setSelection] = useState(() => initialNode.workflowOnly?{...initialTaskSelection(initialNode),history:true,traceId:initialTraces[0]?.id || ''}:initialTaskSelection(initialNode));
  const [panel,setPanel]=useState(initialNode.workflowOnly?'trace':'overview');
  useEffect(() => {
    let cancelled = false;
    const refresh = () => api.pipeline(project, runId).then(payload => {
      const fresh = initialNode.workflowOnly?{...initialNode,status:payload.workflow?.status || initialNode.status,traces:payload.workflow?.traces || []}:payload.nodes?.find(item => item.id === initialNode.id);
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
      onStarted?.();
      const payload = await api.pipeline(project, runId);
      const fresh = payload.nodes.find(item => item.id === node.id);
      if (fresh) { setNode(fresh); setTraces(fresh.traces || []); setSelection(initialTaskSelection(fresh));setPanel('overview'); }
    } catch (error) { setRetryError(error.message); }
    finally { setRetrying(false); }
  }
  const [showRaw, setShowRaw] = useState(false);
  const [text, setText] = useState(null);
  const [error, setError] = useState('');
  const {batchId, task: selectedTask, trace: selected} = resolveTaskSelection(node, traces, selection);
  const teamNode = isCandidateNode(node);
  const memberView = teamNode && Boolean(selectedTask || selected);
  useEffect(() => {
    if (selection.batchId !== batchId) {
      setSelection(initialTaskSelection(node));
    }
  }, [batchId, selection.batchId]);
  useEffect(() => {
    if (node.id !== 'learner' || !selection.traceId?.endsWith('-worker')) return;
    const prefix = selection.traceId.slice(0, -7);
    const session = traces.find(trace => trace.id.startsWith(prefix + '-') && trace.kind === 'claude');
    if (session) setSelection(current => ({...current, history: true, traceId: session.id}));
  }, [node.id, traces, selection.traceId]);
  const selectTask = taskId => {setPanel('trace');setSelection({batchId, taskId, history: false, traceId: ''});};
  const selectHistory = traceId => {setPanel('trace');setSelection({batchId, taskId: null, history: true, traceId});};
  const backToMembers = () => {setPanel('overview');setSelection(initialTaskSelection(node));};

  useEffect(() => { setShowRaw(false); }, [selected?.id]);

  useEffect(() => {
    if (!selected || (['claude', 'execution'].includes(selected.kind) && !showRaw)) {
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
              <span className="drawer-kicker">{memberView ? node.title : node.agent}</span>
              <h2 className="agentic-trace-heading"><TeamAgentIcon node={node.id} active={node.status==='running'} size={26} />{memberView ? `${selectedTask?.id || '历史记录'} · 执行轨迹` : teamNode ? `${node.title} · 队员` : `${node.title} · 执行轨迹`}</h2>
            </div>
            <button type="button" className="icon-button" title="关闭轨迹" aria-label="关闭轨迹" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
          <p className="agentic-trace-subtitle">{project}/{runId} · 历史执行记录</p>
          {memberView ? <button type="button" className="traj-button member-back" onClick={backToMembers}>← 返回队员列表</button> : null}
          {!memberView ? <>
          {node.environment ? (
            <details className="agentic-environment-info">
              <summary>环境能力：{node.environment.scope} · {node.environment.coverage}</summary>
              {node.environment.checksPassed || node.environment.checksFailed ? <p>{node.environment.checksPassed} 项验收通过{node.environment.checksFailed ? `，${node.environment.checksFailed} 项必要验收未通过` : ''}</p> : null}
              {node.environment.limitations.length ? <ul>{node.environment.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>具体能力范围请查看本次环境构建记录。</p>}
            </details>
          ) : null}
          {node.workflowOnly ? <p className="agentic-trace-subtitle">整条流程的只读调度会话，不计入01—08节点执行轨迹。</p> : node.retrySupported === false ? <div className="agentic-retry-unavailable" role="note">
            <strong>此节点暂不支持单独重跑</strong><span>请使用项目的“重新审计”入口。</span>
          </div> : <div className="agentic-trace-picker">
            <button type="button" className="button" disabled={retrying || Boolean(node.retryReason) || node.retryReason === undefined} title={node.retryReason || '复用已有输入，仅重新执行当前节点'} onClick={restartNode}>
              {retrying ? '正在提交…' : node.retryReason === '此节点正在重跑' ? '正在重跑…' : node.retryReason ? '暂时无法重跑' : '重新运行此节点'}
            </button>
            <span>{node.retryReason || (['verify','redteam-lab','redteam-agent','judge'].includes(node.id)?'自动排空当前候选；按前置条件衔接后续节点与08学习，保留历史结果。':'保留历史结果，仅重跑此节点；后续节点不会自动执行')}</span>
          </div>}
          {node.recoveryNotice ? <p className="agentic-trace-subtitle">{node.recoveryNotice}</p> : null}
          {node.learning ? <details className="agentic-learning-info"><summary>下次运行技能</summary><p className="agentic-trace-subtitle">下次运行技能：通用 {node.learning.general ? node.learning.general.slice(0, 8) : '基础规则'} · 仓库专属 {node.learning.project ? node.learning.project.slice(0, 8) : '暂无已验证版本'} · {node.learning.candidates} 个候选待评估</p></details> : null}
          {retryError ? <p className="inline-error" role="alert">{retryError}</p> : null}
          {traces.some((trace) => trace.label.includes('恢复汇总')) ? <p className="agentic-trace-subtitle">本次为已有结果的恢复汇总，未重新扫描；可切换查看原始完整审计。</p> : null}
          {traces.length > 1 ? (teamNode ? (
            <details className="verify-other-traces"><summary>日志与历史记录（{traces.length} 份）</summary>
            <label className="agentic-trace-picker">
              <span>选择执行记录</span>
              <select value={selected?.id || ''} onChange={(event) => selectHistory(event.target.value)}>
                <option value="" disabled>请选择执行记录</option>
                {traces.map((trace) => <option value={trace.id} key={trace.id}>{trace.label}</option>)}
              </select>
            </label>
            </details>
          ) : (
            <label className="agentic-trace-picker">
              <span>选择执行记录</span>
              <select value={selected?.id || ''} onChange={(event) => selectHistory(event.target.value)}>
                <option value="" disabled>请选择执行记录</option>
                {traces.map((trace) => <option value={trace.id} key={trace.id}>{trace.label}</option>)}
              </select>
            </label>
          )) : null}
          </> : null}
        </header>
        {!node.workflowOnly ? <nav className="node-detail-actions" aria-label="节点内容">
          <button type="button" className="traj-button" aria-pressed={panel==='overview'} onClick={backToMembers}>节点概览</button>
          <button type="button" className="traj-button" aria-pressed={panel==='trace'} disabled={!traces.length} onClick={()=>selectHistory(node.repair?.traceId || traces[0]?.id)}>查看执行轨迹</button>
          <button type="button" className="traj-button" aria-pressed={panel==='artifacts'} onClick={()=>{setPanel('artifacts');setSelection(initialTaskSelection(node));}}>查看产物</button>
        </nav> : null}
        <CandidateFlow flow={node.flow} />
        {node.id === 'orchestrator' ? <JevTriage triage={node.triage} /> : null}
        {panel!=='artifacts' && (selectedTask || selected) ? <div className="agentic-current-task" data-team={node.id === 'verify' ? 'blue' : 'red'} aria-live="polite">
          <div><strong>{selectedTask ? `当前候选：${selectedTask.id}` : '当前执行记录'}</strong><span className={`task-state state-${selectedTask?.state || 'history'}`}>{selectedTask ? taskStateLabel(selectedTask) : '日志与历史记录'}</span></div>
          <p title={selectedTask?.title || selected?.label}>{selectedTask?.title || selected?.label}</p>
        </div> : null}
        <div className={`drawer-body agentic-trace-body ${teamNode && !memberView ? 'member-roster-body' : ''}`}>
          {panel==='artifacts' ? <NodeArtifacts project={project} runId={runId} node={node.id} /> : teamNode && !memberView ? <>
            <p className="member-roster-hint">选择一位{node.id === 'verify' ? '蓝队验证' : node.id === 'judge' ? '独立审核' : node.id === 'visual' ? '场景设计' : node.id === 'redteam-agent' ? '红队执行' : '红队构建'}队员，查看他的执行轨迹。</p>
          {node.id === 'judge' ? <JudgeTasks review={node.review} onSelect={selectTask} /> : null}
          {node.id === 'visual' ? <SceneTasks scenes={node.scenes} onSelect={selectTask} /> : null}
          {node.id === 'redteam-agent' ? <AgentTasks execution={node.execution} onSelect={selectTask} /> : null}
          {node.id === 'redteam-lab' ? <LabTasks key={node.construction?.attemptId || 'original'} project={project} runId={runId} construction={node.construction} selectedId={selectedTask?.id} onSelect={selectTask} /> : null}
          {node.id === 'verify' ? <VerifyTasks key={node.verification?.attemptId || 'original'} project={project} runId={runId} verification={node.verification} selectedId={selectedTask?.id} onSelect={selectTask} /> : null}
            {!(candidateTasks(node)?.tasks || []).length ? <p className="member-roster-hint">当前批次尚未生成队员任务，请等待任务启动或查看启动日志。</p> : null}
          </> : panel==='overview' ? <div className="agentic-trace-empty"><MessageSquare size={22} aria-hidden="true"/><strong>{node.title}</strong><p>{node.detail}</p><p>点击“查看执行轨迹”加载会话，或点击“查看产物”阅读报告与文件。</p></div> : ['claude', 'execution'].includes(selected?.kind) && !showRaw ? (
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
              label={selectedTask ? `${selectedTask.id} · 执行轨迹` : selected.label}
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
              <strong>{selectedTask ? `${selectedTask.id} · ${taskStateLabel(selectedTask)}` : '这个节点还没有执行轨迹'}</strong>
              <p>{selectedTask ? selectedTask.state === 'queued' ? '此候选正在等待执行，启动后将在这里显示它的轨迹。' : selectedTask.state === 'running' ? '此候选已开始运行，正在等待它的第一条执行记录。' : selectedTask.reason || '此候选尚无会话记录，可查看对应报告。' : `当前状态为“${node.detail}”。实际启动节点后会显示执行记录。`}</p>
            </div>
          )}
        </div>
      </aside>
    </>, document.body
  );
}
