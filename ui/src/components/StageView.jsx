import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronLeft, Inbox } from 'lucide-react';
import { filterStageFindings, stageCount, stageMeta } from '../stage-model.js';
import { severityRank } from '../utils.js';
import { useI18n } from '../i18n.jsx';
import FindingCard from './FindingCard.jsx';

const INITIAL_LIMIT = 48;

export default function StageView({ findings, stage, statusTotals = {}, onOpen, onBack }) {
  const { t } = useI18n();
  const [limit, setLimit] = useState(INITIAL_LIMIT);
  const meta = stageMeta(stage);

  useEffect(() => {
    setLimit(INITIAL_LIMIT);
  }, [stage]);

  const items = useMemo(() => {
    return filterStageFindings(findings, stage).sort(
      (a, b) =>
        severityRank(a.severity) - severityRank(b.severity) ||
        String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')) ||
        a.id.localeCompare(b.id)
    );
  }, [findings, stage]);

  const visible = items.slice(0, limit);
  const hidden = items.length - visible.length;

  return (
    <section className="stage-view">
      <header className="stage-head">
        <div className="stage-title">
          <button type="button" className="stage-back" onClick={onBack}>
            <ChevronLeft size={14} aria-hidden="true" />
            {t('stage.back')}
          </button>
          <span className="column-code">{meta.code}</span>
          <h2>{meta.label}</h2>
          <span className="stage-count">{items.length}</span>
        </div>
        <p>{meta.hint}</p>
      </header>

      {visible.length ? (
        <div className="stage-grid">
          {visible.map((finding) => (
            <FindingCard key={finding.key} finding={finding} onOpen={onOpen} />
          ))}
        </div>
      ) : (
        <div className="stage-empty">
          <Inbox size={20} aria-hidden="true" />
          <span>当前筛选下没有 finding</span>
          {stageCount(statusTotals, stage) ? (
            <small>全局还有 {stageCount(statusTotals, stage)} 条，清除筛选后可查看</small>
          ) : (
            <small>选择上方的其他环节，或调整筛选条件</small>
          )}
        </div>
      )}

      {hidden > 0 ? (
        <button type="button" className="show-more stage-more" onClick={() => setLimit((value) => value + 48)}>
          <ChevronDown size={14} aria-hidden="true" />
          还有 {hidden} 条
        </button>
      ) : null}
    </section>
  );
}
