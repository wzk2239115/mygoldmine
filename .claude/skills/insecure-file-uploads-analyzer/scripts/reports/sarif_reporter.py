"""SARIF Report Generator"""
import json
from pathlib import Path

class SARIFReporter:
    def __init__(self):
        self.sinks = []

    def add_sinks(self, sinks):
        self.sinks.extend(sinks)

    def generate_report(self, output_file=None):
        report = {'$schema': 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json', 'version': '2.1.0', 'runs': []}
        json_str = json.dumps(report, indent=2)
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                f.write(json_str)
        return json_str
