import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Copy,
  ExternalLink,
  FileJson,
  FileText,
  GitCommit,
  RefreshCw,
  Save,
  Shield,
  Terminal,
  X
} from 'lucide-react';
import { api } from '../api.js';
import { COLUMNS, CVE_STATUSES, VERDICTS } from '../constants.js';
import { cx, formatDateTime } from '../utils.js';
import { CveBadge, SeverityStamp, VerdictBadge } from './Badges.jsx';
import TrajectoryPanel from './TrajectoryPanel.jsx';
import ClaudeSessionEmbed from './ClaudeSessionEmbed.jsx';
import DrawerResizer, { useDrawerWidth } from './DrawerResizer.jsx';

function DetailSection({ label, children, tone }) {
  if (!children) return null;
  return (
    <section className={cx('detail-section', tone && `detail-section-${tone}`)}>
      <h3>{label}</h3>
      {children}
    </section>
  );
}

function TextBlock({ value }) {
  if (!value) return <p className="detail-empty">—</p>;
  return <p className="detail-text">{value}</p>;
}

function EvidenceList({ items, onCopy }) {
  if (!items?.length) return <p className="detail-empty">报告未给出文件或行号。</p>;
  return (
    <ul className="evidence-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>
          <span className="evidence-index">{String(index + 1).padStart(2, '0')}</span>
          <code>{item}</code>
          <button type="button" className="icon-button is-tiny" title="复制" aria-label={`复制 ${item}`} onClick={() => onCopy(item)}>
            <Copy size={12} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function DetailDrawer({ finding, board, onClose, onPatch, onToast }) {
  const [tab, setTab] = useState('brief');
  const [drawerWidth, setDrawerWidth, resetDrawerWidth] = useDrawerWidth();
  const [notes, setNotes] = useState('');
  const [knownCve, setKnownCve] = useState('');
  const [log, setLog] = useState(null);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState('');
  const [follow, setFollow] = useState(false);
  const [raw, setRaw] = useState(null);
  const [rawOpen, setRawOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const closeRef = useRef(null);

  const project = finding ? board?.projects?.find((item) => item.id === finding.project) : null;

  const copy = useCallback(
    async (value, label = '已复制') => {
      const ok = await navigator.clipboard.writeText(value).then(() => true).catch(() => false);
      onToast?.(ok ? `${label}：${value}` : '复制失败，请手动选择文本');
    },
    [onToast]
  );

  const loadLog = useCallback(
    async (silent = false) => {
      if (!finding) return;
      if (!silent) setLogLoading(true);
      setLogError('');
      try {
        const payload = await api.log(finding.project, finding.runId, 500);
        setLog(payload);
      } catch (error) {
        setLogError(error.message);
      } finally {
        if (!silent) setLogLoading(false);
      }
    },
    [finding]
  );

  const loadRaw = useCallback(async () => {
    if (!finding || raw) return;
    try {
      const payload = await api.raw(finding.project, finding.id);
      setRaw(payload);
    } catch (error) {
      onToast?.(error.message);
    }
  }, [finding, raw, onToast]);

  useEffect(() => {
    if (!finding) return;
    setNotes(finding.notes || '');
    setKnownCve(finding.knownCve || '');
    setRaw(null);
    setRawOpen(false);
    setLog(null);
    setLogError('');
    setFollow(false);
    closeRef.current?.focus();
  }, [finding?.key]);

  useEffect(() => {
    if (!finding) return;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [finding, onClose]);

  useEffect(() => {
    if (tab === 'agent' && finding && !log && !logLoading) loadLog();
  }, [tab, finding, log, logLoading, loadLog]);

  useEffect(() => {
    if (tab === 'evidence' && rawOpen && finding && !raw) loadRaw();
  }, [tab, rawOpen, finding, raw, loadRaw]);

  useEffect(() => {
    if (!follow || tab !== 'agent' || !finding) return;
    const timer = window.setInterval(() => loadLog(true), 5000);
    return () => window.clearInterval(timer);
  }, [follow, tab, finding, loadLog]);

  if (!finding) return null;

  const patch = async (data) => {
    setSaving(true);
    try {
      await onPatch(finding, data);
    } finally {
      setSaving(false);
    }
  };

  const saveNotes = () => patch({ notes });
  const saveKnownCve = () => patch({ knownCve });
  const sourceItems = [...new Set([...finding.evidence, ...finding.files, finding.location].filter(Boolean))];
  const startLine = log ? Math.max(1, log.totalLines - log.lines.length + 1) : 1;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside
        className="detail-drawer"
        style={drawerWidth ? { width: drawerWidth } : undefined}
        role="dialog"
        aria-modal="true"
        aria-label={`${finding.projectName} ${finding.id}`}
      >
        <DrawerResizer width={drawerWidth} onResize={setDrawerWidth} onReset={resetDrawerWidth} />
        <header className="drawer-head">
          <div className="drawer-head-top">
            <div className="drawer-ident">
              <SeverityStamp severity={finding.severity} />
              <span className="drawer-project">{finding.projectName}</span>
              <span className="drawer-id">#{finding.id}</span>
            </div>
            <div className="drawer-actions">
              {saving ? <span className="saving-indicator">SAVING</span> : null}
              <button ref={closeRef} type="button" className="icon-button on-dark" title="关闭" aria-label="关闭详情" onClick={onClose}>
                <X size={18} />
              </button>
            </div>
          </div>
          <h2>{finding.title}</h2>
          <div className="drawer-badges">
            <VerdictBadge verdict={finding.verdict} />
            <CveBadge tier={finding.cveTier} knownCve={finding.knownCve} status={finding.cveStatus} />
            {finding.verified ? <span className="verified-badge">VERIFIED</span> : null}
            <span className="confidence-label">confidence {finding.confidence}</span>
          </div>
          <nav className="drawer-tabs" aria-label="详情视图">
            {[
              ['brief', 'Brief'],
              ['evidence', 'Evidence'],
              ['agent', 'Agent stream'],
              ['claude', 'Claude UI'],
              ['trajectory', 'Trajectory']
            ].map(([id, label]) => (
              <button key={id} type="button" className={cx(tab === id && 'is-active')} onClick={() => setTab(id)}>
                {label}
              </button>
            ))}
          </nav>
        </header>

        <div className="drawer-body">
          {tab === 'brief' ? (
            <>
              <section className="detail-section decision-section">
                <div className="decision-head">
                  <h3>Pipeline</h3>
                  <span>{finding.curated ? 'CURATED' : 'RAW'}</span>
                </div>
                <div className="status-grid">
                  {COLUMNS.map((column) => (
                    <button
                      key={column.id}
                      type="button"
                      className={cx('status-button', `status-${column.id}`, finding.status === column.id && 'is-active')}
                      onClick={() => patch({ status: column.id })}
                    >
                      <span>{column.code}</span>
                      <small>{column.label}</small>
                    </button>
                  ))}
                </div>
                <div className="verdict-row">
                  <span className="field-label">判定</span>
                  <div className="segmented">
                    {VERDICTS.map((verdict) => (
                      <button
                        key={verdict.id}
                        type="button"
                        className={cx(finding.verdict === verdict.id && 'is-active')}
                        title={verdict.full}
                        onClick={() => patch({ verdict: verdict.id })}
                      >
                        {verdict.label}
                      </button>
                    ))}
                  </div>
                </div>
              </section>

              <section className="detail-section cve-section">
                <div className="decision-head">
                  <h3>CVE track</h3>
                  <span>{finding.cveStatus || 'none'}</span>
                </div>
                <div className="cve-controls">
                  <div className="segmented">
                    <button type="button" className={cx(!finding.cveTier && 'is-active')} onClick={() => patch({ cveTier: null })}>
                      None
                    </button>
                    <button type="button" className={cx(finding.cveTier === 1 && 'is-active')} onClick={() => patch({ cveTier: 1 })}>
                      Tier 1
                    </button>
                    <button type="button" className={cx(finding.cveTier === 2 && 'is-active')} onClick={() => patch({ cveTier: 2 })}>
                      Tier 2
                    </button>
                  </div>
                  <label className="select-field">
                    <span>状态</span>
                    <select value={finding.cveStatus} onChange={(event) => patch({ cveStatus: event.target.value })}>
                      {CVE_STATUSES.map((status) => (
                        <option key={status.id} value={status.id}>
                          {status.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="text-field">
                  <span>关联 CVE</span>
                  <div className="inline-field">
                    <input
                      value={knownCve}
                      onChange={(event) => setKnownCve(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') saveKnownCve();
                      }}
                      placeholder="例如 CVE-2026-15977"
                      spellCheck={false}
                    />
                    <button type="button" className="button is-small" onClick={saveKnownCve}>
                      保存
                    </button>
                  </div>
                </label>
              </section>

              <DetailSection label="ROOT CAUSE">
                <TextBlock value={finding.rootCause} />
              </DetailSection>
              <DetailSection label="IMPACT">
                <TextBlock value={finding.impact} />
              </DetailSection>
              {finding.preconditions.length ? (
                <DetailSection label="PRECONDITIONS">
                  <ul className="precondition-list">
                    {finding.preconditions.map((item) => (
                      <li key={item}>
                        <span className="precondition-mark">□</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </DetailSection>
              ) : null}
              <DetailSection label="REPRODUCTION IDEA" tone="signal">
                <TextBlock value={finding.reproduction} />
              </DetailSection>
              <DetailSection label="REMEDIATION">
                <TextBlock value={finding.remediation} />
              </DetailSection>
              {finding.finalReviewNote ? (
                <DetailSection label="REVIEW NOTE" tone="muted">
                  <TextBlock value={finding.finalReviewNote} />
                </DetailSection>
              ) : null}

              <section className="detail-section notes-section">
                <div className="decision-head">
                  <h3>Audit notes</h3>
                  <span>{notes.length} chars</span>
                </div>
                <textarea
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  onKeyDown={(event) => {
                    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                      event.preventDefault();
                      saveNotes();
                    }
                  }}
                  placeholder="记录可达性、版本、去重结论、复现结果…"
                  rows={5}
                />
                <div className="notes-actions">
                  <button type="button" className="button is-primary is-small" onClick={saveNotes}>
                    <Save size={13} aria-hidden="true" />
                    保存备注
                  </button>
                  <span>Cmd/Ctrl + Enter</span>
                </div>
              </section>

              <DetailSection label="CASE FILE">
                <dl className="case-meta">
                  <div>
                    <dt>Report</dt>
                    <dd>
                      <code>{finding.reportPath}</code>
                      <button type="button" className="icon-button is-tiny" title="复制报告路径" aria-label="复制报告路径" onClick={() => copy(finding.reportPath, '已复制报告路径')}>
                        <Copy size={12} />
                      </button>
                    </dd>
                  </div>
                  <div>
                    <dt>Run</dt>
                    <dd>
                      <code>{finding.runId}</code>
                      <span className="meta-state">{project?.state || 'unknown'}</span>
                    </dd>
                  </div>
                  <div>
                    <dt>Commit</dt>
                    <dd>
                      <code>{finding.commit || '—'}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>CVSS</dt>
                    <dd>{finding.cvssScore ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>Generated</dt>
                    <dd>{formatDateTime(finding.generatedAt)}</dd>
                  </div>
                </dl>
              </DetailSection>
            </>
          ) : null}

          {tab === 'evidence' ? (
            <>
              <DetailSection label="SOURCE EVIDENCE">
                <EvidenceList items={sourceItems} onCopy={(value) => copy(value, '已复制证据')} />
              </DetailSection>
              <DetailSection label="RELATED ARTIFACTS">
                <EvidenceList items={finding.relatedArtifacts} onCopy={(value) => copy(value, '已复制工件路径')} />
              </DetailSection>
              <DetailSection label="REPORTS">
                <div className="report-links">
                  <a href={`/api/runs/${finding.project}/${finding.runId}/report.md`} target="_blank" rel="noreferrer">
                    <FileText size={14} aria-hidden="true" />
                    打开 audit-report.md
                    <ExternalLink size={12} aria-hidden="true" />
                  </a>
                  <a href={`/api/runs/${finding.project}/${finding.runId}/report.json`} target="_blank" rel="noreferrer">
                    <FileJson size={14} aria-hidden="true" />
                    打开 audit-report.json
                    <ExternalLink size={12} aria-hidden="true" />
                  </a>
                </div>
              </DetailSection>
              <DetailSection label="RAW FINDING">
                <button
                  type="button"
                  className="button is-small"
                  onClick={async () => {
                    setRawOpen((value) => !value);
                    if (!raw) await loadRaw();
                  }}
                >
                  {rawOpen ? '隐藏原始 JSON' : '查看原始 JSON'}
                </button>
                {rawOpen ? (
                  <pre className="raw-json">{raw ? JSON.stringify(raw.raw, null, 2) : '加载中…'}</pre>
                ) : null}
              </DetailSection>
            </>
          ) : null}

          {tab === 'agent' ? (
            <>
              <section className="agent-meta">
                <div>
                  <span>RUN</span>
                  <strong>{finding.runId}</strong>
                </div>
                <div>
                  <span>STATE</span>
                  <strong className={`state-text state-${project?.state || 'unknown'}`}>{project?.state || 'unknown'}</strong>
                </div>
                <div>
                  <span>MODEL</span>
                  <strong>{project?.model || '—'}</strong>
                </div>
                <div>
                  <span>DURATION</span>
                  <strong>{project?.durationSeconds ? `${Math.round(project.durationSeconds / 60)}m` : '—'}</strong>
                </div>
              </section>
              <div className="agent-toolbar">
                <button type="button" className="button is-small" onClick={() => loadLog()} disabled={logLoading}>
                  <RefreshCw size={13} className={cx(logLoading && 'is-spinning')} aria-hidden="true" />
                  刷新
                </button>
                <label className="follow-toggle">
                  <input type="checkbox" checked={follow} onChange={(event) => setFollow(event.target.checked)} />
                  自动刷新 5s
                </label>
                <button
                  type="button"
                  className="button is-small"
                  onClick={() => copy(`bash run.sh --verify-only ${finding.runDir}`, '已复制验证命令')}
                >
                  <Terminal size={13} aria-hidden="true" />
                  复制验证命令
                </button>
              </div>
              <div className="log-meta">
                <span>{log?.path || project?.logPath || 'claude.rendered.log'}</span>
                <span>{log ? `${log.totalLines} lines · ${formatDateTime(log.mtime)}` : ''}</span>
              </div>
              {logError ? <div className="inline-error">{logError}</div> : null}
              <pre className="agent-log" aria-label="Agent rendered log">
                {logLoading && !log ? 'Loading agent stream…\n' : null}
                {log?.lines?.map((line, index) => (
                  <span className="log-line" key={`${startLine + index}-${line.slice(0, 20)}`}>
                    <span className="log-number">{startLine + index}</span>
                    <span className="log-text">{line || ' '}</span>
                  </span>
                ))}
                {!logLoading && !log?.lines?.length ? <span className="log-empty">No rendered log for this run.</span> : null}
              </pre>
            </>
          ) : null}
          {tab === 'claude' ? (
            <ClaudeSessionEmbed
              project={finding.project}
              runId={finding.runId}
              live={Boolean(project?.isLive && project.latestRunId === finding.runId)}
            />
          ) : null}
          {tab === 'trajectory' ? (
            <TrajectoryPanel
              project={finding.project}
              runId={finding.runId}
              finished={!(project?.isLive && project.latestRunId === finding.runId)}
            />
          ) : null}
        </div>

        <footer className="drawer-footer">
          <span className="footer-signal">
            <Shield size={13} aria-hidden="true" />
            static report · {finding.verdict === 'tp' ? 'code-level TP' : finding.verdict}
          </span>
          <div className="footer-actions">
            <button type="button" className="button is-small" onClick={() => copy(finding.key, '已复制 finding key')}>
              <Copy size={13} aria-hidden="true" />
              Copy key
            </button>
            <button type="button" className="button is-small" onClick={() => copy(finding.sourcePaths?.[0] || finding.reportPath, '已复制路径')}>
              <GitCommit size={13} aria-hidden="true" />
              Copy source
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}
