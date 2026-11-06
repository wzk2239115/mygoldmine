#!/usr/bin/env python3
"""把同一轮蓝队确认及实际产物快照交给场景构建者。"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from source_binding import source_binding

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from delivery_contract import runtime_environment, validate_verification_report  # noqa: E402

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,100}')
MAX_FILE = 10 * 1024 * 1024
MAX_TOTAL = 50 * 1024 * 1024


def read(file):
    return json.loads(Path(file).read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def write(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(file)


def bounded(file, root):
    file, root = Path(file), Path(root).resolve()
    if file.is_symlink() or not file.resolve().is_relative_to(root) or not file.is_file():
        raise ValueError('产物路径越界、符号链接或文件缺失')
    if file.stat().st_size > MAX_FILE:
        raise ValueError('单个蓝队产物超过 10 MiB')
    data = file.read_bytes()
    if len(data) > MAX_FILE:
        raise ValueError('单个蓝队产物超过 10 MiB')
    return data


def blue_source(run, project):
    paths = list(Path(str(run) + '.meta/node-retries/verify').glob('*/attempt.json'))
    attempts = sorted((read(p) for p in paths), key=lambda item: item['startedAt'])
    if attempts:
        latest = attempts[-1]
        if latest.get('project') != project or latest.get('runId') != run.name:
            raise ValueError('蓝队重跑记录不属于当前项目和审计运行')
        if latest.get('status') == 'running':
            raise ValueError('蓝队验证正在运行，请等待本批次结束')
        if latest.get('status') != 'completed':
            raise ValueError('最新蓝队批次未完成，不能回退使用旧批次')
        workspace = Path(latest['workspace']).resolve()
        if not workspace.is_relative_to(Path(str(run) + '.meta/node-retries/verify').resolve()):
            raise ValueError('蓝队输出目录不属于本轮审计')
        if (workspace / 'audit-report.json').read_bytes() != (run / 'audit-report.json').read_bytes():
            raise ValueError('蓝队输入的审计报告已过期，请重新验证')
        return workspace / 'verify/agent', latest['id']
    original = run / 'verify/agent'
    plan = original / 'selection.json'
    if plan.exists() and read(plan).get('report_sha256') != sha((run / 'audit-report.json').read_bytes()):
        raise ValueError('蓝队输入的审计报告已过期，请重新验证')
    return original, 'original'


def collect(run, project, maximum=5, severities=('critical', 'high'), only='', reuse=False, refresh=False, drain=False):
    if not isinstance(project, str) or not ID.fullmatch(project):
        raise ValueError('项目编号无效')
    run = Path(run).resolve()
    repo = run.parents[2]
    report_bytes = (run / 'audit-report.json').read_bytes()
    report = json.loads(report_bytes)
    if not isinstance(report, dict):
        raise ValueError('审计报告必须为对象')
    report_project = report.get('project')
    if report_project is not None and (
        not isinstance(report_project, str) or report_project.casefold() != project.casefold()
    ):
        raise ValueError('审计报告不属于当前项目')
    if not any(key in report for key in ['findings', 'vulnerabilities']):
        raise ValueError('审计报告缺少候选列表')
    rows = report.get('findings', report.get('vulnerabilities', []))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('审计报告候选列表无效')
    originals = {}
    for row in rows:
        identifier = row.get('id') or row.get('finding_id')
        if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in originals:
            raise ValueError('审计报告含无效或重复的候选编号')
        originals[identifier] = row
    requested = None
    if reuse and (run / 'redteam/candidates.json').exists():
        requested = []
        for item in read(run / 'redteam/candidates.json')['candidates']:
            identifier = item['id']
            if item.get('project') != project or item.get('run_id') != run.name or identifier not in originals or identifier in requested:
                raise ValueError('红队候选清单含跨运行、重复或无效编号')
            requested.append(identifier)
    if refresh:
        requested = None
    try:
        source, attempt = blue_source(run, project)
        summary = read(source / 'summary.json')
        if summary.get('project') not in (None, project):
            raise ValueError('蓝队汇总不属于当前项目')
        if summary.get('status') in ['running', 'pending'] or summary.get('processed', 0) < summary.get('selected', 0):
            raise ValueError('蓝队验证尚未结束，不能提前使用部分结果')
        manifest = read(repo / 'env' / project / 'env-manifest.json')
        if not manifest.get('image_id'):
            raise ValueError('环境清单缺少镜像编号，无法核对蓝队执行版本')
        source_dir = manifest.get('source')
        if source_dir and (Path(source_dir) / '.git').exists() and manifest.get('commit'):
            revision = subprocess.run(['git', '-C', source_dir, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=10)
            if revision.returncode or not revision.stdout.strip().startswith(str(manifest['commit'])):
                raise ValueError('源码版本已变化，需要重新构建环境并进行蓝队验证')
        if manifest.get('commit'):
            binding = {'commit': str(manifest['commit'])}
        else:
            directory = Path(source_dir) if source_dir else repo / 'targets' / project
            if not directory.is_dir():
                raise ValueError('缺少源码目录，无法绑定蓝队交付版本')
            binding = source_binding(directory.resolve(), repo / 'env' / project / 'env-manifest.json')
        common_error = ''
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        source, attempt, manifest, summary = None, '', {}, {}
        binding = {}
        common_error = str(exc)
    candidates, excluded, deferred, payloads = [], [], [], {}
    for identifier, finding in originals.items():
        if only and identifier != only:
            deferred.append({'id': identifier, 'reason_code': 'finding_filter', 'reason': '未指定此候选，仍待处理', 'state': 'pending'})
            continue
        if requested is not None and identifier not in requested:
            deferred.append({'id': identifier, 'reason_code': 'previous_selection', 'reason': '不在复用范围，仍保留在候选总表', 'state': 'pending'})
            continue
        raw_severity = str(finding.get('severity') or finding.get('severity_raw') or 'info').strip().lower()
        raw_severity = 'critical' if raw_severity == 'crit' else 'medium' if raw_severity.startswith('moderate') else raw_severity
        severity = next((level for level in ['critical', 'high', 'medium', 'low', 'info'] if raw_severity.startswith(level)), raw_severity)
        if requested is None and severity not in severities:
            deferred.append({'id': identifier, 'reason_code': 'severity_filter', 'reason': '不在本批次严重度范围，仍待处理', 'state': 'pending'})
            continue
        error, verdict = common_error, ''
        files = {}
        try:
            if error:
                raise ValueError(error)
            result = source / identifier
            if result.is_symlink() or not result.resolve().is_relative_to(source.resolve()):
                raise ValueError('候选产物目录越界')
            raw_report = bounded(result / 'verify-report.json', source)
            verified = json.loads(raw_report)
            verdict = verified.get('verdict')
            if verified.get('finding_id') != identifier or verified.get('project') != project:
                raise ValueError('蓝队报告的项目或候选编号不匹配')
            if verdict != 'confirmed':
                raise ValueError('蓝队尚未确认：' + str(verdict or '无结论'))
            if verified.get('synthesized') or verified.get('evidence_class') != 'runtime':
                raise ValueError('缺少真实运行确认，不能仅凭合成报告或静态分析进入红队')
            if verified.get('image_id') != manifest['image_id'] or verified.get('image') != manifest.get('image'):
                raise ValueError('蓝队执行镜像与当前环境清单不一致')
            materialized = json.loads(bounded(result / 'finding.json', source))
            if any(materialized.get(k) != v for k, v in finding.items()):
                raise ValueError('蓝队验证的候选内容与当前审计报告不一致')
            files['verify-report.json'] = raw_report
            files['finding.json'] = json.dumps(finding, ensure_ascii=False).encode()
            files['verify-report.md'] = bounded(result / 'verify-report.md', source)
            validate_verification_report(result / 'verify-report.json', result)
            def collect_harness(folder):
                snapshot = runtime_environment(folder)
                if snapshot:
                    prefix = folder.relative_to(result).as_posix()
                    files[prefix + '/runtime-environment.json'] = json.dumps(snapshot, ensure_ascii=False).encode()
                    files[prefix + '/pyvenv.cfg'] = bounded(folder / 'pyvenv.cfg', result)
                    return
                for p in sorted(folder.iterdir()):
                    if p.is_symlink():
                        raise ValueError('验证脚本包含符号链接')
                    if p.is_dir():
                        collect_harness(p)
                    elif p.is_file():
                        files[p.relative_to(result).as_posix()] = bounded(p, result)
            if (result / 'harness').is_dir():
                collect_harness(result / 'harness')
            if not any(name.startswith('harness/') for name in files):
                raise ValueError('蓝队确认缺少验证脚本')
            evidence = verified.get('evidence') or []
            if not isinstance(evidence, list) or not evidence:
                raise ValueError('蓝队确认缺少证据文件')
            for name in evidence:
                if not isinstance(name, str):
                    raise ValueError('证据路径不是字符串')
                relative = Path(name)
                if not relative.parts or relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('证据路径越界')
                p = result / relative if relative.parts[0] == 'evidence' else result / 'evidence' / relative
                files[p.relative_to(result).as_posix()] = bounded(p, result / 'evidence')
            for name in ['verdict.json', 'harness.stdout.log', 'harness.stderr.log']:
                if (result / name).exists():
                    files[name] = bounded(result / name, result)
            if sum(map(len, files.values())) > MAX_TOTAL:
                raise ValueError('单条蓝队交付超过 50 MiB')
            if not drain and len(candidates) >= maximum:
                raise ValueError('已确认，但超出本次候选数量上限')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            error = str(exc)
        if error:
            excluded.append({'id': identifier, 'title': finding.get('title', identifier), 'blue_verdict': verdict, 'reason': error})
            continue
        candidates.append({'project': project, 'id': identifier, 'run_id': run.name, 'title': finding.get('title', identifier)})
        payloads[identifier] = files
    selection = {'schema_version': 1, 'project': project, 'run_id': run.name, 'report_sha256': sha(report_bytes),
                 'report': str(run / 'audit-report.json'), 'max': maximum, 'severity': list(severities), 'total_findings': len(originals), 'matched': len(candidates) + len(excluded),
                 'blue_attempt_id': attempt, 'blue_root': str(source) if source else '', 'selected': len(candidates),
                 'candidates': candidates, 'excluded': excluded, 'deferred': deferred, 'accounted': len(candidates)+len(excluded)+len(deferred), 'gate_reason': common_error,
                 'source': binding, 'image_id': manifest.get('image_id')}
    return selection, payloads, originals


def prepare(run, project, output, **options):
    selection, payloads, originals = collect(run, project, **options)
    output = Path(output).resolve()
    for candidate in selection['candidates']:
        identifier = candidate['id']
        root = output / 'blue-handoff' / identifier
        if root.exists():
            raise ValueError('蓝队交付快照已存在，拒绝覆盖')
        files = payloads[identifier]
        for relative, data in files.items():
            p = root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        context = {'schema_version': 1, 'role': 'builder_only', 'project': project, 'run_id': selection['run_id'],
                   'finding_id': identifier, 'audit_finding_sha256': canonical(originals[identifier]),
                   'report_sha256': selection['report_sha256'], 'blue_attempt_id': selection['blue_attempt_id'],
                   'source': selection['source'], 'image_id': selection['image_id'],
                   'files': [{'path': name, 'sha256': sha(data)} for name, data in files.items()]}
        write(root / 'handoff.json', context)
        candidate['blue_handoff'] = str(root / 'handoff.json')
    write(output / 'candidates.json', {k: selection[k] for k in ['project', 'run_id', 'candidates']})
    write(output / 'selection.json', selection)
    return selection


def validate_packet(file, finding, project, source=None):
    file = Path(file).resolve()
    data = read(file)
    if data.get('role') != 'builder_only' or data.get('project') != project or data.get('finding_id') != (finding.get('id') or finding.get('finding_id')):
        raise ValueError('蓝队交付身份不匹配')
    if data.get('audit_finding_sha256') != canonical(finding):
        raise ValueError('蓝队交付与候选内容不匹配')
    if source and data.get('source') != source:
        raise ValueError('蓝队交付与场景源码版本不匹配')
    names = set()
    total = 0
    for entry in data.get('files', []):
        name = entry['path']
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or name in names:
            raise ValueError('蓝队交付文件清单无效')
        names.add(name)
        content = bounded(file.parent / relative, file.parent)
        total += len(content)
        if total > MAX_TOTAL or sha(content) != entry['sha256']:
            raise ValueError('蓝队交付文件被修改或超出大小限制')
    if not {'verify-report.json', 'verify-report.md', 'finding.json'}.issubset(names) or not any(n.startswith('harness/') for n in names) or not any(n.startswith('evidence/') for n in names):
        raise ValueError('蓝队交付缺少报告、脚本或证据')
    verified = read(file.parent / 'verify-report.json')
    if verified.get('finding_id') != data['finding_id'] or verified.get('project') != project or verified.get('image_id') != data.get('image_id'):
        raise ValueError('蓝队报告与交付身份或镜像编号不匹配')
    if canonical(read(file.parent / 'finding.json')) != canonical(finding):
        raise ValueError('蓝队交付的候选文件不匹配')
    if verified.get('verdict') != 'confirmed' or verified.get('evidence_class') != 'runtime' or verified.get('synthesized'):
        raise ValueError('蓝队交付不是有效运行确认')
    return data


def copy_packet(file, destination, finding, project, source):
    data = validate_packet(file, finding, project, source)
    destination = Path(destination)
    if destination.exists():
        raise ValueError('本场景已有蓝队交付快照，拒绝覆盖')
    for entry in data['files']:
        p = destination / entry['path']
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bounded(Path(file).parent / entry['path'], Path(file).parent))
    write(destination / 'handoff.json', data)
    validate_packet(destination / 'handoff.json', finding, project, source)
    return destination / 'handoff.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--output')
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--refresh-selection', action='store_true')
    parser.add_argument('--drain', action='store_true')
    parser.add_argument('--max', type=int, default=5)
    parser.add_argument('--severity', default='critical,high')
    parser.add_argument('--finding-id', default='')
    parser.add_argument('--reuse-selection', action='store_true')
    args = parser.parse_args()
    if any(value not in ['critical', 'high', 'medium', 'low', 'info'] for value in args.severity.split(',')):
        parser.error('严重度参数无效')
    if args.max < 1:
        parser.error('--max 必须为正整数')
    options = {'maximum': args.max, 'severities': args.severity.split(','), 'only': args.finding_id, 'reuse': args.reuse_selection, 'refresh': args.refresh_selection, 'drain': args.drain}
    try:
        result = collect(args.run_dir, args.project, **options)[0] if args.inspect else prepare(args.run_dir, args.project, args.output, **options)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
