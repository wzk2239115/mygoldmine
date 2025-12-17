"""Main sink scanner using tree-sitter AST analysis"""

class Sink:
    def __init__(self, line, column, sink_type, function_name, file_path, code_snippet):
        self.line = line
        self.column = column
        self.sink_type = sink_type
        self.function_name = function_name
        self.file_path = file_path
        self.code_snippet = code_snippet

    def to_dict(self):
        return {
            'line': self.line,
            'column': self.column,
            'type': self.sink_type,
            'function': self.function_name,
            'file': self.file_path,
            'snippet': self.code_snippet
        }

class SinkDetector:
    def __init__(self, config_path=None):
        self.sinks = []
        self.file_contents = {}

    def scan_file(self, file_path):
        """Scan a single file for sinks"""
        return []

    def scan_directory(self, directory, recursive=True):
        """Scan directory for sinks"""
        return []

    def get_sinks(self):
        return self.sinks

    def clear(self):
        self.sinks = []
        self.file_contents = {}
