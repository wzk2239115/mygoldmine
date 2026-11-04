#!/usr/bin/env python3
"""调度相互隔离的蓝队候选任务，原子保存进度并回收任务进程组。"""
import argparse
import concurrent.futures
import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def write(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--jobs', type=int, required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 10:
        parser.error('并发数必须在 1 到 10 之间')
    output = Path(args.output)
    tasks = output / 'tasks'
    tasks.mkdir(exist_ok=True)
    jobs = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line]
    stopped = threading.Event()
    lock = threading.Lock()
    processes = {}
    cancelled_groups = set()
    cancelled_at = []

    def cancel(signum, frame):
        stopped.set()
        if not cancelled_at:
            cancelled_at.append(time.monotonic())
        with lock:
            for process in processes.values():
                cancelled_groups.add(process.pid)
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)

    def execute(job):
        sid, entry = job['id'], job['entry']
        progress = {**job, 'state': 'queued', 'concurrency': args.jobs,
                    'finding_id': sid, 'title': entry.get('title', ''),
                    'agent_log': str(output / 'logs' / f'{sid}.agent.log'),
                    'report_path': str(output / sid / 'verify-report.json')}
        state_path = tasks / f'{sid}.json'
        def update(state):
            progress['state'] = state
            progress['updatedAt'] = datetime.now(timezone.utc).isoformat()
            write(state_path, progress)
        result_path = output / sid / 'result.json'
        rc = 130
        if not stopped.is_set():
            update('running')
            with lock:
                if not stopped.is_set():
                    entry_path = output / 'inputs' / sid / 'entry.json'
                    entry_path.parent.mkdir(parents=True, exist_ok=True)
                    write(entry_path, entry)
                    process = subprocess.Popen(['bash', '-c', 'set -uo pipefail; verify_one "$(cat "$1")" "$2"',
                                                'verify-worker', str(entry_path), sid], start_new_session=True)
                    processes[sid] = process
                else:
                    process = None
            if process:
                while True:
                    try:
                        rc = process.wait(timeout=.2)
                        break
                    except subprocess.TimeoutExpired:
                        if stopped.is_set():
                            try:
                                rc = process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                try:
                                    os.killpg(process.pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass
                                rc = process.wait()
                            break
                with lock:
                    processes.pop(sid, None)
        if not result_path.exists():
            write(result_path, {'finding_id': sid, 'original_id': entry.get('orig_id'),
                  'source_index': entry['index'], 'title': entry.get('title', ''),
                  'severity': entry.get('severity', ''), 'status': 'worker_interrupted' if stopped.is_set() else 'worker_failed',
                  'verdict': 'blocked', 'reason': '候选任务已中断' if stopped.is_set() else f'候选任务异常退出（退出码 {rc}）',
                  'agent_return_code': rc, 'agent_log': progress['agent_log'], 'report_path': None})
        result = json.loads(result_path.read_text())
        progress.update({k: result.get(k) for k in ['status', 'verdict', 'reason', 'report_path']})
        update('cancelled' if stopped.is_set() else 'completed' if rc == 0 else 'failed')
        return result

    # 先登记全部排队任务，使尚未启动的候选也能出现在界面中。
    for job in jobs:
        write(tasks / f'{job["id"]}.json', {**job, 'finding_id': job['id'], 'title': job['entry'].get('title', ''),
              'state': 'queued', 'concurrency': args.jobs})
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(execute, jobs))
    if stopped.is_set():
        # 组长退出不代表全部后代已退出；给执行器清理容器的时间，再回收残留进程。
        time.sleep(max(0, cancelled_at[0] + 5 - time.monotonic()))
        for group in cancelled_groups:
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
    write(output / '.parallel-results.json', results)
    return 130 if stopped.is_set() else 0


if __name__ == '__main__':
    raise SystemExit(main())
