import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {rsiRewards} from "../server/rsi-rewards.mjs";

test("两项奖励历史按项目与轮次读取，旧公式不混入",()=>{
  const repo=fs.mkdtempSync(path.join(os.tmpdir(),"rsi-rewards-"));
  try {
    const root=path.join(repo,"rsi/exploration/demo");fs.mkdirSync(root,{recursive:true});
    const row=(project,run_id,updated_at)=>({formula_version:"rsi-two-signal-v1",project,run_id,updated_at,total:10.15});
    fs.writeFileSync(path.join(root,"state.json"),JSON.stringify({rounds:{
      one:{result:{objective:row("demo","one","2026-11-07")}},
      two:{result:{objective:row("demo","two","2026-11-08")}},
      other:{result:{objective:row("other","wrong","2026-11-09")}},
      old:{result:{reward:11.1}}
    }}));
    const result=rsiRewards(repo,"demo","one");
    assert.equal(result.current.run_id,"one");
    assert.deepEqual(result.history.map(x=>x.run_id),["two","one"]);
    assert.equal(rsiRewards(repo,"demo","absent").current,null);
    assert.deepEqual(rsiRewards(repo,"missing","one"),{current:null,history:[]});
  } finally {fs.rmSync(repo,{recursive:true,force:true});}
});
