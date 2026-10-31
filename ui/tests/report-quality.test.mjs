import assert from 'node:assert/strict';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { reportQuality } from '../server/report-quality.mjs';

const good = {title: '未认证的控制接口', root_cause: '缺少认证', impact: '拒绝服务',
  reproduction: '本地运行测试', remediation: '增加认证', evidence: ['app.py:10']};

const cases = [good, {}, null, 5,
  {...good, title: '', description: '不能代替标题'},
  {...good, title: 'Missing authorization'},
  {...good, evidence: [' ', null, {}]},
  {...good, evidence: [{path: 'app.py', line: 1}]},
  {...good, evidence: [{snippet: 'danger()'}]},
  {...good, impact: [false, 5, {}]},
  {...good, reproduction: '', verification: {steps: ['第一步', '第二步']}},
  {...good, remediation: '', fix: '增加认证'}];

for (const language of ['zh', 'en']) {
  test(`Python and web report contract agree (${language})`, () => {
    const script = `import json,sys; sys.path.insert(0, 'scripts/workflow'); import report_quality; print(json.dumps([report_quality.quality_of(v, '${language}') for v in json.load(sys.stdin)]))`;
    const child = spawnSync(process.env.PYTHON || 'python3', ['-c', script], {
      cwd: new URL('../..', import.meta.url), input: JSON.stringify(cases), encoding: 'utf8'
    });
    assert.equal(child.status, 0, child.stderr);
    assert.deepEqual(cases.map(raw => reportQuality(raw, language)), JSON.parse(child.stdout));
  });
}

test('display fallbacks cannot satisfy an absent required title', () => {
  assert.ok(reportQuality({...good, title: '', type: '认证问题'}).missing.includes('title'));
});
