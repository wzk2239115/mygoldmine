import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { listAgenticTraces, listWorkflowTraces, resolveAgenticTrace, traceSessionPath } from '../server/agentic-traces.mjs';

function write(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, 'utf8');
}

const claude = `${JSON.stringify({ type: 'system', subtype: 'init', session_id: 'session-1' })}\n${JSON.stringify({ type: 'assistant', message: { content: [] } })}\n`;

test('节点轨迹按真实调用定位并区分 Claude、文本和红队执行', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agentic-traces-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const runDir = path.join(root, 'run-1');
  const run = { runDir };
  write(path.join(runDir, 'raw.jsonl'), claude);
  write(`${runDir}.meta/env-build-agent-1.log`, claude);
  write(path.join(runDir, 'visual/agentic/F-1/agent.log'), '# returncode\n1\n旧文本日志\n');
  write(path.join(runDir, 'verify/agent/logs/F-1.agent.log'), claude);
  write(path.join(runDir, 'redteam/summary.json'), JSON.stringify({
    results: [{
      scenario: path.join(root, 'labs/demo/F-1/scenario.json'),
      run_dir: path.join(root, 'redteam/demo/run-a')
    }]
  }));
  write(path.join(root, 'labs/demo/F-1/builder.log'), claude);
  write(path.join(root, 'redteam/demo/run-a/agent.jsonl'), '{"action":"shell"}\n');
  write(path.join(root, 'redteam/demo/run-a/judge.log'), claude);
  write(path.join(runDir, 'rsi/learner.jsonl'), claude);

  assert.equal(resolveAgenticTrace(run, 'orchestrator').kind, 'claude');
  assert.equal(resolveAgenticTrace(run, 'environment').kind, 'claude');
  assert.equal(resolveAgenticTrace(run, 'visual').kind, 'text');
  assert.equal(resolveAgenticTrace(run, 'verify').kind, 'claude');
  assert.equal(resolveAgenticTrace(run, 'redteam-lab').kind, 'claude');
  assert.equal(resolveAgenticTrace(run, 'redteam-agent').kind, 'execution');
  assert.equal(resolveAgenticTrace(run, 'judge').kind, 'claude');
  assert.equal(resolveAgenticTrace(run, 'learner').kind, 'claude');
  assert.equal(listAgenticTraces(run, 'missing').length, 0);
});

test('没有主会话时展示启动失败日志，有会话后优先显示会话', (t) => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'startup-trace-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const run={runDir:path.join(root,'run')};
  write(`${run.runDir}.meta/wrapper.log`,'cp: cannot create directory: File exists\n');
  assert.equal(resolveAgenticTrace(run,'orchestrator').id,'startup');
  assert.equal(resolveAgenticTrace(run,'orchestrator').kind,'text');
  write(path.join(run.runDir,'raw.jsonl'),claude);
  assert.equal(resolveAgenticTrace(run,'orchestrator').id,'main');
});


test('各节点轨迹缓存不占用审计输出目录', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'trace-cache-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const run=path.join(root,'not-started');
  fs.mkdirSync(run);
  for(const node of ['orchestrator','environment','verify','learner']) write(traceSessionPath(run,node,'round-1'),'{}');
  assert.deepEqual(fs.readdirSync(run),[]);
  assert.ok(fs.existsSync(`${run}.meta/ccui-session.json`));
  assert.ok(fs.existsSync(`${run}.meta/ccui-sessions/environment-round-1.json`));
});

test('恢复汇总保留原始审计入口，且会话缓存互不覆盖', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'recovery-traces-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const source = path.join(root, 'run-1');
  const run = { runDir: `${source}-recovery` };
  write(path.join(source, 'raw.jsonl'), claude);
  write(path.join(run.runDir, 'raw.jsonl'), claude);
  write(path.join(run.runDir, 'audit-report.json'), JSON.stringify({ coverage: { analysis_mode: 'assembly-only' } }));
  const traces = listAgenticTraces(run, 'orchestrator');
  assert.deepEqual(traces.map(trace => trace.label), ['原始完整审计', '恢复汇总（未重新扫描）']);
  assert.equal(resolveAgenticTrace(run, 'orchestrator', 'source-main').sourceRunDir, source);
  assert.notEqual(traceSessionPath(run.runDir, 'orchestrator', 'main'), traceSessionPath(run.runDir, 'orchestrator', 'source-main'));
  fs.rmSync(source, { recursive: true });
  assert.equal(listAgenticTraces(run, 'orchestrator').length, 1);
  assert.equal(listAgenticTraces(run, 'orchestrator')[0].label, '恢复汇总（未重新扫描）');
});

test('恢复汇总能查看原始环境构建会话', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'recovery-environment-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const original=path.join(root,'run'); const run={runDir:`${original}-recovery`};
  write(`${original}.meta/env-build-agent-1.log`,claude);
  write(path.join(run.runDir,'audit-report.json'),JSON.stringify({coverage:{analysis_mode:'assembly-only'}}));
  const trace=listAgenticTraces(run,'environment')[0];
  assert.equal(trace.sourceRunDir,original);
  assert.match(trace.label,/原始运行/);
  write(`${run.runDir}.meta/env-phase0.log`,'new build');
  assert.equal(listAgenticTraces(run,'environment').length,0);
});

test('多次阶段学习默认打开最新会话，明确的错误编号不回退', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'learner-default-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const run={runDir:path.join(root,'run')};
  write(path.join(run.runDir,'rsi/learner.jsonl'),claude);
  write(path.join(run.runDir,'rsi/stage-learning-attempts/new/stream.jsonl'),claude);
  assert.equal(resolveAgenticTrace(run,'learner').id,'stage-learning-new');
  assert.equal(resolveAgenticTrace(run,'learner','not-a-session'),null);
});

test('经验学习展示 SkillOpt 文本轨迹，但默认仍打开阶段学习会话', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'skillopt-trace-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const run={runDir:path.join(root,'run')};
  write(path.join(run.runDir,'rsi/stage-learning-attempts/new/stream.jsonl'),claude);
  write(path.join(run.runDir,'rsi/skillopt/request-1.json'),'{"status":"candidate"}');
  const traces=listAgenticTraces(run,'learner');
  const skillopt=traces.find(item=>item.id==='skillopt-request-1');
  assert.equal(skillopt.kind,'text');
  assert.equal(resolveAgenticTrace(run,'learner').id,'stage-learning-new');
});

test('运行修复会话和验收结果按本批次定位，不混入其他节点', t => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'runner-traces-'));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const run={runDir:path.join(root,'runs/demo/one'),project:'demo',runId:'one'};
  write(path.join(run.runDir,'redteam/batch/runner-repair/agent.jsonl'),claude);
  write(path.join(run.runDir,'redteam/batch/runner-repair/smoke.json'),'{"ok":true}');
  const traces=listAgenticTraces(run,'redteam-agent');
  assert.equal(traces.length,2);
  assert.equal(traces.find(item=>item.path.endsWith('agent.jsonl')).kind,'claude');
  assert.equal(listAgenticTraces(run,'judge').length,0);
});


test('整条工作流调度日志不能计入未开始节点的轨迹',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'workflow-trace-scope-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const run={runDir:path.join(root,'one')};
 write(run.runDir+'.meta/workflows/w1/raw.jsonl',claude);
 write(run.runDir+'.meta/env-build-agent-1.log',claude);
 assert.equal(listAgenticTraces(run,'environment').length,1);
 for(const node of ['orchestrator','visual','verify','redteam-lab','redteam-agent','judge','learner'])assert.equal(listAgenticTraces(run,node).length,0,node);
 assert.equal(listWorkflowTraces(run).length,1);
 assert.equal(resolveAgenticTrace(run,'workflow','workflow-w1').kind,'claude');
 assert.equal(resolveAgenticTrace(run,'orchestrator','workflow-w1'),null);
});
