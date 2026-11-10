import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const helper=fileURLToPath(new URL('../../scripts/workflow/delivery_contract.py',import.meta.url));
function contract(action,args=[],input='') {
 const result=spawnSync(process.env.PYTHON || 'python3',[helper,action,...args],{input,encoding:'utf8',timeout:120000,maxBuffer:32*1024*1024});
 if(result.error || result.status!==0)throw Object.assign(new Error(result.error?.message || result.stderr.trim() || '交付契约检查失败'),{code:'artifact_contract'});
 return JSON.parse(result.stdout);
}
export function reportProject(report,expected) {
 try{return contract('project',expected?['--expected',expected]:[],JSON.stringify(report)).project;}
 catch(error){error.code='artifact_project_identity';throw error;}
}
export function runtimeEnvironment(directory) {
 if(!fs.existsSync(path.join(directory,'pyvenv.cfg')))return null;
 return contract('runtime',['--path',directory]);
}
export function verificationAttachments(file,boundary) {
 return contract('verification',['--path',file,'--boundary',boundary]);
}

export function acceptedStageDelivery(stage,root,minimum=1,allowPartial=false) {
 const helper=fileURLToPath(new URL('../../scripts/stages/submission.py',import.meta.url));
 const result=spawnSync(process.env.PYTHON || 'python3',[helper,stage==='orchestrator'?'finalize':'check','--stage',stage,'--root',root,'--minimum',String(minimum),...(allowPartial?['--allow-partial']:[])],{encoding:'utf8',timeout:120000,maxBuffer:8*1024*1024});
 if(result.error || result.status!==0)throw Object.assign(new Error(result.error?.message || result.stderr.trim() || '阶段没有有效的交付回执'),{code:'stage_delivery_rejected'});
 return JSON.parse(result.stdout);
}

// Illustrations are optional presentation artifacts, never verification evidence.
export function optionalVisualDelivery(root,minimum=1) {
 const delivery=acceptedStageDelivery('visual',root,minimum>0?1:0,true);
 return {...delivery,optional:delivery.excluded.length>0,
  notices:delivery.excluded.length?['部分攻击设计未交付，保留有效成员继续。']:[]};
}
