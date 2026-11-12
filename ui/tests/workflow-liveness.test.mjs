import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { activeWorkflow } from '../server/workflow-liveness.mjs';

test('a live owned workflow keeps its run active after an intermediate status says success', () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'workflow-live-'));
  try {
    const project = 'sample';
    const runDir = path.join(repo, 'runs', project, 'run-1');
    const lock = path.join(repo, 'runs', `.node-retry-${project}.lock`);
    const file = path.join(runDir + '.meta', 'workflows', 'workflow-1', 'state.json');
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.mkdirSync(lock, { recursive: true });
    const state = { id: 'workflow-1', project, runDir, lock, status: 'running', coordinatorPid: 12345 };
    fs.writeFileSync(file, JSON.stringify(state));
    fs.writeFileSync(path.join(lock, 'workflow-owner.json'), JSON.stringify({ id: state.id, file }));
    assert.deepEqual(activeWorkflow(runDir, project, pid => pid === 12345), state);
    assert.equal(activeWorkflow(runDir, project, () => false), null);
    assert.equal(activeWorkflow(path.join(repo, 'runs', project, 'run-2'), project, () => true), null);

    fs.writeFileSync(file, JSON.stringify({ ...state, status: 'completed' }));
    assert.equal(activeWorkflow(runDir, project, () => true), null);
    fs.writeFileSync(file, JSON.stringify({ ...state, project: 'other' }));
    assert.equal(activeWorkflow(runDir, project, () => true), null);
  } finally {
    fs.rmSync(repo, { recursive: true, force: true });
  }
});

test('an active recovered run can use the original workflow state file', () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'workflow-recovery-live-'));
  try {
    const project = 'sample';
    const source = path.join(repo, 'runs', project, 'learning-5');
    const runDir = source + '-recovery';
    const lock = path.join(repo, 'runs', `.node-retry-${project}.lock`);
    const file = path.join(source + '.meta', 'workflows', 'workflow-1', 'state.json');
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.mkdirSync(lock, { recursive: true });
    const state = { id: 'workflow-1', project, runDir, recoveredFrom: source, lock, status: 'running', coordinatorPid: 12345 };
    fs.writeFileSync(file, JSON.stringify(state));
    fs.writeFileSync(path.join(lock, 'workflow-owner.json'), JSON.stringify({ id: state.id, file }));
    assert.deepEqual(activeWorkflow(runDir, project, pid => pid === 12345), state);
    fs.writeFileSync(file, JSON.stringify({ ...state, recoveredFrom: path.join(repo, 'elsewhere') }));
    assert.equal(activeWorkflow(runDir, project, () => true), null);
  } finally {
    fs.rmSync(repo, { recursive: true, force: true });
  }
});
