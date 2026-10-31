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
if (board.stats.curated !== board.findings.filter(f => f.curated).length) throw new Error('curated count mismatch');
if (board.stats.cveCandidates !== board.findings.filter(f => f.cveTier).length) throw new Error('CVE candidate count mismatch');
const inboxCount = board.findings.filter((finding) => finding.status === 'inbox').length;
if (board.stats.status.inbox !== inboxCount) throw new Error(`inbox count mismatch: ${board.stats.status.inbox} != ${inboxCount}`);
const reviewCount = board.findings.filter((finding) => finding.reviewReady).length;
if (board.stats.reviewReady !== reviewCount) throw new Error(`reviewReady mismatch: ${board.stats.reviewReady} != ${reviewCount}`);
if (!board.findings.every((finding) => finding.quality && Array.isArray(finding.quality.missing))) {
  throw new Error('quality metadata missing');
}

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

const topologyRun = live.liveRuns[0] || { project: project.id, runId: project.latestRunId };
const topology = await get(`/api/runs/${topologyRun.project}/${topologyRun.runId}/agents`);
if (!Array.isArray(topology.agents)) throw new Error('agent topology agents invalid');
if (!topology.orchestrator || typeof topology.orchestrator !== 'object') throw new Error('agent orchestrator missing');
if (!topology.summary || topology.summary.total !== topology.agents.length) throw new Error('agent summary mismatch');
if (!topology.stage || typeof topology.stage !== 'object') throw new Error('agent stage missing');
if (!topology.agents.every((agent) => agent.id && agent.agent && agent.boundary && agent.status)) {
  throw new Error('agent lane shape invalid');
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
      agentLanes: topology.agents.length,
      logLines: log.lines.length,
      trajectoryEvents: trajectory.totalEvents,
      trajectoryLines: trajectory.totalLines
    },
    null,
    2
  )
);
