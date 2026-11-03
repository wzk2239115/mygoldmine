import test from 'node:test';
import assert from 'node:assert/strict';
import {createCcuiService} from '../server/ccui-service.mjs';

test('已有服务直接复用，离线时并发请求只启动一次',async()=>{
 let online=false,starts=0;
 const service=createCcuiService({url:'http://127.0.0.1:3001',health:async()=>online,launch:async()=>{starts++;online=true;},wait:async()=>{},attempts:2});
 assert.deepEqual(await Promise.all([service.ensure(),service.ensure()]),[true,true]);
 assert.equal(starts,1);assert.equal(await service.ensure(),true);assert.equal(starts,1);
});

test('启动失败可重试，自定义远程地址不自动启动',async()=>{
 let starts=0;
 const config={url:'http://127.0.0.1:3001',health:async()=>false,launch:async()=>{starts++;},wait:async()=>{},attempts:1};
 const local=createCcuiService(config);
 assert.equal(await local.ensure(),false);assert.equal(await local.ensure(),false);assert.equal(starts,2);
 assert.equal(await createCcuiService({...config,url:'https://example.com'}).ensure(),false);assert.equal(starts,2);
});
