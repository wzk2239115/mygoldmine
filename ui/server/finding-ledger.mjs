const CONFIRMED_VERDICTS = new Set([
  'confirmed', 'verified', 'reproduced', 'tp', 'true-positive', 'true_positive',
  '已确认', '已验证', '复现成功'
]);
const REJECTED_VERDICTS = new Set(['rejected', 'false-positive', 'false_positive', 'fp', 'not-a-vulnerability']);
const UNVERIFIED_VERDICTS = new Set([
  ...REJECTED_VERDICTS, 'unverified', 'not-verified', 'not_verified', '未验证', '未确认'
]);

export function normalizedVerdict(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

export function isVerified(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return false;
  const verification = raw.verification && typeof raw.verification === 'object' && !Array.isArray(raw.verification)
    ? raw.verification
    : null;
  const verdicts = [raw.verdict, verification ? verification.verdict : raw.verification];
  if (verification) verdicts.push(verification.status);
  if (verdicts.map(normalizedVerdict).some((value) => UNVERIFIED_VERDICTS.has(value))) return false;
  if (raw.verified === true || verification?.verified === true) return true;
  return verdicts.map(normalizedVerdict).some((value) => CONFIRMED_VERDICTS.has(value));
}

export function isLedgerV2(ledger) {
  return ledger?.schema_version === 2 &&
    ledger.findings && typeof ledger.findings === 'object' && !Array.isArray(ledger.findings) &&
    ledger.occurrences && typeof ledger.occurrences === 'object' && !Array.isArray(ledger.occurrences);
}

export function latestOccurrences(ledger) {
  if (!isLedgerV2(ledger)) return [];
  const result = [];
  for (const semantic of Object.values(ledger.findings)) {
    const occurrence = ledger.occurrences[semantic?.latest_occurrence_id];
    if (occurrence) result.push(occurrence);
  }
  return result;
}

export function legacyKey(project, findingId) {
  return `${project}:${String(findingId || '').replace(/\s+/g, '').toUpperCase()}`;
}

export function stateForFinding(finding, states, ledger) {
  if (!states || typeof states !== 'object' || Array.isArray(states)) return {};
  const occurrenceId = finding.occurrence_id || finding.occurrenceId || '';
  const semanticId = finding.semantic_id || finding.semanticId || '';
  const canonicalKey = finding.legacy_key || legacyKey(finding.project, finding.finding_id || finding.id);
  const oldKeys = [...new Set([`${finding.project}:${finding.id}`, canonicalKey])];
  const result = {};

  for (const oldKey of oldKeys) {
    if (!states[oldKey] || typeof states[oldKey] !== 'object') continue;
    if (!isLedgerV2(ledger)) {
      Object.assign(result, states[oldKey]);
    } else {
      const semantics = ledger.indexes?.legacy_to_semantics?.[canonicalKey] || [];
      if (semantics.length === 1 && semantics[0] === semanticId) Object.assign(result, states[oldKey]);
    }
  }
  if (semanticId && states[semanticId] && typeof states[semanticId] === 'object') {
    Object.assign(result, states[semanticId]);
  }
  if (occurrenceId && states[occurrenceId] && typeof states[occurrenceId] === 'object') {
    Object.assign(result, states[occurrenceId]);
  }
  return result;
}
