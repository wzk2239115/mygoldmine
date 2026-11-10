import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {coverageTokens} from "../server/coverage-tokens.mjs";
test("跨轮覆盖去重、缓存用量口径、未知数据和源码版本分组",()=>{
 const repo=fs.mkdtempSync(path.join(os.tmpdir(),"cov-tokens-"));
 const write=(file,data)=>{const p=path.join(repo,file);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(data));};
 try{
  for(const [i,start,end,version] of [[1,1,10,"v1"],[2,6,20,"v1"],[3,21,30,"v1"],[4,1,10,"v2"]]){
   write(`runs/demo/r${i}/task-artifacts/read-coverage/summary.json`,{source_version:version,files:[{kind:"read",file:"a.py",file_sha256:"sha",ranges:[{start,end}]}]});
   write(`runs/demo/r${i}.meta/status.json`,{started_at:`2026-11-09T00:00:0${i}Z`});
   write(`runs/demo/r${i}/triage/jev-infra.json`,{units:[{path:"a.py",line_start:1,line_end:30,priority:1}]});
  }
  const group=(id,provider)=>({project:"demo",run_id:id,stage:"orchestrator",provider_convention:provider,totals:{input_tokens:100,output_tokens:20,cache_read_input_tokens:80,cache_creation_input_tokens:0},missing_fields:{},unknown_usage:0});
  write(".runtime/state/token-usage/summary.json",{groups:[group("r1","claude_reported_categories"),group("r2","openai_prompt_includes_cache"),group("r4","claude_reported_categories"),{...group("r1","claude_reported_categories"),stage:"verify"}]});
  const result=coverageTokens(repo,"demo",{fresh:true});
  assert.equal(result.series.length,2);
  const p=result.series[0].points;
  assert.deepEqual(p.map(x=>x.lines),[10,20,30]);
  assert.deepEqual(p.map(x=>x.weighted_lines),[20,40,60]);
  assert.deepEqual(p.map(x=>x.tokens),[200,320,320]);
  assert.equal(p[2].run_tokens,null);assert.equal(p[2].partial,true);
  assert.equal(result.series[1].points[0].lines,10);
 }finally{fs.rmSync(repo,{recursive:true,force:true});}
});
