import fs from 'node:fs';
import path from 'node:path';

export function rsiRewards(repo, project, runId) {
  let state;
  try { state=JSON.parse(fs.readFileSync(path.join(repo,'rsi/exploration',project,'state.json'),'utf8')); }
  catch { return {current:null,history:[]}; }
  const history=Object.values(state.rounds || {}).map(row=>row?.result?.objective)
    .filter(row=>row?.formula_version==='rsi-two-signal-v1' && row.project===project)
    .sort((a,b)=>String(b.updated_at).localeCompare(String(a.updated_at)));
  return {current:history.find(row=>row.run_id===runId) || null,history:history.slice(0,20)};
}
