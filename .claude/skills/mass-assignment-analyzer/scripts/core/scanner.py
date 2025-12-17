"""
Scanner: Main engine for scanning code and detecting mass assignment sinks
"""
import os
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
import json

from .parser_manager import ParserManager


@dataclass
class Finding:
    """Represents a detected mass assignment sink"""
    file: str
    line: int
    column: int
    type: str
    code: str
    message: str
    severity: str = "HIGH"

    def get_truncated_code(self, max_length: int = 150) -> str:
        """Get code truncated to max_length characters"""
        if len(self.code) > max_length:
            return self.code[:max_length] + '...(truncated)'
        return self.code

    def to_dict(self) -> dict:
        """Convert finding to dictionary"""
        result = asdict(self)
        # Limit code field to 150 characters
        result['code'] = self.get_truncated_code(150)
        return result


class Scanner:
    """Main scanner for detecting mass assignment vulnerabilities"""

    def __init__(self, config_path: str = None):
        """Initialize scanner with parser manager"""
        self.parser_manager = ParserManager(config_path)
        self.findings: List[Finding] = []
        self.query_cache: Dict[str, any] = {}
        self.base_path: str = None

    def scan_directory(self, directory: str) -> List[Finding]:
        """Scan entire directory recursively"""
        self.findings = []
        path = Path(directory).resolve()
        self.base_path = str(path)

        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        for file_path in path.rglob('*'):
            if file_path.is_file():
                self.scan_file(str(file_path))

        return self.findings

    def scan_file(self, file_path: str) -> List[Finding]:
        """Scan a single file"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        language = self.parser_manager.get_file_language(file_path)
        if language is None:
            return []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()

            return self._scan_code(code, file_path, language)
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")
            return []

    def _scan_code(self, code: str, file_path: str, language: str) -> List[Finding]:
        """Scan code content using tree-sitter"""
        parser = self.parser_manager.get_parser(language)
        if parser is None:
            return []

        try:
            tree = parser.parse(code.encode('utf-8'))
            query = self._load_query(language)

            if query is None:
                return []

            # Get captures from tree-sitter query using QueryCursor
            from tree_sitter import QueryCursor
            cursor = QueryCursor(query)
            captures = cursor.captures(tree.root_node)

            # Detect sink patterns based on language
            self._detect_sinks(code, file_path, language, tree)

            return self.findings
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return []

    def _load_query(self, language: str):
        """Load tree-sitter query for a language"""
        if language in self.query_cache:
            return self.query_cache[language]

        query_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'languages',
            language,
            'queries',
            'sinks.scm'
        )

        if not os.path.exists(query_path):
            return None

        try:
            with open(query_path, 'r', encoding='utf-8') as f:
                query_str = f.read()

            lang_obj = self.parser_manager.get_language(language)
            if lang_obj:
                from tree_sitter import Query
                query = Query(lang_obj, query_str)
                self.query_cache[language] = query
                return query
        except Exception as e:
            print(f"Error loading query for {language}: {e}")
            return None

        return None

    def _get_relative_path(self, file_path: str) -> str:
        """Convert absolute path to relative path"""
        if self.base_path and file_path.startswith(self.base_path):
            return file_path[len(self.base_path):].lstrip('/')
        return file_path

    def _detect_sinks(self, code: str, file_path: str, language: str, tree):
        """Detect mass assignment sinks based on language patterns"""
        lines = code.split('\n')
        rel_path = self._get_relative_path(file_path)

        # Language-specific sink detection patterns
        if language == 'php':
            self._detect_php_sinks(lines, rel_path)
        elif language == 'python':
            self._detect_python_sinks(lines, rel_path)
        elif language == 'java':
            self._detect_java_sinks(lines, rel_path)
        elif language == 'javascript':
            self._detect_javascript_sinks(lines, rel_path)
        elif language == 'c':
            self._detect_c_sinks(lines, rel_path)
        elif language == 'go':
            self._detect_go_sinks(lines, rel_path)
        elif language == 'rust':
            self._detect_rust_sinks(lines, rel_path)

    def _detect_php_sinks(self, lines: List[str], file_path: str):
        """Detect PHP mass assignment patterns"""
        dangerous_methods = ['create', 'firstOrCreate', 'updateOrCreate', 'fill', 'setAttributes']

        for line_num, line in enumerate(lines, 1):
            for method in dangerous_methods:
                if method in line and ('$' in line or '->' in line):
                    self.findings.append(Finding(
                        file=file_path,
                        line=line_num,
                        column=line.find(method),
                        type='MASS_ASSIGNMENT',
                        code=line.strip(),
                        message=f"Potential mass assignment vulnerability using '{method}'",
                        severity='HIGH'
                    ))

    def _detect_python_sinks(self, lines: List[str], file_path: str):
        """Detect Python mass assignment patterns"""
        dangerous_patterns = ['objects.create', 'session.add', 'parse_obj', '**']

        for line_num, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                if pattern in line and ('request' in line or 'data' in line or 'kwargs' in line):
                    self.findings.append(Finding(
                        file=file_path,
                        line=line_num,
                        column=line.find(pattern),
                        type='MASS_ASSIGNMENT',
                        code=line.strip(),
                        message=f"Potential mass assignment vulnerability with pattern '{pattern}'",
                        severity='HIGH'
                    ))

    def _detect_java_sinks(self, lines: List[str], file_path: str):
        """Detect Java mass assignment patterns"""
        dangerous_methods = ['copyProperties', 'setProperty', 'save', 'map']

        for line_num, line in enumerate(lines, 1):
            for method in dangerous_methods:
                if method in line and ('(' in line or '.' in line):
                    self.findings.append(Finding(
                        file=file_path,
                        line=line_num,
                        column=line.find(method),
                        type='MASS_ASSIGNMENT',
                        code=line.strip(),
                        message=f"Potential mass assignment vulnerability using '{method}'",
                        severity='HIGH'
                    ))

    def _detect_javascript_sinks(self, lines: List[str], file_path: str):
        """Detect JavaScript/TypeScript mass assignment patterns"""
        dangerous_patterns = ['create(', 'findByIdAndUpdate', 'update(', 'Object.assign', 'spread']

        for line_num, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                if pattern in line and ('req' in line or 'body' in line or 'data' in line):
                    self.findings.append(Finding(
                        file=file_path,
                        line=line_num,
                        column=line.find(pattern),
                        type='MASS_ASSIGNMENT',
                        code=line.strip(),
                        message=f"Potential mass assignment vulnerability with pattern '{pattern}'",
                        severity='HIGH'
                    ))

    def _detect_c_sinks(self, lines: List[str], file_path: str):
        """Detect C mass assignment patterns"""
        dangerous_functions = ['memcpy', 'strcpy', 'strncpy', 'sprintf', 'snprintf', 'strcpy_s', 'strncpy_s', 'sprintf_s', 'snprintf_s']

        for line_num, line in enumerate(lines, 1):
            for func in dangerous_functions:
                if func in line and '(' in line:
                    self.findings.append(Finding(
                        file=file_path,
                        line=line_num,
                        column=line.find(func),
                        type='MASS_ASSIGNMENT',
                        code=line.strip(),
                        message=f"Potential buffer overflow vulnerability using '{func}'",
                        severity='HIGH'
                    ))

    def _detect_go_sinks(self, lines: List[str], file_path: str):
        """Detect Go mass assignment patterns"""
        dangerous_patterns = ['json.Unmarshal', 'gorm.Create', 'gorm.Save', 'copier.Copy', 'binary.Unmarshal']

        for line_num, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                if pattern in line and ('data' in line or 'request' in line or 'input' in line):
                    self.findings.append(Finding(
                        file=file_path,
                        line=line_num,
                        column=line.find(pattern.split('.')[-1]),
                        type='MASS_ASSIGNMENT',
                        code=line.strip(),
                        message=f"Potential mass assignment vulnerability with pattern '{pattern}'",
                        severity='HIGH'
                    ))

    def _detect_rust_sinks(self, lines: List[str], file_path: str):
        """Detect Rust mass assignment patterns"""
        dangerous_patterns = ['serde_json::from_str', 'serde_json::from_slice', 'serde_json::from_value', 'diesel::insert_into', 'ptr::copy_nonoverlapping', 'ptr::write']

        for line_num, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                pattern_short = pattern.split('::')[-1]
                if pattern_short in line and ('data' in line or 'request' in line or 'input' in line or 'unsafe' in line):
                    self.findings.append(Finding(
                        file=file_path,
                        line=line_num,
                        column=line.find(pattern_short),
                        type='MASS_ASSIGNMENT',
                        code=line.strip(),
                        message=f"Potential mass assignment vulnerability with pattern '{pattern}'",
                        severity='HIGH'
                    ))

    def get_findings(self) -> List[Finding]:
        """Get all detected findings"""
        return self.findings

    def clear_findings(self):
        """Clear all findings"""
        self.findings = []
