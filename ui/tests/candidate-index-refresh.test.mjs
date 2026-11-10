
import test from 'node:test';
import assert from 'node:assert/strict';
import {candidateIndexResult} from '../server/claude-workflows.mjs';
test('索引超时返回降级信息，不向工作流抛出异常',async()=>{
 assert.deepEqual(await candidateIndexResult(async()=>{throw Error('节点执行超过时限');}),
 {code:1,error:'节点执行超过时限'});
});
test('保留索引正常完成及非零退出状态',async()=>{
 assert.deepEqual(await candidateIndexResult(async()=>0),{code:0});
 assert.deepEqual(await candidateIndexResult(async()=>2),{code:2});
});
