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

test('部分可用的环境不能显示完整完成', (t) => {
  const {runDir,run}=fixture(t);
  writeJson(`${runDir}.meta/env-phase.json`,{agent:{status:'partial'},final:{status:'partial'}});
  const node=buildAgenticPipeline(run).nodes.find(item=>item.id==='environment');
  assert.equal(node.status,'degraded');
  assert.match(node.detail,/部分可用/);
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
