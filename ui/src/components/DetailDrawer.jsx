import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Copy,
  ExternalLink,
  FileJson,
  FileText,
  GitCommit,
  RefreshCw,
  Shield,
  Terminal,
  X
} from 'lucide-react';
import { api } from '../api.js';
import { COLUMNS, CVE_STATUSES, VERDICTS } from '../constants.js';
import { cx, formatDateTime } from '../utils.js';
import { useI18n } from '../i18n.jsx';
import { CveBadge, SeverityStamp, VerdictBadge } from './Badges.jsx';
import TrajectoryPanel from './TrajectoryPanel.jsx';
import DrawerResizer, { useDrawerWidth } from './DrawerResizer.jsx';

const AUTO_SOURCE_KEYS = {
  severity: 'drawer.sourceSeverity',
  verify: 'drawer.sourceVerify',
  handoff: 'drawer.sourceHandoff',
  adjudication: 'drawer.sourceAdjudication'
};

function DetailSection({ label, children, tone }) {
  if (!children) return null;
  return (
    <section className={cx('detail-section', tone && `detail-section-${tone}`)}>
      <h3>{label}</h3>
      {children}
    </section>
  );
}

function TextBlock({ value, emptyText }) {
  if (!value) return <p className="detail-missing">{emptyText}</p>;
  return <p className="detail-text">{value}</p>;
}

function EvidenceList({ items, onCopy, emptyText, copyTitle }) {
  if (!items?.length) return <p className="detail-empty">{emptyText}</p>;
  return (
    <ul className="evidence-list">
      {items.map((item, index) => (
        <li key={`${item}-${index}`}>
          <span className="evidence-index">{String(index + 1).padStart(2, '0')}</span>
          <code>{item}</code>
          <button type="button" className="icon-button is-tiny" title={copyTitle} aria-label={`${copyTitle} ${item}`} onClick={() => onCopy(item)}>
            <Copy size={12} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function DetailDrawer({ finding, board, onClose, onPatch, onToast }) {
  const { t } = useI18n();
  const qualityLabels = {
    title: t('drawer.title'),
    rootCause: t('drawer.rootCause'),
    impact: t('drawer.impact'),
    reproduction: t('drawer.reproduction'),
    remediation: t('drawer.remediation'),
    evidence: t('drawer.evidence'),
    titleLanguage: t('drawer.titleLanguage')
  };

  const [tab, setTab] = useState('brief');
  const [drawerWidth, setDrawerWidth, resetDrawerWidth] = useDrawerWidth();
  const [knownCve, setKnownCve] = useState('');
  const [log, setLog] = useState(null);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState('');
  const [follow, setFollow] = useState(false);
  const [raw, setRaw] = useState(null);
  const [rawOpen, setRawOpen] = useState(false);
  const [rawLoading, setRawLoading] = useState(false);
  const [rawError, setRawError] = useState('');
  const [saving, setSaving] = useState(false);
  const closeRef = useRef(null);
  const savingRef = useRef(false);

  const project = finding ? board?.projects?.find((item) => item.id === finding.project) : null;

  const copy = useCallback(
    async (value, label = t('drawer.copied')) => {
      const ok = await navigator.clipboard.writeText(value).then(() => true).catch(() => false);
      onToast?.(ok ? `${label}: ${value}` : t('drawer.copyFailed'), ok ? 'success' : 'error');
    },
    [onToast, t]
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
    if (!finding || raw || rawLoading) return;
    setRawLoading(true);
    setRawError('');
    try {
      const payload = await api.raw(finding.project, finding.id, finding.occurrence_id);
      setRaw(payload);
    } catch (error) {
      setRawError(error.message);
      onToast?.(error.message, 'error');
    } finally {
      setRawLoading(false);
    }
  }, [finding, raw, rawLoading, onToast]);

  useEffect(() => {
    if (!finding) return;
    setKnownCve(finding.knownCve || '');
    setRaw(null);
    setRawOpen(false);
    setRawLoading(false);
    setRawError('');
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
    if (tab === 'evidence' && rawOpen && finding && !raw && !rawLoading && !rawError) loadRaw();
  }, [tab, rawOpen, finding, raw, rawLoading, rawError, loadRaw]);

  useEffect(() => {
    if (!follow || tab !== 'agent' || !finding) return;
    const timer = window.setInterval(() => loadLog(true), 5000);
    return () => window.clearInterval(timer);
  }, [follow, tab, finding, loadLog]);

  if (!finding) return null;

  const patch = async (data) => {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    try {
      await onPatch(finding, data);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

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
              {saving ? <span className="saving-indicator">{t('drawer.saving')}</span> : null}
              <button ref={closeRef} type="button" className="icon-button on-dark" title={t('drawer.close')} aria-label={t('drawer.close')} onClick={onClose}>
                <X size={18} />
              </button>
            </div>
          </div>
          <h2>{finding.title}</h2>
          <div className="drawer-badges">
            <VerdictBadge verdict={finding.verdict} />
            <CveBadge tier={finding.cveTier} knownCve={finding.knownCve} status={finding.cveStatus} />
            {finding.verified ? <span className="verified-badge">{t('drawer.verified')}</span> : null}
            <span className="confidence-label">{t('drawer.confidence')} {finding.confidence}</span>
          </div>
          <nav className="drawer-tabs" aria-label={t('drawer.tabsLabel')}>
            {[
              ['brief', 'tabs.brief'],
              ['evidence', 'tabs.evidence'],
              ['agent', 'tabs.agent'],
              ['trajectory', 'tabs.trajectory']
            ].map(([id, labelKey]) => (
              <button key={id} type="button" className={cx(tab === id && 'is-active')} onClick={() => setTab(id)}>
                {t(labelKey)}
              </button>
            ))}
          </nav>
        </header>

        <div className="drawer-body">
          {tab === 'brief' ? (
            <>
              {finding.quality && !finding.quality.ok ? (
                <div className="quality-warning" role="status">
                  <strong>{t('drawer.qualityMissing')}</strong>
                  {finding.quality.missing.map((field) => qualityLabels[field] || field).join('、')}
                  <span>{finding.quality.score}/100</span>
                </div>
              ) : null}
              <section className="detail-section decision-section">
                <div className="decision-head">
                  <h3>{t('drawer.pipeline')}</h3>
                  <span>{finding.curated ? t('drawer.curated') : t('drawer.raw')}</span>
                </div>
                <div className="status-grid">
                  {COLUMNS.filter((column) => !column.virtual).map((column) => (
                    <button
                      key={column.id}
                      type="button"
                      className={cx('status-button', `status-${column.id}`, finding.status === column.id && 'is-active')}
                      onClick={() => patch({ status: column.id })}
                      disabled={saving}
                    >
                      <span>{column.code}</span>
                      <small>{column.label}</small>
                    </button>
                  ))}
                </div>
                {finding.routedBy === 'auto' ? (
                  <p className="auto-route" title={finding.autoDetail || finding.autoReason}>
                    {t('drawer.autoRouted')}: {finding.autoReason || 'verify / CVE'}
                    {finding.autoSource ? ` · ${AUTO_SOURCE_KEYS[finding.autoSource] ? t(AUTO_SOURCE_KEYS[finding.autoSource]) : finding.autoSource}` : ''}
                  </p>
                ) : null}
                {finding.reviewReady ? (
                  <p className="review-ready">
                    {t('drawer.reviewReady')} · {finding.reviewReason || ''}
                    {finding.reviewScore ? ` · ${t('drawer.reviewScore')} ${finding.reviewScore}` : ''}
                  </p>
                ) : null}
                <div className="verdict-row">
                  <span className="field-label">{t('drawer.verdict')}</span>
                  <div className="verdict-options">
                    {VERDICTS.map((verdict) => (
                      <button
                        key={verdict.id}
                        type="button"
                        className={cx('verdict-option', finding.verdict === verdict.id && 'is-active')}
                        title={t(`verdict.${verdict.id}.desc`)}
                        onClick={() => patch({ verdict: verdict.id })}
                        disabled={saving}
                      >
                        <strong>{t(`verdict.${verdict.id}.label`)}</strong>
                        <span>{t(`verdict.${verdict.id}.code`)}</span>
                      </button>
                    ))}
                  </div>
                  <p className="verdict-help">
                    <b>{t('verdict.current')}：{t(`verdict.${finding.verdict || 'untriaged'}.label`)}</b>
                    {t(`verdict.${finding.verdict || 'untriaged'}.desc`)}
                  </p>
                </div>
              </section>

              <section className="detail-section cve-section">
                <div className="decision-head">
                  <h3>{t('drawer.cveDedup')}</h3>
                  <span>{t(`cve.${finding.cveStatus || 'none'}`)}</span>
                </div>
                <p className="field-hint">先查 NVD/GHSA/项目公告确认是否已被覆盖；重复时填写 known CVE 并关闭。</p>
                <div className="cve-controls">
                  <div className="segmented">
                    <button type="button" className={cx(!finding.cveTier && 'is-active')} onClick={() => patch({ cveTier: null })} disabled={saving}>
                      {t('cve.none')}
                    </button>
                    <button type="button" className={cx(finding.cveTier === 1 && 'is-active')} onClick={() => patch({ cveTier: 1 })} disabled={saving}>
                      {t('cve.tier1')}
                    </button>
                    <button type="button" className={cx(finding.cveTier === 2 && 'is-active')} onClick={() => patch({ cveTier: 2 })} disabled={saving}>
                      {t('cve.tier2')}
                    </button>
                  </div>
                  <label className="select-field">
                    <span>{t('drawer.status')}</span>
                    <select value={finding.cveStatus} onChange={(event) => patch({ cveStatus: event.target.value })} disabled={saving}>
                      {CVE_STATUSES.map((status) => (
                        <option key={status.id} value={status.id}>
                          {t(`cve.${status.id}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="text-field">
                  <span>{t('drawer.relatedCve')}</span>
                  <div className="inline-field">
                    <input
                      value={knownCve}
                      onChange={(event) => setKnownCve(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') saveKnownCve();
                      }}
                      placeholder={t('drawer.cvePlaceholder')}
                      spellCheck={false}
                      disabled={saving}
                    />
                    <button type="button" className="button is-small" onClick={saveKnownCve} disabled={saving}>
                      {t('common.save')}
                    </button>
                  </div>
                </label>
              </section>

              <DetailSection label={t('drawer.rootCause')}>
                <TextBlock value={finding.rootCause} emptyText={`${t('drawer.missing')} · ${t('drawer.rootCause')}`} />
              </DetailSection>
              <DetailSection label={t('drawer.impact')}>
                <TextBlock value={finding.impact} emptyText={`${t('drawer.missing')} · ${t('drawer.impact')}`} />
              </DetailSection>
              {finding.preconditions.length ? (
                <DetailSection label={t('drawer.preconditions')}>
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
              <DetailSection label={t('drawer.reproduction')} tone="signal">
                <TextBlock value={finding.reproduction} emptyText={`${t('drawer.missing')} · ${t('drawer.reproduction')}`} />
              </DetailSection>
              <DetailSection label={t('drawer.remediation')}>
                <TextBlock value={finding.remediation} emptyText={`${t('drawer.missing')} · ${t('drawer.remediation')}`} />
              </DetailSection>
              {finding.finalReviewNote ? (
                <DetailSection label={t('drawer.reviewNote')} tone="muted">
                  <TextBlock value={finding.finalReviewNote} />
                </DetailSection>
              ) : null}

              <DetailSection label={t('drawer.caseFile')}>
                <dl className="case-meta">
                  <div>
                    <dt>{t('drawer.report')}</dt>
                    <dd>
                      <code>{finding.reportPath}</code>
                      <button type="button" className="icon-button is-tiny" title={t('drawer.copy')} aria-label={t('drawer.copy')} onClick={() => copy(finding.reportPath)}>
                        <Copy size={12} />
                      </button>
                    </dd>
                  </div>
                  <div>
                    <dt>{t('drawer.run')}</dt>
                    <dd>
                      <code>{finding.runId}</code>
                      <span className="meta-state">{project?.state || 'unknown'}</span>
                    </dd>
                  </div>
                  <div>
                    <dt>{t('drawer.commit')}</dt>
                    <dd>
                      <code>{finding.commit || '—'}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>{t('drawer.cvss')}</dt>
                    <dd>{finding.cvssScore ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>{t('drawer.generated')}</dt>
                    <dd>{formatDateTime(finding.generatedAt)}</dd>
                  </div>
                </dl>
              </DetailSection>
            </>
          ) : null}

          {tab === 'evidence' ? (
            <>
              <DetailSection label={t('drawer.sourceEvidence')}>
                <EvidenceList items={sourceItems} emptyText={t('drawer.noEvidence')} copyTitle={t('drawer.copy')} onCopy={(value) => copy(value)} />
              </DetailSection>
              <DetailSection label={t('drawer.relatedArtifacts')}>
                <EvidenceList items={finding.relatedArtifacts} emptyText={t('drawer.noEvidence')} copyTitle={t('drawer.copy')} onCopy={(value) => copy(value)} />
              </DetailSection>
              <DetailSection label={t('drawer.reports')}>
                <div className="report-links">
                  <a href={`/api/runs/${finding.project}/${finding.runId}/report.md`} target="_blank" rel="noreferrer">
                    <FileText size={14} aria-hidden="true" />
                    {t('drawer.openMd')}
                    <ExternalLink size={12} aria-hidden="true" />
                  </a>
                  <a href={`/api/runs/${finding.project}/${finding.runId}/report.json`} target="_blank" rel="noreferrer">
                    <FileJson size={14} aria-hidden="true" />
                    {t('drawer.openJson')}
                    <ExternalLink size={12} aria-hidden="true" />
                  </a>
                </div>
              </DetailSection>
              <DetailSection label={t('drawer.rawFinding')}>
                <button
                  type="button"
                  className="button is-small"
                  onClick={() => setRawOpen((value) => !value)}
                >
                  {rawOpen ? t('drawer.hideRaw') : t('drawer.showRaw')}
                </button>
                {rawOpen ? (
                  raw ? (
                    <pre className="raw-json">{JSON.stringify(raw.raw, null, 2)}</pre>
                  ) : rawError ? (
                    <div className="inline-error" role="alert">
                      <span>{rawError}</span>
                      <button type="button" className="button is-small" onClick={() => loadRaw()} disabled={rawLoading}>
                        <RefreshCw size={13} aria-hidden="true" />
                        重试
                      </button>
                    </div>
                  ) : (
                    <pre className="raw-json">{t('common.loading')}</pre>
                  )
                ) : null}
              </DetailSection>
            </>
          ) : null}

          {tab === 'agent' ? (
            <>
              <section className="agent-meta">
                <div>
                  <span>{t('drawer.runLabel')}</span>
                  <strong>{finding.runId}</strong>
                </div>
                <div>
                  <span>{t('drawer.state')}</span>
                  <strong className={`state-text state-${project?.state || 'unknown'}`}>{project?.state || 'unknown'}</strong>
                </div>
                <div>
                  <span>{t('drawer.model')}</span>
                  <strong>{project?.model || '—'}</strong>
                </div>
                <div>
                  <span>{t('drawer.duration')}</span>
                  <strong>{project?.durationSeconds ? `${Math.round(project.durationSeconds / 60)}m` : '—'}</strong>
                </div>
              </section>
              <div className="agent-toolbar">
                <button type="button" className="button is-small" onClick={() => loadLog()} disabled={logLoading}>
                  <RefreshCw size={13} className={cx(logLoading && 'is-spinning')} aria-hidden="true" />
                  {t('common.refresh')}
                </button>
                <label className="follow-toggle">
                  <input type="checkbox" checked={follow} onChange={(event) => setFollow(event.target.checked)} />
                  {t('drawer.autoRefresh')}
                </label>
                <button
                  type="button"
                  className="button is-small"
                  onClick={() => copy(`bash run.sh --verify-only ${finding.runDir}`)}
                >
                  <Terminal size={13} aria-hidden="true" />
                  {t('drawer.copyVerify')}
                </button>
              </div>
              <div className="log-meta">
                <span>{log?.path || project?.logPath || 'claude.rendered.log'}</span>
                <span>{log ? `${log.totalLines} lines · ${formatDateTime(log.mtime)}` : ''}</span>
              </div>
              {logError ? <div className="inline-error">{logError}</div> : null}
              <pre className="agent-log" aria-label={t('tabs.agent')}>
                {logLoading && !log ? `${t('common.loading')}\n` : null}
                {log?.lines?.map((line, index) => (
                  <span className="log-line" key={`${startLine + index}-${line.slice(0, 20)}`}>
                    <span className="log-number">{startLine + index}</span>
                    <span className="log-text">{line || ' '}</span>
                  </span>
                ))}
                {!logLoading && !log?.lines?.length ? <span className="log-empty">{t('drawer.noLog')}</span> : null}
              </pre>
            </>
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
            {t('drawer.footerStatic')} · {finding.verdict === 'tp' ? t('drawer.codeTp') : finding.verdict}
          </span>
          <div className="footer-actions">
            <button type="button" className="button is-small" onClick={() => copy(finding.key)}>
              <Copy size={13} aria-hidden="true" />
              {t('drawer.copyKey')}
            </button>
            <button type="button" className="button is-small" onClick={() => copy(finding.sourcePaths?.[0] || finding.reportPath)}>
              <GitCommit size={13} aria-hidden="true" />
              {t('drawer.copySource')}
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}
