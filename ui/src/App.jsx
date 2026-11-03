import ModelSettings from './components/ModelSettings.jsx';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, BadgeCheck, BookOpen, ChevronLeft, ChevronRight, Database, GitBranch, LayoutGrid, List, Radar, RefreshCw, Settings, ShieldAlert } from 'lucide-react';
import { api } from './api.js';
import { useI18n } from './i18n.jsx';
import { countBy, cx } from './utils.js';
import StageView from './components/StageView.jsx';
import DetailDrawer from './components/DetailDrawer.jsx';
import LiveRunDrawer from './components/LiveRunDrawer.jsx';
import LiveRunsStrip from './components/LiveRunsStrip.jsx';
import AgenticPipeline from './components/AgenticPipeline.jsx';
import MapView from './components/MapView.jsx';
import RefineryStrip from './components/RefineryStrip.jsx';
import RailButton from './components/RailButton.jsx';
import ArchitectureView from './components/ArchitectureView.jsx';
import WatchView from './components/WatchView.jsx';
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
    reviewReady: findings.filter((finding) => finding.reviewReady).length,
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
  const { language, setLanguage, t } = useI18n();
  const [board, setBoard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFiltersState] = useState(loadFilters);
  const [modelSettingsOpen, setModelSettingsOpen] = useState(false);
  const [view, setViewState] = useState(() => localStorage.getItem('vul-ai-view') || 'board');
  const [activeStage, setActiveStageState] = useState('');
  const [theme, setTheme] = useState(() => localStorage.getItem('vul-ai-theme') || 'light');
  const [selectedKey, setSelectedKey] = useState(null);
  const [liveRun, setLiveRun] = useState(null);
  const [toast, setToast] = useState('');
  const [toastType, setToastType] = useState('success');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('vul-ai-sidebar') === 'collapsed');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const liveSignatureRef = useRef('');
  const hasBoardRef = useRef(false);

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

  const setActiveStage = useCallback((next) => {
    setActiveStageState(next || '');
  }, []);

  const showToast = useCallback((message, type = 'success') => {
    setToast(message);
    setToastType(type);
  }, []);

  const loadBoard = useCallback(async () => {
    if (!hasBoardRef.current) setLoading(true);
    setError('');
    try {
      const payload = await api.board();
      hasBoardRef.current = true;
      setBoard(payload);
      liveSignatureRef.current = (payload.liveRuns || []).map((run) => `${run.project}:${run.runId}`).join('|');
      setLoading(false);
    } catch (loadError) {
      setError(loadError.message);
      setLoading(false);
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
    if (filters.hideInbox && view !== 'board') items = items.filter((finding) => finding.status !== 'inbox');
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
  }, [findings, filters.project, filters.cveOnly, filters.reviewOnly, filters.hideInbox, filters.query, view]);

  const scopedStats = useMemo(() => deriveStats(scoped), [scoped]);

  const filtered = useMemo(() => {
    let items = scoped;
    if (filters.severities.length) items = items.filter((finding) => filters.severities.includes(finding.severity));
    if (filters.verdicts.length) items = items.filter((finding) => filters.verdicts.includes(finding.verdict));
    return items;
  }, [scoped, filters.severities, filters.verdicts]);

  const filteredStats = useMemo(() => deriveStats(filtered), [filtered]);

  const pipelineTarget = useMemo(() => {
    const projects = board?.projects || [];
    const selectedProject = filters.project !== 'all'
      ? projects.find((project) => project.id === filters.project)
      : null;
    const live = board?.liveRuns?.[0];
    const liveProject = live ? projects.find((project) => project.id === live.project) : null;
    const latest = [...projects].sort((a, b) => String(b.startedAt || '').localeCompare(String(a.startedAt || '')))[0];
    const target = selectedProject || liveProject || latest;
    if (!target) return null;
    return {
      project: target.id,
      projectName: target.name,
      runId: target.liveRunId || target.latestRunId,
      live: Boolean(target.isLive)
    };
  }, [board?.projects, board?.liveRuns, filters.project]);

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
        await api.update(finding.project, finding.id, patch, finding.occurrence_id);
        showToast('已保存');
        await loadBoard(true);
      } catch (updateError) {
        setBoard((current) => {
          if (!current) return current;
          const nextFindings = current.findings.map((item) => (item.key === finding.key ? previous : item));
          return { ...current, findings: nextFindings, stats: deriveStats(nextFindings) };
        });
        showToast(`保存失败：${updateError.message}`, 'error');
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
    <div className={cx('app', sidebarOpen && 'sidebar-open', sidebarCollapsed && 'sidebar-collapsed', selected && 'has-drawer')}>
      <nav className="rail" aria-label="主导航">
        <div className="rail-brand" title="VUL/AI">
          <img src="/golden-shovel.webp" alt="VUL/AI 黄金铲子" />
        </div>
        <div className="rail-group">
          <RailButton
            id="nav-board"
            label={t('nav.board')}
            description={t('nav.board.description')}
            active={view === 'board' && activeStage !== 'review'}
            current={view === 'board' && activeStage !== 'review'}
            onClick={() => {
              setView('board');
              setActiveStage('');
            }}
          >
            <LayoutGrid size={18} aria-hidden="true" />
          </RailButton>
          <RailButton
            id="nav-table"
            label={t('nav.table')}
            description={t('nav.table.description')}
            active={view === 'table'}
            current={view === 'table'}
            onClick={() => setView('table')}
          >
            <List size={19} aria-hidden="true" />
          </RailButton>
          <RailButton
            id="nav-map"
            label={t('nav.map')}
            description={t('nav.map.description')}
            active={view === 'map'}
            current={view === 'map'}
            onClick={() => setView('map')}
          >
            <GitBranch size={18} aria-hidden="true" />
          </RailButton>
          <RailButton
            id="nav-watch"
            label={t('nav.watch')}
            description={t('nav.watch.description')}
            active={view === 'watch'}
            current={view === 'watch'}
            onClick={() => setView('watch')}
          >
            <Radar size={18} aria-hidden="true" />
          </RailButton>
          <RailButton
            id="nav-cve"
            label={t('nav.cve')}
            description={t('nav.cve.description')}
            active={filters.cveOnly}
            pressed={filters.cveOnly}
            badge={board?.stats?.cveCandidates}
            onClick={() => setFilters((current) => ({ ...current, cveOnly: !current.cveOnly }))}
          >
            <ShieldAlert size={18} aria-hidden="true" />
          </RailButton>
          <RailButton
            id="nav-review"
            label={t('nav.review')}
            description={t('nav.review.description')}
            active={view === 'board' && activeStage === 'review'}
            current={view === 'board' && activeStage === 'review'}
            badge={board?.stats?.reviewReady}
            onClick={() => {
              setActiveStage('review');
              setView('board');
              setFilters((current) => ({ ...current, reviewOnly: false }));
            }}
          >
            <BadgeCheck size={18} aria-hidden="true" />
          </RailButton>
          <RailButton
            id="nav-architecture"
            label={t('nav.architecture')}
            description={t('nav.architecture.description')}
            active={view === 'architecture'}
            current={view === 'architecture'}
            onClick={() => setView('architecture')}
          >
            <BookOpen size={18} aria-hidden="true" />
          </RailButton>
        </div>
        <div className="rail-bottom">
          <RailButton
            id="nav-settings"
            label={t('settings.title')}
            description={t('settings.description')}
            active={settingsOpen}
            expanded={settingsOpen}
            onClick={() => setSettingsOpen((value) => !value)}
          >
            <Settings size={18} aria-hidden="true" />
          </RailButton>
          <span className="rail-version">v0.1</span>
        </div>
      </nav>

      {modelSettingsOpen ? <ModelSettings onClose={() => setModelSettingsOpen(false)} /> : null}
      {settingsOpen ? (
        <>
          <button type="button" className="settings-backdrop" aria-label={t('settings.title')} onClick={() => setSettingsOpen(false)} />
          <div className="settings-popover" role="dialog" aria-label={t('settings.title')}>
            <div className="settings-head">
              <strong>{t('settings.title')}</strong>
              <span>{t('settings.languageHint')}</span>
            </div>
            <div className="settings-row"><span>阶段模型</span><button type="button" className="button" onClick={() => {setSettingsOpen(false);setModelSettingsOpen(true);}}>配置模型</button></div>
            <label className="settings-row">
              <span>{t('language.label')}</span>
              <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                <option value="zh">中文</option>
                <option value="en">English</option>
              </select>
            </label>
            <div className="settings-row">
              <span>{t('settings.theme')}</span>
              <div className="settings-segment" role="group" aria-label={t('settings.theme')}>
                <button
                  type="button"
                  className={cx(theme === 'light' && 'is-active')}
                  onClick={() => setTheme('light')}
                >
                  {t('settings.themeLight')}
                </button>
                <button
                  type="button"
                  className={cx(theme === 'dark' && 'is-active')}
                  onClick={() => setTheme('dark')}
                >
                  {t('settings.themeDark')}
                </button>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {sidebarOpen ? <button type="button" className="sidebar-backdrop" aria-label="关闭筛选" onClick={() => setSidebarOpen(false)} /> : null}

      <button
        type="button"
        className={sidebarCollapsed ? 'sidebar-expand' : 'sidebar-collapse'}
        title={sidebarCollapsed ? '展开筛选' : '收起筛选'}
        aria-label={sidebarCollapsed ? '展开筛选' : '收起筛选'}
        onClick={() => {
          const next = !sidebarCollapsed;
          setSidebarCollapsed(next);
          localStorage.setItem('vul-ai-sidebar', next ? 'collapsed' : 'open');
        }}
      >
        {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>

      <Sidebar
        board={board}
        filters={filters}
        setFilters={setFilters}
        facets={facetStats}
        onRestart={async (project) => {
          await api.restartProject(project.id);
          setFilters((current) => ({ ...current, project: project.id }));
          setView('board');
          await loadBoard(true);
          showToast(`${project.name} 新一轮审计已启动`);
        }}
        onRemove={async (project) => {
          await api.removeProject(project.id);
          setFilters((current) => ({ ...current, project: current.project === project.id ? 'all' : current.project }));
          await loadBoard(true);
          showToast(`${project.name} 已删除`);
        }}
        onImported={async (result) => {
          setFilters((current) => ({ ...current, project: result.project }));
          showToast(`${result.name} 已导入，完整审计已启动`);
          await loadBoard(true);
        }}
      />

      <main className="main">
        <TopBar
          filters={filters}
          setFilters={setFilters}
          onToggleSidebar={() => setSidebarOpen((value) => !value)}
          view={view}
          activeStage={activeStage}
          sidebarOpen={sidebarOpen}
        />

        {view !== 'board' ? <StatsStrip stats={board?.stats} projects={board?.projects} /> : null}

        {view === 'board' && board?.stats && activeStage ? (
          <RefineryStrip
            stats={scopedStats}
            stageStats={filteredStats}
            activeStage={activeStage}
            onSelectStage={setActiveStage}
            filters={filters}
            setFilters={setFilters}
            flow={board?.flowStatus}
          />
        ) : null}

        {board?.liveRuns?.length ? (
          <LiveRunsStrip
            runs={board.liveRuns}
            onOpen={(run) => {
              setSelectedKey(null);
              setLiveRun(run);
            }}
          />
        ) : null}

        {error ? (
          <div className="error-banner" role="alert">
            <AlertTriangle size={15} aria-hidden="true" />
            <span>{error}</span>
            <button type="button" className="button is-small" disabled={loading} aria-busy={loading} onClick={() => loadBoard()}>
              {loading ? '加载中…' : '重试'}
            </button>
          </div>
        ) : null}

        <div className={cx('content', view === 'board' && !activeStage && 'content-landing')}>
          {view === 'table' ? (
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
          ) : null}

          {loading && !board ? <LoadingBoard /> : null}

          {!loading && board && view === 'board' && !activeStage ? (
            <section className="pipeline-landing">
              <AgenticPipeline {...(pipelineTarget || {})} />
              <RefineryStrip
                stats={scopedStats}
                stageStats={filteredStats}
                activeStage={activeStage}
                onSelectStage={setActiveStage}
                filters={filters}
                setFilters={setFilters}
                flow={board?.flowStatus}
                landing
              />
            </section>
          ) : null}

          {!loading && board && view === 'board' && activeStage ? (
            <StageView
              findings={filtered}
              stage={activeStage}
              statusTotals={{ ...(board.stats?.status || {}), review: board.stats?.reviewReady || 0 }}
              onBack={() => setActiveStage('')}
              onOpen={(finding) => {
                setLiveRun(null);
                setSelectedKey(finding.key);
              }}
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

          {!loading && view === 'watch' ? <WatchView /> : null}

          {!loading && board && view === 'architecture' ? <ArchitectureView board={board} /> : null}

          {!loading && board && view === 'map' ? (
            <MapView
              board={board}
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
              <p>先执行 bash run.sh &lt;source&gt; 命令，生成 runs/*/*/audit-report.json 报告。</p>
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

      <Toast message={toast} type={toastType} onClose={() => setToast('')} />
    </div>
  );
}
