const base = process.env.UI_URL || 'http://127.0.0.1:8787';

async function get(path) {
  const response = await fetch(`${base}${path}`);
  if (!response.ok) throw new Error(`${path} -> HTTP ${response.status}`);
  return response.json();
}

const health = await get('/api/health');
if (!health.ok) throw new Error('health check failed');

const board = await get('/api/board');
if (!Array.isArray(board.projects) || !Array.isArray(board.findings)) throw new Error('board shape invalid');
if (board.stats.total !== board.findings.length) throw new Error('stats total mismatch');
if (board.stats.curated < 25) throw new Error(`expected at least 25 curated findings, got ${board.stats.curated}`);
if (board.stats.cveCandidates < 8) throw new Error(`expected at least 8 CVE candidates, got ${board.stats.cveCandidates}`);

const live = await get('/api/live');
if (!Array.isArray(live.liveRuns) || !Array.isArray(live.projects)) throw new Error('live shape invalid');

const project = board.projects.find((item) => item.id === 'vllm');
if (!project) throw new Error('vllm project missing');

const log = await get(`/api/runs/${project.id}/${project.latestRunId}/log?lines=20`);
if (!Array.isArray(log.lines) || log.lines.length === 0) throw new Error('log tail empty');

const trajectory = await get(`/api/runs/${project.id}/${project.latestRunId}/trajectory?limit=5`);
if (!Array.isArray(trajectory.events)) throw new Error('trajectory events invalid');
if (trajectory.limit !== 5) throw new Error(`trajectory limit mismatch: ${trajectory.limit}`);
if (trajectory.events.length > 5) throw new Error('trajectory first page too large');
if (typeof trajectory.totalEvents !== 'number' || trajectory.totalEvents < 1) throw new Error('trajectory totals missing');
if (typeof trajectory.totalLines !== 'number' || trajectory.totalLines < 1) throw new Error('trajectory line total missing');
if (!trajectory.counts || typeof trajectory.counts !== 'object') throw new Error('trajectory counts missing');
const firstEvent = trajectory.events[0];
if (!firstEvent) throw new Error('trajectory first page empty');
for (const key of ['index', 'kind', 'label', 'text', 'preview', 'lineStart', 'lineEnd', 'error', 'tool']) {
  if (!(key in firstEvent)) throw new Error(`trajectory event missing ${key}`);
}

const first = board.findings[0];
const raw = await get(`/api/findings/${first.project}/${first.id}/raw`);
if (!raw.finding) throw new Error('raw finding missing');

console.log(
  JSON.stringify(
    {
      ok: true,
      projects: board.projects.length,
      findings: board.findings.length,
      curated: board.stats.curated,
      cveCandidates: board.stats.cveCandidates,
      cveTrack: board.stats.cveTrack,
      liveRuns: live.liveRuns.length,
      logLines: log.lines.length,
      trajectoryEvents: trajectory.totalEvents,
      trajectoryLines: trajectory.totalLines
    },
    null,
    2
  )
);
