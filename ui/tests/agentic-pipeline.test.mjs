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
