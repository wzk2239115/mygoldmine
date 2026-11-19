import pathlib,subprocess,time,json,os,datetime
base=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17');repo=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17/tools/mygoldmine')
env=os.environ.copy();env['PATH']='/vol1/1000/mygoldmine-restore/venv/bin:/vol1/1000/mygoldmine-restore/runtime/bin:'+env['PATH'];env['HOME']='/home/wzk';env['PYTHON']='/vol1/1000/mygoldmine-restore/venv/bin/python3'
state=[]
for target in ['sol','libcoap','tlse']:
 out=base/'results/mygoldmine-clean'/target;out.parent.mkdir(exist_ok=True,parents=True)
 row={'tool':'mygoldmine','target':target,'start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'starting','limit_seconds':3600};state.append(row)
 def save(): (base/'results/mygoldmine-clean/status.json').write_text(json.dumps(state,indent=2))
 save();start=time.monotonic()
 with (base/'logs'/('mygoldmine-'+target+'.log')).open('w') as log:
  cmd=['bash',str(repo/'run.sh'),str(base/'targets'/target),'--project','benchmark-'+target,'--run-dir',str(out),'--timeout','3600','--mine-only','--skip-env','--skip-visual','--model','360-proxy/deepseek/deepseek-v4.1-flash']
  r=subprocess.run(cmd,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
  row['launcher_exit']=r.returncode;row['status']='running' if r.returncode==0 else 'launch_failed';save()
  if r.returncode==0:
   meta=pathlib.Path(str(out)+'.meta');pidfile=meta/'supervisor.pid'
   while time.monotonic()-start<3600:
    try:
     pid=int(pidfile.read_text());stat=pathlib.Path('/proc')/str(pid)/'stat'
     if not stat.exists() or stat.read_text().split(') ')[1][0]=='Z':break
    except (ValueError,OSError):break
    time.sleep(10)
   else:
    row['status']='timeout';subprocess.run(['bash',str(repo/'run.sh'),'--stop',str(out)],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
   if row['status']=='running':row['status']='process_finished'
  row['report_exists']=(out/'audit-report.json').exists();row['elapsed_seconds']=round(time.monotonic()-start,2);row['end_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
