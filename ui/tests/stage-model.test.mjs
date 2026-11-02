import test from 'node:test';
import assert from 'node:assert/strict';
import { filterStageFindings, stageCount, stageMeta } from '../src/stage-model.js';

const stats = {
  status: { inbox: 1, triage: 2, reproduce: 1, cve: 1, closed: 1, archived: 722 },
  reviewReady: 1
};

const findings = [
  { key: 'p:raw', id: 'RAW', status: 'inbox', reviewReady: false },
  { key: 'p:archived', id: 'ARC', status: 'archived', reviewReady: false },
  { key: 'p:triage-a', id: 'T1', status: 'triage', reviewReady: false },
  { key: 'p:triage-b', id: 'T2', status: 'triage', reviewReady: false },
  { key: 'p:repro', id: 'R1', status: 'reproduce', reviewReady: false },
  { key: 'p:cve', id: 'C1', status: 'cve', reviewReady: false },
  { key: 'p:closed', id: 'X1', status: 'closed', reviewReady: false },
  { key: 'p:review', id: 'V1', status: 'triage', reviewReady: true }
];

test('raw stage count is inbox only, archived is not expanded', () => {
  assert.equal(stageCount(stats, 'raw'), 1);
  assert.equal(stageCount(stats, 'review'), 1);
  assert.equal(stageCount(stats, 'triage'), 2);
});

test('raw stage filters only inbox', () => {
  const result = filterStageFindings(findings, 'raw');
  assert.deepEqual(result.map((item) => item.id), ['RAW']);
});

test('reviewReady findings move to review and leave their status column', () => {
  const review = filterStageFindings(findings, 'review');
  const triage = filterStageFindings(findings, 'triage');
  assert.deepEqual(review.map((item) => item.id), ['V1']);
  assert.deepEqual(triage.map((item) => item.id), ['T1', 'T2']);
});

test('every non-archived stage count matches its filtered list', () => {
  for (const stage of ['raw', 'triage', 'reproduce', 'cve', 'closed', 'review']) {
    assert.equal(filterStageFindings(findings, stage).length, stageCount(stats, stage), stage);
  }
});

test('stage metadata falls back safely', () => {
  assert.equal(stageMeta('raw').label, '未处理候选');
  assert.equal(stageMeta('unknown').id, 'raw');
});
