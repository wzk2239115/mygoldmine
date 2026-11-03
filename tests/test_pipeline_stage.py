import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pipeline_stage', ROOT / 'scripts/workflow/pipeline_stage.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_stage_records_actual_transition_and_candidate(tmp_path, monkeypatch):
    output = tmp_path / 'run.meta/pipeline-stage.json'
    monkeypatch.setenv('PIPELINE_STAGE_FILE', str(output))
    module.record_stage('environment')
    assert json.loads(output.read_text())['node'] == 'environment'
    module.record_stage('judge', 'F-1')
    state = json.loads(output.read_text())
    assert state['node'] == 'judge'
    assert state['candidate'] == 'F-1'
    assert not list(output.parent.glob('*.tmp'))


def test_standalone_redteam_does_not_require_stage_file(monkeypatch):
    monkeypatch.delenv('PIPELINE_STAGE_FILE', raising=False)
    module.record_stage('redteam-lab')


def test_visual_stage_is_only_recorded_by_supervisor():
    source = (Path(__file__).resolve().parents[1] / "run.sh").read_text()
    supervisor = source.index('if [ "$MODE" = "supervise" ]; then')
    visual = source.index("        set_stage visual")
    assert visual > supervisor
    assert source.count("set_stage visual") == 1
    assert 'set_stage finished' not in source
