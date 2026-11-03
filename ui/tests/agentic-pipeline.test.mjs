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
  assert.equal(result.nodes[1].status, 'running');
  assert.ok(result.nodes.slice(2).every((node) => node.status === 'pending'));
});
