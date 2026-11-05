import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, Network, RefreshCw } from 'lucide-react';
import { api } from '../api.js';
import { cx } from '../utils.js';

const POLL_MS = 5000;

const BOUNDARY_LABELS = {
  config: '配置信任',
  'process-exec': '进程执行',
  mcp: 'MCP 边界',
  sandbox: '沙箱边界',
  'control-plane': '控制面',
  filesystem: '文件系统',
  'model-loading': '模型加载',
  'http-auth': 'HTTP / 认证',
  ipc: 'IPC / 序列化',
  credentials: '凭据',
  general: '通用分析'
};

const STATUS_LABELS = {
  running: '运行中',
  completed: '已完成',
  error: '失败',
  pending: '等待'
};

const STAGE_ORDER = [
  ['profile', '画像'],
  ['jev_triage', 'Jev 初筛'],
  ['knowledge_loaded', '知识加载'],
  ['infra_analysis', '边界分析'],
  ['critic', '证伪去重'],
  ['report', '报告'],
  ['verification', '动态验证'],
  ['knowledge_writeback', '知识回写']
];

const STAGE_LABELS = {
  done: '已完成',
  in_progress: '运行中',
  pending: '等待'
};

function StatusIcon({ status, size = 13 }) {
  if (status === 'running') return <Loader2 size={size} className="agent-spin" aria-hidden="true" />;
  if (status === 'completed') return <CheckCircle2 size={size} aria-hidden="true" />;
  if (status === 'error') return <AlertTriangle size={size} aria-hidden="true" />;
  return <CircleDashed size={size} aria-hidden="true" />;
}

export default function AgentTopology({ project, runId, projectName, model, live = false }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(
    async (silent = false) => {
      if (!project || !runId) return;
      if (!silent) setLoading(true);
      try {
        const payload = await api.agents(project, runId);
        setData(payload);
        setError('');
      } catch (loadError) {
        if (!silent) setError(loadError.message);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [project, runId]
  );

  useEffect(() => {
    setData(null);
    setError('');
    load(false);
  }, [load]);

  useEffect(() => {
    if (!live) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load(true);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [live, load]);

  const agents = data?.agents || [];
  const summary = data?.summary || { total: 0, running: 0, completed: 0, failed: 0 };
  const stages = useMemo(
    () => STAGE_ORDER.map(([key, label]) => ({ key, label, status: data?.stage?.[key] || 'pending' })),
    [data?.stage]
  );

  if (loading && !data) {
    return (
      <div className="agent-topology is-loading">
        <Loader2 size={16} className="agent-spin" aria-hidden="true" />
        正在读取智能体拓扑…
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="agent-topology is-error">
        <p>{error}</p>
        <button type="button" className="button is-small" onClick={() => load(false)}>
          <RefreshCw size={13} aria-hidden="true" />
          重试
        </button>
      </div>
    );
  }

  return (
    <section className="agent-topology" aria-label="智能体拓扑">
      <div className="agent-topo-head">
        <div>
          <span className="agent-topo-title">
            <Network size={14} aria-hidden="true" />
            智能体拓扑
          </span>
          <span className="agent-topo-sub">
            {summary.total} 个边界智能体 · {summary.completed} 完成
            {summary.running ? ` · ${summary.running} 运行中` : ''}
            {summary.failed ? ` · ${summary.failed} 失败` : ''}
          </span>
        </div>
        <button type="button" className="button is-small" onClick={() => load(true)}>
          <RefreshCw size={13} aria-hidden="true" />
          刷新
        </button>
      </div>

      <div className="agent-origin">
        <span className={cx('agent-status-dot', `is-${data?.orchestrator?.status || 'pending'}`)} aria-hidden="true" />
        <div>
          <strong>{data?.orchestrator?.agent || 'security-orchestrator'}</strong>
          <small>
            {projectName || project} · {data?.orchestrator?.model || model || '模型待确定'}
          </small>
        </div>
        <span className={cx('agent-state', `is-${data?.orchestrator?.status || 'pending'}`)}>
          <StatusIcon status={data?.orchestrator?.status || 'pending'} />
          {STATUS_LABELS[data?.orchestrator?.status] || '等待'}
        </span>
      </div>

      {agents.length ? (
        <div className="agent-lane-grid">
          {agents.map((agent, index) => (
            <article key={agent.id} className={cx('agent-lane', `is-${agent.status}`)}>
              <header>
                <span className="agent-lane-index">{String(index + 1).padStart(2, '0')}</span>
                <strong>{BOUNDARY_LABELS[agent.boundary] || agent.description || agent.agent}</strong>
                <span className={cx('agent-state', `is-${agent.status}`)}>
                  <StatusIcon status={agent.status} />
                  {STATUS_LABELS[agent.status] || agent.status}
                </span>
              </header>
              <div className="agent-lane-meta">
                <code>{agent.agent}</code>
                <span>{agent.description || agent.boundary}</span>
              </div>
              <p className="agent-lane-summary">
                {agent.summary || (agent.status === 'running' ? '智能体仍在阅读源码，等待返回…' : '暂无摘要')}
              </p>
              {agent.findings !== null || agent.hypotheses !== null ? (
                <div className="agent-lane-counts">
                  {agent.findings !== null ? <span>{agent.findings} 条候选问题</span> : null}
                  {agent.hypotheses !== null ? <span>{agent.hypotheses} 条假设</span> : null}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="agent-empty">这次审计运行还没有启动边界智能体，或 raw.jsonl 尚未产生智能体调用。</div>
      )}

      <div className="agent-stage-row" aria-label="智能体基础设施审计阶段">
        {stages.map((stage) => (
          <span key={stage.key} className={cx('agent-stage', `is-${stage.status}`)} title={STAGE_LABELS[stage.status]}>
            <span className="agent-stage-dot" aria-hidden="true" />
            {stage.label}
          </span>
        ))}
      </div>
    </section>
  );
}
