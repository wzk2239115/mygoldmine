import test from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../src/api.js';

test('导入状态处理拆分的数据块、成功、错误和连接中断', async () => {
  const original = globalThis.fetch;
  const mock = (events) => {
    const bytes = new TextEncoder().encode(events.map(x => JSON.stringify(x)).join('\n'));
    globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) {
      for (let i=0; i<bytes.length; i+=7) controller.enqueue(bytes.slice(i,i+7));
      controller.close();
    }}));
  };
  try {
    mock([{type:'info',message:'正在下载仓库'}, {type:'heartbeat'}, {type:'result',result:{ok:true}}]);
    const messages=[];
    assert.deepEqual(await api.importWithProgress({}, x=>messages.push(x.message)), {ok:true});
    assert.deepEqual(messages,['正在下载仓库']);
    mock([{type:'info',message:'正在检查'}, {type:'error',message:'目录不可读取'}]);
    await assert.rejects(api.importWithProgress({},()=>{}), /目录不可读取/);
    mock([{type:'heartbeat'}]);
    await assert.rejects(api.importWithProgress({},()=>{}), /连接已中断/);
  } finally { globalThis.fetch=original; }
});
