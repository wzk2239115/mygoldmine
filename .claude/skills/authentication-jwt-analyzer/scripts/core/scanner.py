"""
JWT Sink Scanner: Core scanning engine for detecting JWT authentication operations.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
from dataclasses import dataclass, asdict

from .parser_manager import ParserManager


@dataclass
class Finding:
    """Represents a JWT sink finding."""
    file: str
    line: int
    column: int
    function_name: str
    code_snippet: str
    severity: str = "HIGH"
    language: str = ""
    message: str = ""

    def to_dict(self) -> Dict:
        """Convert finding to dictionary."""
        return asdict(self)


class JWTSinkScanner:
    """Scanner for detecting JWT authentication sinks in code."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the JWT sink scanner.

        Args:
            config_path: Path to languages.yaml config
        """
        self.parser_manager = ParserManager(config_path)
        self.findings: List[Finding] = []
        self.queries: Dict[str, str] = {}
        self._load_queries()

    def _load_queries(self):
        """Load all JWT sink detection queries from language directories."""
        base_path = Path(__file__).parent.parent / "languages"

        for lang_dir in base_path.iterdir():
            if lang_dir.is_dir():
                query_file = lang_dir / "queries" / self.parser_manager.get_query_file(lang_dir.name)
                if query_file.exists():
                    with open(query_file, 'r') as f:
                        self.queries[lang_dir.name] = f.read()

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()

        for lang in self.parser_manager.get_supported_languages():
            if ext in self.parser_manager.get_extensions(lang):
                return lang

        return None

    def _extract_code_snippet(self, source: str, line: int, context_lines: int = 2) -> str:
        """Extract code snippet around the finding."""
        lines = source.split('\n')
        start = max(0, line - context_lines - 1)
        end = min(len(lines), line + context_lines)
        snippet = '\n'.join(lines[start:end])
        return snippet.strip()

    def _get_function_name(self, node) -> str:
        """Extract function name from AST node."""
        # Try different node types for function calls
        if hasattr(node, 'child_by_field_name'):
            func = node.child_by_field_name('function')
            if func:
                return func.text.decode() if isinstance(func.text, bytes) else func.text

        if hasattr(node, 'text'):
            text = node.text.decode() if isinstance(node.text, bytes) else node.text
            # Extract function name from call expression
            if '(' in text:
                return text.split('(')[0].strip()
            return text

        return "unknown"

    def scan_file(self, file_path: str) -> List[Finding]:
        """
        Scan a single file for JWT sinks.

        Args:
            file_path: Path to the file to scan

        Returns:
            List of findings in this file
        """
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            return []

        language = self._detect_language(file_path)
        if not language:
            return []

        parser = self.parser_manager.get_parser(language)
        if not parser:
            return []

        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    source_code = f.read()
            except Exception as e:
                print(f"Warning: Could not read file {file_path}: {e}")
                return []

        # Parse the file
        try:
            tree = parser.parse(source_code.encode('utf-8'))
        except Exception as e:
            print(f"Warning: Could not parse file {file_path}: {e}")
            return []

        # Get or compile query
        if language not in self.queries:
            print(f"Warning: No query file for language {language}")
            return []

        file_findings = self._find_jwt_sinks(
            file_path, source_code, tree, language, self.queries[language]
        )

        self.findings.extend(file_findings)
        return file_findings

    def _find_jwt_sinks(
        self,
        file_path: str,
        source_code: str,
        tree,
        language: str,
        query_str: str
    ) -> List[Finding]:
        """Find JWT sinks using tree-sitter queries."""
        findings = []

        try:
            # Compile and execute the query
            from tree_sitter import Query, QueryCursor
            lang_obj = self.parser_manager.languages.get(language)

            if not lang_obj:
                return findings

            query = Query(lang_obj, query_str)
            cursor = QueryCursor(query)
            captures_dict = cursor.captures(tree.root_node)

            # Process captures - captures is a dict with capture names as keys and lists of nodes as values
            if "jwt_sink" in captures_dict:
                for node in captures_dict["jwt_sink"]:
                    line = node.start_point[0]
                    column = node.start_point[1]

                    finding = Finding(
                        file=file_path,
                        line=line + 1,  # Convert to 1-based indexing
                        column=column,
                        function_name=self._get_function_name(node),
                        code_snippet=self._extract_code_snippet(source_code, line),
                        language=language,
                        message=f"JWT authentication operation detected: {node.type}"
                    )
                    findings.append(finding)

        except Exception as e:
            print(f"Warning: Error querying {file_path}: {e}")

        return findings

    def scan_directory(self, directory: str) -> List[Finding]:
        """
        Scan all supported files in a directory.

        Args:
            directory: Directory to scan recursively

        Returns:
            List of all findings
        """
        if not os.path.isdir(directory):
            print(f"Warning: Directory not found: {directory}")
            return []

        supported_extensions = set()
        for lang in self.parser_manager.get_supported_languages():
            supported_extensions.update(self.parser_manager.get_extensions(lang))

        # Find all supported files
        for root, dirs, files in os.walk(directory):
            # Skip common non-code directories
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}]

            for file in files:
                if any(file.endswith(ext) for ext in supported_extensions):
                    file_path = os.path.join(root, file)
                    self.scan_file(file_path)

        return self.findings

    def get_findings(self) -> List[Finding]:
        """Get all findings from the current scan."""
        return self.findings

    def clear_findings(self):
        """Clear all findings."""
        self.findings = []

    def get_summary(self) -> Dict:
        """Get summary statistics of findings."""
        by_language = {}
        by_severity = {}

        for finding in self.findings:
            # Count by language
            lang = finding.language
            by_language[lang] = by_language.get(lang, 0) + 1

            # Count by severity
            sev = finding.severity
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "total_findings": len(self.findings),
            "by_language": by_language,
            "by_severity": by_severity
        }
