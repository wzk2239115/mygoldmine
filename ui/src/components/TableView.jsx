import { useMemo, useState } from 'react';
import { ChevronDown, Inbox } from 'lucide-react';
import { CveBadge, SeverityStamp, VerdictBadge } from './Badges.jsx';
import { STATUS_LABELS } from '../constants.js';
import { formatDate, severityRank, truncate } from '../utils.js';

const PAGE_SIZE = 120;

export default function TableView({ findings, onOpen }) {
  const [limit, setLimit] = useState(PAGE_SIZE);
  const rows = useMemo(
    () =>
      [...findings].sort(
        (a, b) =>
          severityRank(a.severity) - severityRank(b.severity) ||
          a.project.localeCompare(b.project) ||
          a.id.localeCompare(b.id)
      ),
    [findings]
  );
  const visible = rows.slice(0, limit);

  if (!rows.length) {
    return (
      <div className="table-empty">
        <Inbox size={22} aria-hidden="true" />
        <span>当前筛选下没有 finding</span>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <div className="table-scroll">
        <table className="findings-table">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Finding</th>
              <th>Target</th>
              <th>Verdict</th>
              <th>CVE</th>
              <th>Status</th>
              <th>Evidence</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((finding) => (
              <tr
                key={finding.key}
                tabIndex={0}
                onClick={() => onOpen(finding)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onOpen(finding);
                  }
                }}
              >
                <td>
                  <SeverityStamp severity={finding.severity} compact />
                </td>
                <td>
                  <div className="table-finding">
                    <span className="table-id">{finding.id}</span>
                    <strong>{truncate(finding.title, 120)}</strong>
                    <span className="table-cwe">{finding.cwe?.join(' · ') || finding.category || '—'}</span>
                  </div>
                </td>
                <td>
                  <span className="table-project">{finding.projectName}</span>
                </td>
                <td>
                  <VerdictBadge verdict={finding.verdict} />
                </td>
                <td>
                  <CveBadge tier={finding.cveTier} knownCve={finding.knownCve} />
                </td>
                <td>
                  <span className={`status-pill status-${finding.status}`}>{STATUS_LABELS[finding.status]}</span>
                </td>
                <td className="table-number">{finding.evidence?.length || 0}</td>
                <td className="table-date">{formatDate(finding.updatedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > visible.length ? (
        <button type="button" className="show-more table-show-more" onClick={() => setLimit((value) => value + PAGE_SIZE)}>
          <ChevronDown size={13} aria-hidden="true" />
          还有 {rows.length - visible.length} 条
        </button>
      ) : null}
    </div>
  );
}
