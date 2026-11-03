import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

export const MODEL_ROLES = ['audit','environment','visual','verify','redteam','judge'];
const read = file => {try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return {};}};
export function createModelSettings({repoRoot,env=process.env,providerFile=path.join(os.homedir(),'.config/opencode/opencode.json')}) {
  const file=path.join(repoRoot,'config/stage-models.json');
  const defaults={audit:env.MODEL || '360-proxy/deepseek/deepseek-v4.1-flash',environment:env.ENV_MODEL || '',visual:env.VISUAL_MODEL || '',verify:env.VERIFY_MODEL || '',redteam:env.REDTEAM_MODEL || '',judge:env.JUDGE_MODEL || ''};
  function get() {
    const saved=read(file);
    const models=Object.fromEntries(MODEL_ROLES.map(role=>[role,typeof saved[role]==='string'?saved[role]:defaults[role]]));
    const choices=new Set(Object.values(models).filter(Boolean));
    for(const [provider,config] of Object.entries(read(providerFile).provider || {})) {
      for(const model of Object.keys(config.models || {})) choices.add(`${provider}/${model}`);
    }
    return {models,choices:[...choices],configured:fs.existsSync(file)};
  }
  function save(input) {
    const models={};
    for(const role of MODEL_ROLES) {
      const value=input?.[role];
      if(typeof value!=='string' || value.length>200 || (value && !/^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$/.test(value)) || (!value && role==='audit')) {
        const error=new Error('请选择或填写有效的模型名称');error.status=400;throw error;
      }
      models[role]=value;
    }
    fs.mkdirSync(path.dirname(file),{recursive:true});
    const temp=`${file}.${process.pid}.tmp`;
    fs.writeFileSync(temp,JSON.stringify(models,null,2)+'\n',{mode:0o600});fs.renameSync(temp,file);
    return get();
  }
  function args() {
    const {models,configured}=get();if(!configured)return [];
    const effective=Object.fromEntries(MODEL_ROLES.map(role=>[role,models[role] || models.audit]));
    return Object.entries({audit:'--model',environment:'--env-model',visual:'--visual-model',verify:'--verify-model',redteam:'--redteam-model',judge:'--judge-model'}).flatMap(([role,flag])=>[flag,effective[role]]);
  }
  return {get,save,args};
}
