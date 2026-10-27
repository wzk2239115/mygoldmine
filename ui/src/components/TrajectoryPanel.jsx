import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowDown,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  Info,
  Loader2,
  MessageSquare,
  RefreshCw,
  Search,
  Terminal,
  Wrench
} from 'lucide-react';
import { api } from '../api.js';
import { cx, formatDateTime } from '../utils.js';

const PAGE_SIZE = 200;
const KINDS = ['all', 'meta', 'tool', 'tool_result', 'thinking', 'assistant', 'error', 'result'];

const KIND_ICONS = {
  meta: Info,
  tool: Wrench,
  tool_result: Terminal,
  thinking: MessageSquare,
  assistant: MessageSquare,
  error: AlertTriangle,
  result: CheckCircle2
};

function EventIcon({ kind }) {
  const Icon = KIND_ICONS[kind] || Info;
  return <Icon size={15} aria-hidden="true" />;
}

function EventRow({ event, expanded, onToggle }) {
  const lineLabel = event.lineEnd > event.lineStart ? `L${event.lineStart}–${event.lineEnd}` : `L${event.lineStart}`;
  return (
    <article className={cx('traj-event', `traj-kind-${event.kind}`, event.error && 'is-error')}>
      <button
        type="button"
        className="traj-event-head"
        aria-expanded={expanded}
        onClick={() => onToggle(event.index)}
      >
        <span className="traj-icon">
          <EventIcon kind={event.kind} />
        </span>
        <span className="traj-badge">{event.kind.replace('_', ' ')}</span>
        <span className="traj-label" title={event.label}>
          {event.label}
        </span>
        {event.error ? <span className="traj-error-mark">ERROR</span> : null}
        <span className="traj-lines">{lineLabel}</span>
        <span className="traj-chevron">
          {expanded ? <ChevronDown size={15} aria-hidden="true" /> : <ChevronRight size={15} aria-hidden="true" />}
        </span>
      </button>
      {expanded ? (
        <pre className="traj-text">{event.text || event.preview}</pre>
      ) : (
        <p className="traj-preview">{event.preview || '—'}</p>
      )}
    </article>
  );
}

export default function TrajectoryPanel({ project, runId, finished = true, fill = false }) {
  const [events, setEvents] = useState([]);
  const [pageInfo, setPageInfo] = useState(null);
  const [counts, setCounts] = useState({});
  const [totalEvents, setTotalEvents] = useState(0);
  const [matchingTotal, setMatchingTotal] = useState(0);
  const [startIndex, setStartIndex] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [kind, setKind] = useState('all');
  const [queryInput, setQueryInput] = useState('');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(() => new Set());
  const [follow, setFollow] = useState(!finished);
  const listRef = useRef(null);
  const requestSeq = useRef(0);

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(queryInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [queryInput]);

  const fetchPage = useCallback(
    async ({ offset, limit = PAGE_SIZE, append = false }) => {
      if (!project || !runId) return null;
      const seq = requestSeq.current + 1;
      requestSeq.current = seq;
      if (!append) setLoading(true);
      setError('');
      try {
        const payload = await api.trajectory(project, runId, {
          offset,
          limit,
          kind,
          q: query || undefined
        });
        if (seq !== requestSeq.current) return null;
        setPageInfo(payload);
        setCounts(payload.counts || {});
        setTotalEvents(payload.totalEvents || 0);
        setMatchingTotal(payload.filteredEvents ?? payload.totalEvents ?? 0);
        setHasMore(Boolean(payload.hasMore));
        if (append) {
          setEvents((previous) => {
            const seen = new Set(previous.map((event) => event.index));
            const merged = [...previous];
            for (const event of payload.events || []) {
              if (!seen.has(event.index)) merged.push(event);
            }
            merged.sort((a, b) => a.index - b.index);
            return merged;
          });
        } else {
          setEvents(payload.events || []);
          setStartIndex(payload.offset || 0);
          setExpanded(new Set());
        }
        return payload;
      } catch (loadError) {
        if (seq === requestSeq.current) setError(loadError.message);
        return null;
      } finally {
        if (seq === requestSeq.current && !append) setLoading(false);
      }
    },
    [project, runId, kind, query]
  );

  useEffect(() => {
    setEvents([]);
    setStartIndex(0);
    setHasMore(false);
    setPageInfo(null);
    setError('');
    setExpanded(new Set());
    setFollow(!finished);
    fetchPage({ offset: 0, limit: PAGE_SIZE });
  }, [fetchPage]);

  useEffect(() => {
    if (finished || !project || !runId) return undefined;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      const endIndex = startIndex + events.length;
      const offset = Math.max(0, matchingTotal - PAGE_SIZE);
      try {
        const payload = await api.trajectory(project, runId, {
          offset,
          limit: PAGE_SIZE,
          kind,
          q: query || undefined
        });
        if (cancelled) return;
        setPageInfo((previous) => ({ ...(previous || {}), ...payload }));
        setCounts(payload.counts || {});
        setTotalEvents(payload.totalEvents || 0);
        setMatchingTotal(payload.filteredEvents ?? payload.totalEvents ?? 0);
        const canMerge = Boolean(payload.events?.length) && payload.offset <= endIndex;
        if (canMerge) {
          setHasMore(Boolean(payload.hasMore));
          setEvents((previous) => {
            const seen = new Set(previous.map((event) => event.index));
            const merged = [...previous];
            for (const event of payload.events) {
              if (!seen.has(event.index)) merged.push(event);
            }
            merged.sort((a, b) => a.index - b.index);
            return merged;
          });
        }
      } catch {
        // Polling failures are silent; the manual refresh surfaces errors.
      }
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [finished, project, runId, kind, query, startIndex, events.length, matchingTotal]);

  useEffect(() => {
    if (!follow) return;
    const element = listRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [events, follow]);

  const loadMore = useCallback(async () => {
    if (!hasMore || loadingMore) return;
    setLoadingMore(true);
    const offset = startIndex + events.length;
    await fetchPage({ offset, limit: PAGE_SIZE, append: true });
    setLoadingMore(false);
  }, [fetchPage, hasMore, loadingMore, startIndex, events.length]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    const limit = Math.min(500, Math.max(PAGE_SIZE, events.length));
    await fetchPage({ offset: startIndex, limit });
    setRefreshing(false);
  }, [fetchPage, startIndex, events.length]);

  const jumpToLatest = useCallback(async () => {
    setFollow(true);
    const endIndex = startIndex + events.length;
    if (matchingTotal > endIndex) {
      const offset = Math.max(0, matchingTotal - PAGE_SIZE);
      await fetchPage({ offset, limit: Math.min(PAGE_SIZE, matchingTotal - offset) });
    } else {
      const element = listRef.current;
      if (element) element.scrollTop = element.scrollHeight;
    }
  }, [fetchPage, matchingTotal, startIndex, events.length]);

  const toggleEvent = useCallback((index) => {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }, []);

  const handleScroll = (event) => {
    const element = event.currentTarget;
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 72;
    setFollow(atBottom);
  };

  const logHref = `/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/log.txt`;
  const endingIndex = startIndex + events.length;
  const countSummary = KINDS.filter((item) => item !== 'all' && counts[item]).map(
    (item) => `${item.replace('_', ' ')} ${counts[item]}`
  );

  return (
    <section className={cx('traj-panel', fill && 'traj-panel-fill')} aria-label="Full audit trajectory">
      <div className="traj-toolbar">
        <div className="traj-stats">
          <span>
            <strong>{matchingTotal}</strong> {query || kind !== 'all' ? 'matches' : 'events'}
          </span>
          <span>
            <strong>{totalEvents}</strong> total
          </span>
          <span>
            <strong>{pageInfo?.totalLines ?? 0}</strong> lines
          </span>
          {!finished ? <span className="traj-live-dot">live · 3s</span> : null}
        </div>

        <label className="traj-control">
          <span>Kind</span>
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            {KINDS.map((item) => (
              <option key={item} value={item}>
                {item === 'all' ? 'all kinds' : item.replace('_', ' ')}
                {item !== 'all' && counts[item] ? ` (${counts[item]})` : ''}
              </option>
            ))}
          </select>
        </label>

        <label className="traj-control traj-search">
          <Search size={15} aria-hidden="true" />
          <input
            type="search"
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            placeholder="Search trajectory…"
            spellCheck={false}
            aria-label="Search trajectory"
          />
        </label>

        <div className="traj-actions">
          <button type="button" className="traj-button" onClick={refresh} disabled={loading || refreshing}>
            {loading || refreshing ? (
              <Loader2 size={15} className="traj-spin" aria-hidden="true" />
            ) : (
              <RefreshCw size={15} aria-hidden="true" />
            )}
            Refresh
          </button>
          {hasMore ? (
            <button type="button" className="traj-button" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? <Loader2 size={15} className="traj-spin" aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}
              Load more
            </button>
          ) : null}
          <button type="button" className="traj-button" onClick={jumpToLatest}>
            <ArrowDown size={15} aria-hidden="true" />
            Jump to latest
          </button>
          <a
            className="traj-link"
            href={logHref}
            target="_blank"
            rel="noreferrer"
            download={`${runId}-claude.rendered.log`}
          >
            <Download size={15} aria-hidden="true" />
            Full log
          </a>
        </div>
      </div>

      <div className="traj-meta">
        <code>{pageInfo?.path || 'claude.rendered.log'}</code>
        <span>{pageInfo ? `${pageInfo.bytes.toLocaleString()} bytes · ${formatDateTime(pageInfo.mtime)}` : ''}</span>
        {countSummary.length ? <span>{countSummary.join(' · ')}</span> : null}
        <span>
          showing {events.length ? `${startIndex + 1}–${endingIndex}` : '0'} of {matchingTotal}
        </span>
      </div>

      {error ? <div className="traj-error">{error}</div> : null}

      <div ref={listRef} className="traj-list" onScroll={handleScroll} tabIndex={0}>
        {loading && !events.length ? (
          <div className="traj-empty">
            <Loader2 size={16} className="traj-spin" aria-hidden="true" /> Loading trajectory…
          </div>
        ) : null}
        {!loading && !events.length && !error ? (
          <div className="traj-empty">{query || kind !== 'all' ? 'No matching events.' : 'No rendered log events for this run.'}</div>
        ) : null}

        {events.map((event) => (
          <EventRow key={event.index} event={event} expanded={expanded.has(event.index)} onToggle={toggleEvent} />
        ))}

        {hasMore ? (
          <div className="traj-more">
            <button type="button" className="traj-button is-primary" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? <Loader2 size={15} className="traj-spin" aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}
              Load more ({Math.max(0, matchingTotal - endingIndex)} remaining)
            </button>
          </div>
        ) : null}
      </div>

      <div className="traj-footer">
        <span>page size {PAGE_SIZE} · {events.length} rendered</span>
        {!follow ? (
          <button type="button" className="traj-button is-small" onClick={jumpToLatest}>
            <ArrowDown size={14} aria-hidden="true" />
            Follow tail
          </button>
        ) : (
          <span>following</span>
        )}
      </div>
    </section>
  );
}
