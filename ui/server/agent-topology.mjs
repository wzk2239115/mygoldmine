import fs from 'node:fs';

const AGENT_TOOL_NAMES = new Set(['Agent', 'Task']);
const BOUNDARY_PATTERNS = [
  ['filesystem', /filesystem|file system|工作区外文件|文件读写|路径穿越/],
  ['control-plane', /control[- ]plane|控制面|local[- ]control|app[- ]server|exec[- ]server/],
  ['process-exec', /process[- ]exec|process exec|命令\/?进程执行|subprocess|shell/],
  ['sandbox', /sandbox|沙箱|sandbox-local/],
  ['mcp', /\bmcp\b|model context protocol/],
  ['config', /config|配置|boot|plugin|AGENTS\.md|CLAUDE\.md/],
  ['model-loading', /model[- ]loading|trust_remote_code|torch\.load|from_pretrained/],
  ['http-auth', /http|grpc|auth|认证|授权|tenant/],
  ['ipc', /\bipc\b|serialization|序列化/],
  ['credentials', /credential|secret|token|api[-_ ]?key|凭据/]
];

function textFromContent(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item.text === 'string') return item.text;
        if (item && typeof item.content === 'string') return item.content;
        return '';
      })
      .filter(Boolean)
      .join('\n');
  }
  if (content && typeof content === 'object') {
    if (typeof content.text === 'string') return content.text;
    if (typeof content.content === 'string') return content.content;
  }
  return '';
}

function compact(text, limit = 260) {
  const value = String(text || '')
    .replace(/\r/g, '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

function matchBoundary(text) {
  const haystack = String(text || '').toLowerCase();
  for (const [boundary, pattern] of BOUNDARY_PATTERNS) {
    if (pattern.test(haystack)) return boundary;
  }
  return 'general';
}

export function deriveBoundary(description = '', prompt = '') {
  const fromDescription = matchBoundary(description);
  if (fromDescription !== 'general') return fromDescription;
  return matchBoundary(prompt.slice(0, 1200));
}

function countMatches(text, pattern) {
  const match = String(text || '').match(pattern);
  return match ? Number(match[1]) : null;
}

export function parseAgentTopology(rawPath) {
  const result = {
    agents: [],
    summary: { total: 0, running: 0, completed: 0, failed: 0 }
  };
  if (!rawPath || !fs.existsSync(rawPath)) return result;

  let raw = '';
  try {
    raw = fs.readFileSync(rawPath, 'utf8');
  } catch {
    return result;
  }

  const agents = new Map();
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim()) continue;
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      continue;
    }
    const content = event?.message?.content;
    if (!Array.isArray(content)) continue;

    for (const block of content) {
      if (!block || typeof block !== 'object') continue;
      if (block.type === 'tool_use' && AGENT_TOOL_NAMES.has(block.name)) {
        const input = block.input || {};
        const id = String(block.id || `agent-${agents.size + 1}`);
        if (agents.has(id)) continue;
        const description = String(input.description || '');
        agents.set(id, {
          id,
          agent: String(input.subagent_type || 'general-purpose'),
          description,
          boundary: deriveBoundary(description, String(input.prompt || '')),
          status: 'running',
          summary: '',
          startedAt: event.timestamp || null,
          completedAt: null,
          findings: null,
          hypotheses: null
        });
      }

      if (block.type === 'tool_result') {
        const agent = agents.get(String(block.tool_use_id || ''));
        if (!agent) continue;
        const output = textFromContent(block.content);
        agent.status = block.is_error ? 'error' : 'completed';
        agent.summary = compact(output);
        agent.completedAt = event.timestamp || null;
        agent.findings = countMatches(output, /(\d+)\s*(?:条\s*)?findings?/i);
        agent.hypotheses = countMatches(output, /(\d+)\s*(?:条\s*)?hypothes(?:is|es)/i);
      }
    }
  }

  result.agents = [...agents.values()];
  result.summary.total = result.agents.length;
  for (const agent of result.agents) {
    if (agent.status === 'completed') result.summary.completed += 1;
    else if (agent.status === 'error') result.summary.failed += 1;
    else result.summary.running += 1;
  }
  return result;
}
