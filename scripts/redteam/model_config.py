"""为红队解析与审计相同的模型服务配置，不输出密钥。"""
import json
import os
from pathlib import Path

DEFAULT_MODEL = '360-proxy/deepseek/deepseek-v4.1-flash'


def resolve_model(model='', base_url='', api_key='', *, env=None, provider_file=None):
    env = os.environ if env is None else env
    model = model or env.get('REDTEAM_MODEL') or env.get('MODEL') or DEFAULT_MODEL
    provider_file = Path(provider_file or Path.home() / '.config/opencode/opencode.json')
    try:
        providers = json.loads(provider_file.read_text()).get('provider', {})
    except (OSError, ValueError):
        providers = {}
    provider, separator, name = model.partition('/')
    options = providers.get(provider, {}).get('options', {}) if separator else {}
    if options:
        model = name
        base_url = base_url or options.get('baseURL', '')
        api_key = api_key or options.get('apiKey', '')
    if provider == '360-proxy' and not options:
        raise ValueError('未找到审计模型服务配置，请检查已有的模型服务设置')
    base_url = base_url or env.get('OPENAI_BASE_URL', '')
    api_key = api_key or env.get('OPENAI_API_KEY', '')
    if model == 'flint' and not base_url:
        base_url = 'http://100.81.81.75:8081/v1'
    if not base_url:
        raise ValueError('模型服务地址未配置，请配置对应服务或指定红队服务地址')
    return model, base_url, api_key or 'local'
