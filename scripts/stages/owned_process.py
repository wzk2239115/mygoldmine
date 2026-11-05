"""Run a bounded child session, cleaning up descendants when it times out."""

import os
import signal
import subprocess
from pathlib import Path


def _descendants(pid):
    result = []
    try:
        children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        for child in children:
            result.extend(_descendants(int(child)))
            result.append(int(child))
    except OSError:
        pass
    return result


def run_session(command, *, timeout, **kwargs):
    capture = kwargs.pop("capture_output", False)
    check = kwargs.pop("check", False)
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process = subprocess.Popen(command, start_new_session=True, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        descendants = _descendants(process.pid)
        identities = {}
        for pid in descendants:
            try:
                identities[pid] = Path(f"/proc/{pid}/stat").read_text().split(") ")[1].split()[19]
            except OSError:
                continue

        def terminate(sig):
            for pid, start in identities.items():
                try:
                    current = Path(f"/proc/{pid}/stat").read_text().split(") ")[1].split()[19]
                    if current == start:
                        os.kill(pid, sig)
                except (OSError, ProcessLookupError):
                    pass
            if process.poll() is None:
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass

        terminate(signal.SIGTERM)
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        terminate(signal.SIGKILL)
        process.communicate(timeout=5)
        raise error
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check:
        result.check_returncode()
    return result
