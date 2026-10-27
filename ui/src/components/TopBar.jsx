import { useEffect, useRef } from 'react';
import { Database, LayoutGrid, List, Moon, PanelLeft, RefreshCw, Search, Sun, X } from 'lucide-react';
import { SCOPE_OPTIONS } from '../constants.js';
import { cx, formatDate } from '../utils.js';

export default function TopBar({
  board,
  filters,
  setFilters,
  view,
  setView,
  onRefresh,
  refreshing,
  theme,
  onToggleTheme,
  onToggleSidebar
}) {
  const searchRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (event) => {
      const target = event.target;
      const isTyping =
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable);
      if (event.key === '/' && !isTyping) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const latest = board?.projects
    ?.map((project) => project.endedAt || project.startedAt)
    .filter(Boolean)
    .sort()
    .at(-1);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="icon-button topbar-menu"
          title="打开筛选"
          aria-label="打开筛选"
          onClick={onToggleSidebar}
        >
          <PanelLeft size={17} />
        </button>
        <div className="page-title">
          <span className="eyebrow">SECURITY OPERATIONS / FINDINGS</span>
          <h1>
            证据看板 <span className="title-slash">/</span> <em>Kanban</em>
          </h1>
        </div>
      </div>

      <div className="topbar-center">
        <div className="search-box">
          <Search size={15} aria-hidden="true" />
          <input
            ref={searchRef}
            value={filters.query}
            onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setFilters((current) => ({ ...current, query: '' }));
            }}
            placeholder="搜索 ID、标题、CWE…"
            aria-label="搜索 findings"
            spellCheck={false}
          />
          {filters.query ? (
            <button
              type="button"
              className="search-clear"
              aria-label="清除搜索"
              onClick={() => setFilters((current) => ({ ...current, query: '' }))}
            >
              <X size={13} />
            </button>
          ) : (
            <kbd>/</kbd>
          )}
        </div>
      </div>

      <div className="topbar-right">
        <div className="scope-switch" role="group" aria-label="数据范围">
          {SCOPE_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              className={cx(filters.scope === option.id && 'is-active')}
              onClick={() => setFilters((current) => ({ ...current, scope: option.id }))}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="view-switch" role="group" aria-label="视图">
          <button
            type="button"
            className={cx(view === 'board' && 'is-active')}
            title="看板"
            aria-label="看板"
            onClick={() => setView('board')}
          >
            <LayoutGrid size={15} />
          </button>
          <button
            type="button"
            className={cx(view === 'table' && 'is-active')}
            title="表格"
            aria-label="表格"
            onClick={() => setView('table')}
          >
            <List size={16} />
          </button>
        </div>

        <button
          type="button"
          className="icon-button"
          title={theme === 'dark' ? '切换到浅色' : '切换到深色'}
          aria-label={theme === 'dark' ? '切换到浅色' : '切换到深色'}
          onClick={onToggleTheme}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <button
          type="button"
          className={cx('icon-button', refreshing && 'is-spinning')}
          title="刷新报告"
          aria-label="刷新报告"
          onClick={onRefresh}
        >
          <RefreshCw size={16} />
        </button>

        <div className="source-status" title="数据来自 runs/*/*/audit-report.json">
          <Database size={13} aria-hidden="true" />
          <span>{board?.projects?.length ?? 0} targets</span>
          <i />
          <span>{latest ? formatDate(latest) : '—'}</span>
        </div>
      </div>
    </header>
  );
}
