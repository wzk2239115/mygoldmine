import fs from 'node:fs';
import path from 'node:path';

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function traceKind(file, fallback = 'text') {
  try {
    const fd = fs.openSync(file, 'r');
    const buffer = Buffer.alloc(Math.min(fs.statSync(file).size, 64 * 1024));
    fs.readSync(fd, buffer, 0, buffer.length, 0);
    fs.closeSync(fd);
    for (const line of buffer.toString('utf8').split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('{')) continue;
      try {
        const event = JSON.parse(trimmed);
        if (['system', 'assistant', 'user', 'result'].includes(event.type)) return 'claude';
      } catch {}
    }
  } catch {}
  return fallback;
}

function makeTrace(node, id, label, file, fallback = 'text') {
  if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) return null;
  return {
    node,
    id,
    label,
    path: file,
    kind: traceKind(file, fallback),
    size: fs.statSync(file).size,
    updatedAt: fs.statSync(file).mtime.toISOString()
  };
}

function redteamTrace(run, node) {
  const summary = readJson(path.join(run.runDir, 'redteam/summary.json'));
  const results = Array.isArray(summary?.results) ? summary.results : [];
  const traces = [];
  for (const [index, item] of results.entries()) {
    const suffix = String(index + 1).padStart(2, '0');
    if (node === 'redteam-lab' && item.scenario) {
      const finding = path.basename(path.dirname(item.scenario)) || suffix;
      traces.push(makeTrace(node, `${finding}-${suffix}`, `场景 ${finding}`, path.join(path.dirname(item.scenario), 'builder.log')));
    }
    if (node === 'redteam-agent' && item.run_dir) {
      const runId = path.basename(item.run_dir) || suffix;
      traces.push(makeTrace(node, `${runId}-${suffix}`, `红队执行 ${runId}`, path.join(item.run_dir, 'agent.jsonl'), 'execution'));
    }
    if (node === 'judge' && item.run_dir) {
      const runId = path.basename(item.run_dir) || suffix;
      traces.push(makeTrace(node, `${runId}-${suffix}`, `独立审核 ${runId}`, path.join(item.run_dir, 'judge.log')));
    }
  }
  return traces.filter(Boolean);
}

export function listAgenticTraces(run, node) {
  if (node === 'orchestrator') {
    const main = makeTrace(node, 'main', '安全审计主会话', path.join(run.runDir, 'raw.jsonl'), 'claude');
    if (main?.size) return [main];
    const startup = makeTrace(node, 'startup', '审计启动日志', `${run.runDir}.meta/wrapper.log`);
    return startup ? [{ ...startup, kind: 'text' }] : [];

  }
  if (node === 'environment') {
    const meta = `${run.runDir}.meta`;
    const files = fs.existsSync(meta)
      ? fs.readdirSync(meta).filter((file) => /^env-build-agent-\d+\.log$/.test(file)).sort()
      : [];
    return files.map((file, index) => makeTrace(node, file.replace(/\.log$/, ''), `环境构建第 ${index + 1} 轮`, path.join(meta, file))).filter(Boolean);
  }
  if (node === 'visual') {
    const root = path.join(run.runDir, 'visual/agentic');
    const directories = fs.existsSync(root)
      ? fs.readdirSync(root, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort()
      : [];
    return directories.map((finding) => makeTrace(node, finding, `场景设计 ${finding}`, path.join(root, finding, 'agent.log'))).filter(Boolean);
  }
  if (node === 'verify') {
    const root = path.join(run.runDir, 'verify/agent/logs');
    const files = fs.existsSync(root)
      ? fs.readdirSync(root).filter((file) => file.endsWith('.agent.log')).sort()
      : [];
    return files.map((file) => {
      const finding = file.replace(/\.agent\.log$/, '');
      return makeTrace(node, finding, `蓝队验证 ${finding}`, path.join(root, file));
    }).filter(Boolean);
  }
  if (['redteam-lab', 'redteam-agent', 'judge'].includes(node)) return redteamTrace(run, node);
  if (node === 'learner') {
    return [makeTrace(node, 'learner', '经验学习主会话', path.join(run.runDir, 'rsi/learner.jsonl'), 'claude')].filter(Boolean);
  }
  return [];
}

export function resolveAgenticTrace(run, node, traceId = '') {
  const traces = listAgenticTraces(run, node);
  if (traceId) return traces.find((trace) => trace.id === traceId) || null;
  return traces.length === 1 ? traces[0] : null;
}
