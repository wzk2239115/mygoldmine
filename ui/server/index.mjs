import {labTaskReport} from './lab-tasks.mjs';
import {verifyTaskReport} from './verify-tasks.mjs';
import { sessionMatchesTrace } from './ccui-cache.mjs';
import { startNodeRetry } from './node-retries.mjs';
import { createModelSettings } from './model-settings.mjs';
import { createCcuiService } from './ccui-service.mjs';
import { projectLogo } from './project-logo.mjs';
import { removeProjectRecords } from './project-removal.mjs';
import { discoverRunNames } from './run-directories.mjs';
import http from 'node:http';
import { reportQuality } from './report-quality.mjs';
import { summarizeRecovery } from './recovery-status.mjs';
import { parseAgentTopology } from './agent-topology.mjs';
import { buildAgenticPipeline } from './agentic-pipeline.mjs';
import { resolveAgenticTrace, traceSessionPath } from './agentic-traces.mjs';
import { browseServerDirectory, normalizeProjectId, createGithubCommitLister, createGithubBranchLister, createProjectImporter } from './project-import.mjs';
import { isLedgerV2, isVerified, latestOccurrences, stateForFinding } from './finding-ledger.mjs';
import net from 'node:net';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UI_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(UI_ROOT, '..');
const RUNS_ROOT = path.join(REPO_ROOT, 'runs');
const DATA_ROOT = path.join(UI_ROOT, 'data');
const CONFIG_ROOT = path.join(REPO_ROOT, 'config');

function pidAlive(pid) {
  try {
    process.kill(Number(pid), 0);
    return true;
  } catch {
    return false;
  }
}

function currentLanguage() {
  try {
    const payload = JSON.parse(fs.readFileSync(path.join(CONFIG_ROOT, 'system.json'), 'utf8'));
    return payload.language === 'en' ? 'en' : 'zh';
  } catch {
    return 'zh';
  }
}
const DIST_ROOT = path.join(UI_ROOT, 'dist');
const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || '127.0.0.1';
const CCUI_URL = (process.env.CCUI_URL || 'http://127.0.0.1:3001').replace(/\/+$/, '');
const CCUI_HOME = process.env.CCUI_HOME || path.join(RUNS_ROOT, 'ccui-home');
const CCUI_PREFIX = '/ccui';
// CloudCLI mounts these under /api; none collide with the board's own API
// (board|live|runs|findings|health|ccui), so they are proxied as-is and the
// embedded SPA can keep its absolute fetch('/api/...') URLs.
const CCUI_API_PREFIXES = [
  '/api/auth', '/api/file-tree', '/api/projects', '/api/assets', '/api/git',
  '/api/worktrees', '/api/taskmaster', '/api/commands', '/api/settings',
  '/api/system', '/api/notifications', '/api/user', '/api/plugins',
  '/api/browser-use-mcp', '/api/browser-use', '/api/providers',
  '/api/scheduled-messages', '/api/agent', '/api/voice'
];
const CCUI_WS_PATHS = ['/ws', '/shell', '/desktop-notifications', '/plugin-ws'];
const EXCLUDED_PROJECTS = new Set(['smoke', 'smoke-real', 'smoke-target']);
const STATUSES = new Set(['inbox', 'triage', 'reproduce', 'cve', 'closed', 'archived']);
const VERDICTS = new Set(['untriaged', 'tp', 'fp', 'duplicate', 'unclear']);
const CVE_STATUSES = new Set(['none', 'tracking', 'known', 'blocked', 'disclosed']);
const PROJECT_NAMES = {
  vllm: 'vLLM',
  sglang: 'SGLang',
  codex: 'Codex',
  'deepseek-harness': 'DeepSeek Harness',
  verl: 'verl'
};
const PROJECT_META = (() => {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA_ROOT, 'projects.json'), 'utf8')).projects || {};
  } catch {
    return {};
  }
})();

function projectInfo(project) {
  const meta = PROJECT_META[project] || {};
  return {
    name: meta.name || PROJECT_NAMES[project] || project,
    direction: meta.direction || '',
    icon: meta.icon || 'layers',
    tone: meta.tone || 'ink',
    logo: projectLogo(REPO_ROOT, project, meta.logo),
    url: meta.url || '',
    auditId: meta.audit_id || ''
  };
}
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

function textValue(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => (item && typeof item === 'object' ? textValue(item) : String(item || '').trim()))
      .filter(Boolean)
      .join(' ');
  }
  if (value && typeof value === 'object') {
    return textValue(value.idea || value.steps || value.note || value.description || '');
  }
  return String(value || '').trim();
}

function normalizeEvidence(value) {
  if (Array.isArray(value)) {
    return unique(
      value.map((item) => {
        if (typeof item === 'string') return item.trim();
        if (item && typeof item === 'object') {
          const file = item.file || item.path || item.location || '';
          const line = item.lines || item.line || item.range || '';
          return file ? `${file}${line ? `:${line}` : ''}` : textValue(item.description || item.snippet);
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
  return file ? `${file}${line ? `:${line}` : ''}` : textValue(value.description || value.snippet);
}

function runState(meta, status) {
  const state = String(status?.state || '').toLowerCase();
  if (state === 'starting') return 'starting';
  if (state === 'running' || state === 'stopping') return 'running';
  if (state === 'success' || state === 'completed') return 'completed';
  if (state === 'timeout') return 'timeout';
  if (state === 'partial') return 'partial';
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
    branch: run.branch || '',
    container: run.container,
    logPath: run.logPath,
    reportPath: run.reportPath,
    lastLogLine: run.lastLogLine,
    logMtime: run.logMtime,
    logSize: run.logSize,
    findingsCount: run.findingsCount,
    visualStatus: run.visualStatus || '',
    verifyAgentStatus: run.verifyAgentStatus || '',
    redteamStatus: run.redteamStatus || '',
    reviewReady: run.reviewReady || 0,
    recovery: run.recovery
  };
}

function normalizeFindings(project, runId, report, meta) {
  const language = currentLanguage();
  const list = Array.isArray(report.findings)
    ? report.findings
    : Array.isArray(report.vulnerabilities)
      ? report.vulnerabilities
      : [];
  const seen = new Map();

  return list.map((item, index) => {
    const raw = item && typeof item === 'object' && !Array.isArray(item) ? item : {};
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
    const verified = isVerified(raw);
    const confidence = String(raw.confidence || (verified ? 'verified' : 'unverified')).toLowerCase();
    const preconditions = normalizeList(raw.preconditions || raw.precondition || raw.precondition_list);
    const remediation = textValue(
      raw.remediation_items || raw.remediation || raw.fix || raw.fixed_code ||
      raw.recommendation || raw.remediation_note || ''
    );
    const verification = raw.verification && typeof raw.verification === 'object' ? raw.verification : {};
    const reproduction = textValue(
      raw.reproduction_idea || raw.reproduction || raw.exploit || raw.poc ||
      raw.poc_steps || raw.test_plan || raw.verification_idea ||
      verification.idea || verification.steps || verification.reproduction || ''
    );
    const rootCause = textValue(raw.root_cause || raw.rootCause || raw.description || raw.summary || raw.type || '');
    const impact = textValue(raw.impact || raw.effect || raw.consequence || '');
    const category = String(raw.category || raw.type || '').trim();
    const cwe = normalizeCwe(raw.cwe || raw.cwe_id);
    const relatedArtifacts = unique([
      ...normalizeList(raw.related_artifacts),
      ...normalizeList(raw.source_artifact),
      ...normalizeList(raw.source_tasks)
    ]);

    const quality = reportQuality(raw, language);

    return {
      quality,
      key: `${project}/${runId}/${id}`,
      occurrence_id: `${project}/${runId}/${id}`,
      semantic_id: '',
      finding_id: baseId,
      id,
      project,
      projectName: projectInfo(project).name,
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
  const autoPayload = readJson(path.join(DATA_ROOT, 'auto-state.json')) || {};
  const auto = autoPayload.findings && typeof autoPayload.findings === 'object' ? autoPayload.findings : {};
  const review = autoPayload.review && typeof autoPayload.review === 'object' ? autoPayload.review : {};
  const refinePayload = readJson(path.join(DATA_ROOT, 'refine-state.json')) || {};
  const refine = refinePayload.findings && typeof refinePayload.findings === 'object' ? refinePayload.findings : {};
  const flowPayload = readJson(path.join(DATA_ROOT, 'flow-state.json')) || {};
  const flow = flowPayload.findings && typeof flowPayload.findings === 'object' ? flowPayload.findings : {};
  const flowQueue = readJson(path.join(DATA_ROOT, 'flow-queue.json')) || {};
  const watchPayload = readJson(path.join(DATA_ROOT, 'watch-state.json')) || {};
  const watchBranches = Object.fromEntries(
    (Array.isArray(watchPayload.repos) ? watchPayload.repos : [])
      .filter((repo) => repo && repo.project && repo.branch)
      .map((repo) => [repo.project, repo.branch])
  );
  const ledger = readJson(path.join(DATA_ROOT, 'finding-ledger.json')) || {};
  return {
    curated, state, auto, refine, flow, review, ledger, watchBranches,
    autoGeneratedAt: autoPayload.generated_at || null,
    flowStatus: {
      updatedAt: flowQueue.updated_at || null,
      paused: Boolean(flowQueue.paused),
      stats: flowQueue.stats || {},
      worker: flowQueue.worker || {}
    }
  };
}

function mergeOverrides(finding, curated, state, auto, refine, flow, review, ledger) {
  const seed = stateForFinding(finding, curated, ledger);
  const saved = stateForFinding(finding, state, ledger);
  const detected = stateForFinding(finding, auto, ledger);
  const refined = stateForFinding(finding, refine, ledger);
  const flowed = stateForFinding(finding, flow, ledger);
  const reviewSeed = stateForFinding(finding, review, ledger);
  const merged = { ...detected, ...refined, ...flowed, ...seed, ...saved };
  const hasSeed = Boolean(Object.keys(seed).length);
  const hasSaved = Boolean(Object.keys(saved).length);
  const hasAuto = Boolean(Object.keys(detected).length);
  const hasRefine = Boolean(Object.keys(refined).length);
  const hasFlow = Boolean(Object.keys(flowed).length);

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
    touched: hasSaved,
    routedBy: hasSaved ? 'manual' : hasSeed ? 'curated' : hasFlow ? 'flow' : hasRefine ? 'refine' : hasAuto ? 'auto' : 'raw',
    autoReason: hasAuto || hasRefine || hasFlow ? String(merged.reason || '') : '',
    autoSource: hasAuto || hasRefine || hasFlow ? String(merged.source || '') : '',
    autoDetail: hasAuto || hasRefine || hasFlow ? String(merged.source_detail || '') : '',
    autoArtifacts: (hasAuto || hasRefine || hasFlow) && Array.isArray(merged.artifacts) ? merged.artifacts : [],
    verifyVerdict: hasAuto || hasRefine || hasFlow ? String(merged.verifyVerdict || '') : '',
    verifyEvidenceClass: hasAuto || hasRefine || hasFlow ? String(merged.verifyEvidenceClass || '') : '',
    flowStage: hasFlow ? String(merged.flowStage || '') : '',
    flowOutcome: hasFlow ? String(merged.flowOutcome || '') : '',
    flowAttempts: hasFlow ? Number(merged.flowAttempts || 0) : 0,
    flowBlocked: hasFlow ? Boolean(merged.flowBlocked) : false,
    reviewReady: Boolean(Object.keys(reviewSeed).length),
    reviewScore: Number(reviewSeed.score) || null,
    reviewReason: String(reviewSeed.reason || '')
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
    const runEntries = discoverRunNames(projectDir).map(name => ({ name }));

    for (const runEntry of runEntries) {
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
      const supervisorPath = path.join(`${runDir}.meta`, 'supervisor.pid');
      const supervisorPid = fileExists(supervisorPath) ? fs.readFileSync(supervisorPath, 'utf8').trim() : '';
      const supervisorAlive = supervisorPid ? pidAlive(supervisorPid) : null;
      const liveState = ['starting', 'running', 'stopping'].includes(rawState);
      const isLive = liveState
        ? supervisorAlive !== false
        : (!hasReport && !hasStatus && !hasMeta && recentLog);
      const state = liveState && supervisorAlive === false
        ? 'stopped'
        : (isLive && rawState === 'unknown' ? 'running' : rawState);
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
        projectName: projectInfo(project).name,
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
        commit: meta.commit || status.commit || '',
        branch: meta.branch || status.branch || '',
        targetUrl: meta.target_url || '',
        recovery: summarizeRecovery(status.recovery),
        container: status.container || '',
        state,
        exitCode: meta.exit_code ?? null,
        timedOut: Boolean(meta.timed_out) || state === 'timeout',
        interrupted: Boolean(meta.interrupted) || state === 'stopped',
        reportsComplete: Boolean(meta.reports_complete),
        visualStatus: status.visual_status || '',
        verifyAgentStatus: status.verify_agent_status || '',
        redteamStatus: status.redteam_status || '',
        reviewReady: Number(status.review_ready || 0),
        reportGeneratedAt: report.generated_at || null,
        lastLogLine: (() => {
          const renderedLine = hasLog ? readLastLine(logPath) : '';
          const wrapperPath = path.join(`${runDir}.meta`, 'wrapper.log');
          const wrapperLine = fileExists(wrapperPath) ? readLastLine(wrapperPath) : '';
          return renderedLine && !renderedLine.startsWith('#') ? renderedLine : wrapperLine || renderedLine;
        })(),
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

function findingFromOccurrence(occurrence, runs) {
  const run = runs.find((item) => item.project === occurrence.project && item.runId === occurrence.run_id);
  let finding = run?.findings.find((item) => item.occurrence_id === occurrence.occurrence_id);
  if (!finding) {
    const reportPath = path.resolve(REPO_ROOT, occurrence.report);
    const meta = readJson(path.join(path.dirname(reportPath), 'run-meta.json')) || {};
    finding = normalizeFindings(
      occurrence.project,
      occurrence.run_id,
      { findings: [occurrence.raw || {}], generated_at: occurrence.generated_at },
      meta
    )[0];
  }
  return {
    ...finding,
    key: occurrence.occurrence_id,
    occurrence_id: occurrence.occurrence_id,
    semantic_id: occurrence.semantic_id,
    finding_id: occurrence.finding_id,
    legacy_key: occurrence.legacy_key,
    id: occurrence.local_id,
    runId: occurrence.run_id,
    severity: occurrence.severity,
    verified: occurrence.verified === true,
    confidence: occurrence.confidence,
    generatedAt: occurrence.generated_at,
    commit: occurrence.commit,
    reportPath: run?.reportPath || path.resolve(REPO_ROOT, occurrence.report),
    reportMdPath: run?.reportMdPath || '',
    runDir: run?.runDir || path.dirname(path.resolve(REPO_ROOT, occurrence.report))
  };
}

function buildBoard() {
  const runs = discoverRuns();
  const {
    curated, state, auto, refine, flow, review, ledger, watchBranches,
    autoGeneratedAt, flowStatus
  } = loadOverrides();
  const useLedger = isLedgerV2(ledger);
  const ledgerOccurrences = latestOccurrences(ledger);
  const latestReport = new Map();
  const latestLive = new Map();
  const latestAny = new Map();

  for (const run of runs) {
    if (!latestAny.has(run.project)) latestAny.set(run.project, run);
    if (!useLedger && run.hasReport && !latestReport.has(run.project)) latestReport.set(run.project, run);
    if (run.isLive && !latestLive.has(run.project)) latestLive.set(run.project, run);
  }
  if (useLedger) {
    for (const [project, latestValid] of Object.entries(ledger.latest_by_project || {})) {
      const run = runs.find((item) => item.project === project && item.runId === latestValid.run_id);
      if (run) latestReport.set(project, run);
    }
  }

  const projectIds = new Set([
    ...latestAny.keys(), ...latestReport.keys(), ...latestLive.keys(),
    ...Object.keys(useLedger ? ledger.latest_by_project || {} : {})
  ]);
  const projects = [];
  const findings = [];

  for (const project of projectIds) {
    const reportRun = latestReport.get(project) || null;
    const liveRun = latestLive.get(project) || null;
    const latest = latestAny.get(project) || null;
    const baseFindings = useLedger
      ? ledgerOccurrences
        .filter((occurrence) => occurrence.project === project)
        .map((occurrence) => findingFromOccurrence(occurrence, runs))
      : reportRun?.findings || [];
    const mergedFindings = baseFindings.map((finding) =>
      mergeOverrides(finding, curated, state, auto, refine, flow, review, ledger)
    );
    findings.push(...mergedFindings);
    const severityCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    for (const finding of mergedFindings) severityCounts[finding.severity] += 1;
    const projectRuns = runs.filter((item) => item.project === project);
    const sourceRun = reportRun || latest;
    const activeRun = liveRun || latest;

    const info = projectInfo(project);
    projects.push({
      id: project,
      name: info.name,
      direction: info.direction,
      icon: info.icon,
      tone: info.tone,
      logo: info.logo,
      url: info.url,
      auditId: info.auditId,
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
      branch: sourceRun?.branch || watchBranches[project] || '',
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
  const status = { inbox: 0, triage: 0, reproduce: 0, cve: 0, closed: 0, archived: 0 };
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
    flowStatus,
    stats: {
      total: findings.length,
      curated: findings.filter((finding) => finding.curated).length,
      tp: findings.filter((finding) => finding.verdict === 'tp').length,
      cveCandidates: findings.filter((finding) => finding.cveTier).length,
      cveTrack: findings.filter((finding) => finding.status === 'cve').length,
      autoRouted: findings.filter((finding) => finding.routedBy === 'auto').length,
      manualRouted: findings.filter((finding) => finding.routedBy === 'manual').length,
      archived: findings.filter((finding) => finding.status === 'archived').length,
      reviewReady: findings.filter((finding) => finding.reviewReady).length,
      closed: findings.filter((finding) => finding.status === 'closed').length,
      live: liveRuns.length,
      severity,
      status,
      verdict
    },
    sources: {
      curated: path.join(DATA_ROOT, 'curated.json'),
      state: path.join(DATA_ROOT, 'state.json'),
      auto: path.join(DATA_ROOT, 'auto-state.json'),
      autoGeneratedAt
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
      name: projectInfo(project).name,
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
      visualStatus: run.visualStatus || '',
      verifyAgentStatus: run.verifyAgentStatus || '',
      redteamStatus: run.redteamStatus || '',
      reviewReady: run.reviewReady || 0,
      lastLogLine: run.lastLogLine,
      logMtime: run.logMtime
    };
  });
  return { generatedAt: new Date().toISOString(), liveRuns, projects };
}

const modelSettings = createModelSettings({repoRoot:REPO_ROOT});
const githubCommitLister = createGithubCommitLister();
const projectImporter = createProjectImporter({
  repoRoot: REPO_ROOT,
  getModelArgs: () => modelSettings.args(),
  isProjectLive: (project) => buildLive().liveRuns.some((run) => run.project === project),
  onImported: (project, metadata) => { if (metadata) PROJECT_META[project] = metadata; else delete PROJECT_META[project]; }
});
const githubBranchLister = createGithubBranchLister();

function findRun(project, runId, withFindings = true) {
  const runs = discoverRuns({ withFindings });
  return runs.find((run) => run.project === project && run.runId === runId) || null;
}

const AGENT_TOPOLOGY_CACHE = new Map();
const AGENT_TOPOLOGY_CACHE_LIMIT = 8;

function loadAgentTopology(run) {
  const rawPath = path.join(run.runDir, 'raw.jsonl');
  let stat = null;
  try {
    stat = fs.statSync(rawPath);
  } catch {
    stat = null;
  }

  const cached = AGENT_TOPOLOGY_CACHE.get(rawPath);
  if (cached && stat && cached.mtimeMs === stat.mtimeMs && cached.size === stat.size) {
    return cached.payload;
  }

  const parsed = stat ? parseAgentTopology(rawPath) : { agents: [], summary: { total: 0, running: 0, completed: 0, failed: 0 } };
  const report = readJson(run.reportPath, null) || {};
  const boundaries = [...new Set(parsed.agents.map((agent) => agent.boundary))];
  const payload = {
    project: run.project,
    projectName: run.projectName,
    runId: run.runId,
    isLive: run.isLive,
    updatedAt: stat ? stat.mtime.toISOString() : null,
    orchestrator: {
      agent: 'security-orchestrator',
      model: run.model || '',
      status: run.isLive ? 'running' : 'completed',
      startedAt: run.startedAt || null
    },
    agents: parsed.agents,
    summary: parsed.summary,
    boundaries,
    stage: report.stage && typeof report.stage === 'object' ? report.stage : {}
  };

  if (stat) {
    if (AGENT_TOPOLOGY_CACHE.size >= AGENT_TOPOLOGY_CACHE_LIMIT) {
      const oldest = AGENT_TOPOLOGY_CACHE.keys().next().value;
      AGENT_TOPOLOGY_CACHE.delete(oldest);
    }
    AGENT_TOPOLOGY_CACHE.set(rawPath, { mtimeMs: stat.mtimeMs, size: stat.size, payload });
  }
  return payload;
}

const CCUI_HEALTH_TTL_MS = 5000;
let ccuiHealthCache = { at: 0, reachable: false };

async function ccuiReachable(force = false) {
  const now = Date.now();
  if (!force && now - ccuiHealthCache.at < CCUI_HEALTH_TTL_MS) return ccuiHealthCache.reachable;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch(`${CCUI_URL}/health`, { signal: controller.signal });
    ccuiHealthCache = { at: now, reachable: response.ok };
    return response.ok;
  } catch {
    ccuiHealthCache = { at: now, reachable: false };
    return false;
  } finally {
    clearTimeout(timer);
  }
}

const ccuiService = createCcuiService({repoRoot:REPO_ROOT,home:CCUI_HOME,url:CCUI_URL,health:ccuiReachable});

const indexedCcuiSessions = new Map();
async function indexCcuiSession(session) {
  const key = `${session.sessionId}:${session.importedAt}`;
  if (indexedCcuiSessions.has(key)) return indexedCcuiSessions.get(key);
  const pending = new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(REPO_ROOT, 'scripts/ccui/index_trace.mjs'), session.sessionFile], {
      env: { ...process.env, HOME: CCUI_HOME, DATABASE_PATH: path.join(CCUI_HOME, '.cloudcli/auth.db') },
      stdio: ['ignore', 'ignore', 'pipe']
    });
    let error = '';
    const timer = setTimeout(() => child.kill('SIGKILL'), 15000);
    child.stderr.on('data', chunk => { error = `${error}${chunk}`.slice(-1000); });
    child.on('error', cause => { clearTimeout(timer); reject(cause); });
    child.on('close', code => { clearTimeout(timer); code === 0 ? resolve() : reject(new Error(`轨迹会话登记失败：${error}`)); });
  }).catch(error => { indexedCcuiSessions.delete(key); throw error; });
  if (indexedCcuiSessions.size >= 100) indexedCcuiSessions.delete(indexedCcuiSessions.keys().next().value);
  indexedCcuiSessions.set(key, pending);
  return pending;
}

const ccuiImports = new Map();

function runCcuiImporter(run, trace, sidecarPath) {
  return new Promise((resolve) => {
    const child = spawn(
      'python3',
      [
        path.join(REPO_ROOT, 'scripts', 'ccui', 'import_trace.py'),
        '--run-dir', trace.sourceRunDir || run.runDir,
        '--home', CCUI_HOME,
        '--raw', trace.path,
        '--sidecar', sidecarPath,
        '--title', trace.node === 'orchestrator' ? '' : ` · ${trace.label}`,
        '--agent', trace.node === 'orchestrator' ? '' : trace.label
      ],
      { stdio: ['ignore', 'pipe', 'pipe'] }
    );
    let output = '';
    child.stdout.on('data', (chunk) => { output += chunk; });
    child.stderr.on('data', (chunk) => { output += chunk; });
    child.on('error', (error) => resolve({ ok: false, output: String(error) }));
    child.on('close', (code) => resolve({ ok: code === 0, output }));
  });
}

async function ensureCcuiSession(run, { force = false, node = 'orchestrator', traceId = '' } = {}) {
  const trace = resolveAgenticTrace(run, node, traceId);
  if (!trace) {
    return { available: false, reason: 'no recorded trace for this node', traceKind: 'missing' };
  }
  if (!['claude', 'execution'].includes(trace.kind)) {
    return {
      available: false,
      reason: trace.kind === 'execution'
        ? 'redteam execution uses a structured model loop, not Claude Code'
        : 'this legacy log is not a native Claude Code stream',
      traceKind: trace.kind,
      trace: { id: trace.id, label: trace.label, kind: trace.kind }
    };
  }
  const sidecarPath = traceSessionPath(run.runDir, node, trace.id);
  const sidecar = readJson(sidecarPath, null);
  const rawStat = fs.statSync(trace.path, {bigint: true});
  const sidecarFresh =
    sidecar && sidecar.sessionId && fileExists(String(sidecar.sessionFile || ''));
  if (!force && sidecarFresh) {
    if (sessionMatchesTrace(sidecar, trace.path, rawStat)) {
      return { available: true, session: sidecar, reimported: false, traceKind: trace.kind };
    }
  }

  const key = `${run.project}/${run.runId}/${node}/${trace.id}`;
  const inflight = ccuiImports.get(key);
  if (inflight) await inflight;
  else {
    const job = runCcuiImporter(run, trace, sidecarPath).finally(() => ccuiImports.delete(key));
    ccuiImports.set(key, job);
    const result = await job;
    if (!result.ok) {
      return { available: false, reason: `import failed: ${result.output.slice(-400)}`, traceKind: trace.kind };
    }
  }

  const updated = readJson(sidecarPath, null);
  if (!updated || !updated.sessionId) {
    return { available: false, reason: 'import produced no session (empty trace?)', traceKind: trace.kind };
  }
  return { available: true, session: updated, reimported: true, traceKind: trace.kind };
}

function isCcuiApiPath(pathname) {
  return CCUI_API_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

function proxyCcui(req, res, targetPath) {
  const target = new URL(CCUI_URL);
  const headers = { ...req.headers };
  delete headers.connection;
  delete headers['transfer-encoding'];
  headers.host = target.host;
  const upstreamReq = http.request(
    {
      hostname: target.hostname,
      port: Number(target.port) || 80,
      path: targetPath,
      method: req.method,
      headers
    },
    (upstreamRes) => {
      const headersOut = { ...upstreamRes.headers };
      delete headersOut['transfer-encoding'];
      res.writeHead(upstreamRes.statusCode || 502, headersOut);
      upstreamRes.pipe(res);
    }
  );
  upstreamReq.on('error', () => {
    ccuiHealthCache = {at: 0, reachable: false};
    if (!res.headersSent) sendError(res, 502, 'CloudCLI upstream unavailable');
    else res.end();
  });
  req.pipe(upstreamReq);
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

async function saveState(project, id, patch, occurrenceId = '') {
  const statePath = path.join(DATA_ROOT, 'state.json');
  const state = readJson(statePath) || {};
  const key = occurrenceId || `${project}:${id}`;
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
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
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
  if (fileExists(candidate) && relative !== 'index.html') {
    sendFile(res, candidate, pathname.startsWith('/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache');
    return;
  }
  const index = path.join(DIST_ROOT, 'index.html');
  if (fileExists(index)) {
    const language = currentLanguage();
    let html = fs.readFileSync(index, 'utf8');
    html = html.replace(/<html lang="[^"]*"/, `<html lang="${language === 'zh' ? 'zh-CN' : 'en'}"`);
    html = html.replace(
      '<head>',
      `<head>\n    <script>window.__MYGOLDMINE_LANGUAGE__=${JSON.stringify(language)};</script>`
    );
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-cache'
    });
    res.end(html);
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

  if (pathname === CCUI_PREFIX || pathname.startsWith(`${CCUI_PREFIX}/`)) {
    proxyCcui(req, res, req.url.slice(CCUI_PREFIX.length) || '/');
    return;
  }
  if (isCcuiApiPath(pathname) || pathname === '/health') {
    proxyCcui(req, res, req.url);
    return;
  }

  try {
    if (req.method === 'GET' && pathname === '/api/health') {
      sendJson(res, 200, { ok: true, repoRoot: REPO_ROOT, time: new Date().toISOString() });
      return;
    }

    if (req.method === 'GET' && pathname === '/api/board') {
      sendJson(res, 200, buildBoard());
      return;
    }

    const restartTarget = pathname.match(/^\/api\/targets\/([^/]+)\/restart$/);
    if (req.method === 'POST' && restartTarget) {
      const project = normalizeProjectId(restartTarget[1]);
      if (fs.existsSync(path.join(REPO_ROOT, 'runs', `.learning-cycle-${project}.lock`))) return sendError(res, 409, '该项目正在执行学习循环');
      if (fs.existsSync(path.join(REPO_ROOT, 'runs', `.node-retry-${project}.lock`))) return sendError(res, 409, '该项目正在执行节点重跑');
      if (!discoverRuns({withFindings:false}).some(run => run.project === project)) return sendError(res,404,'项目不存在');
      sendJson(res,201,await projectImporter.restart(project));
      return;
    }

    const removedTarget = pathname.match(/^\/api\/targets\/([^/]+)$/);
    if (req.method === 'DELETE' && removedTarget) {
      const project = normalizeProjectId(decodeURIComponent(removedTarget[1]));
      const runs = discoverRuns({ withFindings: false });
      if (runs.some(run => run.project === project && run.isLive)) return sendError(res, 409, '项目仍在审计中，请先停止审计后再删除');
      if (!runs.some(run => run.project === project)) return sendError(res, 404, '项目不存在');
      removeProjectRecords(REPO_ROOT, project);
      delete PROJECT_META[project];
      sendJson(res, 200, { ok: true, project });
      return;
    }

    if (req.method === 'GET' && pathname === '/api/targets/browse') {
      const result = await browseServerDirectory(url.searchParams.get('path') || '');
      sendJson(res, 200, result);
      return;
    }

    if (req.method === 'POST' && pathname === '/api/targets/github-commits') {
      const body = await readBody(req);
      sendJson(res, 200, await githubCommitLister.list(body.source, { page: body.page, limit: body.limit }));
      return;
    }

    if (req.method === 'POST' && pathname === '/api/targets/github-branches') {
      const body = await readBody(req);
      const result = await githubBranchLister.list(body.source, { offset: body.offset, limit: body.limit });
      sendJson(res, 200, result);
      return;
    }

    if (req.method === 'POST' && pathname === '/api/targets/import-stream') {
      const body = await readBody(req);
      res.writeHead(200, { 'Content-Type': 'application/x-ndjson; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no' });
      res.flushHeaders();
      const controller = new AbortController();
      const cancel = () => controller.abort();
      res.on('close', cancel);
      const send = (payload) => { if (!res.destroyed) res.write(JSON.stringify(payload) + '\n'); };
      const heartbeat = setInterval(() => send({ type: 'heartbeat' }), 10000);
      try {
        const result = await projectImporter.import(body, (message) => send({ type: 'info', message, at: new Date().toISOString() }), controller.signal);
        send({ type: 'result', result });
      } catch (error) {
        send({ type: 'error', message: error.message });
      } finally {
        clearInterval(heartbeat);
        res.off('close', cancel);
        res.end();
      }
      return;
    }

    if (req.method === 'POST' && pathname === '/api/targets/import') {
      const body = await readBody(req);
      const result = await projectImporter.import(body);
      sendJson(res, 201, result);
      return;
    }

    if (pathname === '/api/stage-models' && req.method === 'GET') {
      sendJson(res,200,modelSettings.get());return;
    }
    if (pathname === '/api/stage-models' && req.method === 'POST') {
      const body=await readBody(req);sendJson(res,200,modelSettings.save(body.models));return;
    }

    if (req.method === 'GET' && pathname === '/api/language') {
      sendJson(res, 200, { language: currentLanguage() });
      return;
    }

    if (req.method === 'POST' && pathname === '/api/language') {
      const body = await readBody(req);
      const language = String(body?.language || '').toLowerCase();
      if (language !== 'zh' && language !== 'en') {
        return sendError(res, 400, 'language must be zh or en');
      }
      try {
        fs.mkdirSync(CONFIG_ROOT, { recursive: true });
        fs.writeFileSync(
          path.join(CONFIG_ROOT, 'system.json'),
          JSON.stringify({ language }, null, 2) + '\n',
          'utf8'
        );
      } catch (error) {
        return sendError(res, 500, `failed to save language: ${error.message}`);
      }
      sendJson(res, 200, { language });
      return;
    }

    if (req.method === 'GET' && pathname === '/api/watch') {
      try {
        const payload = JSON.parse(fs.readFileSync(path.join(DATA_ROOT, 'watch-state.json'), 'utf8'));
        sendJson(res, 200, payload);
      } catch {
        sendJson(res, 200, { generatedAt: null, counts: {}, repos: [], brief: { top: [] } });
      }
      return;
    }

    if (req.method === 'GET' && pathname === '/api/live') {
      sendJson(res, 200, buildLive());
      return;
    }

    const pipelineMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/pipeline$/);
    if (req.method === 'GET' && pipelineMatch) {
      const run = findRun(pipelineMatch[1], pipelineMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      sendJson(res, 200, buildAgenticPipeline(run));
      return;
    }

    const agentsMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/agents$/);
    if (req.method === 'GET' && agentsMatch) {
      const run = findRun(agentsMatch[1], agentsMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      sendJson(res, 200, loadAgentTopology(run));
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
        recovery: run.recovery,
        severityCounts: run.severityCounts
      }));
      sendJson(res, 200, { runs });
      return;
    }

    if (req.method === 'GET' && pathname === '/api/ccui') {
      const reachable = await ccuiService.ensure();
      sendJson(res, 200, { url: CCUI_URL, embedPrefix: CCUI_PREFIX, home: CCUI_HOME, reachable });
      return;
    }

    const retryMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/nodes\/([^/]+)\/restart$/);
    if (req.method === 'POST' && retryMatch) {
      const run = findRun(retryMatch[1], retryMatch[2], false);
      if (!run) return sendError(res, 404, '未找到审计运行');
      return sendJson(res, 201, startNodeRetry({repoRoot: REPO_ROOT, run, node: retryMatch[3], models: modelSettings.get().models}));
    }

    const labReportMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/lab-tasks\/([^/]+)\/report$/);
    if(req.method==='GET' && labReportMatch) {
      const run=findRun(labReportMatch[1],labReportMatch[2],false);
      if(!run)return sendError(res,404,'未找到审计运行');
      const report=labTaskReport(run,labReportMatch[3],url.searchParams.get('attempt') || '');
      return report?sendJson(res,200,{report}):sendError(res,404,'该批次交付不存在或已切换批次，请刷新后重试');
    }

    const verifyReportMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/verify-tasks\/([^/]+)\/report$/);
    if (req.method === 'GET' && verifyReportMatch) {
      const run = findRun(verifyReportMatch[1], verifyReportMatch[2], false);
      if (!run) return sendError(res, 404, '未找到审计运行');
      const report = verifyTaskReport(run, verifyReportMatch[3], url.searchParams.get('attempt') || '');
      return report ? sendJson(res, 200, {report}) : sendError(res, 404, '该批次报告不存在或已切换批次，请刷新后重试');
    }

    const traceMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/trace$/);
    if (req.method === 'GET' && traceMatch) {
      const run = findRun(traceMatch[1], traceMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      const node = url.searchParams.get('node') || 'orchestrator';
      const trace = resolveAgenticTrace(run, node, url.searchParams.get('id') || '');
      if (!trace) return sendError(res, 404, 'Trace not found');
      const lines = readText(trace.path).split(/\r?\n/);
      sendJson(res, 200, {
        node,
        id: trace.id,
        label: trace.label,
        kind: trace.kind,
        totalLines: lines.length,
        lines: lines.slice(-1000)
      });
      return;
    }

    const ccuiMatch = pathname.match(/^\/api\/runs\/([^/]+)\/([^/]+)\/ccui$/);
    if (req.method === 'GET' && ccuiMatch) {
      const run = findRun(ccuiMatch[1], ccuiMatch[2], false);
      if (!run) return sendError(res, 404, 'Run not found');
      const force = url.searchParams.get('force') === '1';
      const node = url.searchParams.get('node') || 'orchestrator';
      const traceId = url.searchParams.get('trace') || '';
      const [outcome, reachable] = await Promise.all([
        ensureCcuiSession(run, { force, node, traceId }), ccuiService.ensure()
      ]);
      if (!outcome.available) {
        sendJson(res, 200, {
          available: false,
          reason: outcome.reason,
          reachable,
          url: CCUI_URL,
          traceKind: outcome.traceKind || 'missing',
          trace: outcome.trace || null
        });
        return;
      }
      const session = outcome.session;
      if (reachable) await indexCcuiSession(session);
      sendJson(res, 200, {
        available: true,
        reachable,
        sessionId: session.sessionId,
        projectPath: session.cwd || '',
        messages: session.messages || 0,
        importedAt: session.importedAt || null,
        reimported: Boolean(outcome.reimported),
        traceKind: outcome.traceKind || 'claude',
        url: `${CCUI_PREFIX}/session/${session.sessionId}`
      });
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
      const occurrenceId = url.searchParams.get('occurrence_id') || '';
      const finding = board.findings.find((item) =>
        item.project === rawMatch[1] && item.id === rawMatch[2] &&
        (!occurrenceId || item.occurrence_id === occurrenceId)
      );
      if (!finding) return sendError(res, 404, 'Finding not found');
      const report = readJson(finding.reportPath);
      const list = Array.isArray(report?.findings) ? report.findings : Array.isArray(report?.vulnerabilities) ? report.vulnerabilities : [];
      const baseId = finding.id.replace(/~\d+$/, '');
      const duplicateIndex = Number(finding.id.match(/~(\d+)$/)?.[1] || 1) - 1;
      const raw = list.filter((item) => String(item.id || item.finding_id) === baseId)[duplicateIndex] || null;
      sendJson(res, 200, { finding, raw, reportPath: finding.reportPath, runDir: finding.runDir, commit: finding.commit });
      return;
    }

    const patchMatch = pathname.match(/^\/api\/findings\/([^/]+)\/([^/]+)$/);
    if (req.method === 'PATCH' && patchMatch) {
      const project = patchMatch[1];
      const id = patchMatch[2];
      const occurrenceId = url.searchParams.get('occurrence_id') || '';
      const board = buildBoard();
      const finding = board.findings.find((item) =>
        item.project === project && item.id === id &&
        (!occurrenceId || item.occurrence_id === occurrenceId)
      );
      if (!finding) return sendError(res, 404, 'Finding not found');
      const body = await readBody(req);
      const patch = sanitizePatch(body);
      const saved = await saveState(project, id, patch, finding.occurrence_id || occurrenceId);
      sendJson(res, 200, { ok: true, state: saved });
      return;
    }

    if (pathname.startsWith('/api/')) {
      sendError(res, 404, 'Not found');
      return;
    }

    serveStatic(req, res, pathname);
  } catch (error) {
    const statusCode = Number.isInteger(error?.status) && error.status >= 400 && error.status < 500
      ? error.status
      : 500;
    sendError(res, statusCode, error instanceof Error ? error.message : 'Internal error');
  }
});

server.on('upgrade', (req, clientSocket, head) => {
  const { pathname } = new URL(req.url, 'http://localhost');
  const isCcuiWs = CCUI_WS_PATHS.some(
    (wsPath) => pathname === wsPath || pathname.startsWith(`${wsPath}/`)
  );
  if (!isCcuiWs) {
    clientSocket.destroy();
    return;
  }
  const target = new URL(CCUI_URL);
  const upstream = net.connect(Number(target.port) || 3001, target.hostname, () => {
    const lines = [`${req.method} ${req.url} HTTP/1.1`];
    for (let i = 0; i < req.rawHeaders.length; i += 2) {
      lines.push(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}`);
    }
    upstream.write(`${lines.join('\r\n')}\r\n\r\n`);
    if (head.length) upstream.write(head);
    upstream.pipe(clientSocket);
    clientSocket.pipe(upstream);
  });
  upstream.on('error', () => clientSocket.destroy());
  clientSocket.on('error', () => upstream.destroy());
});

server.listen(PORT, HOST, () => {
  console.log(`[vul-ai-board] http://${HOST}:${PORT}`);
  console.log(`[vul-ai-board] repo=${REPO_ROOT}`);
});
