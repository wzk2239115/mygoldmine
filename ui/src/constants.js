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
    hint: '自动分类进入分诊；自动流转后台任务会调用验证智能体',
    tone: 'cool'
  },
  {
    id: 'reproduce',
    code: 'REPRODUCE',
    label: '待验证',
    hint: 'CVE 等级候选或已有确认的验证结论；自动流转会补图文报告并触发红队',
    tone: 'amber'
  },
  {
    id: 'cve',
    code: 'CVE TRACK',
    label: 'CVE 跟踪',
    hint: '先查已知 CVE 和 GHSA 去重，再披露或联系 CNA',
    tone: 'hot'
  },
  {
    id: 'review',
    code: 'REVIEW',
    label: '待验收',
    hint: '红队捕获随机标记、独立审核通过并生成图文报告',
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
  { id: 'critical', label: 'CRIT', full: '严重' },
  { id: 'high', label: 'HIGH', full: '高危' },
  { id: 'medium', label: 'MED', full: '中危' },
  { id: 'low', label: 'LOW', full: '低危' },
  { id: 'info', label: 'INFO', full: '信息' }
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
