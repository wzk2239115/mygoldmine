import { useEffect, useRef } from 'react';
import { PanelLeft, Search, X } from 'lucide-react';
import { useI18n } from '../i18n.jsx';

export default function TopBar({
  filters,
  setFilters,
  onToggleSidebar,
  view,
  activeStage,
  sidebarOpen
}) {
  const { t } = useI18n();
  const searchRef = useRef(null);
  const searchEnabled = view === 'board' || view === 'table';
  const titleKey = view === 'board' && activeStage === 'review' ? 'nav.review' : `nav.${view}`;

  useEffect(() => {
    const handleKeyDown = (event) => {
      const target = event.target;
      const isTyping =
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable);
      if (searchEnabled && event.key === '/' && !isTyping) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [searchEnabled]);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="icon-button topbar-menu"
          title={t(sidebarOpen ? 'topbar.closeFilters' : 'topbar.openFilters')}
          aria-label={t(sidebarOpen ? 'topbar.closeFilters' : 'topbar.openFilters')}
          aria-expanded={sidebarOpen}
          aria-controls="finding-filters"
          onClick={onToggleSidebar}
        >
          <PanelLeft size={17} aria-hidden="true" />
        </button>
        <div className="page-title">
          <h1>{t(titleKey)}</h1>
        </div>
      </div>

      {searchEnabled ? (
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
              placeholder={t('topbar.search')}
              aria-label={t('topbar.searchLabel')}
              spellCheck={false}
            />
            {filters.query ? (
              <button
                type="button"
                className="search-clear"
                aria-label={t('topbar.clearSearch')}
                onClick={() => setFilters((current) => ({ ...current, query: '' }))}
              >
                <X size={13} aria-hidden="true" />
              </button>
            ) : (
              <kbd>/</kbd>
            )}
          </div>
        </div>
      ) : null}
    </header>
  );
}
