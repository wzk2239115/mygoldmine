// The browser and Python gate share this contract; parity is tested without model calls.
function text(value) {
  if (Array.isArray(value)) return value.map(text).filter(Boolean).join(' ');
  if (value && typeof value === 'object') {
    return text(value.idea || value.steps || value.note || value.description || '');
  }
  return typeof value === 'string' ? value.trim() : '';
}

function hasEvidence(value) {
  const items = typeof value === 'string' ? value.split(/\r?\n/) : value;
  return Array.isArray(items) && items.some(item => {
    if (typeof item === 'string') return Boolean(item.trim());
    return item && typeof item === 'object' && !Array.isArray(item) && Boolean(
      text(item.path || item.file) || text(item.description || item.snippet)
    );
  });
}

export function reportQuality(raw, language = 'zh') {
  raw = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
  const verification = raw.verification || {};
  const values = {
    title: text(raw.title),
    rootCause: text(raw.root_cause || raw.rootCause || raw.description || raw.summary || raw.type),
    impact: text(raw.impact || raw.effect || raw.consequence),
    reproduction: text(raw.reproduction_idea || raw.reproduction || raw.exploit || raw.poc ||
      raw.poc_steps || raw.test_plan || raw.verification_idea || verification.idea ||
      verification.steps || verification.reproduction),
    remediation: text(raw.remediation_items || raw.remediation || raw.fix || raw.fixed_code ||
      raw.recommendation || raw.remediation_note),
    evidence: hasEvidence(raw.evidence)
  };
  const missing = Object.entries(values).filter(([, value]) => !value).map(([field]) => field);
  const titleLanguage = /[\u4e00-\u9fff]/.test(values.title) ? 'zh' :
    (/[A-Za-z]/.test(values.title) ? 'en' : 'unknown');
  const languageMismatch = language === 'zh' && Boolean(values.title) && titleLanguage !== 'zh';
  if (languageMismatch) missing.push('titleLanguage');
  return {ok: missing.length === 0, score: Math.round((6 - missing.length) / 6 * 100),
    missing, titleLanguage, languageMismatch};
}
