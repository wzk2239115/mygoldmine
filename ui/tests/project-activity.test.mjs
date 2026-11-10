
import test from 'node:test';
import assert from 'node:assert/strict';
import {projectActivity} from '../server/project-activity.mjs';
test('排队项目显示静态等待状态与队列位置',()=>{
 const rows=[{project:'demo',status:'queued',file:'state'}];
 assert.deepEqual(projectActivity('demo',true,rows,()=>({admission:{status:'queued',position:11}})),
 {status:'queued',label:'排队中',position:11});
});
test('运行优先于同项目排队任务，空闲项目不显示动画',()=>{
 const rows=[{project:'demo',status:'queued'},{project:'demo',status:'active'}];
 assert.equal(projectActivity('demo',true,rows).status,'running');
 assert.equal(projectActivity('other',false,rows).status,'idle');
});

test('后半段运行名额不受旧 isLive 影响，排队不计运行数量',async()=>{
 const {projectIsBusy,runningProjectCount}=await import('../src/project-activity.js');
 const projects=Array.from({length:15},(_,i)=>({id:'p'+i,isLive:i<2,activity:{status:'running'}}));
 projects.push({id:'queued',isLive:true,activity:{status:'queued'}});
 assert.equal(runningProjectCount({projects}),15);
 assert.ok(projects.every(projectIsBusy));
 assert.equal(projectIsBusy({isLive:true,activity:{status:'idle'}}),false);
});
