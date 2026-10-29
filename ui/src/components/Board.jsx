import { useMemo, useState } from 'react';
import { ChevronDown, Inbox } from 'lucide-react';
import { COLUMNS, SEVERITIES } from '../constants.js';
import { cx, severityRank } from '../utils.js';
import FindingCard from './FindingCard.jsx';

const INITIAL_LIMIT = 30;

function SeverityBar({ findings }) {
  const counts = Object.fromEntries(SEVERITIES.map((severity) => [severity.id, 0]));
  for (const finding of findings) counts[finding.severity] += 1;
  const total = findings.length || 1;

  return (
    <div className="severity-bar" aria-hidden="true">
      {SEVERITIES.map((severity) =>
        counts[severity.id] ? (
          <span
            key={severity.id}
            className={`severity-bar-segment severity-${severity.id}`}
            style={{ width: `${(counts[severity.id] / total) * 100}%` }}
            title={`${severity.full}: ${counts[severity.id]}`}
          />
        ) : null
      )}
    </div>
  );
}

export default function Board({ findings, onOpen, onMove, hiddenStatuses = [], statusTotals = {} }) {
  const [dragging, setDragging] = useState(null);
  const [overColumn, setOverColumn] = useState(null);
  const [expanded, setExpanded] = useState({});

  const columns = useMemo(
    () => COLUMNS.filter((column) => !hiddenStatuses.includes(column.id)),
    [hiddenStatuses]
  );
  const grouped = useMemo(() => {
    const result = Object.fromEntries(columns.map((column) => [column.id, []]));
    for (const finding of findings) {
      result[finding.status]?.push(finding);
    }
    for (const column of columns) {
      result[column.id].sort(
        (a, b) =>
          severityRank(a.severity) - severityRank(b.severity) ||
          String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')) ||
          a.id.localeCompare(b.id)
      );
    }
    return result;
  }, [findings, columns]);

  return (
    <div className="board-scroll">
      <div className="board" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(262px, 1fr))` }}>
        {columns.map((column, index) => {
          const items = grouped[column.id];
          const limit = expanded[column.id] ? items.length : Math.min(items.length, INITIAL_LIMIT);
          const visible = items.slice(0, limit);
          const hidden = items.length - visible.length;
          const isOver = overColumn === column.id;

          return (
            <section
              key={column.id}
              className={cx('board-column', `tone-${column.tone}`, isOver && 'is-over')}
              style={{ '--column-index': index }}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                if (overColumn !== column.id) setOverColumn(column.id);
              }}
              onDragLeave={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) setOverColumn(null);
              }}
              onDrop={(event) => {
                event.preventDefault();
                const key = event.dataTransfer.getData('text/plain') || dragging?.key;
                setOverColumn(null);
                setDragging(null);
                if (key) onMove(key, column.id);
              }}
            >
              <header className="column-head">
                <div className="column-kicker">
                  <span className="column-code">{column.code}</span>
                  <span className="column-index">0{COLUMNS.findIndex((item) => item.id === column.id) + 1}</span>
                </div>
                <div className="column-title-row">
                  <h2>{column.label}</h2>
                  <span className="column-count">{items.length}</span>
                </div>
                <p className="column-hint">{column.hint}</p>
                <SeverityBar findings={items} />
              </header>

              <div className="column-list">
                {visible.map((finding) => (
                  <FindingCard
                    key={finding.key}
                    finding={finding}
                    onOpen={onOpen}
                    onDragStart={setDragging}
                    onDragEnd={() => {
                      setDragging(null);
                      setOverColumn(null);
                    }}
                  />
                ))}

                {hidden > 0 ? (
                  <button
                    type="button"
                    className="show-more"
                    onClick={() => setExpanded((current) => ({ ...current, [column.id]: true }))}
                  >
                    <ChevronDown size={13} aria-hidden="true" />
                    还有 {hidden} 条
                  </button>
                ) : null}

                {items.length === 0 ? (
                  <div className="column-empty">
                    <Inbox size={18} aria-hidden="true" />
                    <span>当前筛选下没有 finding</span>
                    {statusTotals[column.id] ? (
                      <small>全局还有 {statusTotals[column.id]} 条，清除筛选后可查看</small>
                    ) : (
                      <small>自动流转或拖拽后会出现在这里</small>
                    )}
                  </div>
                ) : null}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
