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
  board: () => request('/api/board'),
  live: () => request('/api/live'),
  visual: (project, runId) => request(`/api/visual/${encodeURIComponent(project)}/${encodeURIComponent(runId)}`),
  runs: () => request('/api/runs'),
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
  raw: (project, id) =>
    request(`/api/findings/${encodeURIComponent(project)}/${encodeURIComponent(id)}/raw`),
  update: (project, id, patch) =>
    request(`/api/findings/${encodeURIComponent(project)}/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(patch)
    })
};
