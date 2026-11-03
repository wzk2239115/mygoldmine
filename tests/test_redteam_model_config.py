import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('redteam_model_config', ROOT / 'scripts/redteam/model_config.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_audit_provider_is_resolved_without_using_old_flint_service(tmp_path):
    file = tmp_path / 'providers.json'
    file.write_text(json.dumps({'provider': {'360-proxy': {'options': {'baseURL': 'https://provider.example/v1', 'apiKey': 'test-key'}}}}))
    result = module.resolve_model('', env={'MODEL': '360-proxy/deepseek/test'}, provider_file=file)
    assert result == ('deepseek/test', 'https://provider.example/v1', 'test-key')
    explicit = module.resolve_model('360-proxy/deepseek/test', 'https://explicit.example/v1', 'explicit-key', env={}, provider_file=file)
    assert explicit == ('deepseek/test', 'https://explicit.example/v1', 'explicit-key')


def test_missing_audit_provider_fails_instead_of_calling_flint(tmp_path):
    with pytest.raises(ValueError, match='未找到审计模型服务配置'):
        module.resolve_model('', env={}, provider_file=tmp_path / 'missing')
