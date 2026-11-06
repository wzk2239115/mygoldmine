import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "project_admission", ROOT / "scripts/workflow/project_admission.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_global_limit_fifo_and_release(tmp_path):
    def request(i):
        return module.update(tmp_path, "acquire", str(i), f"project-{i}", f"/task/{i}", os.getpid())

    assert all(request(i)["status"] == "active" for i in range(5))
    assert request(5)["position"] == 1
    assert request(6)["position"] == 2
    module.update(tmp_path, "release", "0", "project-0", "/task/0", os.getpid())
    assert request(6)["status"] == "queued"
    assert request(5)["status"] == "active"
    assert request(6)["status"] == "queued"


def test_simultaneous_requests_never_over_admit(tmp_path):
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        rows = list(
            pool.map(
                lambda i: module.update(tmp_path, "acquire", str(i), f"p{i}", "/task", os.getpid()),
                range(20),
            )
        )
    assert sum(x["status"] == "active" for x in rows) == 5
    saved = json.loads((tmp_path / ".state/project-admission/queue.json").read_text())
    assert len(saved["tickets"]) == 20


def test_deployment_existing_workflows_occupy_slots(tmp_path):
    for i in range(5):
        state = tmp_path / f"state{i}.json"
        state.write_text(
            json.dumps({"project": f"old{i}", "status": "running", "coordinatorPid": os.getpid()})
        )
        lock = tmp_path / f"runs/.node-retry-old{i}.lock"
        lock.mkdir(parents=True)
        (lock / "workflow-owner.json").write_text(json.dumps({"file": str(state)}))
    result = module.update(tmp_path, "acquire", "new", "new", "/task", os.getpid())
    assert result["status"] == "queued" and result["activeProjects"] == 5
