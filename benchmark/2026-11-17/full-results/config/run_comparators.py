import pathlib,subprocess,json,time,os,datetime,shutil
base=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17');image='mygoldmine-benchmark-tools:ready';envfile='/home/wzk/.config/mygoldmine-benchmark/provider.env';rows=[]
def save(): (base/'results/comparator-status.json').write_text(json.dumps(rows,indent=2))
def run(tool,target,command,limit=3600,suffix=''):
 out=base/'results'/tool/target;out.mkdir(parents=True,exist_ok=True);os.chown(out,1000,1001);out.chmod(0o755)
 name='benchmark-'+tool+'-'+target+suffix;start=time.monotonic();row={'tool':tool,'target':target,'subtask':suffix,'status':'running','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'limit_seconds':limit};rows.append(row);save()
 mounts=['-v',str(base/'config')+':'+str(base/'config')+':ro','-v',str(out)+':'+str(out)]
 if tool=='claude-security-review':mounts+=['-v',str(base/'tools/claude-code-security-review')+':'+str(base/'tools/claude-code-security-review')+':ro','-v',str(base/'targets'/target)+':'+str(base/'targets'/target)+':ro']
 elif tool=='repoaudit':mounts+=['-v',str(base/'tools/RepoAudit')+':'+str(base/'tools/RepoAudit'),'-v',str(base/'targets'/target)+':'+str(base/'targets'/target)+':ro']
 else:mounts+=['-v','/var/run/docker.sock:/var/run/docker.sock','-v','/usr/bin/docker:/usr/local/bin/docker:ro']
 cmd=['docker','run','--rm','--name',name,'--network','host','--memory','3g','--cpus','2','--env-file',envfile,'-e','HOME=/tmp/benchmark-home','-u','1000:1001','--group-add','994',*mounts,'-w',str(out),image,*command]
 with (out/('execution'+suffix+'.log')).open('w') as f:
  try:
   r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=limit);row['exit_code']=r.returncode;row['status']='finished' if r.returncode in [0,2] else 'failed'
  except subprocess.TimeoutExpired:
   row['status']='timeout';subprocess.run(['docker','stop','-t','10',name],stdout=f,stderr=f,timeout=30)
 row['elapsed_seconds']=round(time.monotonic()-start,2);row['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();return row
for t in ['sol','pure-ftpd','libcoap','tlse']:
 out=base/'results/claude-security-review'/t
 run('claude-security-review',t,['python',str(base/'config/claude_review_adapter.py'),str(base/'targets'/t),str(out)])
for t in ['sol','pure-ftpd','libcoap','tlse']:
 if not (base/'config/parsers-ready').exists():
  rows.append({'tool':'repoaudit','target':t,'status':'not_run_parser_setup_failed'});save();continue
 for kind in ['NPD','MLK','UAF']:
  command=['bash','-c','cd '+str(base/'tools/RepoAudit/src')+' && python repoaudit.py --language Cpp --model-name deepseek/deepseek-v4.1-flash --project-path '+str(base/'targets'/t)+' --bug-type '+kind+' --is-reachable --temperature 0 --scan-type dfbscan --call-depth 3 --max-neural-workers 4']
  run('repoaudit',t,command,1200,'-'+kind.lower())
for t in ['sol','pure-ftpd','libcoap','tlse']:
 imagecheck=subprocess.run(['docker','image','inspect','ghcr.io/usestrix/strix-sandbox:1.4.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 if imagecheck.returncode:
  rows.append({'tool':'strix','target':t,'status':'not_run_sandbox_image_unavailable'});save();continue
 work=base/'results/strix'/t/'source';work.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(base/'targets'/t,work,dirs_exist_ok=True);subprocess.run(['chown','-R','1000:1001',str(work)]);subprocess.run(['chmod','-R','u+rwX,go+rX',str(work)])
 run('strix',t,['strix','-n','-t',str(work),'--scope-mode','full','--scan-mode','standard','--max-budget','10','--instruction','Audit only this local source snapshot and any service you build inside its sandbox. Do not contact upstream services or the LAN. Report validated findings with evidence.'],3600)
 (base/'results/strix'/t/'source-revision-after.txt').write_text(subprocess.check_output(['git','-C',str(work),'status','--short'],text=True))
rows.append({'tool':'codex-security','status':'not_run_missing_official_access','targets':['sol','pure-ftpd','libcoap','tlse'],'findings':None});save()
(base/'results/comparators-finished').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
