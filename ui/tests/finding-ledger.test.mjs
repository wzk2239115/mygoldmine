import test from 'node:test';
import assert from 'node:assert/strict';
import {
  isVerified,
  latestOccurrences,
  stateForFinding
} from '../server/finding-ledger.mjs';

function fixtureLedger() {
  const first = {
    occurrence_id: 'p/r1/F-1', semantic_id: 'sem-history', project: 'p', run_id: 'r1',
    finding_id: 'F-1', local_id: 'F-1', legacy_key: 'p:F-1'
  };
  const second = {
    occurrence_id: 'p/r2/F-1', semantic_id: 'sem-other', project: 'p', run_id: 'r2',
    finding_id: 'F-1', local_id: 'F-1', legacy_key: 'p:F-1'
  };
  return {
    schema_version: 2,
    findings: {
      'sem-history': { latest_occurrence_id: first.occurrence_id },
      'sem-other': { latest_occurrence_id: second.occurrence_id }
    },
    occurrences: { [first.occurrence_id]: first, [second.occurrence_id]: second },
    indexes: {
      legacy_to_semantics: { 'p:F-1': ['sem-history', 'sem-other'] },
      legacy_to_occurrences: { 'p:F-1': [first.occurrence_id, second.occurrence_id] }
    },
    latest_by_project: {}
  };
}

test('strict verified rejects unverified, prose, and unknown verdicts', () => {
  assert.equal(isVerified({ verified: 'true' }), false);
  assert.equal(isVerified({ verified: true, verdict: 'unverified' }), false);
  assert.equal(isVerified({ verification: 'verified in prose' }), false);
  assert.equal(isVerified({ verdict: 'needs-review' }), false);
  assert.equal(isVerified({ verdict: 'confirmed' }), true);
});

test('latest occurrences retain distinct historical semantics', () => {
  const ledger = fixtureLedger();
  assert.deepEqual(
    latestOccurrences(ledger).map((item) => item.occurrence_id).sort(),
    ['p/r1/F-1', 'p/r2/F-1']
  );
});

test('ambiguous legacy project:id state is not applied to either semantic', () => {
  const ledger = fixtureLedger();
  const finding = { ...ledger.occurrences['p/r1/F-1'], id: 'F-1' };
  assert.deepEqual(stateForFinding(finding, { 'p:F-1': { status: 'closed' } }, ledger), {});
});

test('specific occurrence state overrides semantic and unambiguous legacy state', () => {
  const ledger = fixtureLedger();
  ledger.indexes.legacy_to_semantics['p:F-1'] = ['sem-history'];
  const finding = { ...ledger.occurrences['p/r1/F-1'], id: 'F-1' };
  const states = {
    'p:F-1': { status: 'triage', notes: 'legacy' },
    'sem-history': { status: 'reproduce', notes: 'semantic' },
    'p/r1/F-1': { status: 'closed' }
  };
  assert.deepEqual(stateForFinding(finding, states, ledger), {
    status: 'closed', notes: 'semantic'
  });
});

test('old project:id state remains readable without a v2 ledger', () => {
  const finding = { project: 'p', id: 'f-1', finding_id: 'f-1' };
  assert.deepEqual(stateForFinding(finding, { 'p:F-1': { status: 'triage' } }, {}), {
    status: 'triage'
  });
  assert.deepEqual(stateForFinding(finding, { 'p:f-1': { status: 'closed' } }, {}), {
    status: 'closed'
  });
});
