#!/usr/bin/env python3
import json, sys
from pathlib import Path

SCAN = Path('/vol1/1000/mygoldmine-benchmark/2026-11-17/results/codex-security/sol')
PLUGIN = Path('/vol1/1000/mygoldmine-benchmark/2026-11-17/tools/codex-cli/node_modules/@openai/codex-security/_bundled_plugin')
sys.path.insert(0, str(PLUGIN / 'scripts'))

draft = json.loads((SCAN / 'drafts' / 'final-draft.json').read_text())
manifest = draft['manifest']
findings = draft['findings']
scan_id = manifest['scan']['id']

findings['documentType'] = 'codex-security.findings'
findings['schemaVersion'] = '1.0'
findings['scanId'] = scan_id
manifest['documentType'] = 'codex-security.scan-manifest'
manifest['schemaVersion'] = '1.0'

(SCAN / 'findings.json').write_text(json.dumps(findings, indent=2) + '\n')
(SCAN / 'scan-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('published canonical files:', len(findings['findings']), 'findings')
