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

ROOT = Path(__file__).resolve().parents[2]
STAGES = ('environment', 'orchestrator', 'visual', 'verify', 'redteam-lab', 'redteam-agent', 'judge', 'learner')
INSTRUCTION = '结束前调用 mcp__stage_delivery__submit_stage_result，提交实际交付文件路径和限制；工具返回 needs_revision 时修正后再次提交。accepted 仅表示交付文件通过该阶段检查，不代表漏洞已验证。无法提供最小能力时如实报告受阻，不为获得 accepted 无限重试。不要伪造证据或为通过检查降低原有验收标准。'
SCHEMA = {'type':'object','properties':{'artifact':{'type':'string','description':'交付文件的绝对路径'},'summary':{'type':'string'},'limitations':{'type':'array','items':{'type':'string'}}},'required':['artifact','summary','limitations'],'additionalProperties':False}

def config(stage, root):
    return {'mcpServers':{'stage_delivery':{'command':'python3','args':[str(Path(__file__).resolve()),'serve','--stage',stage,'--root',str(Path(root).resolve())]}}}

def submit(stage, root, arguments):
    root=Path(root).resolve(); errors=[]; artifact=None; digest=None
    try:
        if stage not in STAGES: raise ValueError('未知阶段')
        if not isinstance(arguments.get('summary'),str) or not arguments['summary'].strip(): raise ValueError('需要简短交付说明')
        if not isinstance(arguments.get('limitations'),list) or any(not isinstance(v,str) for v in arguments['limitations']): raise ValueError('limitations 必须是字符串数组')
        artifact=Path(arguments['artifact']).resolve(strict=True)
        if not artifact.is_relative_to(root) or not artifact.is_file(): raise ValueError('交付文件必须位于本次指定输出目录内')
        if artifact.stat().st_size > 10*1024*1024: raise ValueError('交付文件超过 10 MiB')
        data=artifact.read_bytes();digest=hashlib.sha256(data).hexdigest()
        if stage=='learner':
            if not data.strip(): raise ValueError('经验文件为空')
        else:
            d=json.loads(data)
            if not isinstance(d,dict): raise ValueError('交付文件必须是 JSON 对象')
            if stage=='orchestrator':
                sys.path.insert(0,str(ROOT/'scripts/mine'))
                from check_report import check_report
                result=check_report(artifact)
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
                images=[p for p in artifact.parent.glob(artifact.name.replace('.director.json','')+'.*') if p.suffix in ('.webp','.png','.jpg','.svg') and p.stat().st_size>0]
                if not artifact.name.endswith('.director.json') or not images: raise ValueError('需要场景设计 .director.json 及同名非空图片')
            elif stage=='verify':
                status=d.get('verdict') or d.get('verification',{}).get('status') or d.get('status')
                if not status or not (d.get('finding_id') or d.get('id')): raise ValueError('验证报告缺少明确结论或候选问题编号')
                if status in ('blocked','inconclusive') and not arguments['limitations']: raise ValueError('受阻或不确定结论必须声明限制')
            elif stage=='redteam-lab':
                sys.path.insert(0,str(ROOT/'scripts/redteam'))
                from contracts import validate_scenario
                # 完整的来源绑定与隔离检查继续由构建执行器执行。
                validate_scenario(d, expected_finding_id=d.get('finding_id'), expected_finding_sha256=d.get('finding_sha256'), expected_source=d.get('source'))
            elif stage=='redteam-agent':
                if not d.get('status'): raise ValueError('红队结果缺少状态')
            elif stage=='judge':
                sys.path.insert(0,str(ROOT/'scripts/redteam'))
                from contracts import validate_verdict
                validate_verdict(d)
    except Exception as exc:
        errors.append(str(exc))
    receipt={'id':str(uuid.uuid4()),'stage':stage,'decision':'needs_revision' if errors else 'accepted','validation_scope':'artifact_contract','artifact':str(artifact) if artifact else None,'sha256':digest,'summary':arguments.get('summary'),'limitations':arguments.get('limitations'),'errors':errors,'checked_at':datetime.now(timezone.utc).isoformat(),'notice':'交付文件检查不替代动态验收、随机标记来源检查或人工验收；原有阶段门槛继续生效。'}
    directory=root/'.stage-submissions'/stage;directory.mkdir(parents=True,exist_ok=True)
    (directory/(receipt['id']+'.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt

def serve(stage, root):
    for line in sys.stdin:
        request=None
        try:
            request=json.loads(line);method=request.get('method'); ident=request.get('id')
            if ident is None: continue
            if method=='initialize': result={'protocolVersion':request.get('params',{}).get('protocolVersion','2024-11-05'),'capabilities':{'tools':{}},'serverInfo':{'name':'stage-delivery','version':'1.0'}}
            elif method=='ping': result={}
            elif method=='tools/list': result={'tools':[{'name':'submit_stage_result','description':f'提交 {stage} 阶段交付文件，返回具体修改意见或验收凭据；允许多次调用。','inputSchema':SCHEMA}]}
            elif method=='tools/call':
                params=request.get('params',{})
                if params.get('name')!='submit_stage_result': raise ValueError('未知工具')
                receipt=submit(stage,root,params.get('arguments',{}));result={'content':[{'type':'text','text':json.dumps(receipt,ensure_ascii=False)}],'isError':receipt['decision']!='accepted'}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'未知方法'}}),flush=True);continue
            print(json.dumps({'jsonrpc':'2.0','id':ident,'result':result}),flush=True)
        except Exception as exc:
            if isinstance(request,dict) and 'id' in request: print(json.dumps({'jsonrpc':'2.0','id':request['id'],'error':{'code':-32602,'message':str(exc)}}),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['config','serve','instruction']);parser.add_argument('--stage',choices=STAGES);parser.add_argument('--root');args=parser.parse_args()
    if args.mode=='instruction': print(INSTRUCTION)
    elif args.mode=='config': print(json.dumps(config(args.stage,args.root)))
    else: serve(args.stage,args.root)
if __name__=='__main__':main()
