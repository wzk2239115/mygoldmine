import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, MinusCircle, RefreshCw, Workflow } from 'lucide-react';
import { api } from '../api.js';
import { ccuiSessions, traceVersion } from '../ccui-cache.js';
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
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);

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
    load(false);
  }, [load]);

  useEffect(() => {
    if (!live) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load(true);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [live, load]);

  const prepareTrace = (node) => {
    const task = node.verification?.tasks.find(item => item.state === 'running') || node.verification?.tasks[0];
    const trace = node.traces?.find(item => item.id === task?.traceId) || node.traces?.[0];
    if (trace?.kind !== 'claude') return;
    ccuiSessions.load(project, runId, {node: node.id, trace: trace.id, version: traceVersion(trace)}).catch(() => {});
  };

  return (
    <section className={cx('agentic-pipeline', compact && 'is-compact')} aria-label="正式执行链">
      <header className="agentic-pipeline-head">
        <div>
          <span className="agentic-pipeline-title"><Workflow size={16} aria-hidden="true" />正式执行链</span>
          <p>{projectName || project || '尚未选择项目'} · {data?.notice || (data?.activeNode ? `当前：${data.nodes.find(node => node.id === data.activeNode)?.title || '处理中'}` : '点击节点查看执行记录')}</p>
        </div>
        <div className="agentic-pipeline-summary">
          {data ? `${data.summary.completed}/${data.summary.total} 完成` : '等待运行状态'}
          <button type="button" className="icon-button" title="刷新执行链" aria-label="刷新执行链" onClick={() => load(false)} disabled={loading || !runId}>
            <RefreshCw size={14} className={cx(loading && 'is-spinning')} aria-hidden="true" />
          </button>
        </div>
      </header>
      {error ? <div className="inline-error" role="alert">{error}</div> : null}
      {data ? (
        <div className="agentic-pipeline-grid">
          {data.nodes.map((node, index) => (
            <button
              type="button"
              className={cx('agentic-node', `is-${node.status}`)}
              data-node-id={node.id}
              key={node.id}
              title={`${node.title}：${node.detail} · 点击查看执行轨迹`}
              aria-label={`查看${node.title}执行轨迹，${node.verification ? `${node.verification.selectedCount} 条候选，` : ''}${node.traces?.length || 0} 份执行记录`}
              onPointerEnter={() => prepareTrace(node)}
              onFocus={() => prepareTrace(node)}
              onClick={() => setSelectedNode(node)}
            >
              <div className="agentic-node-top">
                <span className="agentic-node-index">{String(index + 1).padStart(2, '0')}</span>
                <span className={cx('agentic-node-status', `is-${node.status}`)}>
                  <StatusIcon status={node.status} />
                  {node.statusLabel || STATUS_LABELS[node.status] || node.status}
                </span>
              </div>
              <strong><span className="agentic-node-name"><TeamAgentIcon node={node.id} active={node.status==='running'} />{node.title}</span></strong>
              <code>{node.agent}</code>
              <p>{node.detail}</p>
              {node.environment?.status === 'partial' ? <span className="agentic-node-scope">{node.environment.scope} · 能力受限</span> : null}
              <span className="agentic-node-candidates">{node.candidateSummary}</span>
              <span className="agentic-node-trace">{node.verification ? `查看 ${node.verification.selectedCount} 条候选` : node.traces?.length ? `查看 ${node.traces.length} 条轨迹` : '暂无轨迹'}</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="agentic-pipeline-empty">
          {loading ? '正在读取八个节点的真实状态…' : '当前项目还没有可展示的执行链。'}
        </div>
      )}
      {selectedNode ? (
        <AgenticTraceDrawer
          key={`${project}/${runId}/${selectedNode.id}`}
          project={project}
          runId={runId}
          node={selectedNode}
          traces={selectedNode.traces || []}
          live={live}
          onClose={() => setSelectedNode(null)}
        />
      ) : null}
    </section>
  );
}
