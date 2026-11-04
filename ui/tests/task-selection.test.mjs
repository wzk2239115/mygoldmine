import test from 'node:test';
import assert from 'node:assert/strict';
import {initialTaskSelection, resolveTaskSelection, taskStateLabel} from '../src/task-selection.js';
for (const field of ['verification','construction']) test(`${field} 候选选择在并发刷新时保持身份，排队项不显示其他会话`, () => {
  const tasks=[{id:'F-1',traceId:'new-1',state:'running',label:'构建中'},{id:'F-2',traceId:'new-2',state:'queued',label:'排队'}];
  const node={[field]:{attemptId:'new',tasks}};
  const traces=[{id:'old-2'},{id:'new-1'}];
  const first=initialTaskSelection(node);
  assert.equal(first.taskId,'F-1');
  const waiting={batchId:'new',taskId:'F-2',history:false};
  assert.equal(resolveTaskSelection(node,traces,waiting).trace,null);
  assert.equal(resolveTaskSelection(node,traces,waiting).task.id,'F-2');
  tasks[1].state='running';
  assert.equal(resolveTaskSelection(node,[...traces,{id:'new-2'}],waiting).trace.id,'new-2');
  tasks[1].state='completed';tasks[1].label='受阻';
  assert.equal(resolveTaskSelection(node,traces,waiting).task.id,'F-2');
  assert.equal(taskStateLabel(tasks[1]),'已结束 · 受阻');
  assert.equal(taskStateLabel({state:'queued'}),'待运行');
  const history=resolveTaskSelection(node,traces,{batchId:'new',history:true,traceId:'old-2'});
  assert.equal(history.task,null);assert.equal(history.trace.id,'old-2');
  const next=resolveTaskSelection({...node,[field]:{attemptId:'next',tasks:[{id:'F-2',state:'queued',traceId:'next-2'}]}},traces,waiting);
  assert.equal(next.task.id,'F-2');assert.equal(next.trace,null);
});
test('普通节点仍可选择新重跑日志', () => {
  const node={id:'scene'};
  const selection={...initialTaskSelection(node),history:true,traceId:'new-worker'};
  assert.equal(resolveTaskSelection(node,[{id:'old'},{id:'new-worker'}],selection).trace.id,'new-worker');
});
