import { AlertTriangle, BadgeCheck, CircleHelp, Copy, GitMerge, ShieldAlert } from 'lucide-react';
import { cx, severityLabel } from '../utils.js';

export function SeverityStamp({ severity, compact = false }) {
  return (
    <span className={cx('severity-stamp', `severity-${severity}`, compact && 'is-compact')} title={severity}>
      {severityLabel(severity)}
    </span>
  );
}

export function VerdictBadge({ verdict }) {
  if (!verdict || verdict === 'untriaged') return null;
  const map = {
    tp: { label: 'TP', title: '代码级成立', icon: BadgeCheck },
    fp: { label: 'FP', title: '误报', icon: ShieldAlert },
    duplicate: { label: 'DUP', title: '重复', icon: GitMerge },
    unclear: { label: '?', title: '待定', icon: CircleHelp }
  };
  const entry = map[verdict];
  if (!entry) return null;
  const Icon = entry.icon;
  return (
    <span className={cx('verdict-badge', `verdict-${verdict}`)} title={entry.title}>
      <Icon size={11} strokeWidth={2.2} aria-hidden="true" />
      {entry.label}
    </span>
  );
}

export function CveBadge({ tier, knownCve, status }) {
  if (knownCve) {
    return (
      <span className="cve-badge is-known" title={knownCve}>
        <AlertTriangle size={11} aria-hidden="true" />
        KNOWN
      </span>
    );
  }
  if (!tier) return null;
  return (
    <span className={cx('cve-badge', `is-tier-${tier}`)} title={`CVE Tier ${tier}`}>
      CVE T{tier}
    </span>
  );
}

export function CopyPathButton({ value, onToast, label = 'Copy path' }) {
  return (
    <button
      type="button"
      className="icon-button is-small"
      title={label}
      aria-label={label}
      onClick={async (event) => {
        event.stopPropagation();
        const ok = await navigator.clipboard.writeText(value).then(() => true).catch(() => false);
        if (onToast) onToast(ok ? `已复制：${value}` : '复制失败，请手动选择路径');
      }}
    >
      <Copy size={13} aria-hidden="true" />
    </button>
  );
}
