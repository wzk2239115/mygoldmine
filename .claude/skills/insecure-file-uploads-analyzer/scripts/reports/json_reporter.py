"""JSON Report Generator"""
import json
from pathlib import Path

class JSONReporter:
    def __init__(self):
        self.report_data = {'sinks': [], 'summary': {'total': 0, 'by_type': {}, 'by_file': {}}}

    def add_sinks(self, sinks):
        for sink in sinks:
            self.report_data['sinks'].append(sink.to_dict())

    def generate_report(self, output_file=None):
        self.report_data['summary']['total'] = len(self.report_data['sinks'])
        json_str = json.dumps(self.report_data, indent=2)
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                f.write(json_str)
        return json_str
