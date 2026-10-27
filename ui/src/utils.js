export function cx(...values) {
  return values.filter(Boolean).join(' ');
}

export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (number) => String(number).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toISOString().replace('T', ' ').replace('Z', ' UTC');
}

export function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `${hours}h ${rest}m`;
}

export function relativeTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime();
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} 天前`;
  return formatDate(value);
}

export function severityRank(severity) {
  return { critical: 0, high: 1, medium: 2, low: 3, info: 4 }[severity] ?? 9;
}

export function severityLabel(severity) {
  return { critical: 'CRIT', high: 'HIGH', medium: 'MED', low: 'LOW', info: 'INFO' }[severity] || 'INFO';
}

export function countBy(items, getter) {
  const result = {};
  for (const item of items) {
    const key = getter(item) || 'none';
    result[key] = (result[key] || 0) + 1;
  }
  return result;
}

export function truncate(value, length = 120) {
  const text = String(value || '');
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

export async function copyText(text) {
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function projectInitial(project) {
  const map = {
    vllm: 'V',
    sglang: 'S',
    'deepseek-harness': 'D',
    codex: 'C',
    verl: 'V'
  };
  return map[project] || String(project || '?').slice(0, 1).toUpperCase();
}
