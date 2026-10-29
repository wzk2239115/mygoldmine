import { useEffect, useMemo, useState } from 'react';
import { hierarchy, tree as treeLayout } from 'd3-hierarchy';
import { ChevronRight, Copy, ExternalLink, GitBranch, Layers3, Minus, Plus, RefreshCw, RotateCcw, ShieldAlert } from 'lucide-react';
import { api } from '../api.js';
import { copyText, cx, formatDate, truncate } from '../utils.js';

const STATUS_COLOR = {
  root: '#1c1b16',
  scope: '#e4dccb',
  covered: '#4b654d',
  unknown: '#b9af99',
  critical: '#b23a2b',
  high: '#c05d2c',
  medium: '#a66a18',
  low: '#3e596f',
  info: '#746c5b',
  closed: '#8f8674',
  gate: '#a66a18',
  sink: '#b23a2b',
  impact: '#8e2b20',
  goal: '#1c1b16',
  entry: '#3e596f',
  precondition: '#a66a18'
};

function colorFor(node) {
  if (node.kind === 'finding' && node.severity) return STATUS_COLOR[node.severity] || STATUS_COLOR.info;
  return STATUS_COLOR[node.status] || STATUS_COLOR.scope;
}

function isDark(node) {
  return ['root', 'finding', 'goal', 'sink', 'impact'].includes(node.kind);
}

function buildLayout(rootData) {
  if (!rootData) return null;
  const root = hierarchy(rootData);
  const layout = treeLayout().nodeSize([38, 225]);
  layout(root);
  const nodes = root.descendants();
  const minX = Math.min(...nodes.map((node) => node.x));
  const maxX = Math.max(...nodes.map((node) => node.x));
  const maxDepth = Math.max(...nodes.map((node) => node.depth));
  return {
    root,
    nodes,
    links: root.links(),
    width: 260 + maxDepth * 225,
    height: maxX - minX + 100,
    minX
  };
}

function TreeCanvas({ data, selected, onSelect, zoom, setZoom }) {
  const layout = useMemo(() => buildLayout(data), [data]);
  if (!layout) return <div className="map-empty">没有树数据</div>;
  const x = (node) => 28 + node.y;
  const y = (node) => node.x - layout.minX + 50;
  return (
    <div className="map-canvas-wrap">
      <div className="map-zoom">
        <button type="button" className="icon-button is-small" title="放大" aria-label="放大" onClick={() => setZoom((value) => Math.min(1.8, value + 0.12))}>
          <Plus size={14} />
        </button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" className="icon-button is-small" title="缩小" aria-label="缩小" onClick={() => setZoom((value) => Math.max(0.45, value - 0.12))}>
          <Minus size={14} />
        </button>
        <button type="button" className="icon-button is-small" title="重置" aria-label="重置" onClick={() => setZoom(1)}>
          <RotateCcw size={13} />
        </button>
      </div>
      <div className="map-canvas-scroll">
        <svg
          className="map-svg"
          style={{ width: layout.width * zoom, height: layout.height * zoom }}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="img"
          aria-label="项目审计树"
        >
          <rect width={layout.width} height={layout.height} fill="transparent" />
          {layout.links.map((link) => {
            const sx = x(link.source) + 200;
            const sy = y(link.source) + 14;
            const tx = x(link.target);
            const ty = y(link.target) + 14;
            return <path key={`${link.source.data.id}-${link.target.data.id}`} className="map-link" d={`M${sx},${sy} C${sx + 50},${sy} ${tx - 50},${ty} ${tx},${ty}`} />;
          })}
          {layout.nodes.map((node) => {
            const item = node.data;
            const fill = colorFor(item);
            const dark = isDark(item);
            const active = selected?.id === item.id;
            return (
              <g key={item.id} className={cx('map-node', active && 'is-selected')} transform={`translate(${x(node)},${y(node)})`} onClick={() => onSelect(item)} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') onSelect(item); }}>
                <rect width="200" height="30" rx="1" fill={fill} stroke={active ? '#b23a2b' : '#403c32'} strokeWidth={active ? 2 : 1} />
                <text x="7" y="13" className="map-node-label" fill={dark ? '#fff8ec' : '#1c1b16'}>{truncate(item.label || item.id, 31)}</text>
                <text x="7" y="24" className="map-node-sub" fill={dark ? '#fff8ec' : '#746c5b'} opacity=".72">
                  {truncate(item.finding_id || item.path || item.kind || '', 34)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

export default function MapView({ board, filters, onOpenFinding, onToast }) {
  const project = useMemo(() => {
    const projects = board?.projects || [];
    return projects.find((item) => item.id === filters.project) || projects.find((item) => item.hasReport) || projects[0] || null;
  }, [board, filters.project]);
  const runId = project?.latestReportRunId || project?.latestRunId || '';
  const [model, setModel] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mode, setMode] = useState('project');
  const [attackId, setAttackId] = useState('');
  const [selected, setSelected] = useState(null);
  const [zoom, setZoom] = useState(1);

  const load = async () => {
    if (!project || !runId) return;
    setLoading(true);
    setError('');
    try {
      const payload = await api.visual(project.id, runId);
      setModel(payload);
      setSelected(null);
      setAttackId(payload.trees?.attacks?.[0]?.finding_id || '');
    } catch (loadError) {
      setModel(null);
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [project?.id, runId]);

  const tree = mode === 'project' ? model?.trees?.project : mode === 'coverage' ? model?.trees?.coverage : (model?.trees?.attacks || []).find((item) => item.finding_id === attackId) || model?.trees?.attacks?.[0];
  const attacks = model?.trees?.attacks || [];
  const selectedFinding = selected?.finding_id ? board?.findings?.find((item) => item.project === project?.id && item.id === selected.finding_id) : null;

  if (!project) return <div className="map-empty">没有可读取的项目。</div>;

  return (
    <div className="map-view">
      <div className="map-head">
        <div className="map-title">
          <span className="eyebrow">PROJECT CARTOGRAPHY / {project.id}</span>
          <h2>{model?.project_name || project.name}</h2>
          <p>
            {model?.audit_id || 'audit'} · {model?.direction || project.direction || 'direction unknown'} ·{' '}
            {project.findingsCount} findings · {runId}
          </p>
        </div>
        <div className="map-head-actions">
          <div className="map-mode-switch">
            <button type="button" className={cx(mode === 'project' && 'is-active')} onClick={() => { setMode('project'); setSelected(null); }}>
              <GitBranch size={14} /> 结构
            </button>
            <button type="button" className={cx(mode === 'coverage' && 'is-active')} onClick={() => { setMode('coverage'); setSelected(null); }}>
              <Layers3 size={14} /> 覆盖
            </button>
            <button type="button" className={cx(mode === 'attack' && 'is-active')} onClick={() => { setMode('attack'); setSelected(null); }}>
              <ShieldAlert size={14} /> 攻击路径
            </button>
          </div>
          <button type="button" className={cx('icon-button', loading && 'is-spinning')} title="刷新视觉模型" aria-label="刷新视觉模型" onClick={load}>
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {loading && !model ? <div className="map-loading">正在读取 visual-model.json…</div> : null}
      {error ? (
        <div className="map-empty">
          <strong>这个 run 还没有视觉模型</strong>
          <p>{error}</p>
          <code>python3 .claude/skills/project-cartographer/scripts/build_visual_model.py --project {project.id}</code>
        </div>
      ) : null}

      {model ? (
        <>
          <div className="map-body">
            <section className="map-stage">
              {model.cover ? (
                <div className="map-cover">
                  <img src={`/api/visual/${encodeURIComponent(project.id)}/${encodeURIComponent(runId)}/asset?path=cover.webp`} alt={`${project.name} audit cover`} />
                  <div>
                    <span className="eyebrow">AUDIT CASE FILE</span>
                    <strong>{model.project_name}</strong>
                    <p>{model.counts?.findings || 0} findings · generated {formatDate(model.generated_at)}</p>
                  </div>
                </div>
              ) : null}
              {mode === 'attack' && attacks.length ? (
                <div className="map-attack-tabs">
                  {attacks.map((attack) => (
                    <button key={attack.finding_id || attack.id} type="button" className={cx((attack.finding_id === attackId) && 'is-active')} onClick={() => { setAttackId(attack.finding_id); setSelected(null); }}>
                      <span>{attack.finding_id}</span>
                      <small>{truncate(attack.label, 28)}</small>
                    </button>
                  ))}
                </div>
              ) : null}
              <TreeCanvas data={tree} selected={selected} onSelect={setSelected} zoom={zoom} setZoom={setZoom} />
              <div className="map-legend">
                <span><i className="is-scope" /> scope</span>
                <span><i className="is-critical" /> critical</span>
                <span><i className="is-high" /> high</span>
                <span><i className="is-covered" /> covered</span>
                <span><i className="is-unknown" /> unknown</span>
              </div>
            </section>

            <aside className="map-detail">
              {selected ? (
                <>
                  <span className="eyebrow">{selected.kind || 'node'}</span>
                  <h3>{selected.label}</h3>
                  <dl>
                    {selected.finding_id ? <><dt>Finding</dt><dd>{selected.finding_id}</dd></> : null}
                    {selected.severity ? <><dt>Severity</dt><dd>{selected.severity}</dd></> : null}
                    {selected.status ? <><dt>Status</dt><dd>{selected.status}</dd></> : null}
                    {selected.path ? <><dt>Path</dt><dd><code>{selected.path}</code></dd></> : null}
                    {selected.files ? <><dt>Files</dt><dd>{selected.files}</dd></> : null}
                  </dl>
                  {selectedFinding ? (
                    <button type="button" className="button is-primary" onClick={() => onOpenFinding(selectedFinding)}>
                      打开 finding <ChevronRight size={14} />
                    </button>
                  ) : null}
                  {selected.path ? (
                    <button type="button" className="button" onClick={async () => { const ok = await copyText(selected.path); onToast?.(ok ? `已复制：${selected.path}` : '复制失败'); }}>
                      <Copy size={13} /> 复制路径
                    </button>
                  ) : null}
                </>
              ) : (
                <>
                  <span className="eyebrow">READING THE MAP</span>
                  <h3>从结构到证据</h3>
                  <p>结构树按源码目录和 finding 证据路径生成；覆盖树按审计阶段生成；攻击路径把入口、前置条件、sink 和影响串起来。</p>
                  <div className="map-stat-row">
                    <div><strong>{model.counts?.findings || 0}</strong><span>findings</span></div>
                    <div><strong>{model.counts?.critical || 0}</strong><span>critical</span></div>
                    <div><strong>{model.counts?.high || 0}</strong><span>high</span></div>
                  </div>
                  {model.url ? <a className="map-source-link" href={model.url} target="_blank" rel="noreferrer">打开上游仓库 <ExternalLink size={12} /></a> : null}
                </>
              )}
            </aside>
          </div>
        </>
      ) : null}
    </div>
  );
}
