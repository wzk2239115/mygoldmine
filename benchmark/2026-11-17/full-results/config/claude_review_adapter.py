import pathlib,sys,subprocess,json,os,dataclasses
base=pathlib.Path('/vol1/1000/mygoldmine-benchmark/2026-11-17');sys.path.insert(0,str(base/'tools/claude-code-security-review'))
from claudecode.prompts import get_security_audit_prompt
from claudecode.github_action_audit import SimpleClaudeRunner
from claudecode.findings_filter import FindingsFilter
from claudecode.claude_api_client import ClaudeAPIClient
target=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(exist_ok=True,parents=True)
files=subprocess.check_output(['git','-C',str(target),'ls-files'],text=True).splitlines(); files=[f for f in files if pathlib.Path(f).suffix.lower() in {'.c','.h','.cc','.cpp','.hpp','.sh','.py'} or pathlib.Path(f).name in {'Makefile','CMakeLists.txt'}]
context={'number':0,'title':'Benchmark: review entire frozen source snapshot','files':[{'filename':f} for f in files],'head':{'repo':{'full_name':target.name}}}
context.update({'additions':0,'deletions':0,'changed_files':len(files),'user':{'login':'benchmark'}})
prompt=get_security_audit_prompt(context,include_diff=False,custom_scan_instructions='This is a local full-source benchmark, not a real PR. All listed files are in scope. Inspect source and local build/test artifacts only. Do not contact upstream production systems or scan the local network. Clearly distinguish static candidates from tested findings.')
(out/'prompt.txt').write_text(prompt)
original=subprocess.run;counter=0
def run(cmd,*args,**kwargs):
 global counter
 if isinstance(cmd,list) and cmd and cmd[0]=='claude':
  cmd=cmd+['--print','--permission-mode','bypassPermissions'];counter+=1
  r=original(cmd,*args,**kwargs);(out/f'claude-{counter}.json').write_text(r.stdout or '');(out/f'claude-{counter}.stderr').write_text(r.stderr or '');return r
 return original(cmd,*args,**kwargs)
subprocess.run=run
ok,error,raw=SimpleClaudeRunner(timeout_minutes=58).run_security_audit(target,prompt)
(out/'raw-findings.json').write_text(json.dumps({'success':ok,'error':error,'results':raw},indent=2))
if not ok:raise SystemExit(2)
def validate(self):
 try:
  self.client.messages.create(model=self.model,max_tokens=8,messages=[{'role':'user','content':'Reply OK'}],timeout=30);return True,''
 except Exception as e:return False,type(e).__name__
ClaudeAPIClient.validate_api_access=validate
f=FindingsFilter(model=os.environ['CLAUDE_MODEL']);good,filtered,stats=f.filter_findings(raw.get('findings',[]),context)
(out/'filtered-findings.json').write_text(json.dumps({'success':good,'results':filtered,'stats':dataclasses.asdict(stats),'model':os.environ['CLAUDE_MODEL'],'filtering_enabled':f.use_claude_filtering},indent=2,default=str))
