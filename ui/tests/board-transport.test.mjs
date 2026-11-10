
import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {gunzipSync} from 'node:zlib';
import {summarizeBoard,sendJsonResponse} from '../server/board-transport.mjs';
test('列表保留筛选与证据数量，报告正文不提前下发',()=>{
 const finding={key:'a',title:'title',rootCause:'需要全文搜索的根因',notes:'备注',
  stageResults:{blue:{reason:'long'}},evidence:['one','two'],reproduction:'步骤'};
 const board={findings:[finding]};
 const summary=summarizeBoard(board);
 assert.equal(summary.findings[0].evidenceCount,2);
 assert.ok(summary.findings[0].searchText.includes(finding.rootCause));
 assert.equal(summary.findings[0].rootCause,undefined);
 assert.equal(summary.findings[0].stageResults,undefined);
 assert.equal(board.findings[0].reproduction,'步骤');
});
test('大响应支持gzip，禁用gzip的客户端仍可读取原JSON',async t=>{
 const payload={text:'测试压缩'.repeat(5000)};
 const server=http.createServer((req,res)=>sendJsonResponse(res,200,payload));
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 t.after(()=>new Promise(resolve=>server.close(resolve)));
 async function get(encoding){
  return new Promise((resolve,reject)=>{
   http.get({host:'127.0.0.1',port:server.address().port,headers:{'Accept-Encoding':encoding}},response=>{
    const chunks=[];response.on('data',chunk=>chunks.push(chunk));
    response.on('end',()=>resolve({headers:response.headers,body:Buffer.concat(chunks)}));
   }).on('error',reject);
  });
 }
 const compressed=await get('gzip');
 assert.equal(compressed.headers['content-encoding'],'gzip');
 assert.deepEqual(JSON.parse(gunzipSync(compressed.body)),payload);
 assert.equal(compressed.headers.vary,'Accept-Encoding');
 const plain=await get('gzip;q=0, identity');
 assert.equal(plain.headers['content-encoding'],undefined);
 assert.deepEqual(JSON.parse(plain.body),payload);
 assert.ok(compressed.body.length<plain.body.length/10);
});
