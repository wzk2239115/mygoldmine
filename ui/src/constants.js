export const COLUMNS = [
  {
    id: 'inbox',
    code: 'INBOX',
    label: '收件箱',
    hint: '未进入流程的新 finding',
    tone: 'neutral'
  },
  {
    id: 'triage',
    code: 'TRIAGE',
    label: '分诊',
    hint: 'Critical / High+verified 自动入队，等待人工判定',
    tone: 'cool'
  },
  {
    id: 'reproduce',
    code: 'REPRODUCE',
    label: '复现',
    hint: '已有 verify 记录；补充版本映射与最小 PoC',
    tone: 'amber'
  },
  {
    id: 'cve',
    code: 'CVE TRACK',
    label: 'CVE 跟踪',
    hint: '先查已知 CVE/GHSA 去重，再披露/CNA',
    tone: 'hot'
  },
  {
    id: 'closed',
    code: 'CLOSED',
    label: '已关闭',
    hint: '误报、重复、已知 CVE 或设计限制',
    tone: 'muted'
  }
];

export const SEVERITIES = [
  { id: 'critical', label: 'CRIT', full: 'Critical' },
  { id: 'high', label: 'HIGH', full: 'High' },
  { id: 'medium', label: 'MED', full: 'Medium' },
  { id: 'low', label: 'LOW', full: 'Low' },
  { id: 'info', label: 'INFO', full: 'Info' }
];

export const VERDICTS = [
  { id: 'tp', label: 'TP', full: '代码级成立' },
  { id: 'fp', label: 'FP', full: '误报' },
  { id: 'duplicate', label: 'DUP', full: '重复' },
  { id: 'unclear', label: 'UNCLEAR', full: '待定' },
  { id: 'untriaged', label: 'UNTRIAGED', full: '未判定' }
];

export const CVE_STATUSES = [
  { id: 'none', label: '无' },
  { id: 'tracking', label: '跟踪中' },
  { id: 'known', label: '已知 CVE' },
  { id: 'blocked', label: '受阻' },
  { id: 'disclosed', label: '已披露' }
];

export const STATUS_LABELS = Object.fromEntries(COLUMNS.map((column) => [column.id, column.label]));
export const VERDICT_LABELS = Object.fromEntries(VERDICTS.map((verdict) => [verdict.id, verdict.label]));
export const CVE_STATUS_LABELS = Object.fromEntries(CVE_STATUSES.map((status) => [status.id, status.label]));
export const PROJECT_ORDER = ['vllm', 'sglang', 'deepseek-harness', 'codex', 'verl'];
