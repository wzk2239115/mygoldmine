import test from 'node:test';
import assert from 'node:assert/strict';
import {createCcuiCache} from '../src/ccui-cache.js';
import {sessionMatchesTrace} from '../server/ccui-cache.mjs';

const result = id => ({available:true,reachable:true,sessionId:id,importedAt:id});

test('悬停准备和打开面板合并请求，重复打开复用缓存',async()=>{
 let calls=0,resolve;
 const cache=createCcuiCache(()=>{calls++;return new Promise(r=>{resolve=r;});});
 const options={node:'environment',trace:'round-1',version:'one'};
 const first=cache.load('demo','run',options);
 assert.equal(first,cache.load('demo','run',options));
 await Promise.resolve();resolve(result('one'));
 assert.equal((await first).sessionId,'one');
 assert.equal(cache.peek('demo','run',options).sessionId,'one');
 assert.equal((await cache.load('demo','run',options)).sessionId,'one');
 assert.equal(calls,1);
});

test('缓存隔离项目、运行、节点和调用，版本变化、过期或主动同步重新读取',async()=>{
 let calls=0,time=0;
 const cache=createCcuiCache(async()=>result(String(++calls)),{now:()=>time,ttl:100});
 const options={node:'verify',trace:'one',version:'a'};
 await cache.load('demo','run',options);
 for(const [project,run,opts] of [['other','run',options],['demo','other',options],
  ['demo','run',{...options,node:'environment'}],['demo','run',{...options,trace:'two'}],
  ['demo','run',{...options,version:'b'}]]) {
  assert.equal(cache.peek(project,run,opts),null);await cache.load(project,run,opts);
 }
 assert.equal(calls,6);
 await cache.load('demo','run',{...options,version:'b',force:true});assert.equal(calls,7);
 await cache.load('demo','run',{...options,version:'b',refresh:true});assert.equal(calls,8);
 time=101;assert.equal(cache.peek('demo','run',{...options,version:'b'}),null);
 await cache.load('demo','run',{...options,version:'b'});assert.equal(calls,9);
});

test('失败和离线响应不固化为缓存，较旧的并发响应不覆盖新版本',async()=>{
 let fail=true;
 const cache=createCcuiCache(async()=>{if(fail)throw Error('offline');return result('ok');});
 await assert.rejects(cache.load('demo','run'),/offline/);fail=false;
 assert.equal((await cache.load('demo','run')).sessionId,'ok');
 const resolvers=[];
 const race=createCcuiCache(()=>new Promise(r=>resolvers.push(r)));
 const old=race.load('demo','run',{version:'old'});
 const fresh=race.load('demo','run',{version:'new'});
 await Promise.resolve();resolvers[1](result('new'));await fresh;
 resolvers[0](result('old'));await old;
 assert.equal(race.peek('demo','run',{version:'new'}).sessionId,'new');
 const unavailable=createCcuiCache(async()=>({available:true,reachable:false}));
 await unavailable.load('demo','run');assert.equal(unavailable.peek('demo','run'),null);
});

test('缓存达到容量后淘汰旧记录',async()=>{
 const cache=createCcuiCache(async(p,r)=>result(r),{limit:2});
 for(const id of ['one','two','three'])await cache.load('demo',id);
 assert.equal(cache.peek('demo','one'),null);
 assert.equal(cache.peek('demo','three').sessionId,'three');
});

test('轨迹按源文件版本复用，未来时间戳不会导致反复转换',()=>{
 const stat={size:12n,mtimeNs:9999999999999999999n};
 const session={sourceFile:'/trace',sourceSize:12,sourceMtimeNs:String(stat.mtimeNs),importedAt:'2026-01-01'};
 assert.equal(sessionMatchesTrace(session,'/trace',stat),true);
 assert.equal(sessionMatchesTrace(session,'/other',stat),false);
 assert.equal(sessionMatchesTrace(session,'/trace',{...stat,size:13n}),false);
 assert.equal(sessionMatchesTrace(session,'/trace',{...stat,mtimeNs:stat.mtimeNs+1n}),false);
 assert.equal(sessionMatchesTrace({importedAt:'2026-01-01'},'/trace',{size:1n,mtimeNs:1n}),true);
});
