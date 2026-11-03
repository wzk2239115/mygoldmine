import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { listAgenticTraces, resolveAgenticTrace } from '../server/agentic-traces.mjs';

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
