#!/usr/bin/env python3
"""阶段交付工具：提供 MCP 函数和命令行，共用实际产物检查。"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_bank import SkillBank, infer_project, instruction as skill_instruction, spool_proposal

ROOT = Path(__file__).resolve().parents[2]
STAGES = ('environment', 'orchestrator', 'visual', 'verify', 'redteam-lab', 'redteam-agent', 'judge', 'learner')
INSTRUCTION = '本节点交付必须通过 mcp__stage_delivery__submit_stage_result。主文件写入 artifact，必须随下游交接的附件写入 artifacts；收到 needs_revision 时按具体错误修正后再次提交。节点结束前必须取得 accepted 回执，否则工作流不会交给下一节点。accepted 只表示文件与契约检查通过，不代表漏洞已验证。无法满足契约时提交结构化受阻结果并说明限制；不要伪造证据或为获得 accepted 降低原有业务验收标准。'
SCHEMA = {'type':'object','properties':{'artifact':{'type':'string','description':'主交付文件的绝对路径'},'artifacts':{'type':'array','items':{'type':'string'},'description':'与主交付相关、需要随节点交接的附件绝对路径'},'summary':{'type':'string'},'limitations':{'type':'array','items':{'type':'string'}}},'required':['artifact','summary','limitations'],'additionalProperties':False}
SKILLOPT_SCHEMA = {'type':'object','properties':{'target_stage':{'type':'string','enum':list(STAGES)},'scope':{'type':'string','enum':['general','project']},'problem':{'type':'string'},'suggestions':{'type':'array','minItems':1,'maxItems':4,'items':{'type':'object','properties':{'type':{'type':'string','enum':['add','replace','delete']},'title':{'type':'string'},'instruction':{'type':'string'}},'required':['instruction'],'additionalProperties':False}},'evidence':{'type':'array','minItems':1,'maxItems':5,'items':{'type':'string'}},'source_stages':{'type':'array','items':{'type':'string','enum':list(STAGES)}},'expected_improvement':{'type':'string'},'possible_regression':{'type':'string'},'conditions':{'type':'object','properties':{key:{'type':'string'} for key in ('machine','python','commit')},'additionalProperties':False}},'required':['target_stage','scope','problem','suggestions','evidence','expected_improvement','possible_regression'],'additionalProperties':False}

def config(stage, root):
    return {'mcpServers':{'stage_delivery':{'command':'python3','args':[str(Path(__file__).resolve()),'serve','--stage',stage,'--root',str(Path(root).resolve())]}}}

def accepted_submissions(stage, root, minimum=1):
    """Recheck accepted receipts and their exact artifact bytes at the stage boundary."""
    root = Path(root).resolve(strict=True)
    if stage not in STAGES or minimum < 0:
        raise ValueError('阶段交付检查参数无效')
    found = []
    latest = {}
    receipt_roots = [root]
    summary = root / 'verify' / 'agent' / 'summary.json'
    if stage == 'verify' and summary.is_file():
        batch = json.loads(summary.read_text(encoding='utf-8'))
        rows = batch.get('findings')
        if not isinstance(rows, list):
            raise ValueError('蓝队批次缺少候选结果数组')
        ids = [row.get('finding_id') for row in rows]
        if any(not isinstance(sid, str) or not sid or sid in {'.', '..'} or
               any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-' for c in sid)
               for sid in ids) or len(ids) != len(set(ids)):
            raise ValueError('蓝队批次候选编号无效或重复')
        receipt_roots = [summary.parent / sid for sid in ids]
    for directory, names, files in (
        item for receipt_root in receipt_roots
        for item in os.walk(receipt_root, followlinks=False)
    ):
        names[:] = [name for name in names if name != 'retry-history' and not (Path(directory) / name).is_symlink()]
        if '.stage-submissions' not in names:
            continue
        folder = Path(directory) / '.stage-submissions' / stage
        if not folder.is_dir() or folder.is_symlink():
            continue
        for receipt_file in sorted(folder.glob('*.json')):
            if receipt_file.is_symlink() or not receipt_file.is_file():
                continue
            receipt = json.loads(receipt_file.read_text(encoding='utf-8'))
            if not isinstance(receipt, dict) or receipt.get('stage') != stage:
                raise ValueError(f'阶段交付回执格式无效：{receipt_file}')
            key = receipt.get('artifact') or str(receipt_file)
            previous = latest.get(key)
            if previous is None or receipt.get('checked_at', '') > previous[1].get('checked_at', ''):
                latest[key] = (receipt_file, receipt)
    for receipt_file, receipt in latest.values():
            try:
                if receipt.get('decision') != 'accepted':
                    continue
                artifact = Path(receipt.get('artifact') or '')
                if not artifact.is_absolute():
                    raise ValueError('验收回执中的产物路径不是绝对路径')
                artifact = Path(os.path.abspath(artifact))
                if not artifact.is_relative_to(root):
                    raise ValueError('验收回执中的产物路径超出本阶段目录')
                cursor = root
                for part in artifact.relative_to(root).parts:
                    cursor = cursor / part
                    if cursor.is_symlink():
                        raise ValueError(f'已验收产物包含符号链接：{cursor}')
                if not artifact.is_file():
                    raise ValueError(f'已验收产物已缺失：{artifact}')
                digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
                if digest != receipt.get('sha256'):
                    raise ValueError(f'已验收产物内容已改变：{artifact}')
                files = receipt.get('files') or [{'path': str(artifact), 'sha256': digest}]
                if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
                    raise ValueError('交付包清单格式无效')
                for item in files:
                    file = Path(item.get('path') or '')
                    if not file.is_absolute():
                        raise ValueError('交付包文件路径必须是绝对路径')
                    file = Path(os.path.abspath(file))
                    if not file.is_relative_to(root):
                        raise ValueError('交付包文件路径超出本阶段目录')
                    cursor = root
                    for part in file.relative_to(root).parts:
                        cursor = cursor / part
                        if cursor.is_symlink():
                            raise ValueError(f'交付包包含符号链接：{cursor}')
                    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != item.get('sha256'):
                        raise ValueError(f'交付包文件缺失或内容已改变：{file}')
                found.append({'receipt': str(receipt_file), 'artifact': str(artifact), 'sha256': digest, 'files': files})
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError(f'阶段交付回执无效：{receipt_file}：{exc}') from exc
    unique = {item['artifact']: item for item in found}
    found = list(unique.values())
    if len(found) < minimum:
        raise ValueError(f'{stage} 阶段需要至少 {minimum} 份有效交付回执，实际为 {len(found)}')
    return {'stage': stage, 'root': str(root), 'accepted': len(found), 'deliveries': found}


def finalize_orchestrator(root):
    """Revalidate producer finalization without discarding declared dependencies."""
    root = Path(root).resolve(strict=True)
    try:
        return accepted_submissions('orchestrator', root)
    except ValueError as original_error:
        folder = root / '.stage-submissions' / 'orchestrator'
        if folder.is_symlink() or folder.parent.is_symlink():
            raise original_error
        receipts = []
        for file in folder.glob('*.json'):
            if file.is_symlink():
                raise ValueError('交付回执不能是符号链接')
            value = json.loads(file.read_text(encoding='utf-8'))
            if value.get('stage') == 'orchestrator':
                receipts.append(value)
        if not receipts:
            raise original_error
        prior = max(receipts, key=lambda value: value.get('checked_at', ''))
        artifact = root / 'audit-report.json'
        if (prior.get('decision') != 'accepted' or prior.get('artifact') != str(artifact)
                or artifact.is_symlink() or not artifact.is_file()
                or hashlib.sha256(artifact.read_bytes()).hexdigest() != prior.get('sha256')):
            raise original_error
        declared = prior.get('files')
        if not isinstance(declared, list) or not declared:
            raise original_error
        attachments = []
        for item in declared:
            file = Path(item['path'])
            if not file.is_absolute() or not file.is_relative_to(root):
                raise original_error
            cursor = root
            for part in file.relative_to(root).parts:
                cursor /= part
                if cursor.is_symlink():
                    raise original_error
            if not file.is_file():
                raise original_error
            if file.name == 'coverage-ledger.json':
                sys.path.insert(0, str(ROOT / 'scripts' / 'audit'))
                from coverage_ledger import validate_ledger
                ledger = json.loads(file.read_text(encoding='utf-8'))
                errors = validate_ledger(ledger)
                if errors:
                    raise ValueError('覆盖记录未通过重新验收：' + '; '.join(errors))
            if file != artifact:
                attachments.append(str(file))
        # One final submission, using all prior declared dependencies and the same validators.
        receipt = submit('orchestrator', root, {
            'artifact': str(artifact), 'artifacts': attachments,
            'summary': prior.get('summary') or '编排结束后重新验收交付附件',
            'limitations': prior.get('limitations') or [],
        })
        if receipt['decision'] != 'accepted':
            raise ValueError('编排附件重新验收失败：' + str(receipt['errors']))
        delivery = accepted_submissions('orchestrator', root)
        delivery['revalidated'] = True
        delivery['previous_receipt_id'] = prior.get('id')
        return delivery


def submit(stage, root, arguments):
    root=Path(root).resolve(); errors=[]; artifact=None; digest=None; package_files=[]
    try:
        if stage not in STAGES: raise ValueError('未知阶段')
        if not isinstance(arguments.get('summary'),str) or not arguments['summary'].strip(): raise ValueError('需要简短交付说明')
        if not isinstance(arguments.get('limitations'),list) or any(not isinstance(v,str) for v in arguments['limitations']): raise ValueError('limitations 必须是字符串数组')
        raw_artifact=Path(arguments['artifact'])
        artifact=Path(os.path.abspath(raw_artifact if raw_artifact.is_absolute() else root/raw_artifact))
        if not artifact.is_relative_to(root): raise ValueError('交付文件必须位于本次指定输出目录内')
        cursor=root
        for part in artifact.relative_to(root).parts:
            cursor=cursor/part
            if cursor.is_symlink(): raise ValueError('交付文件路径不能包含符号链接')
        if not artifact.is_file(): raise ValueError('交付文件必须是普通文件')
        if artifact.stat().st_size > 10*1024*1024: raise ValueError('交付文件超过 10 MiB')
        data=artifact.read_bytes();digest=hashlib.sha256(data).hexdigest()
        requested=arguments.get('artifacts',[])
        if not isinstance(requested,list) or any(not isinstance(name,str) for name in requested) or len(requested)>100:
            raise ValueError('artifacts 必须是最多 100 个绝对路径组成的数组')
        package={str(artifact):data}
        for name in requested:
            raw=Path(name)
            file=Path(os.path.abspath(raw if raw.is_absolute() else root/raw))
            if not file.is_relative_to(root): raise ValueError('交付附件必须位于本次指定输出目录内')
            cursor=root
            for part in file.relative_to(root).parts:
                cursor=cursor/part
                if cursor.is_symlink(): raise ValueError('交付附件路径不能包含符号链接')
            if not file.is_file(): raise ValueError('交付附件必须是普通文件')
            if file.stat().st_size>10*1024*1024: raise ValueError('单个交付附件超过 10 MiB')
            package[str(file)]=file.read_bytes()
        if stage=='learner':
            if not data.strip(): raise ValueError('经验文件为空')
        elif stage=='redteam-lab':
            if artifact.suffix.lower() in {'.md','.markdown'}:
                raise ValueError('红队场景阶段受阻时请提交结构化受阻文件，不要提交说明文档')
            try:
                d=json.loads(data)
            except ValueError as exc:
                raise ValueError('红队场景交付必须是 JSON 对象；受阻时请提交结构化受阻文件') from exc
            if not isinstance(d,dict): raise ValueError('交付文件必须是 JSON 对象')
            sys.path.insert(0,str(ROOT/'scripts/redteam'))
            from contracts import validate_blocked, validate_scenario
            if d.get('status')=='blocked':
                validate_blocked(d, expected_finding_id=d.get('finding_id'), expected_finding_sha256=d.get('finding_sha256'), expected_source=d.get('source'))
            else:
                # 完整的来源绑定与隔离检查继续由构建执行器执行。
                validate_scenario(d, expected_finding_id=d.get('finding_id'), expected_finding_sha256=d.get('finding_sha256'), expected_source=d.get('source'))
        else:
            d=json.loads(data)
            if not isinstance(d,dict): raise ValueError('交付文件必须是 JSON 对象')
            if stage=='orchestrator':
                sys.path.insert(0,str(ROOT/'scripts/mine'))
                from check_report import check_report
                expected_project=infer_project(root)
                expected_project=None if expected_project=="unknown" else expected_project
                result=check_report(artifact, expected_project=expected_project)
                if not result['valid'] or result['incomplete']: errors.append({'report_quality':result})
            elif stage=='environment':
                if d.get('env_status') not in ('ready','partial'): raise ValueError('环境未达到可交付状态')
                if d.get('build_exit_code') != 0 or not d.get('image') or not d.get('image_id'): raise ValueError('缺少成功构建和镜像编号证据')
                actual=subprocess.run(['docker','image','inspect',d['image'],'--format','{{.Id}}'],capture_output=True,text=True,timeout=15)
                if actual.returncode or actual.stdout.strip()!=d['image_id']: raise ValueError('实际镜像不存在或编号与清单不符')
                if not d.get('acceptance') or any(c.get('exit_code')!=0 for c in d['acceptance']): raise ValueError('需要明确且通过的验收记录')
                if d['env_status']=='partial' and not arguments['limitations']: raise ValueError('部分可用必须声明限制')
            elif stage=='visual':
                # 单个场景的设计交付；整阶段仍由原有渲染与汇总检查验收。
                if not d.get('finding_id'): raise ValueError('场景设计缺少 finding_id')
                sys.path.insert(0, str(ROOT/'.claude/skills/project-cartographer/scripts'))
                from image_provenance import generated_image
                images=[p for p in artifact.parent.glob(artifact.name.replace('.director.json','')+'.*') if p.suffix in ('.webp','.png','.jpg') and generated_image(p)]
                for image in images:
                    if image.is_relative_to(root): package[str(image)]=image.read_bytes()
                if not artifact.name.endswith('.director.json') or not images: raise ValueError('需要场景设计 .director.json 及同名文生图图片；必须有匹配图片哈希的文生图记录，SVG 不可作为交付')
            elif stage=='verify':
                sys.path.insert(0,str(ROOT/'scripts/workflow'))
                from delivery_contract import validate_verification_report
                checked=validate_verification_report(artifact,artifact.parent)
                for name in checked['files']:
                    file=Path(name)
                    if file.is_relative_to(root): package[str(file)]=file.read_bytes()
                status=d.get('verdict') or d.get('verification',{}).get('status') or d.get('status')
                if not status or not (d.get('finding_id') or d.get('id')): raise ValueError('验证报告缺少明确结论或候选问题编号')
                if status in ('blocked','inconclusive') and not arguments['limitations']: raise ValueError('受阻或不确定结论必须声明限制')
            elif stage=='redteam-agent':
                if not d.get('status'): raise ValueError('红队结果缺少状态')
            elif stage=='judge':
                sys.path.insert(0,str(ROOT/'scripts/redteam'))
                from contracts import validate_verdict
                validate_verdict(d)
        if sum(len(value) for value in package.values())>50*1024*1024:
            raise ValueError('交付包总大小超过 50 MiB')
        package_files=[{'path':name,'size':len(value),'sha256':hashlib.sha256(value).hexdigest()} for name,value in sorted(package.items())]
    except Exception as exc:
        errors.append(str(exc))
    receipt={'id':str(uuid.uuid4()),'stage':stage,'decision':'needs_revision' if errors else 'accepted','validation_scope':'artifact_contract','artifact':str(artifact) if artifact else None,'sha256':digest,'files':package_files,'summary':arguments.get('summary'),'limitations':arguments.get('limitations'),'errors':errors,'checked_at':datetime.now(timezone.utc).isoformat(),'notice':'交付文件检查不替代动态验收、随机标记来源检查或人工验收；原有阶段门槛继续生效。'}
    directory=root/'.stage-submissions'/stage;directory.mkdir(parents=True,exist_ok=True)
    (directory/(receipt['id']+'.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt


def request_skillopt_optimization(stage, root, arguments):
    root=Path(root).resolve()
    if stage!='learner':raise ValueError('只有经验学习节点可以提交 SkillOpt 改进请求')
    target=arguments.get('target_stage')
    if target not in STAGES:raise ValueError('目标阶段无效')
    scope=arguments.get('scope')
    if scope not in ('general','project'):raise ValueError('技能层级必须是通用或仓库专属')
    problem=str(arguments.get('problem') or '').strip()
    if not problem or len(problem)>4000:raise ValueError('需要 1—4000 字符的问题归因')
    suggestions=arguments.get('suggestions')
    if not isinstance(suggestions,list) or not 1<=len(suggestions)<=4:raise ValueError('需要 1—4 条修改建议')
    normalized=[]
    for item in suggestions:
        if not isinstance(item,dict):raise ValueError('修改建议必须是对象')
        if item.get('type','add') not in ('add','replace','delete'):raise ValueError('修改建议类型只能是 add、replace、delete')
        instruction=str(item.get('instruction') or '').strip()
        if not instruction or len(instruction)>2000:raise ValueError('修改建议需要 1—2000 字符的说明')
        normalized.append({'type':item.get('type','add'),'title':str(item.get('title') or '')[:120],'instruction':instruction})
    evidence=arguments.get('evidence')
    if not isinstance(evidence,list) or not 1<=len(evidence)<=5:raise ValueError('需要 1—5 份本次执行证据')
    conditions=arguments.get('conditions') or {}
    if not isinstance(conditions,dict) or set(conditions)-{'machine','python','commit'} or any(not isinstance(v,str) for v in conditions.values()):raise ValueError('conditions 仅支持 machine、python、commit 字符串')
    source=arguments.get('source_stages') or ['learner']
    if not isinstance(source,list) or any(item not in STAGES for item in source):raise ValueError('来源阶段无效')
    expected=str(arguments.get('expected_improvement') or '').strip()
    regression=str(arguments.get('possible_regression') or '').strip()
    if len(expected)>1000 or len(regression)>1000:raise ValueError('预期改善和可能退化各最多 1000 字符')
    queue=root/'rsi/skillopt-requests'
    existing=[item for item in queue.glob('*.json') if item.is_file()] if queue.exists() else []
    if len(existing)>=2:raise ValueError('每轮最多提交两个 SkillOpt 改进请求')
    request_id=uuid.uuid4().hex
    refs=[]
    for index,name in enumerate(evidence):
        source_path=Path(name).resolve(strict=True)
        if not source_path.is_relative_to(root) or not source_path.is_file() or source_path.stat().st_size>2*1024*1024:raise ValueError('证据必须位于本次输出目录内，单份不超过 2 MiB')
        snapshot=queue/'evidence'/f'{request_id}-{index}.txt';snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes(source_path.read_bytes());refs.append(str(snapshot))
    meta=Path(str(root)+'.meta')/'status.json'
    status={}
    try:status=json.loads(meta.read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    request={'id':request_id,'run_dir':str(root),'project':infer_project(root),'target_stage':target,'scope':scope,'problem':problem,'suggestions':normalized,'evidence':refs,'source_stages':source,'source_commit':status.get('commit',''),'expected_improvement':expected,'possible_regression':regression,'conditions':conditions,'created_at':datetime.now(timezone.utc).isoformat()}
    (queue).mkdir(parents=True,exist_ok=True)
    (queue/f'{request_id}.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'status':'queued_skillopt_request','id':request_id,'publication':'requires_independent_evaluation'}

def serve(stage, root):
    for line in sys.stdin:
        request=None
        try:
            request=json.loads(line);method=request.get('method'); ident=request.get('id')
            if ident is None: continue
            if method=='initialize': result={'protocolVersion':request.get('params',{}).get('protocolVersion','2024-11-05'),'capabilities':{'tools':{}},'serverInfo':{'name':'stage-delivery','version':'1.0'}}
            elif method=='ping': result={}
            elif method=='tools/list':
                tools=[{'name':'propose_skill_update','description':'提交本阶段的通用或仓库专属技能改进候选，引用本次实际执行证据；不会自动发布。','inputSchema':{'type':'object','properties':{'target_stage':{'type':'string','enum':list(STAGES)},'scope':{'type':'string','enum':['general','project']},'content':{'type':'string'},'evidence':{'type':'array','items':{'type':'string'}},'conditions':{'type':'object','properties':{key:{'type':'string'} for key in ('machine','python','commit')},'additionalProperties':False},'provenance':{'type':'object'}},'required':['scope','content','evidence'],'additionalProperties':False}},{'name':'submit_stage_result','description':f'提交 {stage} 阶段交付文件，返回具体修改意见或验收凭据；允许多次调用。','inputSchema':SCHEMA}]
                if stage=='redteam-lab':
                    from stage_builds import SCHEMA as build_schema
                    tools.append({'name':'start_stage_build','description':'登记本场景的持久镜像构建；返回任务文件，宿主机等待真实完成。','inputSchema':build_schema})
                if stage=='learner':
                    tools.append({'name':'request_skillopt_optimization','description':'提交一个由 SkillOpt 重写的阶段技能请求。只写请求，不直接发布；宿主机随后调用第三方优化引擎并转换为现有候选。','inputSchema':SKILLOPT_SCHEMA})
                    tools.append({'name':'get_rsi_scorecard','description':'读取本项目本轮 RSI 评分卡及相同源码版本的历史对照。只读；包含两项奖励、系数和计算依据，不改变任何验收状态。','inputSchema':{'type':'object','properties':{},'additionalProperties':False}})
                result={'tools':tools}
            elif method=='tools/call':
                params=request.get('params',{})
                if params.get('name')=='propose_skill_update':
                    args=params.get('arguments',{})
                    for name in args.get('evidence',[]):
                        if not Path(name).resolve().is_relative_to(Path(root).resolve()): raise ValueError('只能引用本次输出目录中的证据')
                    target_stage=args.get('target_stage',stage)
                    if target_stage != stage and stage != 'learner':raise ValueError('只能提炼当前阶段；学习节点可整理八阶段反馈')
                    candidate=spool_proposal(target_stage,root,args['scope'],args['content'],args['evidence'],args.get('conditions'),args.get('provenance'))
                    result={'content':[{'type':'text','text':json.dumps({'status':'queued_candidate','id':candidate['id'],'publication':'requires_independent_evaluation'},ensure_ascii=False)}]}
                elif params.get('name')=='start_stage_build':
                    from stage_builds import start_build
                    task=start_build(stage,root,params.get('arguments',{}));result={'content':[{'type':'text','text':json.dumps(task,ensure_ascii=False)}]}
                elif params.get('name')=='request_skillopt_optimization':
                    request=request_skillopt_optimization(stage,root,params.get('arguments',{}));result={'content':[{'type':'text','text':json.dumps(request,ensure_ascii=False)}]}
                elif params.get('name')=='get_rsi_scorecard':
                    if stage!='learner':raise ValueError('只有第八阶段经验学习节点可以读取 RSI 评分卡')
                    from rsi_scorecard import scorecard
                    project=infer_project(root)
                    if project=='unknown':raise ValueError('无法从本次运行目录确定项目标识')
                    data=scorecard(ROOT,root,project)
                    result={'content':[{'type':'text','text':json.dumps(data,ensure_ascii=False)}]}
                elif params.get('name')=='submit_stage_result':
                    receipt=submit(stage,root,params.get('arguments',{}));result={'content':[{'type':'text','text':json.dumps(receipt,ensure_ascii=False)}],'isError':receipt['decision']!='accepted'}
                else: raise ValueError('未知工具')
            else:
                print(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'未知方法'}}),flush=True);continue
            print(json.dumps({'jsonrpc':'2.0','id':ident,'result':result}),flush=True)
        except Exception as exc:
            if isinstance(request,dict) and 'id' in request: print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':str(exc)}}),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['config','serve','instruction','check','finalize']);parser.add_argument('--stage',choices=STAGES);parser.add_argument('--root');parser.add_argument('--minimum',type=int,default=1);args=parser.parse_args()
    if args.mode=='instruction': print(INSTRUCTION + ('\n'+skill_instruction(args.stage,args.root) if args.stage and args.root else ''))
    elif args.mode=='config': print(json.dumps(config(args.stage,args.root)))
    elif args.mode=='finalize':
        if args.stage != 'orchestrator': raise ValueError('此收尾入口仅用于审计编排阶段')
        print(json.dumps(finalize_orchestrator(args.root), ensure_ascii=False))
    elif args.mode=='check': print(json.dumps(accepted_submissions(args.stage,args.root,args.minimum),ensure_ascii=False))
    else: serve(args.stage,args.root)
if __name__=='__main__':main()
