import { FileCode2, GripVertical, StickyNote } from 'lucide-react';
import { CveBadge, SeverityStamp, VerdictBadge } from './Badges.jsx';
import { cx, truncate } from '../utils.js';

export default function FindingCard({ finding, onOpen, onDragStart, onDragEnd }) {
  const cwe = finding.cwe?.slice(0, 2).join(' · ');
  const evidenceCount = finding.evidence?.length || 0;

  return (
    <article
      className={cx('finding-card', `severity-${finding.severity}`, finding.touched && 'is-touched')}
      draggable
      tabIndex={0}
      role="button"
      aria-label={`打开 ${finding.projectName} ${finding.id}: ${finding.title}`}
      onClick={() => onOpen(finding)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onOpen(finding);
        }
      }}
      onDragStart={(event) => {
        event.dataTransfer.setData('text/plain', finding.key);
        event.dataTransfer.effectAllowed = 'move';
        onDragStart(finding);
      }}
      onDragEnd={onDragEnd}
    >
      <div className="card-grip" aria-hidden="true">
        <GripVertical size={13} />
      </div>
      <div className="card-topline">
        <SeverityStamp severity={finding.severity} compact />
        <span className="card-project">{finding.projectName}</span>
        <span className="card-id">{finding.id}</span>
      </div>
      <h3 className="card-title" title={finding.title}>
        {truncate(finding.title, 170)}
      </h3>
      <div className="card-badges">
        <VerdictBadge verdict={finding.verdict} />
        <CveBadge tier={finding.cveTier} knownCve={finding.knownCve} status={finding.cveStatus} />
        {finding.notes ? (
          <span className="card-note-indicator" title="有审计备注">
            <StickyNote size={11} aria-hidden="true" />
          </span>
        ) : null}
      </div>
      <div className="card-footer">
        <span className="card-cwe">{cwe || finding.category || 'uncategorized'}</span>
        <span className="card-evidence" title={`${evidenceCount} 条证据`}>
          <FileCode2 size={12} aria-hidden="true" />
          {evidenceCount}
        </span>
        <span className="card-confidence">{finding.confidence}</span>
      </div>
    </article>
  );
}
