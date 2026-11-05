import { nodeAttempts } from './node-retries.mjs';
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

function originalTraces(run, node) {
  if (node === 'orchestrator') {
    const main = makeTrace(node, 'main', '安全审计主会话', path.join(run.runDir, 'raw.jsonl'), 'claude');
    if (main?.size) {
      const report = readJson(path.join(run.runDir, 'audit-report.json'));
      if (report?.coverage?.analysis_mode === 'assembly-only') {
        main.label = '恢复汇总（未重新扫描）';
        // 仅关联同一项目下约定名称的原始运行，不信任报告中的任意路径。
        const name = path.basename(run.runDir);
        if (name.endsWith('-recovery')) {
          const sourceDir = path.join(path.dirname(run.runDir), name.slice(0, -9));
          const source = makeTrace(node, 'source-main', '原始完整审计', path.join(sourceDir, 'raw.jsonl'), 'claude');
          if (source?.size) return [{ ...source, sourceRunDir: sourceDir }, main];
        }
      }
      return [main];
    }
    const startup = makeTrace(node, 'startup', '审计启动日志', `${run.runDir}.meta/wrapper.log`);
    return startup ? [{ ...startup, kind: 'text' }] : [];

  }
  if (node === 'environment') {
    const report = readJson(path.join(run.runDir, 'audit-report.json'));
    if (path.basename(run.runDir).endsWith('-recovery') && report?.coverage?.analysis_mode === 'assembly-only' && !fs.existsSync(`${run.runDir}.meta/env-phase0.log`)) {
      const sourceDir = path.join(path.dirname(run.runDir), path.basename(run.runDir).slice(0, -9));
      return originalTraces({...run, runDir:sourceDir}, node).map(trace => ({...trace, id:`source-${trace.id}`, label:`原始运行 · ${trace.label}`, sourceRunDir:sourceDir}));
    }
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
  if(node==='redteam-lab') {
    const root=path.join(run.runDir,'redteam/batch/construction');
    const tasks=readJson(path.join(root,'selection.json'))?.candidates || [];
    const current=tasks.filter(task=>task.project===run.project && /^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(task.id)).map(task=>makeTrace(node,`lab-${task.id}`,`场景 ${task.id}`,path.join(root,'labs',run.project,task.id,'builder.log'))).filter(Boolean);
    if(current.length)return [...current,...redteamTrace(run,node).filter(trace=>!current.some(item=>item.path===trace.path))];
  }
  if (['redteam-lab', 'redteam-agent', 'judge'].includes(node)) return redteamTrace(run, node);
  if (node === 'learner') {
    const directory=path.join(run.runDir,'rsi/stage-learning-attempts');
    const attempts=fs.existsSync(directory)?fs.readdirSync(directory).map(id=>makeTrace(node,`stage-learning-${id}`,'八阶段技能提炼',path.join(directory,id,'stream.jsonl'),'claude')).filter(Boolean).sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)):[];
    const skilloptDirectory=path.join(run.runDir,'rsi/skillopt');
    const skillopt=fs.existsSync(skilloptDirectory)?fs.readdirSync(skilloptDirectory).filter(name=>name.endsWith('.json')).map(name=>makeTrace(node,`skillopt-${name.replace(/\.json$/,'') }`,'SkillOpt 技能重写',path.join(skilloptDirectory,name),'text')).filter(Boolean).sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt)):[];
    return [...attempts, ...skillopt, makeTrace(node, 'stage-learning-pilot', '八阶段技能提炼（试运行）', path.join(run.runDir,'rsi/stage-learning.jsonl'),'claude'), makeTrace(node, 'learner', '挖掘修复经验学习', path.join(run.runDir, 'rsi/learner.jsonl'), 'claude')].filter(Boolean);
  }
  return [];
}

export function listAgenticTraces(run, node) {
  const retries = nodeAttempts(run.runDir, node).reverse().flatMap(attempt => {
    const label = `节点重跑 ${new Date(attempt.startedAt).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false})} · ${attempt.status === 'running' ? '运行中' : attempt.resultStatus === 'degraded' ? '部分完成' : attempt.status === 'completed' ? '已结束' : '失败'}`;
    const worker=makeTrace(node, `${attempt.id}-worker`, `${label} · 批次日志`, path.join(attempt.root, 'worker.log'));
    if(node==='learner') {
      return [...originalTraces({...run,runDir:attempt.workspace},node).map(trace=>({...trace,id:`${attempt.id}-${trace.id}`,label:`${label} · ${trace.label}`})),worker].filter(Boolean);
    }
    if(node==='judge') {
      const root=path.join(attempt.workspace,'judge/runs');
      const entries=fs.existsSync(root)?fs.readdirSync(root):[];
      return [worker,...entries.flatMap(id=>[makeTrace(node,`${attempt.id}-judge-${id}`,`${label} · ${id} · 审核会话`,path.join(root,id,'judge.log')),makeTrace(node,`${attempt.id}-judge-${id}-worker`,`${label} · ${id} · 审核执行日志`,path.join(root,id,'judge-worker.log'))])].filter(Boolean);
    }
    if(node==='redteam-agent') {
      const directory=path.join(attempt.workspace,'redteam/agent-runs',run.project);
      const runs=fs.existsSync(directory)?fs.readdirSync(directory,{withFileTypes:true}).filter(entry=>entry.isDirectory()).map(entry=>entry.name):[];
      return [worker, ...runs.map(id=>makeTrace(node, `${attempt.id}-redteam-agent-${id}-agent`, `${label} · ${id} · 执行轨迹`, path.join(directory,id,'agent.jsonl'),'execution'))].filter(Boolean);
    }
    const directory=path.join(attempt.workspace,node==='visual'?'visual/agentic':node==='redteam-lab'?'redteam/labs':'verify/agent/logs');
    const logs=fs.existsSync(directory)?fs.readdirSync(directory).map(id=>node==='visual'?path.join(directory,id,'agent.log'):node==='redteam-lab'?path.join(directory,id,'builder.log'):path.join(directory,id)):[];
    return [worker, ...logs.map(file => {
      const name=path.basename(file), finding=node==='verify'?name.replace(/\.(agent|runner)\.log$/,''):path.basename(path.dirname(file));
      const kind=node==='verify' && name.endsWith('.runner.log')?'runner':'agent';
      return makeTrace(node, `${attempt.id}-${node}-${finding}-${kind}`, `${label} · ${finding} · ${kind==='runner'?'执行器日志':'智能体轨迹'}`, file);
    })].filter(Boolean);
  });
  const original = originalTraces(run, node);
  const roots = new Set([run.runDir, path.join(run.runDir, 'visual-rendered')]);
  for (const attempt of nodeAttempts(run.runDir, node)) { roots.add(attempt.workspace); roots.add(path.join(attempt.workspace, 'visual-rendered')); }
  for (const trace of original) roots.add(path.dirname(trace.path));
  if (node === 'verify') {
    const directory = path.join(run.runDir, 'verify/agent');
    if (fs.existsSync(directory)) for (const name of fs.readdirSync(directory)) roots.add(path.join(directory,name));
  }
  if(node==='redteam-lab')for(const attempt of nodeAttempts(run.runDir,node)) {
    const directory=path.join(attempt.workspace,'redteam/labs');
    if(fs.existsSync(directory))for(const entry of fs.readdirSync(directory,{withFileTypes:true}))if(entry.isDirectory())roots.add(path.join(directory,entry.name));
  }
  const receipts = [];
  for (const root of roots) {
    const directory = path.join(root, '.stage-submissions', node);
    if (!fs.existsSync(directory)) continue;
    for (const name of fs.readdirSync(directory)) {
      const file = path.join(directory,name), receipt = readJson(file);
      if (!receipt?.id || receipt.stage !== node) continue;
      receipts.push(makeTrace(node, `submission-${receipt.id}`, `交付检查 · ${receipt.decision === 'accepted' ? '通过' : '需修改'} · ${new Date(receipt.checked_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}`, file, 'text'));
    }
  }
  return [...retries, ...original, ...receipts.filter(Boolean)];
}

export function resolveAgenticTrace(run, node, traceId = '') {
  const traces = listAgenticTraces(run, node);
  if (traceId) return traces.find((trace) => trace.id === traceId) || null;
  return traces[0] || null;
}

export function traceSessionPath(runDir, node, traceId) {
  const safe = value => value.replace(/[^A-Za-z0-9._-]/g, '_');
  const metadata = `${runDir}.meta`;
  return node === 'orchestrator' && traceId !== 'source-main'
    ? path.join(metadata, 'ccui-session.json')
    : path.join(metadata, 'ccui-sessions', `${safe(node)}-${safe(traceId)}.json`);
}
