import test from 'node:test';
import assert from 'node:assert/strict';
import {executeProcess} from '../server/project-import.mjs';

test('持续输出可超过空闲时限；无输出任务会停止', async () => {
  const outputs=[];
  const result=await executeProcess(process.execPath,['-e',"let n=0; const t=setInterval(()=>{console.log(++n);if(n===8)clearInterval(t)},80)"],{timeout:0,idleTimeout:400,onOutput:x=>outputs.push(x)});
  assert.equal(result.code,0); assert.ok(outputs.length>1);
  await assert.rejects(executeProcess(process.execPath,['-e','setTimeout(()=>{},10000)'],{timeout:0,idleTimeout:150}), /没有收到下载输出/);
});
