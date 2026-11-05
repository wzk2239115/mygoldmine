import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, MinusCircle, RefreshCw, Workflow, Wrench } from 'lucide-react';
import { api } from '../api.js';
import { cx } from '../utils.js';
import AgenticTraceDrawer from './AgenticTraceDrawer.jsx';
import TeamAgentIcon from './TeamAgentIcon.jsx';

const STATUS_LABELS = {
  completed: '已完成',
  degraded: '降级',
  blocked: '受阻',
  failed: '失败',
  running: '运行中',
  pending: '等待',
  stopped: '已中断',
  not_started: '未执行',
  skipped: '已跳过'
};

function StatusIcon({ status }) {
  if (status === 'running') return <Loader2 size={14} className="is-spinning" aria-hidden="true" />;
  if (status === 'completed') return <CheckCircle2 size={14} aria-hidden="true" />;
  if (status === 'degraded' || status === 'blocked' || status === 'failed') return <AlertTriangle size={14} aria-hidden="true" />;
  if (status === 'stopped' || status === 'not_started' || status === 'skipped') return <MinusCircle size={14} aria-hidden="true" />;
  return <CircleDashed size={14} aria-hidden="true" />;
}

export default function AgenticPipeline({ project, runId, projectName, live = false, compact = false }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [cycleBusy,setCycleBusy]=useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [focusedNode, setFocusedNode] = useState(null);

  const load = useCallback(async (silent = false) => {
    if (!project || !runId) return;
    if (!silent) setLoading(true);
    try {
      const payload = await api.pipeline(project, runId);
      setData(payload);
      setError('');
    } catch (loadError) {
      if (!silent) setError(loadError.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [project, runId]);

  useEffect(() => {
    setData(null);
    setError('');
    setSelectedNode(null);
    setFocusedNode(null);
    load(false);
  }, [load]);

  const cycleLive=Boolean(data?.cycle?.active);
  async function controlCycle() {
    setCycleBusy(true);setError('');
    try { await (cycleLive?api.stopCycle(project):api.startCycle(project));await load(true); }
    catch(error){setError(error.message);}
    finally{setCycleBusy(false);}
  }
  const retryLive = data?.workflow?.status==='running' || data?.nodes.some(node=>node.retryReason==='此节点正在重跑' || node.continuationPending) || false;
  useEffect(() => {
    if (!live && !retryLive && !cycleLive) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load(true);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [live, retryLive, cycleLive, load]);


  return (
    <section className={cx('agentic-pipeline', compact && 'is-compact')} aria-label="正式执行链">
      <header className="agentic-pipeline-head">
        <div>
          <span className="agentic-pipeline-title"><Workflow size={16} aria-hidden="true" />正式执行链</span>
          <p>{projectName || project || '尚未选择项目'} · {data?.workflow ? `原生工作流 · 已交付 ${data.workflow.receipts} 个节点${data.workflow.status==='failed'?' · 调度失败':''}` : data?.notice || (data?.activeNode ? `当前：${data.nodes.find(node => node.id === data.activeNode)?.title || '处理中'}` : '点击节点查看执行记录')}</p>
        </div>
        <div className="agentic-pipeline-summary">
          {data?.workflow?.traces?.length ? <button type="button" className="cycle-control" title="查看整条流程的调度会话，不计入节点轨迹" onClick={()=>setSelectedNode({id:'workflow',title:'工作流调度',agent:'pipeline-coordinator',workflowOnly:true,status:data.workflow.status,traces:data.workflow.traces,retrySupported:false})}>工作流调度</button> : null}
          <button type="button" className="cycle-control" onClick={controlCycle} disabled={cycleBusy || !project || (!cycleLive && (live || retryLive)) || data?.cycle?.stopRequested}
            title={cycleLive?'当前轮结束后停止，不打断正在执行的阶段':'执行01—08，最多3轮；连续2轮无发布改善则停止'}>
            {data?.cycle?.stopRequested?'本轮结束后停止':cycleLive?'停止连续循环':'启动连续循环'}
          </button>

          {data ? `${data.summary.completed}/${data.summary.total} 完成` : '等待运行状态'}
          <button type="button" className="icon-button" title="刷新执行链" aria-label="刷新执行链" onClick={() => load(false)} disabled={loading || !runId}>
            <RefreshCw size={14} className={cx(loading && 'is-spinning')} aria-hidden="true" />
          </button>
        </div>
      </header>
      {data?.cycle?.active ? <p className="cycle-progress" role="status">连续循环 · 第 {data.cycle.current_round || 0}/{data.cycle.max_rounds || 3} 轮 · {data.cycle.stopRequested?'本轮结束后停止':'08结束后将按停止条件进入下一轮01'}</p> : null}
      {error ? <div className="inline-error" role="alert">{error}</div> : null}
      {data ? (
        <div className="agentic-cycle-scroll">
        <div className={cx('agentic-cycle-frame', data.nodes.some(node => node.status === 'running') && 'has-running-stage', cycleLive && 'has-active-cycle')}>
          <svg className="agentic-cycle-lines" viewBox="0 0 1000 330" preserveAspectRatio="none" aria-hidden="true">
            <path className="cycle-forward" d="M 62.5 24 H 937.5" />
            {[125,250,375,500,625,750,875].map(x => <path key={x} d={`M ${x-4} 20 L ${x+4} 24 L ${x-4} 28`} />)}
            <path className="cycle-return" d="M 937.5 24 H 965 Q 987 24 987 48 V 280 Q 987 306 961 306 H 39 Q 13 306 13 280 V 48 Q 13 24 39 24 H 62.5" />
            <path d="M 407 302 L 399 306 L 407 310 M 51 20 L 59 24 L 51 28" />
          </svg>
        <div className="agentic-pipeline-grid">
          {data.nodes.map((node, index) => (
            <button
              type="button"
              className={cx('agentic-node', `is-${node.status}`, node.repair?.active && 'is-repairing')}
              data-node-id={node.id}
              key={node.id}
              title={`${node.title}：${node.detail} · 点击查看执行轨迹`}
              aria-label={`查看${node.title}执行轨迹，${(node.verification || node.construction) ? `${(node.verification || node.construction).selectedCount} 条候选，` : ''}${node.traces?.length || 0} 份执行记录`}
              onPointerEnter={() => { setFocusedNode(node); }}
              onFocus={() => { setFocusedNode(node); }}
              onClick={() => { setFocusedNode(node); setSelectedNode({...node, openRepair: Boolean(node.repair)}); }}
            >
              <div className="agentic-node-top">
                <span className="agentic-node-index">{String(index + 1).padStart(2, '0')}</span>
                <span className={cx('agentic-node-status', `is-${node.status}`, node.repair?.active && 'is-repairing')}>
                  {node.repair?.active ? <Wrench size={14} className="runner-wrench" aria-hidden="true" /> : <StatusIcon status={node.status} />}
                  {node.repair?.active ? '修复中' : node.statusLabel || STATUS_LABELS[node.status] || node.status}
                </span>
              </div>
              <strong><span className="agentic-node-name"><TeamAgentIcon node={node.id} active={node.status==='running'} />{node.title}</span></strong>
              <code>{node.agent}</code>
              <p>{node.detail}</p>
              {node.triage ? <span className="agentic-node-scope">Jev 初筛 · {node.triage.processedUnits ?? '待统计'} / {node.triage.stats.units ?? '未知'} 个单元</span> : null}
              {node.environment?.status === 'partial' ? <span className="agentic-node-scope">{node.environment.scope} · 能力受限</span> : null}
              {node.repair ? <span className={cx('runner-repair-badge',node.repair.active && 'is-active')} role="status">
                <span><Wrench size={13} className={node.repair.active?'runner-wrench':''} aria-hidden="true" />{node.repair.active?'修复智能体已介入':node.repair.label}</span>
                {node.repair.missingModules.length ? <small>运行依赖：{node.repair.missingModules.join('、')}</small> : null}
              </span> : null}
              {node.flow?<span className="agentic-node-flow">总表 {node.flow.total} · 本阶段 {node.flow.recorded}<br/>未进入 {node.flow.pending}</span>:null}
              <span className="agentic-node-candidates">{node.candidateSummary}</span>
              <span className="agentic-node-trace">{node.status==='pending' && !node.traces?.length ? '尚未开始' : node.repair ? '查看修复轨迹 →' : (node.verification || node.construction) ? `查看 ${(node.verification || node.construction).selectedCount} 条候选` : node.traces?.length ? `查看 ${node.traces.length} 条轨迹` : '暂无轨迹'}</span>
            </button>
          ))}
        </div>
          <span className="agentic-cycle-caption">{cycleLive ? (data.cycle.stopRequested?'本轮结束后停止':'08结束后进入下一轮01；仅加载已发布技能') : '评估通过后，下一轮加载技能'}</span>
        </div>
        </div>
      ) : (
        <div className="agentic-pipeline-empty">
          {loading ? '正在读取八个节点的真实状态…' : '当前项目还没有可展示的执行链。'}
        </div>
      )}
      {data ? <div className="agentic-cycle-context" aria-live="polite">
        {cycleLive ? <><strong>连续循环已启动</strong><span>最多 {data.cycle.max_rounds || 3} 轮，连续两轮无发布改善则停止</span></> : focusedNode ? <><strong>{focusedNode.title}</strong><span>{focusedNode.statusLabel || STATUS_LABELS[focusedNode.status]}</span><span>{focusedNode.detail || '点击节点查看执行记录'}</span></> : <><strong>01 → 08 → 01</strong><span>经验学习与独立评估后进入下一轮</span><span>连续执行需启动循环任务</span></>}
      </div> : null}
      {selectedNode ? (
        <AgenticTraceDrawer
          key={`${project}/${runId}/${selectedNode.id}`}
          project={project}
          runId={runId}
          node={selectedNode}
          traces={selectedNode.traces || []}
          live={live}
          onStarted={() => load(true)}
          onClose={() => { setSelectedNode(null); load(true); }}
        />
      ) : null}
    </section>
  );
}
