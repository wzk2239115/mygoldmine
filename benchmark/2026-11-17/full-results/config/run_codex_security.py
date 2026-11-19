import pathlib,subprocess,os,json,datetime
b=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17');env=os.environ.copy();env['PATH']='/vol1/1000/mygoldmine-restore/runtime/bin:'+env['PATH'];env['CODEX_SECURITY_NO_UPDATE_NOTICE']='1'
c=json.load(open('/home/wzk/.config/opencode/opencode.json'))['provider']['360-proxy']['options'];env['BENCHMARK_MODEL_KEY']=c['apiKey']
with (b/'logs/codex-security-install.log').open('w') as log:
 r=subprocess.run(['npm','install','--prefix',str(b/'tools/codex-cli'),'@openai/codex-security'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
 if r.returncode:raise SystemExit(r.returncode)
cli=str(b/'tools/codex-cli/node_modules/.bin/codex-security');rows=[]
for t in ['sol','pure-ftpd','libcoap','tlse']:
 out=b/'results/codex-security'/t;out.mkdir(parents=True,exist_ok=True);out.chmod(0o700);private=pathlib.Path('/home/wzk/.local/state/codex-security-benchmark')/t;private.mkdir(parents=True,exist_ok=True);private.chmod(0o700);home=private/'codex-home';home.mkdir(exist_ok=True);home.chmod(0o700);env['CODEX_SECURITY_STATE_DIR']=str(private)
 row={'target':t,'status':'starting','started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model':'deepseek/deepseek-v4.1-flash','limit_seconds':3600};rows.append(row)
 def save(): (b/'results/codex-security/status.json').write_text(json.dumps(rows,indent=2))
 save();cmd=[cli,'scan',str(b/'targets'/t),'--output-dir',str(out),'--auth','api-key','--model','deepseek/deepseek-v4.1-flash','--codex',"model_provider='benchmark360'",'--codex',"model_providers.benchmark360.name='Benchmark 360'",'--codex',"model_providers.benchmark360.base_url='https://api.360.cn/v1'",'--codex',"model_providers.benchmark360.wire_api='responses'",'--codex',"model_providers.benchmark360.env_key='BENCHMARK_MODEL_KEY'"]
 with (b/'logs'/('codex-security-'+t+'.log')).open('w') as log:
  try:
   row['status']='running';save();r=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=3600,start_new_session=True);row.update(status='finished' if r.returncode==0 else 'failed',exit_code=r.returncode)
  except subprocess.TimeoutExpired:row['status']='timeout'
 row['ended_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
