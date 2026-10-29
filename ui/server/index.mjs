import http from 'node:http';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UI_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(UI_ROOT, '..');
const RUNS_ROOT = path.join(REPO_ROOT, 'runs');
const DATA_ROOT = path.join(UI_ROOT, 'data');
const DIST_ROOT = path.join(UI_ROOT, 'dist');
const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || '127.0.0.1';
const EXCLUDED_PROJECTS = new Set(['smoke', 'smoke-real', 'smoke-target']);
const STATUSES = new Set(['inbox', 'triage', 'reproduce', 'cve', 'closed']);
const VERDICTS = new Set(['untriaged', 'tp', 'fp', 'duplicate', 'unclear']);
const CVE_STATUSES = new Set(['none', 'tracking', 'known', 'blocked', 'disclosed']);
const PROJECT_NAMES = {
  vllm: 'vLLM',
  sglang: 'SGLang',
  codex: 'Codex',
  'deepseek-harness': 'DeepSeek Harness',
  verl: 'verl'
};
const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.ico': 'image/x-icon',
  '.map': 'application/json; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8'
};
const ANSI_PATTERN = /\x1b\[[0-?]*[ -/]*[@-~]/g;
const TRAJECTORY_KINDS = ['meta', 'tool', 'tool_result', 'thinking', 'assistant', 'error', 'result'];
const TRAJECTORY_KIND_SET = new Set(TRAJECTORY_KINDS);
const TRAJECTORY_CACHE = new Map();
const TRAJECTORY_CACHE_LIMIT = 6;
const TRAJECTORY_PREVIEW_LIMIT = 240;
const TRAJECTORY_SIMPLE_TAGS = new Set([
  'init',
  'thinking',
  'tool-result',
  'tool-error',
  'result',
  'assistant',
  'error',
  'summary',
  'notice',
  'workspace',
  'build-system',
  'core',
  'index',
  'project'
]);

function redactSecrets(value) {
  return String(value || '')
    .replace(/\b(sk-[A-Za-z0-9_-]{12,})\b/g, '[redacted]')
    .replace(/\b(gh[pousr]_[A-Za-z0-9]{12,})\b/g, '[redacted]')
    .replace(/\b(AKIA[0-9A-Z]{12,})\b/g, '[redacted]')
    .replace(/\b(xox[baprs]-[A-Za-z0-9-]{10,})\b/g, '[redacted]')
    .replace(/\b(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,})\b/g, '[redacted-jwt]')
    .replace(/\b([A-Za-z0-9_.-]*(?:token|secret|password|passwd|api[_-]?key)[A-Za-z0-9_.-]*\s*[=:]\s*)("?)([^\s"']{8,})\2/gi, '$1[redacted]');
}

function classifyTrajectoryTag(tag) {
  const lower = tag.toLowerCase();
  if (lower === 'init') return { kind: 'meta', label: 'init' };
  if (lower === 'thinking') return { kind: 'thinking', label: 'thinking' };
  if (lower === 'tool-result') return { kind: 'tool_result', label: 'tool-result' };
  if (lower === 'tool-error') return { kind: 'tool_result', label: 'tool-error', error: true };
  if (lower === 'result') return { kind: 'result', label: 'result' };
  if (lower === 'assistant') return { kind: 'assistant', label: 'assistant' };
  if (lower === 'error') return { kind: 'error', label: 'error', error: true };
  if (lower.startsWith('tool:')) {
    const name = tag.slice(5);
    return { kind: 'tool', label: name || 'tool', tool: name || 'tool' };
  }
  if (lower.startsWith('system:')) return { kind: 'meta', label: tag };
  if (/-final$/.test(lower) || lower === 'summary') return { kind: 'result', label: tag };
  if (TRAJECTORY_SIMPLE_TAGS.has(lower)) return { kind: 'meta', label: tag };
  return { kind: 'assistant', label: tag || 'assistant' };
}

function matchTrajectoryLine(line) {
  const match = line.match(/^\[([^\]\n]{1,80})\](?:\s?(.*))?$/);
  if (!match) return null;
  const tag = match[1];
  const lower = tag.toLowerCase();
  const known =
    TRAJECTORY_SIMPLE_TAGS.has(lower) ||
    lower.startsWith('tool:') ||
    lower.startsWith('system:') ||
    /-final$/.test(lower);
  if (!known) return null;
  return { tag, rest: match[2] || '' };
}

function buildTrajectoryPreview(label, text) {
  const sample = String(text || '').slice(0, 8000);
  const clean = redactSecrets(sample).replace(/\s+/g, ' ').trim();
  const composed = clean ? `${label} — ${clean}` : label;
  return composed.length > TRAJECTORY_PREVIEW_LIMIT
    ? `${composed.slice(0, TRAJECTORY_PREVIEW_LIMIT - 1)}…`
    : composed;
}

function parseTrajectory(text) {
  const lines = String(text || '').split(/\r?\n/);
  const events = [];
  const counts = Object.fromEntries(TRAJECTORY_KINDS.map((kind) => [kind, 0]));
  let current = null;
  let sawEvent = false;

  const flush = () => {
    if (!current) return;
    const body = current.parts.join('\n').replace(/^\n+/, '').replace(/\s+$/, '');
    const preview = buildTrajectoryPreview(current.label, body);
    events.push({
      index: events.length,
      kind: current.kind,
      label: current.label,
      text: body,
      preview,
      lineStart: current.lineStart,
      lineEnd: current.lineEnd,
      error: Boolean(current.error),
      tool: current.tool || ''
    });
    counts[current.kind] += 1;
    current = null;
  };

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    const matched = matchTrajectoryLine(line);

    if (matched) {
      flush();
      const classified = classifyTrajectoryTag(matched.tag);
      current = {
        ...classified,
        parts: matched.rest ? [matched.rest] : [],
        lineStart: lineIndex + 1,
        lineEnd: lineIndex + 1,
        error: Boolean(classified.error)
      };
      sawEvent = true;
      continue;
    }

    if (!sawEvent) {
      if (!line.trim() || line.startsWith('#')) continue;
      current = {
        kind: 'assistant',
        label: 'assistant',
        tool: '',
        error: false,
        parts: [line],
        lineStart: lineIndex + 1,
        lineEnd: lineIndex + 1
      };
      sawEvent = true;
      continue;
    }

    if (current) {
      current.parts.push(line);
      if (line.trim()) current.lineEnd = lineIndex + 1;
    }
  }

  flush();

  return { totalLines: lines.length, events, counts };
}

function getTrajectory(logPath) {
  const stat = fs.statSync(logPath);
  const key = `${logPath}:${stat.mtimeMs}:${stat.size}`;
  const cached = TRAJECTORY_CACHE.get(key);
  if (cached) return cached;

  const text = readText(logPath).replace(ANSI_PATTERN, '');
  const parsed = parseTrajectory(text);
  const result = {
    path: logPath,
    mtime: stat.mtime.toISOString(),
    bytes: stat.size,
    totalLines: parsed.totalLines,
    totalEvents: parsed.events.length,
    counts: parsed.counts,
    events: parsed.events
  };

  for (const existingKey of [...TRAJECTORY_CACHE.keys()]) {
    if (existingKey.startsWith(`${logPath}:`)) TRAJECTORY_CACHE.delete(existingKey);
  }
  TRAJECTORY_CACHE.set(key, result);
  while (TRAJECTORY_CACHE.size > TRAJECTORY_CACHE_LIMIT) {
    const oldest = TRAJECTORY_CACHE.keys().next().value;
    TRAJECTORY_CACHE.delete(oldest);
  }
  return result;
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function readText(file) {
  try {
    return fs.readFileSync(file, 'utf8');
  } catch {
    return '';
  }
}

function fileExists(file) {
  try {
    return fs.statSync(file).isFile();
  } catch {
    return false;
  }
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function normalizeSeverity(value) {
  const raw = String(value || 'info').toLowerCase();
  if (raw.startsWith('critical') || raw === 'crit') return 'critical';
  if (raw.startsWith('high')) return 'high';
  if (raw.startsWith('medium') || raw.startsWith('moderate')) return 'medium';
  if (raw.startsWith('low')) return 'low';
  return 'info';
}

function normalizeCwe(value) {
  if (Array.isArray(value)) return unique(value.map((item) => String(item).trim()));
  if (typeof value === 'string') {
    return unique(value.split(/[,;]/).map((item) => item.trim()));
  }
  return [];
}

function normalizeList(value) {
  if (Array.isArray(value)) return unique(value.map((item) => String(item).trim()));
  if (typeof value === 'string' && value.trim()) return [value.trim()];
  return [];
}

function normalizeEvidence(value) {
  if (Array.isArray(value)) {
    return unique(
      value.map((item) => {
        if (typeof item === 'string') return item.trim();
        if (item && typeof item === 'object') {
          const file = item.file || item.path || item.location || '';
          const line = item.lines || item.line || item.range || '';
          return file ? `${file}${line ? `:${line}` : ''}` : '';
        }
        return '';
      })
    );
  }
  if (typeof value === 'string') {
    return unique(value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean));
  }
  return [];
}

function formatLocation(value) {
  if (!value) return '';
  if (typeof value === 'string') return value;
  const file = value.file || value.path || '';
  const line = value.line || value.lines || '';
  return file ? `${file}${line ? `:${line}` : ''}` : '';
}

function runState(meta, status) {
  const state = String(status?.state || '').toLowerCase();
  if (state === 'starting') return 'starting';
  if (state === 'running' || state === 'stopping') return 'running';
  if (state === 'success' || state === 'completed') return 'completed';
  if (state === 'timeout') return 'timeout';
  if (state === 'failed' || state === 'error') return 'failed';
  if (state === 'stopped' || state === 'interrupted') return 'stopped';
  if (meta.timed_out) return 'timeout';
  if (meta.interrupted) return 'stopped';
  if (meta.exit_code === 0) return 'completed';
  if (meta.exit_code !== undefined && meta.exit_code !== null) return 'failed';
  return 'unknown';
}

function readLastLine(file, maxBytes = 64 * 1024) {
  try {
    const stat = fs.statSync(file);
    if (!stat.size) return '';
    const size = Math.min(stat.size, maxBytes);
    const buffer = Buffer.alloc(size);
    const fd = fs.openSync(file, 'r');
    fs.readSync(fd, buffer, 0, size, stat.size - size);
    fs.closeSync(fd);
    const lines = buffer
      .toString('utf8')
      .replace(ANSI_PATTERN, '')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    return lines.at(-1) || '';
  } catch {
    return '';
  }
}

function summarizeRun(run) {
  const start = run.startedAt ? new Date(run.startedAt).getTime() : null;
  const end = run.endedAt ? new Date(run.endedAt).getTime() : null;
  const elapsedSeconds = start ? Math.max(0, Math.round(((end || Date.now()) - start) / 1000)) : null;
  return {
    project: run.project,
    projectName: run.projectName,
    runId: run.runId,
    runDir: run.runDir,
    state: run.state,
    isLive: run.isLive,
    hasReport: run.hasReport,
    hasLog: run.hasLog,
    startedAt: run.startedAt,
    updatedAt: run.updatedAt,
    endedAt: run.endedAt,
    elapsedSeconds,
    durationSeconds: run.durationSeconds,
    timeoutSeconds: run.timeoutSeconds,
    model: run.model,
    commit: run.commit,
    container: run.container,
    logPath: run.logPath,
    reportPath: run.reportPath,
    lastLogLine: run.lastLogLine,
    logMtime: run.logMtime,
    logSize: run.logSize,
    findingsCount: run.findingsCount
  };
}

function normalizeFindings(project, runId, report, meta) {
  const list = Array.isArray(report.findings)
    ? report.findings
    : Array.isArray(report.vulnerabilities)
      ? report.vulnerabilities
      : [];
  const seen = new Map();

  return list.map((raw, index) => {
    const baseId = String(raw.id || `F-${String(index + 1).padStart(2, '0')}`).trim();
    const count = (seen.get(baseId) || 0) + 1;
    seen.set(baseId, count);
    const id = count === 1 ? baseId : `${baseId}~${count}`;
    const evidence = normalizeEvidence(raw.evidence);
    const files = normalizeList(raw.files);
    const location = formatLocation(raw.location);
    const sourcePaths = unique([...evidence, ...files, location]);
    const title = String(raw.title || raw.description || raw.type || raw.category || 'Untitled finding').trim();
    const severity = normalizeSeverity(raw.severity || raw.severity_raw);
    const confidence = String(raw.confidence || (raw.verified ? 'verified' : 'unverified')).toLowerCase();
    const verified = Boolean(raw.verified) || /confirm|verified|已.*验证|reproduced/i.test(String(raw.verification || raw.severity_raw || ''));
    const preconditions = normalizeList(raw.preconditions);
    const remediation = Array.isArray(raw.remediation_items)
      ? unique(raw.remediation_items.map((item) => String(item).trim())).join(' ')
      : String(raw.remediation || raw.fixed_code || '').trim();
    const reproduction = String(raw.reproduction_idea || raw.reproduction || raw.exploit || raw.poc || '').trim();
    const rootCause = String(raw.root_cause || raw.description || raw.type || '').trim();
    const impact = String(raw.impact || '').trim();
    const category = String(raw.category || raw.type || '').trim();
    const cwe = normalizeCwe(raw.cwe || raw.cwe_id);
    const relatedArtifacts = unique([
      ...normalizeList(raw.related_artifacts),
      ...normalizeList(raw.source_artifact),
      ...normalizeList(raw.source_tasks)
    ]);

    return {
      key: `${project}:${id}`,
      id,
      project,
      projectName: PROJECT_NAMES[project] || project,
      runId,
      title,
      severity,
      confidence,
      verified,
      category,
      cwe,
      evidence,
      files,
      location,
      sourcePaths,
      rootCause,
      impact,
      preconditions,
      reproduction,
      remediation,
      relatedArtifacts,
      cvssScore: raw.cvss_score ?? null,
      cvssEstimated: Boolean(raw.cvss_estimated),
      finalReviewNote: String(raw.final_review_note || '').trim(),
      generatedAt: report.generated_at || meta.ended_at || meta.started_at || null,
      commit: meta.commit || '',
      reportPath: '',
      reportMdPath: '',
      runDir: '',
      status: 'inbox',
      verdict: 'untriaged',
      cveTier: null,
      cveStatus: 'none',
      knownCve: '',
      notes: '',
      assignee: '',
      updatedAt: null,
      curated: false,
      touched: false
    };
  });
}

function loadOverrides() {
  const curated = readJson(path.join(DATA_ROOT, 'curated.json')) || {};
  const state = readJson(path.join(DATA_ROOT, 'state.json')) || {};
  return { curated, state };
}

function mergeOverrides(finding, curated, state) {
  const seed = curated[finding.key] || {};
  const saved = state[finding.key] || {};
  const merged = { ...seed, ...saved };
  const hasSeed = Boolean(curated[finding.key]);
  const hasSaved = Boolean(state[finding.key]);

  return {
    ...finding,
    status: STATUSES.has(merged.status) ? merged.status : 'inbox',
    verdict: VERDICTS.has(merged.verdict) ? merged.verdict : 'untriaged',
    cveTier: merged.cveTier === 1 || merged.cveTier === 2 ? merged.cveTier : null,
    cveStatus: CVE_STATUSES.has(merged.cveStatus) ? merged.cveStatus : 'none',
    knownCve: String(merged.knownCve || ''),
    notes: String(merged.notes || ''),
    assignee: String(merged.assignee || ''),
    updatedAt: merged.updatedAt || finding.generatedAt,
    curated: hasSeed || hasSaved,
    touched: hasSaved
  };
}

function discoverRuns({ withFindings = true } = {}) {
  if (!fs.existsSync(RUNS_ROOT)) return [];
  const projectEntries = fs.readdirSync(RUNS_ROOT, { withFileTypes: true });
  const runs = [];

  for (const projectEntry of projectEntries) {
    if (!projectEntry.isDirectory()) continue;
    if (projectEntry.name.startsWith('.')) continue;
    if (EXCLUDED_PROJECTS.has(projectEntry.name)) continue;
    const project = projectEntry.name;
    const projectDir = path.join(RUNS_ROOT, project);
    const runEntries = fs.readdirSync(projectDir, { withFileTypes: true });

    for (const runEntry of runEntries) {
      if (!runEntry.isDirectory() || runEntry.name.startsWith('.')) continue;
      const runDir = path.join(projectDir, runEntry.name);
      const reportPath = path.join(runDir, 'audit-report.json');
      const reportMdPath = path.join(runDir, 'audit-report.md');
      const logPath = path.join(runDir, 'claude.rendered.log');
      const metaPath = path.join(runDir, 'run-meta.json');
      const statusPath = path.join(`${runDir}.meta`, 'status.json');
      const hasReport = fileExists(reportPath);
      const hasLog = fileExists(logPath);
      const hasMeta = fileExists(metaPath);
      const hasStatus = fileExists(statusPath);

      if (!hasReport && !hasLog && !hasMeta && !hasStatus) continue;

      const meta = readJson(metaPath) || {};
      const status = readJson(statusPath) || {};
      const report = withFindings && hasReport ? readJson(reportPath) || {} : {};
      const findings = withFindings && hasReport ? normalizeFindings(project, runEntry.name, report, meta) : [];
      const rawState = runState(meta, status);
      const logStat = hasLog ? fs.statSync(logPath) : null;
      const recentLog = Boolean(logStat && Date.now() - logStat.mtime.getTime() < 30 * 60 * 1000);
      const isLive = rawState === 'starting' || rawState === 'running' || (!hasReport && !hasStatus && !hasMeta && recentLog);
      const state = isLive && rawState === 'unknown' ? 'running' : rawState;
      const startedAt = meta.started_at || status.started_at || report.generated_at || runEntry.name;
      const endedAt =
        meta.ended_at ||
        (hasReport ? report.generated_at : null) ||
        (isLive ? null : status.updated_at || null);
      const updatedAt = status.updated_at || meta.ended_at || (logStat ? logStat.mtime.toISOString() : null) || startedAt;

      for (const finding of findings) {
        finding.reportPath = reportPath;
        finding.reportMdPath = fileExists(reportMdPath) ? reportMdPath : '';
        finding.runDir = runDir;
      }

      const severityCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
      for (const finding of findings) severityCounts[finding.severity] += 1;

      runs.push({
        project,
        projectName: PROJECT_NAMES[project] || project,
        runId: runEntry.name,
        runDir,
        reportPath: hasReport ? reportPath : '',
        reportMdPath: fileExists(reportMdPath) ? reportMdPath : '',
        logPath: hasLog ? logPath : '',
        hasReport,
        hasLog,
        isLive,
        startedAt,
        endedAt,
        updatedAt,
        durationSeconds: meta.duration_seconds ?? null,
        timeoutSeconds: status.timeout_seconds ?? meta.timeout_seconds ?? null,
        model: meta.model || status.model || '',
        agent: meta.agent || status.agent || '',
        commit: meta.commit || '',
        targetUrl: meta.target_url || '',
        container: status.container || '',
        state,
        exitCode: meta.exit_code ?? null,
        timedOut: Boolean(meta.timed_out) || state === 'timeout',
        interrupted: Boolean(meta.interrupted) || state === 'stopped',
        reportsComplete: Boolean(meta.reports_complete),
        reportGeneratedAt: report.generated_at || null,
        lastLogLine: hasLog ? readLastLine(logPath) : '',
        logMtime: logStat ? logStat.mtime.toISOString() : null,
        logSize: logStat ? logStat.size : 0,
        findings,
        findingsCount: findings.length,
        severityCounts
      });
    }
  }

  return runs.sort((a, b) => String(b.startedAt).localeCompare(String(a.startedAt)));
}

function buildBoard() {
  const runs = discoverRuns();
  const { curated, state } = loadOverrides();
  const latestReport = new Map();
  const latestLive = new Map();
  const latestAny = new Map();

  for (const run of runs) {
    if (!latestAny.has(run.project)) latestAny.set(run.project, run);
    if (run.hasReport && !latestReport.has(run.project)) latestReport.set(run.project, run);
    if (run.isLive && !latestLive.has(run.project)) latestLive.set(run.project, run);
  }

  const projectIds = new Set([...latestAny.keys(), ...latestReport.keys(), ...latestLive.keys()]);
  const projects = [];
  const findings = [];

  for (const project of projectIds) {
    const reportRun = latestReport.get(project) || null;
    const liveRun = latestLive.get(project) || null;
    const latest = latestAny.get(project) || null;
    const mergedFindings = (reportRun?.findings || []).map((finding) => mergeOverrides(finding, curated, state));
    findings.push(...mergedFindings);
    const severityCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    for (const finding of mergedFindings) severityCounts[finding.severity] += 1;
    const projectRuns = runs.filter((item) => item.project === project);
    const sourceRun = reportRun || latest;
    const activeRun = liveRun || latest;

    projects.push({
      id: project,
      name: PROJECT_NAMES[project] || project,
      latestRunId: activeRun?.runId || sourceRun?.runId || '',
      latestReportRunId: reportRun?.runId || '',
      liveRunId: liveRun?.runId || '',
      isLive: Boolean(liveRun),
      hasReport: Boolean(reportRun),
      runDir: sourceRun?.runDir || '',
      reportPath: reportRun?.reportPath || '',
      reportMdPath: reportRun?.reportMdPath || '',
      logPath: liveRun?.logPath || sourceRun?.logPath || '',
      startedAt: activeRun?.startedAt || sourceRun?.startedAt || null,
      endedAt: reportRun?.endedAt || (liveRun ? null : latest?.endedAt || null),
      durationSeconds: reportRun?.durationSeconds ?? latest?.durationSeconds ?? null,
      timeoutSeconds: activeRun?.timeoutSeconds ?? null,
      model: activeRun?.model || sourceRun?.model || '',
      commit: sourceRun?.commit || '',
      targetUrl: sourceRun?.targetUrl || '',
      state: liveRun ? liveRun.state : latest?.state || 'unknown',
      exitCode: sourceRun?.exitCode ?? null,
      container: activeRun?.container || '',
      findingsCount: mergedFindings.length,
      curatedCount: mergedFindings.filter((finding) => finding.curated).length,
      severityCounts,
      cveCount: mergedFindings.filter((finding) => finding.cveTier).length,
      runCount: projectRuns.length,
      lastLogLine: liveRun?.lastLogLine || latest?.lastLogLine || '',
      logMtime: liveRun?.logMtime || latest?.logMtime || null,
      updatedAt: activeRun?.updatedAt || null
    });
  }

  projects.sort((a, b) => a.name.localeCompare(b.name));
  findings.sort((a, b) => {
    const rank = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    return (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9) || a.project.localeCompare(b.project) || a.id.localeCompare(b.id);
  });

  const liveRuns = runs.filter((run) => run.isLive).map(summarizeRun);
  const severity = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  const status = { inbox: 0, triage: 0, reproduce: 0, cve: 0, closed: 0 };
  const verdict = { untriaged: 0, tp: 0, fp: 0, duplicate: 0, unclear: 0 };
  for (const finding of findings) {
    severity[finding.severity] += 1;
    status[finding.status] += 1;
    verdict[finding.verdict] += 1;
  }

  return {
    generatedAt: new Date().toISOString(),
    repoRoot: REPO_ROOT,
    runsRoot: RUNS_ROOT,
    projects,
    findings,
    liveRuns,
    stats: {
      total: findings.length,
      curated: findings.filter((finding) => finding.curated).length,
      tp: findings.filter((finding) => finding.verdict === 'tp').length,
      cveCandidates: findings.filter((finding) => finding.cveTier).length,
      cveTrack: findings.filter((finding) => finding.status === 'cve').length,
      closed: findings.filter((finding) => finding.status === 'closed').length,
      live: liveRuns.length,
      severity,
      status,
      verdict
    },
    sources: {
      curated: path.join(DATA_ROOT, 'curated.json'),
      state: path.join(DATA_ROOT, 'state.json')
    }
  };
}

function buildLive() {
  const runs = discoverRuns({ withFindings: false });
  const liveRuns = runs.filter((run) => run.isLive).map(summarizeRun);
  const projects = [...new Set(liveRuns.map((run) => run.project))].map((project) => {
    const run = liveRuns.find((item) => item.project === project);
    return {
      id: project,
      name: PROJECT_NAMES[project] || project,
      state: run.state,
      isLive: true,
      latestRunId: run.runId,
      runDir: run.runDir,
      logPath: run.logPath,
      startedAt: run.startedAt,
      updatedAt: run.updatedAt,
      timeoutSeconds: run.timeoutSeconds,
      model: run.model,
      commit: run.commit,
      container: run.container,
      hasReport: run.hasReport,
      findingsCount: null,
      lastLogLine: run.lastLogLine,
      logMtime: run.logMtime
    };
  });
  return { generatedAt: new Date().toISOString(), liveRuns, projects };
}

function findRun(project, runId, withFindings = true) {
  const runs = discoverRuns({ withFindings });
  return runs.find((run) => run.project === project && run.runId === runId) || null;
}

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  });
  res.end(body);
}

function sendError(res, statusCode, message) {
  sendJson(res, statusCode, { error: message });
}

function sendFile(res, file, cacheControl = 'no-store') {
  const extension = path.extname(file).toLowerCase();
  res.writeHead(200, {
    'Content-Type': MIME_TYPES[extension] || 'application/octet-stream',
    'Cache-Control': cacheControl
  });
  fs.createReadStream(file).pipe(res);
}

async function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > 1024 * 1024) {
        reject(new Error('Request body too large'));
        req.destroy();
      }
    });
    req.on('end', () => {
      if (!body.trim()) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch {
        reject(new Error('Invalid JSON body'));
      }
    });
    req.on('error', reject);
  });
}

function sanitizePatch(body) {
  const patch = {};
  if ('status' in body) {
    if (!STATUSES.has(body.status)) throw new Error('Invalid status');
    patch.status = body.status;
  }
  if ('verdict' in body) {
    if (!VERDICTS.has(body.verdict)) throw new Error('Invalid verdict');
    patch.verdict = body.verdict;
  }
  if ('cveTier' in body) {
    if (body.cveTier !== null && body.cveTier !== 1 && body.cveTier !== 2) throw new Error('Invalid cveTier');
    patch.cveTier = body.cveTier;
  }
  if ('cveStatus' in body) {
    if (!CVE_STATUSES.has(body.cveStatus)) throw new Error('Invalid cveStatus');
    patch.cveStatus = body.cveStatus;
  }
  if ('knownCve' in body) patch.knownCve = String(body.knownCve || '').slice(0, 200);
  if ('notes' in body) patch.notes = String(body.notes || '').slice(0, 20000);
  if ('assignee' in body) patch.assignee = String(body.assignee || '').slice(0, 120);
  patch.updatedAt = new Date().toISOString();
  return patch;
}

async function saveState(project, id, patch) {
  const statePath = path.join(DATA_ROOT, 'state.json');
  const state = readJson(statePath) || {};
  const key = `${project}:${id}`;
  state[key] = { ...(state[key] || {}), ...patch };
  await fsp.mkdir(DATA_ROOT, { recursive: true });
  const tempPath = path.join(DATA_ROOT, `.state.${process.pid}.${Date.now()}.tmp`);
  await fsp.writeFile(tempPath, `${JSON.stringify(state, null, 2)}\n`);
  await fsp.rename(tempPath, statePath);
  return state[key];
}

function applyCors(req, res) {
  const origin = req.headers.origin;
  if (origin) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
  } else {
    res.setHeader('Access-Control-Allow-Origin', '*');
  }
  res.setHeader('Access-Control-Allow-Methods', 'GET, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

function serveStatic(req, res, pathname) {
  if (!fs.existsSync(DIST_ROOT)) {
    sendError(res, 503, 'UI is not built. Run: cd ui && npm install && npm run build');
    return;
  }
  const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const candidate = path.resolve(DIST_ROOT, relative);
  if (candidate !== DIST_ROOT && !candidate.startsWith(`${DIST_ROOT}${path.sep}`)) {
    sendError(res, 403, 'Forbidden');
    return;
  }
  if (fileExists(candidate)) {
    sendFile(res, candidate, pathname.startsWith('/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache');
    return;
  }
  const index = path.join(DIST_ROOT, 'index.html');
  if (fileExists(index)) {
    sendFile(res, index, 'no-cache');
    return;
  }
  sendError(res, 404, 'Not found');
}

const server = http.createServer(async (req, res) => {
  applyCors(req, res);
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = decodeURIComponent(url.pathname);

  try {
    if (req.method === 'GET' && pathname === '/api/health') {
      sendJson(res, 200, { ok: true, repoRoot: REPO_ROOT, time: new Date().toISOString() });
      return;
    }

    if (req.method === 'GET' && pathname === '/api/board') {
      sendJson(res, 200, buildBoard());
      return;
    }

    if (req.method === 'GET' && pathname === '/api/live') {
      sendJson(res, 200, buildLive());
      return;
    }

    if (req.method === 'GET' && pathname === '/api/runs') {
      const runs = discoverRuns({ withFindings: false }).map((run) => ({
        project: run.project,
        projectName: run.projectName,
        runId: run.runId,
        runDir: run.runDir,
        reportPath: run.reportPath,
        startedAt: run.startedAt,
        endedAt: run.endedAt,
        durationSeconds: run.durationSeconds,
        state: run.state,
        isLive: run.isLive,
        hasReport: run.hasReport,
        hasLog: run.hasLog,
        logPath: run.logPath,
        updatedAt: run.updatedAt,
        lastLogLine: run.lastLogLine,
        model: run.model,
        commit: run.commit,
        findingsCount: run.findingsCount,
        severityCounts: run.severityCounts
      }));
      sendJson(res, 200, { runs });
      return;
    }

    const logMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/log$/);
    if (req.method === 'GET' && logMatch) {
      const project = logMatch[1];
      const runId = logMatch[2];
      const run = findRun(project, runId, false);
      if (!run) return sendError(res, 404, 'Run not found');
      if (!run.logPath) return sendError(res, 404, 'Log not found');
      const requested = Number(url.searchParams.get('lines') || 400);
      const limit = Number.isFinite(requested) ? Math.min(Math.max(requested, 20), 2000) : 400;
      const stat = fs.statSync(run.logPath);
      const text = readText(run.logPath).replace(ANSI_PATTERN, '');
      const lines = text.split(/\r?\n/);
      sendJson(res, 200, {
        project,
        runId,
        path: run.logPath,
        mtime: stat.mtime.toISOString(),
        size: stat.size,
        totalLines: lines.length,
        lines: lines.slice(-limit)
      });
      return;
    }

    const trajectoryMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/trajectory$/);
    if (req.method === 'GET' && trajectoryMatch) {
      const project = trajectoryMatch[1];
      const runId = trajectoryMatch[2];
      const run = findRun(project, runId, false);
      if (!run) return sendError(res, 404, 'Run not found');
      if (!run.logPath) return sendError(res, 404, 'Log not found');

      const requestedKind = String(url.searchParams.get('kind') || 'all').toLowerCase();
      const kind = requestedKind === 'all' || TRAJECTORY_KIND_SET.has(requestedKind) ? requestedKind : 'all';
      const q = String(url.searchParams.get('q') || '').trim().toLowerCase();
      const requestedOffset = Number(url.searchParams.get('offset'));
      const offset = Number.isFinite(requestedOffset) ? Math.max(0, Math.floor(requestedOffset)) : 0;
      const requestedLimit = Number(url.searchParams.get('limit'));
      const limit = Number.isFinite(requestedLimit) ? Math.min(Math.max(Math.floor(requestedLimit), 1), 500) : 200;

      const data = getTrajectory(run.logPath);
      let matched = data.events;
      if (kind !== 'all') matched = matched.filter((event) => event.kind === kind);
      if (q) {
        matched = matched.filter(
          (event) =>
            event.label.toLowerCase().includes(q) ||
            event.tool.toLowerCase().includes(q) ||
            event.text.toLowerCase().includes(q)
        );
      }

      const page = matched.slice(offset, offset + limit);
      sendJson(res, 200, {
        project,
        runId,
        path: data.path,
        mtime: data.mtime,
        bytes: data.bytes,
        totalLines: data.totalLines,
        totalEvents: data.totalEvents,
        filteredEvents: matched.length,
        offset,
        limit,
        hasMore: offset + page.length < matched.length,
        counts: data.counts,
        events: page
      });
      return;
    }

    const visualMatch = pathname.match(/^\/api\/visual\/([^/]+)\/([^/]+)$/);
    if (req.method === 'GET' && visualMatch) {
      const run = findRun(visualMatch[1], visualMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      const file = path.join(run.runDir, 'visual', 'visual-model.json');
      if (!fileExists(file)) return sendError(res, 404, 'Visual model not generated');
      sendFile(res, file, 'no-store');
      return;
    }

    const visualAssetMatch = pathname.match(/^\/api\/visual\/([^/]+)\/([^/]+)\/asset$/);
    if (req.method === 'GET' && visualAssetMatch) {
      const run = findRun(visualAssetMatch[1], visualAssetMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      const requested = String(url.searchParams.get('path') || '');
      if (!requested || requested.includes('..') || path.isAbsolute(requested)) return sendError(res, 400, 'Invalid asset path');
      const roots = [path.join(run.runDir, 'visual'), path.join(run.runDir, 'visual-rendered')];
      for (const root of roots) {
        const file = path.resolve(root, requested);
        if (file !== root && file.startsWith(`${root}${path.sep}`) && fileExists(file)) {
          sendFile(res, file, 'no-store');
          return;
        }
      }
      return sendError(res, 404, 'Visual asset not found');
    }

    const logTextMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/log\.txt$/);
    if (req.method === 'GET' && logTextMatch) {
      const run = findRun(logTextMatch[1], logTextMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      if (!run.logPath) return sendError(res, 404, 'Log not found');
      const text = readText(run.logPath).replace(ANSI_PATTERN, '');
      res.writeHead(200, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store'
      });
      res.end(text);
      return;
    }

    const reportMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/report(\.json|\.md)?$/);
    if (req.method === 'GET' && reportMatch) {
      const run = findRun(reportMatch[1], reportMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      const wantsMarkdown = reportMatch[3] === '.md';
      const file = wantsMarkdown ? run.reportMdPath : run.reportPath;
      if (!file || !fileExists(file)) return sendError(res, 404, 'Report not found');
      sendFile(res, file, 'no-store');
      return;
    }

    const rawMatch = pathname.match(/^\/api\/findings\/([^/]+)\/([^/]+)\/raw$/);
    if (req.method === 'GET' && rawMatch) {
      const board = buildBoard();
      const finding = board.findings.find((item) => item.project === rawMatch[1] && item.id === rawMatch[2]);
      if (!finding) return sendError(res, 404, 'Finding not found');
      const latestRun = board.projects.find((item) => item.id === finding.project);
      const report = latestRun ? readJson(latestRun.reportPath) : null;
      const list = Array.isArray(report?.findings) ? report.findings : Array.isArray(report?.vulnerabilities) ? report.vulnerabilities : [];
      const baseId = finding.id.replace(/~\d+$/, '');
      const raw = list.find((item) => String(item.id) === baseId) || null;
      sendJson(res, 200, { finding, raw, reportPath: finding.reportPath, runDir: finding.runDir, commit: finding.commit });
      return;
    }

    const patchMatch = pathname.match(/^\/api\/findings\/([^/]+)\/([^/]+)$/);
    if (req.method === 'PATCH' && patchMatch) {
      const project = patchMatch[1];
      const id = patchMatch[2];
      const board = buildBoard();
      const finding = board.findings.find((item) => item.project === project && item.id === id);
      if (!finding) return sendError(res, 404, 'Finding not found');
      const body = await readBody(req);
      const patch = sanitizePatch(body);
      const saved = await saveState(project, id, patch);
      sendJson(res, 200, { ok: true, state: saved });
      return;
    }

    if (pathname.startsWith('/api/')) {
      sendError(res, 404, 'Not found');
      return;
    }

    serveStatic(req, res, pathname);
  } catch (error) {
    sendError(res, 500, error instanceof Error ? error.message : 'Internal error');
  }
});

server.listen(PORT, HOST, () => {
  console.log(`[vul-ai-board] http://${HOST}:${PORT}`);
  console.log(`[vul-ai-board] repo=${REPO_ROOT}`);
});
