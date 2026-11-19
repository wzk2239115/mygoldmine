import pathlib,json,subprocess,time,datetime,concurrent.futures,threading,os,shutil,traceback
base=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17');status=base/'results/comparator-status.json';rows=json.loads(status.read_text());lock=threading.Lock()
prefix=(base/'config/run_comparators.py').read_text().split("for t in ['sol'",1)[0]
prefix=prefix.replace("r.returncode in [0,2]","(r.returncode==0 or (tool=='strix' and r.returncode==2))")
ns={};exec(compile(prefix,'comparator_runtime','exec'),ns);ns['rows']=rows

def save():
 with lock:
  p=status.with_suffix('.tmp');p.write_text(json.dumps(rows,indent=2));p.replace(status)
ns['save']=save;run=ns['run']

def adopt(job):
 name='benchmark-'+job['tool']+'-'+job['target'];beg=datetime.datetime.fromisoformat(job['started_utc']);remaining=max(1,3600-(datetime.datetime.now(datetime.timezone.utc)-beg).total_seconds())
 try:
  r=subprocess.run(['docker','wait',name],capture_output=True,text=True,timeout=remaining);code=int(r.stdout.strip());job['exit_code']=code;job['status']='finished' if code==0 else 'failed'
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','-t','10',name],capture_output=True,timeout=30);job['status']='timeout'
 except Exception as e:job['status']='reconcile_required';job['error']=type(e).__name__
 job['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();job['elapsed_seconds']=round((datetime.datetime.now(datetime.timezone.utc)-beg).total_seconds(),2);save()

def claude(t):
 out=base/'results/claude-security-review'/t;run('claude-security-review',t,['python',str(base/'config/claude_review_adapter.py'),str(base/'targets'/t),str(out)])

def repoaudit(t):
 if not (base/'config/parsers-ready').exists():rows.append({'tool':'repoaudit','target':t,'status':'not_run_parser_setup_failed'});save();return
 for kind in ['NPD','MLK','UAF']:
  cmd=['bash','-c','cd '+str(base/'tools/RepoAudit/src')+' && python repoaudit.py --language Cpp --model-name deepseek/deepseek-v4.1-flash --project-path '+str(base/'targets'/t)+' --bug-type '+kind+' --is-reachable --temperature 0 --scan-type dfbscan --call-depth 3 --max-neural-workers 4']
  run('repoaudit',t,cmd,1200,'-'+kind.lower())

def strix(t):
 if subprocess.run(['docker','image','inspect','ghcr.io/usestrix/strix-sandbox:1.4.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
  rows.append({'tool':'strix','target':t,'status':'not_run_sandbox_image_unavailable'});save();return
 work=base/'results/strix'/t/'source';work.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(base/'targets'/t,work,dirs_exist_ok=True);subprocess.run(['chown','-R','1000:1001',str(work)]);subprocess.run(['chmod','-R','u+rwX,go+rX',str(work)])
 run('strix',t,['strix','-n','-t',str(work),'--scope-mode','full','--scan-mode','standard','--max-budget','10','--instruction','Audit only this local source snapshot and any service you build inside its sandbox. Do not contact upstream services or the LAN. Report validated findings with evidence.'])
 r=subprocess.run(['git','-c','safe.directory='+str(work),'-C',str(work),'status','--short'],capture_output=True,text=True);(work.parent/'source-status-after.txt').write_text(r.stdout+r.stderr)

jobs=[]
for job in rows:
 if job.get('status')=='running':jobs.append((adopt,(job,)))
for t in ['sol','pure-ftpd','libcoap','tlse']:
 if not any(x.get('tool')=='claude-security-review' and x.get('target')==t for x in rows):jobs.append((claude,(t,)))
jobs += [(repoaudit,(t,)) for t in ['sol','pure-ftpd','libcoap','tlse']]+[(strix,(t,)) for t in ['sol','pure-ftpd','libcoap','tlse']]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 fs=[pool.submit(fn,*args) for fn,args in jobs]
 for f in concurrent.futures.as_completed(fs):
  try:f.result()
  except Exception:traceback.print_exc()
rows.append({'tool':'codex-security','status':'not_run_missing_official_access','targets':['sol','pure-ftpd','libcoap','tlse'],'findings':None});save();(base/'results/comparators-finished').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
