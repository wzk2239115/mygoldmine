import fs from 'node:fs';
import path from 'node:path';
const read=file=>{try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{return {};}};
export function stageLearning(repoRoot,project,stage) {
 const root=path.join(repoRoot,'rsi/stage-skills');
 const active=read(path.join(root,'active.json'));
 const directory=path.join(root,'candidates');
 const candidates=fs.existsSync(directory)?fs.readdirSync(directory).filter(name=>name.endsWith('.json')).map(name=>read(path.join(directory,name))).filter(value=>value.project===project && active[value.key]!==value.id):[];
 return {general:active[`${stage}/general/shared`] || null,project:active[`${stage}/project/${project}`] || null,candidates:candidates.filter(value=>value.stage===stage).length,projectCandidates:candidates.length};
}
