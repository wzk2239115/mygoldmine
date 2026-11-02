export const COLUMNS = [
  {
    id: 'inbox',
    code: 'INBOX',
    label: '未处理候选',
    hint: '未进入流程的候选问题',
    tone: 'neutral'
  },
  {
    id: 'triage',
    code: 'TRIAGE',
    label: '分诊',
    hint: 'Critical/High 自动进入初筛队列，等待人工判定',
    tone: 'cool'
  },
  {
    id: 'reproduce',
    code: 'REPRODUCE',
    label: '待验证',
    hint: 'CVE Tier 候选或 confirmed verify；等待验证（尚未复现）',
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
    id: 'review',
    code: 'REVIEW',
    label: '待验收',
    hint: '红队捕获 flag、judge 通过并生成图文报告',
    tone: 'green',
    virtual: true
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

export const STATUS_LABELS = { ...Object.fromEntries(COLUMNS.map((column) => [column.id, column.label])), archived: '已归档' };
export const VERDICT_LABELS = Object.fromEntries(VERDICTS.map((verdict) => [verdict.id, verdict.label]));
export const CVE_STATUS_LABELS = Object.fromEntries(CVE_STATUSES.map((status) => [status.id, status.label]));
export const PROJECT_ORDER = ['vllm', 'sglang', 'deepseek-harness', 'codex', 'verl'];
