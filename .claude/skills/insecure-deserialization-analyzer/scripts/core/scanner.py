"""
Scanner Engine - Main scanning engine for detecting insecure deserialization sinks.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
from .parser_manager import ParserManager


class Sink:
    """Represents a detected deserialization sink."""

    MAX_CONTEXT_LENGTH = 100  # Maximum length for context output

    def __init__(self, file_path: str, line: int, column: int, function: str, context: str):
        self.file_path = file_path
        self.line = line
        self.column = column
        self.function = function
        self.context = context

    def _truncate_context(self, text: str, max_length: int = MAX_CONTEXT_LENGTH) -> str:
        """Truncate context to max_length characters, adding ... if truncated."""
        if len(text) > max_length:
            return text[:max_length - 3] + '...'
        return text

    def to_dict(self) -> Dict:
        return {
            'file': self.file_path,
            'line': self.line,
            'column': self.column,
            'function': self.function,
            'context': self._truncate_context(self.context)
        }


class Scanner:
    """Main scanner for detecting insecure deserialization sinks."""

    # Deserialization sinks patterns for each language
    SINKS = {
        'php': {
            'unserialize': {'pattern': r'unserialize\s*\(', 'danger': 'critical'},
            '__wakeup': {'pattern': r'function\s+__wakeup', 'danger': 'critical'},
            '__destruct': {'pattern': r'function\s+__destruct', 'danger': 'critical'},
        },
        'python': {
            'pickle.loads': {'pattern': r'pickle\.loads\s*\(', 'danger': 'critical'},
            'pickle.load': {'pattern': r'pickle\.load\s*\(', 'danger': 'critical'},
            'yaml.load': {'pattern': r'yaml\.load\s*\(', 'danger': 'critical'},
            'yaml.unsafe_load': {'pattern': r'yaml\.unsafe_load\s*\(', 'danger': 'critical'},
            'dill.loads': {'pattern': r'dill\.loads\s*\(', 'danger': 'critical'},
            'cloudpickle.loads': {'pattern': r'cloudpickle\.loads\s*\(', 'danger': 'critical'},
        },
        'java': {
            'ObjectInputStream.readObject': {'pattern': r'readObject\s*\(', 'danger': 'critical'},
            'ObjectInputStream.readUnshared': {'pattern': r'readUnshared\s*\(', 'danger': 'critical'},
            'Jackson.readValue': {'pattern': r'readValue\s*\(', 'danger': 'high'},
            'XStream.fromXML': {'pattern': r'fromXML\s*\(', 'danger': 'critical'},
            'snakeyaml.load': {'pattern': r'load\s*\(', 'danger': 'critical'},
        },
        'javascript': {
            'vm.runInContext': {'pattern': r'vm\.runInContext\s*\(', 'danger': 'critical'},
            'vm.runInNewContext': {'pattern': r'vm\.runInNewContext\s*\(', 'danger': 'critical'},
            'eval': {'pattern': r'eval\s*\(', 'danger': 'high'},
            'Function': {'pattern': r'new\s+Function\s*\(', 'danger': 'high'},
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the scanner.

        Args:
            config_path: Path to languages.yaml config file
        """
        self.parser_manager = ParserManager(config_path)
        self.sinks = []

    def scan_file(self, file_path: str, language: Optional[str] = None) -> List[Sink]:
        """
        Scan a single file for deserialization sinks.

        Args:
            file_path: Path to the file to scan
            language: Language (auto-detected if not provided)

        Returns:
            List of detected sinks
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Auto-detect language if not provided
        if language is None:
            language = self._detect_language(file_path)

        if language is None:
            return []

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return []

        # Get parser for the language
        parser = self.parser_manager.get_parser(language)
        if parser is None:
            return self._simple_pattern_scan(file_path, content, language)

        # Use tree-sitter for parsing and querying
        return self._tree_sitter_scan(file_path, content, language, parser)

    def scan_directory(self, directory: str, language: Optional[str] = None, recursive: bool = True) -> List[Sink]:
        """
        Scan a directory for deserialization sinks.

        Args:
            directory: Directory to scan
            language: Language filter (scan all if not provided)
            recursive: Recursively scan subdirectories

        Returns:
            List of detected sinks
        """
        if not os.path.isdir(directory):
            raise NotADirectoryError(f"Directory not found: {directory}")

        results = []

        # Get supported extensions
        if language:
            extensions = self.parser_manager.get_extensions_for_language(language)
        else:
            extensions = []
            for lang in self.parser_manager.get_supported_languages():
                extensions.extend(self.parser_manager.get_extensions_for_language(lang))

        # Scan files
        if recursive:
            pattern = f"**/*"
            files = Path(directory).glob(pattern)
        else:
            files = os.listdir(directory)
            files = [os.path.join(directory, f) for f in files]

        for file_path in files:
            if isinstance(file_path, Path):
                file_path = str(file_path)

            if not os.path.isfile(file_path):
                continue

            # Check if file extension matches
            if extensions and not any(file_path.endswith(ext) for ext in extensions):
                continue

            try:
                sinks = self.scan_file(file_path, language)
                results.extend(sinks)
            except Exception as e:
                print(f"Error scanning file {file_path}: {e}")

        return results

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Auto-detect language from file extension."""
        ext = os.path.splitext(file_path)[1].lower()

        for lang in self.parser_manager.get_supported_languages():
            extensions = self.parser_manager.get_extensions_for_language(lang)
            if ext in extensions:
                return lang

        return None

    def _simple_pattern_scan(self, file_path: str, content: str, language: str) -> List[Sink]:
        """
        Fallback pattern-based scanning when tree-sitter parser is not available.
        """
        import re

        results = []
        sinks = self.SINKS.get(language, {})

        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for sink_name, sink_info in sinks.items():
                pattern = sink_info.get('pattern', '')
                if re.search(pattern, line):
                    results.append(Sink(
                        file_path=file_path,
                        line=line_num,
                        column=0,
                        function=sink_name,
                        context=line.strip()
                    ))

        return results

    def _tree_sitter_scan(self, file_path: str, content: str, language: str, parser: object) -> List[Sink]:
        """
        Use tree-sitter queries to detect sinks.
        """
        results = []

        try:
            # Parse the file
            tree = parser.parse(content.encode('utf-8'))

            # Load and run query
            query_path = self._get_query_path(language)
            if os.path.exists(query_path):
                query_results = self._run_query(parser, tree, query_path, language)
                for line, column, function, context in query_results:
                    results.append(Sink(
                        file_path=file_path,
                        line=line,
                        column=column,
                        function=function,
                        context=context
                    ))
            else:
                # Fallback to pattern-based scanning
                results = self._simple_pattern_scan(file_path, content, language)

        except Exception as e:
            # Fallback to pattern-based scanning
            print(f"Tree-sitter scan failed for {file_path}, using pattern-based scan: {e}")
            results = self._simple_pattern_scan(file_path, content, language)

        return results

    def _get_query_path(self, language: str) -> str:
        """Get path to tree-sitter query file for language."""
        return os.path.join(
            os.path.dirname(__file__),
            '..',
            'languages',
            language,
            'queries',
            'deserialization_sinks.scm'
        )

    def _run_query(self, parser: object, tree: object, query_path: str, language: str) -> List:
        """
        Run a tree-sitter query on the parsed tree.
        Returns list of (line, column, function, context)
        """
        try:
            from tree_sitter import Query
            import tree_sitter

            # Get language object
            try:
                from tree_sitter_languages import get_language
                lang = get_language(language)
            except:
                # Fallback
                return []

            # Load query
            with open(query_path, 'r', encoding='utf-8') as f:
                query_string = f.read()

            query = lang.query(query_string)
            captures = query.captures(tree.root_node)

            results = []
            for node, capture_name in captures:
                if node.type == 'identifier' or 'call' in node.type.lower():
                    line = node.start_point[0] + 1
                    column = node.start_point[1]
                    results.append((line, column, capture_name, node.text.decode('utf-8') if isinstance(node.text, bytes) else str(node.text)))

            return results

        except Exception as e:
            print(f"Error running query: {e}")
            return []

    def get_results(self) -> List[Sink]:
        """Get all detected sinks."""
        return self.sinks
