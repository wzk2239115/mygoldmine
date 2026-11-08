async function importWithProgress(payload, onProgress, signal) {
  const response = await fetch('/api/targets/import-stream', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`导入请求失败（HTTP ${response.status}）`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = '';
  let result;
  const consume = (line) => {
    if (!line.trim()) return;
    const item = JSON.parse(line);
    if (item.type === 'info') onProgress(item);
    if (item.type === 'error') throw new Error(item.message);
    if (item.type === 'result') result = item.result;
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      const lines = pending.split('\n');
      pending = lines.pop();
      lines.forEach(consume);
      if (done) { consume(pending); break; }
    }
  } finally { reader.releaseLock(); }
  if (!result) throw new Error('导入状态连接已中断，请先查看项目列表和运行状态，确认后再重试。');
  return result;
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (payload.error) message = payload.error;
    } catch {
      // response was not JSON
    }
    throw new Error(message);
  }
  return response.json();
}

export const api = {
  importWithProgress,
  verifiedReports: () => request('/api/verified-reports'),
  startCycle: project => request('/api/targets/'+encodeURIComponent(project)+'/cycle/start', {method:'POST',body:JSON.stringify({continuous:true,rounds:8})}),
  stopCycle: project => request('/api/targets/'+encodeURIComponent(project)+'/cycle/stop', {method:'POST'}),
  nodeArtifacts: (project,runId,node) => request('/api/runs/'+encodeURIComponent(project)+'/'+encodeURIComponent(runId)+'/nodes/'+encodeURIComponent(node)+'/artifacts'),
  nodeArtifact: (project,runId,node,id) => request('/api/runs/'+encodeURIComponent(project)+'/'+encodeURIComponent(runId)+'/nodes/'+encodeURIComponent(node)+'/artifacts/'+id),
  nodeArtifactUrl: (project,runId,node,id) => '/api/runs/'+encodeURIComponent(project)+'/'+encodeURIComponent(runId)+'/nodes/'+encodeURIComponent(node)+'/artifacts/'+id,
  restartNode: (project, runId, node) => request(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(node)}/restart`, {method: 'POST'}),
  modelSettings: () => request('/api/stage-models'),
  saveModelSettings: (models) => request('/api/stage-models', {method:'POST',body:JSON.stringify({models})}),
  restartProject: (project) => request(`/api/targets/${encodeURIComponent(project)}/restart`, { method: 'POST' }),
  removeProject: (project) => request(`/api/targets/${encodeURIComponent(project)}`, { method: 'DELETE' }),
  board: () => request('/api/board'),
  serverDirectories: (directory = '') => request(`/api/targets/browse${directory ? `?path=${encodeURIComponent(directory)}` : ''}`),
  githubCommits: (source, { page = 1, limit = 10 } = {}) => request('/api/targets/github-commits', { method: 'POST', body: JSON.stringify({ source, page, limit }) }),
  githubBranches: (source, { offset = 0, limit = 10 } = {}) => request('/api/targets/github-branches', {
    method: 'POST',
    body: JSON.stringify({ source, offset, limit })
  }),
  importProject: (payload) => request('/api/targets/import', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  watch: () => request('/api/watch'),
  live: () => request('/api/live'),
  agents: (project, runId) =>
    request(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/agents`),
  pipeline: (project, runId) =>
    request(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/pipeline`),
  visual: (project, runId) => request(`/api/visual/${encodeURIComponent(project)}/${encodeURIComponent(runId)}`),
  runs: () => request('/api/runs'),
  ccuiStatus: () => request('/api/ccui'),
  runCcui: (project, runId, { force = false, node = 'orchestrator', trace = '' } = {}) => {
    const search = new URLSearchParams();
    if (force) search.set('force', '1');
    if (node !== 'orchestrator') search.set('node', node);
    if (trace) search.set('trace', trace);
    const suffix = search.toString();
    return request(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/ccui${suffix ? `?${suffix}` : ''}`);
  },
  traceText: (project, runId, node, trace = '') =>
    request(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/trace?node=${encodeURIComponent(node)}&id=${encodeURIComponent(trace)}`),
  log: (project, runId, lines = 400) =>
    request(`/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/log?lines=${lines}`),
  trajectory: (project, runId, params = {}) => {
    const search = new URLSearchParams();
    if (params.offset !== undefined && params.offset !== null) search.set('offset', params.offset);
    if (params.limit !== undefined && params.limit !== null) search.set('limit', params.limit);
    if (params.kind && params.kind !== 'all') search.set('kind', params.kind);
    if (params.q) search.set('q', params.q);
    const suffix = search.toString();
    return request(
      `/api/runs/${encodeURIComponent(project)}/${encodeURIComponent(runId)}/trajectory${suffix ? `?${suffix}` : ''}`
    );
  },
  raw: (project, id, occurrenceId = '') =>
    request(`/api/findings/${encodeURIComponent(project)}/${encodeURIComponent(id)}/raw${occurrenceId ? `?occurrence_id=${encodeURIComponent(occurrenceId)}` : ''}`),
  update: (project, id, patch, occurrenceId = '') =>
    request(`/api/findings/${encodeURIComponent(project)}/${encodeURIComponent(id)}${occurrenceId ? `?occurrence_id=${encodeURIComponent(occurrenceId)}` : ''}`, {
      method: 'PATCH',
      body: JSON.stringify(patch)
    })
};
