import assert from 'node:assert/strict';
import test from 'node:test';
import {summarizeRecovery} from '../server/recovery-status.mjs';

test('recovery summary separates reused work from the retried task', () => {
  assert.deepEqual(summarizeRecovery({
    config: {status:'reused', prompt:'private context'},
    filesystem: {status:'running', description:'filesystem', attempts:[{status:'failed'}, {status:'running'}]}
  }), {total:2,reused:1,completed:0,failed:0,active:'filesystem',attempt:2});
});
test('partial failures are visible without exposing prompts or logs', () => {
  const result = summarizeRecovery({a:{status:'completed'},b:{status:'failed',prompt:'private'}});
  assert.equal(result.failed,1);
  assert.equal(result.completed,1);
  assert.equal(result.active,null);
  assert.ok(!JSON.stringify(result).includes('private'));
});
test('ordinary runs have no recovery banner', () => {
  assert.equal(summarizeRecovery(undefined),null);
  assert.equal(summarizeRecovery({}),null);
});
