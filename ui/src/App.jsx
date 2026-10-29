import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, BadgeCheck, Database, GitBranch, LayoutGrid, List, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from './api.js';
import { countBy, cx } from './utils.js';
import Board from './components/Board.jsx';
import DetailDrawer from './components/DetailDrawer.jsx';
import LiveRunDrawer from './components/LiveRunDrawer.jsx';
import RunsDrawer from './components/RunsDrawer.jsx';
import LiveRunsStrip from './components/LiveRunsStrip.jsx';
import MapView from './components/MapView.jsx';
import RefineryStrip from './components/RefineryStrip.jsx';
import Sidebar from './components/Sidebar.jsx';
import StatsStrip from './components/StatsStrip.jsx';
import TableView from './components/TableView.jsx';
import Toast from './components/Toast.jsx';
import TopBar from './components/TopBar.jsx';

const DEFAULT_FILTERS = {
  project: 'all',
  severities: [],
  verdicts: [],
  cveOnly: false,
  reviewOnly: false,
  hideInbox: true,
  query: ''
};

function loadFilters() {
  try {
    const raw = localStorage.getItem('vul-ai-filters');
    if (!raw) return DEFAULT_FILTERS;
    const saved = JSON.parse(raw);
    delete saved.scope;
    return { ...DEFAULT_FILTERS, ...saved };
  } catch {
    return DEFAULT_FILTERS;
  }
}

function deriveStats(findings) {
  const severity = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  const status = { inbox: 0, triage: 0, reproduce: 0, cve: 0, closed: 0, archived: 0 };
  const verdict = { untriaged: 0, tp: 0, fp: 0, duplicate: 0, unclear: 0 };
  for (const finding of findings) {
    severity[finding.severity] += 1;
    status[finding.status] += 1;
    verdict[finding.verdict] += 1;
  }
  return {
    total: findings.length,
    curated: findings.filter((finding) => finding.curated).length,
    tp: findings.filter((finding) => finding.verdict === 'tp').length,
    cveCandidates: findings.filter((finding) => finding.cveTier).length,
    cveTrack: findings.filter((finding) => finding.status === 'cve').length,
    closed: findings.filter((finding) => finding.status === 'closed').length,
    severity,
    status,
    verdict
  };
}

function toRunView(run) {
  return {
    ...run,
    projectName: run.projectName || run.project,
    finished: !run.isLive,
    elapsedSeconds: Number(run.durationSeconds) || 0,
    logMtime: run.updatedAt || run.startedAt || null,
    timeoutSeconds: 0,
    container: ''
  };
}

function LoadingBoard() {
  return (
    <div className="loading-state">
      <div className="loading-mark">V/A</div>
      <div>
        <strong>读取审计报告</strong>
        <p>正在聚合 runs/*/*/audit-report.json 与二次审计状态…</p>
      </div>
      <RefreshCw className="is-spinning" size={18} aria-hidden="true" />
    </div>
  );
}

export default function App() {
  const [board, setBoard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [filters, setFiltersState] = useState(loadFilters);
  const [view, setViewState] = useState(() => localStorage.getItem('vul-ai-view') || 'board');
  const [theme, setTheme] = useState(() => localStorage.getItem('vul-ai-theme') || 'light');
  const [selectedKey, setSelectedKey] = useState(null);
  const [liveRun, setLiveRun] = useState(null);
  const [runsOpen, setRunsOpen] = useState(false);
  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState('');
  const [toast, setToast] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const liveSignatureRef = useRef('');

  const setFilters = useCallback((next) => {
    setFiltersState((current) => {
      const value = typeof next === 'function' ? next(current) : next;
      localStorage.setItem('vul-ai-filters', JSON.stringify(value));
      return value;
    });
  }, []);

  const setView = useCallback((next) => {
    setViewState(next);
    localStorage.setItem('vul-ai-view', next);
  }, []);

  const showToast = useCallback((message) => setToast(message), []);

  const openRuns = useCallback(async () => {
    setSelectedKey(null);
    setLiveRun(null);
    setRunsOpen(true);
    setRunsLoading(true);
    setRunsError('');
    try {
      const payload = await api.runs();
      setRuns(payload.runs || []);
    } catch (error) {
      setRunsError(error.message);
    } finally {
      setRunsLoading(false);
    }
  }, []);

  const loadBoard = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    setError('');
    try {
      const payload = await api.board();
      setBoard(payload);
      liveSignatureRef.current = (payload.liveRuns || []).map((run) => `${run.project}:${run.runId}`).join('|');
      setLoading(false);
    } catch (loadError) {
      setError(loadError.message);
      setLoading(false);
    } finally {
      if (!silent) setRefreshing(false);
    }
  }, []);

  const applyLive = useCallback(async () => {
    try {
      const payload = await api.live();
      const signature = (payload.liveRuns || []).map((run) => `${run.project}:${run.runId}`).join('|');
      setBoard((current) => {
        if (!current) return current;
        const projects = new Map(current.projects.map((project) => [project.id, project]));
        for (const liveProject of payload.projects || []) {
          const existing = projects.get(liveProject.id);
          if (existing) {
            projects.set(liveProject.id, {
              ...existing,
              isLive: true,
              liveRunId: liveProject.latestRunId,
              state: liveProject.state,
              logPath: liveProject.logPath,
              startedAt: liveProject.startedAt,
              updatedAt: liveProject.updatedAt,
              timeoutSeconds: liveProject.timeoutSeconds,
              model: liveProject.model || existing.model,
              container: liveProject.container,
              lastLogLine: liveProject.lastLogLine,
              logMtime: liveProject.logMtime
            });
          } else {
            projects.set(liveProject.id, {
              ...liveProject,
              findingsCount: 0,
              curatedCount: 0,
              cveCount: 0,
              severityCounts: { critical: 0, high: 0, medium: 0, low: 0, info: 0 },
              runCount: 1,
              hasReport: false
            });
          }
        }
        const liveIds = new Set((payload.projects || []).map((project) => project.id));
        const mergedProjects = [...projects.values()]
          .map((project) => {
            if (!project.isLive || liveIds.has(project.id)) return project;
            if (!project.hasReport && project.findingsCount === 0) return null;
            return { ...project, isLive: false, liveRunId: '', state: project.hasReport ? 'completed' : 'unknown' };
          })
          .filter(Boolean);
        return {
          ...current,
          projects: mergedProjects,
          liveRuns: payload.liveRuns || [],
          stats: { ...current.stats, live: (payload.liveRuns || []).length }
        };
      });

      const previous = liveSignatureRef.current;
      liveSignatureRef.current = signature;
      if (previous && previous !== signature) {
        await loadBoard(true);
        showToast('运行状态变化，看板已刷新');
      }
    } catch {
      // keep the last board state on transient polling errors
    }
  }, [loadBoard, showToast]);

  useEffect(() => {
    loadBoard();
    const timer = window.setInterval(() => loadBoard(true), 60000);
    return () => window.clearInterval(timer);
  }, [loadBoard]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') applyLive();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [applyLive]);

  useEffect(() => {
    if (!liveRun) return;
    const next = board?.liveRuns?.find((run) => run.project === liveRun.project && run.runId === liveRun.runId);
    if (next) {
      setLiveRun((current) => (current ? { ...current, ...next } : next));
    } else if (!liveRun.finished) {
      setLiveRun((current) => (current ? { ...current, finished: true, state: 'finished' } : current));
    }
  }, [board?.liveRuns, liveRun?.project, liveRun?.runId]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('vul-ai-theme', theme);
  }, [theme]);

  const findings = board?.findings || [];
  const selected = useMemo(
    () => findings.find((finding) => finding.key === selectedKey) || null,
    [findings, selectedKey]
  );

  const scoped = useMemo(() => {
    let items = findings;
    if (filters.hideInbox) items = items.filter((finding) => finding.status !== 'inbox');
    if (filters.reviewOnly) items = items.filter((finding) => finding.reviewReady);
    if (filters.project !== 'all') items = items.filter((finding) => finding.project === filters.project);
    if (filters.cveOnly) items = items.filter((finding) => finding.cveTier);
    const query = filters.query.trim().toLowerCase();
    if (query) {
      items = items.filter((finding) =>
        [
          finding.id,
          finding.title,
          finding.project,
          finding.projectName,
          finding.category,
          finding.rootCause,
          finding.notes,
          ...finding.cwe
        ]
          .join(' ')
          .toLowerCase()
          .includes(query)
      );
    }
    return items;
  }, [findings, filters.project, filters.cveOnly, filters.reviewOnly, filters.hideInbox, filters.query]);

  const filtered = useMemo(() => {
    let items = scoped;
    if (filters.severities.length) items = items.filter((finding) => filters.severities.includes(finding.severity));
    if (filters.verdicts.length) items = items.filter((finding) => filters.verdicts.includes(finding.verdict));
    return items;
  }, [scoped, filters.severities, filters.verdicts]);

  const facetStats = useMemo(
    () => ({
      severity: countBy(scoped, (finding) => finding.severity),
      verdict: countBy(scoped, (finding) => finding.verdict)
    }),
    [scoped]
  );

  const updateFinding = useCallback(
    async (finding, patch) => {
      const previous = board?.findings?.find((item) => item.key === finding.key);
      if (!previous) return;
      setBoard((current) => {
        if (!current) return current;
        const nextFindings = current.findings.map((item) =>
          item.key === finding.key
            ? { ...item, ...patch, touched: true, curated: true, updatedAt: new Date().toISOString() }
            : item
        );
        return { ...current, findings: nextFindings, stats: deriveStats(nextFindings) };
      });
      try {
        await api.update(finding.project, finding.id, patch);
        showToast('已保存');
        await loadBoard(true);
      } catch (updateError) {
        setBoard((current) => {
          if (!current) return current;
          const nextFindings = current.findings.map((item) => (item.key === finding.key ? previous : item));
          return { ...current, findings: nextFindings, stats: deriveStats(nextFindings) };
        });
        showToast(`保存失败：${updateError.message}`);
      }
    },
    [board, loadBoard, showToast]
  );

  const moveFinding = useCallback(
    (key, status) => {
      const finding = findings.find((item) => item.key === key);
      if (!finding || finding.status === status) return;
      updateFinding(finding, { status });
    },
    [findings, updateFinding]
  );

  const hasFilters = Boolean(
    filters.project !== 'all' ||
      filters.severities.length ||
      filters.verdicts.length ||
      filters.cveOnly ||
      filters.reviewOnly ||
      !filters.hideInbox ||
      filters.query
  );

  const clearFilters = () => setFilters(DEFAULT_FILTERS);

  return (
    <div className={cx('app', sidebarOpen && 'sidebar-open', selected && 'has-drawer')}>
      <nav className="rail" aria-label="主导航">
        <div className="rail-brand" title="VUL/AI">
          <span>V</span>
          <i>/</i>
          <span>A</span>
        </div>
        <div className="rail-group">
          <button
            type="button"
            className={cx('rail-button', view === 'board' && 'is-active')}
            title="看板"
            aria-label="看板"
            onClick={() => setView('board')}
          >
            <LayoutGrid size={18} />
          </button>
          <button
            type="button"
            className={cx('rail-button', view === 'table' && 'is-active')}
            title="表格"
            aria-label="表格"
            onClick={() => setView('table')}
          >
            <List size={19} />
          </button>
          <button
            type="button"
            className={cx('rail-button', view === 'map' && 'is-active')}
            title="项目地图"
            aria-label="项目地图"
            onClick={() => setView('map')}
          >
            <GitBranch size={18} />
          </button>
          <button
            type="button"
            className={cx('rail-button', filters.cveOnly && 'is-active')}
            title="只看 CVE 候选"
            aria-label="只看 CVE 候选"
            onClick={() => setFilters((current) => ({ ...current, cveOnly: !current.cveOnly }))}
          >
            <ShieldAlert size={18} />
            {board?.stats?.cveCandidates ? <span className="rail-badge">{board.stats.cveCandidates}</span> : null}
          </button>
          <button
            type="button"
            className={cx('rail-button', filters.reviewOnly && 'is-active')}
            title="待验收：只看图文精品"
            aria-label="待验收：只看图文精品"
            onClick={() => setFilters((current) => ({ ...current, reviewOnly: !current.reviewOnly }))}
          >
            <BadgeCheck size={18} />
            {board?.stats?.reviewReady ? <span className="rail-badge">{board.stats.reviewReady}</span> : null}
          </button>
        </div>
        <div className="rail-bottom">
          <span className="rail-version">v0.1</span>
        </div>
      </nav>

      {sidebarOpen ? <button type="button" className="sidebar-backdrop" aria-label="关闭筛选" onClick={() => setSidebarOpen(false)} /> : null}

      <Sidebar
        board={board}
        filters={filters}
        setFilters={setFilters}
        facets={facetStats}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="main">
        <TopBar
          board={board}
          filters={filters}
          setFilters={setFilters}
          view={view}
          setView={setView}
          onRefresh={() => loadBoard()}
          refreshing={refreshing}
          theme={theme}
          onOpenRuns={openRuns}
          onToggleTheme={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
          onToggleSidebar={() => setSidebarOpen((value) => !value)}
        />

        <StatsStrip stats={board?.stats} projects={board?.projects} />

        {view === 'board' && board?.stats ? <RefineryStrip stats={board.stats} /> : null}

        <LiveRunsStrip
          runs={board?.liveRuns}
          onOpen={(run) => {
            setSelectedKey(null);
            setLiveRun(run);
          }}
        />

        {error ? (
          <div className="error-banner" role="alert">
            <AlertTriangle size={15} aria-hidden="true" />
            <span>{error}</span>
            <button type="button" className="button is-small" onClick={() => loadBoard()}>
              重试
            </button>
          </div>
        ) : null}

        <div className="content">
          <div className="content-head">
            <div className="content-summary">
              <span className="summary-count">{filtered.length}</span>
              <span>
                findings
                {filters.project !== 'all' ? ` · ${board?.projects?.find((project) => project.id === filters.project)?.name || filters.project}` : ''}
              </span>
              {hasFilters ? (
                <button type="button" className="link-button" onClick={clearFilters}>
                  清除筛选
                </button>
              ) : null}
            </div>
          </div>

          {loading && !board ? <LoadingBoard /> : null}

          {!loading && board && view === 'board' ? (
            <Board
              findings={filtered}
              hiddenStatuses={filters.hideInbox ? ['inbox'] : []}
              statusTotals={board.stats?.status || {}}
              onOpen={(finding) => {
                setLiveRun(null);
                setSelectedKey(finding.key);
              }}
              onMove={moveFinding}
            />
          ) : null}

          {!loading && board && view === 'table' ? (
            <TableView
              findings={filtered}
              onOpen={(finding) => {
                setLiveRun(null);
                setSelectedKey(finding.key);
              }}
            />
          ) : null}

          {!loading && board && view === 'map' ? (
            <MapView
              board={board}
              filters={filters}
              onOpenFinding={(finding) => {
                setLiveRun(null);
                setSelectedKey(finding.key);
              }}
              onToast={showToast}
            />
          ) : null}

          {!loading && !board && !error ? (
            <div className="empty-state">
              <Database size={24} aria-hidden="true" />
              <strong>没有可读取的报告</strong>
              <p>先运行 `bash run.sh &lt;source&gt;` 生成 runs/*/*/audit-report.json。</p>
            </div>
          ) : null}
        </div>
      </main>

      {selected ? (
        <DetailDrawer
          finding={selected}
          board={board}
          onClose={() => setSelectedKey(null)}
          onPatch={updateFinding}
          onToast={showToast}
        />
      ) : null}

      {liveRun ? <LiveRunDrawer run={liveRun} onClose={() => setLiveRun(null)} onToast={showToast} /> : null}

      {runsOpen ? (
        <RunsDrawer
          runs={runs}
          loading={runsLoading}
          error={runsError}
          onClose={() => setRunsOpen(false)}
          onOpen={(run) => {
            setRunsOpen(false);
            setSelectedKey(null);
            setLiveRun(toRunView(run));
          }}
        />
      ) : null}

      <Toast message={toast} onClose={() => setToast('')} />
    </div>
  );
}
