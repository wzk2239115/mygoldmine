import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildAgenticPipeline } from '../server/agentic-pipeline.mjs';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agentic-pipeline-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const runDir = path.join(root, 'runs/demo/run-1');
  fs.mkdirSync(`${runDir}.meta`, { recursive: true });
  fs.mkdirSync(runDir, { recursive: true });
  return {
    root,
    runDir,
    run: {
      project: 'demo',
      projectName: 'Demo',
      runId: 'run-1',
      runDir,
      reportPath: '',
      state: 'running',
      isLive: true,
      hasReport: false,
      hasLog: false,
      reportsComplete: false,
      visualStatus: '',
      verifyAgentStatus: '',
      redteamStatus: ''
    }
  };
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(value), 'utf8');
}

test('八节点区分真实完成、备用方案降级、受阻和未开始', (t) => {
  const { runDir, run } = fixture(t);
  writeJson(`${runDir}.meta/env-phase.json`, {
    agent: { status: 'failed_fallback' },
    final: { status: 'ready' },
    manifest: '/tmp/env-manifest.json'
  });
  writeJson(path.join(runDir, 'audit-report.json'), { findings: Array.from({ length: 14 }, () => ({})) });
  Object.assign(run, {
    reportPath: path.join(runDir, 'audit-report.json'),
    state: 'partial',
    isLive: false,
    hasReport: true,
    reportsComplete: true,
    verifyAgentStatus: 'blocked',
    redteamStatus: 'blocked'
  });
  writeJson(path.join(runDir, 'visual-rendered/visual-summary.json'), {
    scene_count: 2,
    steps: { render_attack_scenes_agentic: { attempted: true, returncode: 1 } }
  });
  writeJson(path.join(runDir, 'rsi/post-validation.json'), { status: 'completed', candidates: 0 });

  const result = buildAgenticPipeline(run);
  assert.equal(result.nodes.length, 8);
  assert.deepEqual(result.nodes.map((node) => [node.id, node.status]), [
    ['environment', 'degraded'],
    ['orchestrator', 'completed'],
    ['visual', 'degraded'],
    ['verify', 'blocked'],
    ['redteam-lab', 'blocked'],
    ['redteam-agent', 'pending'],
    ['judge', 'pending'],
    ['learner', 'completed']
  ]);
  assert.match(result.nodes[0].detail, /确定性备用方案/);
  assert.match(result.nodes[2].detail, /直接绘图备用方案/);
  assert.match(result.nodes[1].detail, /14 条候选/);
});

test('红队场景、执行和独立审核分别使用真实结果', (t) => {
  const { runDir, run } = fixture(t);
  Object.assign(run, { state: 'completed', isLive: false, hasReport: true, reportsComplete: true });
  writeJson(path.join(runDir, 'redteam/summary.json'), {
    results: [
      { scenario: '/tmp/lab-1.json', agent_returncode: 0, judge_returncode: 0, status: 'judge_approved' },
      { scenario: '/tmp/lab-2.json', agent_returncode: 1, status: 'agent_failed' },
      { scenario: '/tmp/lab-3.json', builder_returncode: 1, status: 'build_failed' }
    ]
  });

  const result = buildAgenticPipeline(run);
  const nodes = Object.fromEntries(result.nodes.map((node) => [node.id, node]));
  assert.equal(nodes['redteam-lab'].status, 'degraded');
  assert.match(nodes['redteam-lab'].detail, /2\/3 个隔离场景可用/);
  assert.equal(nodes['redteam-agent'].status, 'degraded');
  assert.match(nodes['redteam-agent'].detail, /2\/3 个红队执行已结束/);
  assert.match(nodes['redteam-agent'].detail, /1 个失败/);
  assert.equal(nodes.judge.status, 'completed');
  assert.match(nodes.judge.detail, /通过 1\/1/);
});

test('没有产物时不会把总运行状态伪装成八节点完成', (t) => {
  const { run } = fixture(t);
  const result = buildAgenticPipeline(run);
  assert.equal(result.summary.total, 8);
  assert.equal(result.summary.completed, 0);
  assert.equal(result.nodes[0].status, 'running');
  assert.equal(result.nodes[1].status, 'pending');
  assert.ok(result.nodes.slice(2).every((node) => node.status === 'pending'));
});

test('智能体已交付部分可用环境时完成状态与能力范围分开', (t) => {
  const {runDir,run}=fixture(t);
  writeJson(`${runDir}.meta/env-phase.json`,{agent:{status:'partial'},final:{status:'partial'}});
  const node=buildAgenticPipeline(run).nodes.find(item=>item.id==='environment');
  assert.equal(node.status,'completed');
  assert.match(node.detail,/部分能力可用/);
  assert.equal(node.environment.status,'partial');
  assert.equal(node.environment.coverage,'能力受限');
});

test('源码复制失败标明启动前失败，保留启动日志入口', (t) => {
  const {runDir,run}=fixture(t);
  fs.writeFileSync(`${runDir}.meta/wrapper.log`,'cp: cannot create directory: File exists\n');
  Object.assign(run,{state:'failed',isLive:false});
  const node=buildAgenticPipeline(run).nodes.find(item=>item.id==='orchestrator');
  assert.match(node.detail,/源码复制失败/);
  assert.equal(node.traces[0].id,'startup');
});

test('环境构建期间下游等待，忽略旧版预填的跳过状态', (t) => {
  const {runDir,run}=fixture(t);
  Object.assign(run,{state:'starting',visualStatus:'skipped',verifyAgentStatus:'skipped',redteamStatus:'skipped'});
  const result=buildAgenticPipeline(run);
  assert.equal(result.activeNode,'environment');
  assert.deepEqual(result.nodes.filter(n=>n.status==='running').map(n=>n.id),['environment']);
  assert.ok(result.nodes.slice(1).every(n=>n.status==='pending'));
  assert.match(result.nodes[1].detail,/等待环境构建/);
});

test('当前阶段推进后审计显示完成，不会持续运行到后续阶段', (t) => {
  const {runDir,run}=fixture(t);
  writeJson(`${runDir}.meta/env-phase.json`,{agent:{status:'ready'},final:{status:'ready'}});
  const report=path.join(runDir,'audit-report.json');writeJson(report,{findings:[]});
  Object.assign(run,{hasReport:true,reportPath:report,visualStatus:'skipped',verifyAgentStatus:'skipped',redteamStatus:'skipped'});
  writeJson(`${runDir}.meta/pipeline-stage.json`,{node:'visual'});
  let result=buildAgenticPipeline(run);
  assert.equal(result.nodes[1].status,'completed');
  assert.deepEqual(result.nodes.filter(n=>n.status==='running').map(n=>n.id),['visual']);
  assert.ok(result.nodes.slice(3).every(n=>n.status==='pending'));
  writeJson(`${runDir}.meta/pipeline-stage.json`,{node:'judge',candidate:'F-1'});
  result=buildAgenticPipeline(run);
  assert.deepEqual(result.nodes.filter(n=>n.status==='running').map(n=>n.id),['judge']);
  assert.match(result.nodes[6].detail,/F-1/);
  assert.equal(result.nodes[7].status,'pending');
});


test('环境构建中断的旧任务不会误报审计失败或后续已跳过', (t) => {
  const {runDir,run}=fixture(t);
  Object.assign(run,{state:'stopped',isLive:false,visualStatus:'skipped',verifyAgentStatus:'skipped',redteamStatus:'skipped'});
  fs.writeFileSync(`${runDir}.meta/env-phase0.log`,'环境构建开始');
  const result=buildAgenticPipeline(run);
  assert.equal(result.activeNode,null);
  assert.equal(result.nodes[0].status,'stopped');
  assert.ok(result.nodes.slice(1).every(n=>n.status==='not_started'));
  assert.match(result.notice,/环境构建阶段中断/);
});

test('审计阶段中断保留环境完成结果，后续不再显示等待', (t) => {
  const {runDir,run}=fixture(t);
  Object.assign(run,{state:'timeout',isLive:false});
  writeJson(`${runDir}.meta/pipeline-stage.json`,{node:'orchestrator'});
  writeJson(`${runDir}.meta/env-phase.json`,{agent:{status:'ready'},final:{status:'ready'}});
  const result=buildAgenticPipeline(run);
  assert.equal(result.nodes[0].status,'completed');
  assert.equal(result.nodes[1].status,'failed');
  assert.ok(result.nodes.slice(2).every(n=>n.status==='not_started'));
});

test('蓝队汇总存在也按受阻结果展示，红队缺少场景不算完成', (t) => {
  const { runDir, run } = fixture(t);
  Object.assign(run, { state: 'success', isLive: false });
  writeJson(path.join(runDir, 'verify/agent/summary.json'), {
    counts: { blocked: 4 }, processed: 4,
    findings: Array.from({ length: 4 }, () => ({ verdict: 'blocked' }))
  });
  writeJson(path.join(runDir, 'redteam/summary.json'), {
    results: Array.from({ length: 4 }, () => ({ status: 'blocked_no_finding' }))
  });
  let nodes = Object.fromEntries(buildAgenticPipeline(run).nodes.map((node) => [node.id, node]));
  assert.equal(nodes.verify.status, 'blocked');
  assert.equal(nodes['redteam-lab'].status, 'blocked');
  assert.equal(nodes['redteam-agent'].status, 'pending');
  writeJson(path.join(runDir, 'verify/agent/summary.json'), {
    status: 'partial', counts: { blocked: 1, confirmed: 1 }, processed: 2
  });
  nodes = Object.fromEntries(buildAgenticPipeline(run).nodes.map((node) => [node.id, node]));
  assert.equal(nodes.verify.status, 'degraded');
});

test('CPU 验收通过显示交付完成，并保留 GPU 限制与底层部分可用状态', (t) => {
 const {runDir,run}=fixture(t);
 writeJson(`${runDir}.meta/env-phase.json`, {agent:{status:'partial',exit_code:'0'},baseline:{status:'not_run'},
  final:{status:'partial',capabilities:{platform:{torch:'2.13.0+cpu'},acceptance:[{exit_code:0}],limitations:['GPU/CUDA 路径未验证']}}});
 const node=buildAgenticPipeline(run).nodes[0];
 assert.equal(node.status,'completed');
 assert.equal(node.environment.scope,'CPU 沙箱可用');
 assert.equal(node.environment.checksPassed,1);
 assert.deepEqual(node.environment.limitations,['GPU/CUDA 路径未验证']);
 assert.equal(node.environment.status,'partial');
});

test('备用方案、必要验收失败与不可用环境不冒充交付完成', (t) => {
 const {runDir,run}=fixture(t);
 for(const [phase,expected] of [
  [{agent:{status:'failed'},baseline:{status:'partial'},final:{status:'partial'}},'degraded'],
  [{agent:{status:'partial'},final:{status:'partial',capabilities:{acceptance:[{exit_code:1}]}}},'degraded'],
  [{agent:{status:'partial',exit_code:'1'},final:{status:'partial'}},'degraded'],
  [{agent:{status:'failed'},final:{status:'blocked'}},'blocked']
 ]) {
  writeJson(`${runDir}.meta/env-phase.json`,phase);
  assert.equal(buildAgenticPipeline(run).nodes[0].status,expected);
 }
});

test('可选能力验收失败保留限制，不改写必要验收已通过的交付', (t) => {
 const {runDir,run}=fixture(t);
 writeJson(`${runDir}.meta/env-phase.json`,{agent:{status:'partial'},final:{status:'partial',capabilities:{
  acceptance:[{exit_code:0},{exit_code:1,required:false}],limitations:['可选 GPU 验收未通过']}}});
 const node=buildAgenticPipeline(run).nodes[0];
 assert.equal(node.status,'completed');
 assert.equal(node.environment.checksFailed,0);
 assert.deepEqual(node.environment.limitations,['可选 GPU 验收未通过']);
});

test('旧运行只读取仍与本次环境绑定的清单，拒绝后来更新的说明', (t) => {
 const {root,runDir,run}=fixture(t);
 const manifest=path.join(root,'env/demo/env-manifest.json');
 const phase={project:'demo',source:'/source/demo',updated_at:'2026-11-04T04:00:00Z',manifest,
  agent:{status:'partial'},final:{status:'partial',image:'fixture:one'}};
 const value={project:'demo',source:'/source/demo',image:'fixture:one',platform:{torch:'2.13.0+cpu'},
  reuse_verification:{verified_at:'2026-11-04T03:59:00Z',checks:[{exit_code:0}]},limitations:['原环境 GPU 未验证']};
 writeJson(`${runDir}.meta/env-phase.json`,phase);writeJson(manifest,value);
 fs.utimesSync(manifest,new Date(value.reuse_verification.verified_at),new Date(value.reuse_verification.verified_at));
 assert.equal(buildAgenticPipeline(run).nodes[0].environment.scope,'CPU 沙箱可用');
 for(const change of [{image:'fixture:two'},{source:'/source/other'},{project:'other'},
  {reuse_verification:{verified_at:'2026-11-04T05:00:00Z'}}]) {
  writeJson(manifest,{...value,...change});
  const node=buildAgenticPipeline(run).nodes[0];
  assert.equal(node.environment.scope,'部分能力可用');
  assert.deepEqual(node.environment.limitations,[]);
 }
 writeJson(`${runDir}.meta/env-phase.json`,{...phase,final:{...phase.final,capabilities:{platform:{torch:'2.13.0+cpu'},limitations:['本次快照']}}});
 assert.deepEqual(buildAgenticPipeline(run).nodes[0].environment.limitations,['本次快照']);
});


test('蓝队最新批次候选数与日志数分开，部分受阻保留原因并明确重跑支持范围', t=>{
 const {runDir,run}=fixture(t);
 const root=`${runDir}.meta/node-retries/verify/latest`, workspace=path.join(root,'output');
 writeJson(path.join(root,'attempt.json'),{id:'latest',workspace,root,status:'completed',resultStatus:'degraded',startedAt:'2026-11-04T01:00:00Z',recovery:{kind:'aggregation-only'}});
 writeJson(path.join(workspace,'audit-report.json'),{findings:Array.from({length:30},(_,i)=>({id:`F-${i}`}))});
 writeJson(path.join(runDir,'verify/agent/summary.json'),{status:'blocked',counts:{blocked:4},processed:4});
 const findings=Array.from({length:4},(_,i)=>({finding_id:`F-${i}`,title:`候选 ${i}`,severity:'high',verdict:i===3?'blocked':'confirmed',reason:i===3?'验证智能体超时，未生成验证脚本':''}));
 writeJson(path.join(workspace,'verify/agent/summary.json'),{status:'partial',selected:4,processed:4,counts:{confirmed:3,blocked:1},findings});
 fs.writeFileSync(path.join(root,'worker.log'),'批次记录');
 for(let i=0;i<4;i++)for(const kind of ['agent','runner']) {
  const file=path.join(workspace,`verify/agent/logs/F-${i}.${kind}.log`);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,'执行记录');
 }
 const nodes=Object.fromEntries(buildAgenticPipeline(run).nodes.map(n=>[n.id,n]));
 assert.equal(nodes.verify.traces.length,9);
 assert.equal(nodes.verify.verification.selectedCount,4);
 assert.equal(nodes.verify.verification.processedCount,4);
 assert.equal(nodes.verify.verification.reportTotal,30);
 assert.deepEqual(nodes.verify.verification.counts,{confirmed:3,rejected:0,inconclusive:0,blocked:1});
 assert.equal(nodes.verify.status,'degraded');assert.equal(nodes.verify.statusLabel,'部分受阻');
 assert.match(nodes.verify.candidateSummary,/确认 3.*受阻 1/);
 assert.match(nodes.verify.detail,/F-3：验证智能体超时/);
 assert.match(nodes.verify.recoveryNotice,/汇总已恢复/);
 assert.equal(nodes.verify.retrySupported,true);
 assert.equal(nodes.visual.retrySupported,true);
 assert.equal(nodes['redteam-lab'].retrySupported,true);
 assert.equal(nodes['redteam-agent'].retrySupported,true);
 assert.equal(nodes.judge.retrySupported,true);
 assert.match(nodes.judge.retryReason,/项目正在运行/);
});

test('经验学习读取阶段技能与 SkillOpt 候选，不伪造发布', (t) => {
  const { runDir, run } = fixture(t);
  run.isLive = false;
  writeJson(path.join(runDir, 'rsi/post-validation.json'), { status: 'completed', candidates: 0 });
  writeJson(path.join(runDir, 'rsi/stage-learning-run.json'), {
    exit_code: 0,
    skillopt_candidates: 1,
    skillopt: { status: 'candidate', requests: 1, candidates: ['candidate-1'] }
  });
  const node = buildAgenticPipeline(run).nodes.find((item) => item.id === 'learner');
  assert.match(node.detail, /阶段技能候选 1/);
  assert.doesNotMatch(node.detail, /已发布/);
});

test('运行修复标记仅在当前任务活动时生效，健康检查不显示', t => {
 const {runDir,run}=fixture(t);
 const file=path.join(runDir,'redteam/batch/runner-repair/runner-repair.json');
 writeJson(file,{status:'repairing',missing_modules:['openai']});
 let node=buildAgenticPipeline(run).nodes.find(n=>n.id==='redteam-agent');
 assert.equal(node.repair.active,true);
 assert.deepEqual(node.repair.missingModules,['openai']);
 assert.ok(node.repair.traceId);
 run.isLive=false;
 node=buildAgenticPipeline(run).nodes.find(n=>n.id==='redteam-agent');
 assert.equal(node.repair.active,false);
 assert.equal(node.repair.status,'interrupted');
 writeJson(file,{status:'ready',repaired:true,missing_modules:['openai']});
 node=buildAgenticPipeline(run).nodes.find(n=>n.id==='redteam-agent');
 assert.equal(node.repair.status,'ready');
 assert.equal(node.repair.active,false);
 writeJson(file,{status:'ready',repaired:false});
 assert.equal(buildAgenticPipeline(run).nodes.find(n=>n.id==='redteam-agent').repair,null);
});


test('原生工作流状态覆盖历史完成结果，并明确显示待执行节点',t=>{
 const {runDir,run}=fixture(t);
 Object.assign(run,{state:'success',isLive:false});
 writeJson(runDir+'.meta/workflows/one/state.json',{id:'one',startedAt:'2026-11-05',status:'running',current:'redteam-agent',steps:['redteam-agent','judge','learner'],receipts:[]});
 const data=buildAgenticPipeline(run);
 assert.equal(data.workflow.status,'running');assert.equal(data.activeNode,'redteam-agent');
 assert.equal(data.nodes.find(n=>n.id==='redteam-agent').status,'running');
 assert.equal(data.nodes.find(n=>n.id==='learner').status,'pending');
 assert.equal(data.nodes.find(n=>n.id==='judge').retryReason,'项目工作流正在运行');
});


test('01构建期间只提供独立调度入口，02—08没有执行轨迹',t=>{
 const {runDir,run}=fixture(t);
 writeJson(runDir+'.meta/workflows/one/state.json',{id:'one',startedAt:'2026-11-05',status:'running',current:'environment',steps:['environment','orchestrator','visual','verify','redteam-lab','redteam-agent','judge','learner'],receipts:[]});
 fs.writeFileSync(runDir+'.meta/workflows/one/raw.jsonl',JSON.stringify({type:'system',subtype:'init'})+'\n');
 const data=buildAgenticPipeline(run);
 assert.equal(data.workflow.traces.length,1);
 for(const node of data.nodes.slice(1)){assert.equal(node.status,'pending');assert.equal(node.traces.length,0,node.id);}
});
