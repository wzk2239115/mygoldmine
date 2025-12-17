"""Scanner module for CSRF sink detection."""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re

# Import parser manager
from .parser_manager import ParserManager

# Make tree_sitter optional
try:
    import tree_sitter
    from tree_sitter import Language, Parser
except ImportError:
    tree_sitter = None


class SinkDetector:
    """Base class for CSRF sink detectors."""

    def __init__(self):
        """Initialize detector."""
        self.sinks = []

    def detect(self, filepath: str, content: str) -> List[Dict[str, Any]]:
        """Detect sinks in file content."""
        raise NotImplementedError


class PHPCSRFDetector(SinkDetector):
    """CSRF sink detector for PHP."""

    def detect(self, filepath: str, content: str) -> List[Dict[str, Any]]:
        """Detect POST routes in PHP code."""
        sinks = []
        lines = content.split('\n')

        # Patterns for detecting POST routes
        patterns = [
            r"\$app\s*->\s*post\s*\(",  # Laravel route
            r"\$router\s*->\s*post\s*\(",  # Generic router
            r"post\s*\(",  # Function call
            r"\$_POST",  # Direct POST access
            r"REQUEST_METHOD\s*==\s*['\"]POST['\"]",  # POST method check
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    sinks.append({
                        'file': filepath,
                        'line': line_num,
                        'column': line.find('post'),
                        'type': 'POST_ROUTE',
                        'sink': 'POST endpoint',
                        'code': line.strip()
                    })

        return sinks


class PythonCSRFDetector(SinkDetector):
    """CSRF sink detector for Python."""

    def detect(self, filepath: str, content: str) -> List[Dict[str, Any]]:
        """Detect POST routes in Python code."""
        sinks = []
        lines = content.split('\n')

        # Patterns for detecting POST routes
        patterns = [
            r"@app\s*\.\s*route\s*\(",  # Flask decorator
            r"@router\s*\.\s*post\s*\(",  # Generic router
            r"methods\s*=\s*\[\s*['\"]POST['\"]",  # methods=['POST']
            r"@csrf_exempt",  # CSRF exempt decorator
            r"def\s+\w+\s*\([^)]*request[^)]*\):",  # Django view function
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line):
                    sinks.append({
                        'file': filepath,
                        'line': line_num,
                        'column': line.find('route') if 'route' in line else line.find('post'),
                        'type': 'POST_ROUTE' if 'post' in line.lower() or 'POST' in line else 'CSRF_EXEMPT',
                        'sink': 'POST endpoint',
                        'code': line.strip()
                    })

        return sinks


class JavaCSRFDetector(SinkDetector):
    """CSRF sink detector for Java."""

    def detect(self, filepath: str, content: str) -> List[Dict[str, Any]]:
        """Detect POST endpoints in Java code."""
        sinks = []
        lines = content.split('\n')

        # Patterns for detecting POST endpoints
        patterns = [
            r"@PostMapping",  # Spring PostMapping
            r"@RequestMapping.*method\s*=\s*RequestMethod\.POST",  # RequestMapping POST
            r"@PutMapping",  # PutMapping
            r"@DeleteMapping",  # DeleteMapping
            r"csrf\(\)\.disable\(\)",  # CSRF disabled
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.DOTALL):
                    sinks.append({
                        'file': filepath,
                        'line': line_num,
                        'column': line.find('@') if '@' in line else 0,
                        'type': 'POST_ENDPOINT',
                        'sink': 'State-changing endpoint',
                        'code': line.strip()
                    })

        return sinks


class JavaScriptCSRFDetector(SinkDetector):
    """CSRF sink detector for JavaScript."""

    def detect(self, filepath: str, content: str) -> List[Dict[str, Any]]:
        """Detect POST routes in JavaScript code."""
        sinks = []
        lines = content.split('\n')

        # Patterns for detecting POST routes
        patterns = [
            r"app\s*\.\s*post\s*\(",  # Express app.post
            r"router\s*\.\s*post\s*\(",  # Express router.post
            r"app\s*\.\s*put\s*\(",  # Express app.put
            r"app\s*\.\s*delete\s*\(",  # Express app.delete
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line):
                    sinks.append({
                        'file': filepath,
                        'line': line_num,
                        'column': line.find('post') if 'post' in line else line.find('put') if 'put' in line else line.find('delete'),
                        'type': 'POST_ROUTE',
                        'sink': 'POST endpoint',
                        'code': line.strip()
                    })

        return sinks


class CSRFSinkScanner:
    """Main scanner for CSRF sinks."""

    def __init__(self):
        """Initialize scanner."""
        self.parser_manager = ParserManager()
        self.detectors = {
            'php': PHPCSRFDetector(),
            'python': PythonCSRFDetector(),
            'java': JavaCSRFDetector(),
            'javascript': JavaScriptCSRFDetector(),
            'typescript': JavaScriptCSRFDetector(),
        }
        self.all_sinks = []

    def find_files(self, directory: str, patterns: List[str]) -> List[str]:
        """Find files matching patterns in directory."""
        directory = Path(directory)
        matched_files = []

        for pattern in patterns:
            # Convert glob pattern to regex
            regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
            regex = re.compile(f'^{regex_pattern}$')

            for file_path in directory.rglob('*'):
                if file_path.is_file() and regex.match(file_path.name):
                    matched_files.append(str(file_path))

        return sorted(set(matched_files))

    def scan_directory(
        self,
        directory: str,
        languages: List[str] = None,
        verbose: bool = False,
    ) -> List[Dict[str, Any]]:
        """Scan directory for CSRF sinks."""
        if languages is None:
            languages = self.parser_manager.get_enabled_languages()

        all_sinks = []

        for language in languages:
            if not self.parser_manager.is_language_enabled(language):
                continue

            if verbose:
                print(f"Scanning {language} files...")

            file_patterns = self.parser_manager.get_file_patterns(language)
            files = self.find_files(directory, file_patterns)

            if verbose:
                print(f"Found {len(files)} {language} files")

            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    detector = self.detectors.get(language)
                    if detector:
                        sinks = detector.detect(file_path, content)
                        all_sinks.extend(sinks)

                        if verbose and sinks:
                            print(f"Found {len(sinks)} sinks in {file_path}")

                except Exception as e:
                    if verbose:
                        print(f"Error scanning {file_path}: {e}")

        return all_sinks

    def scan_file(self, filepath: str, language: str = None) -> List[Dict[str, Any]]:
        """Scan a single file for CSRF sinks."""
        if language is None:
            # Infer language from file extension
            ext = Path(filepath).suffix.lower()
            ext_map = {
                '.php': 'php',
                '.py': 'python',
                '.java': 'java',
                '.js': 'javascript',
                '.ts': 'typescript',
            }
            language = ext_map.get(ext)

        if not language:
            return []

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            detector = self.detectors.get(language)
            if detector:
                return detector.detect(filepath, content)

        except Exception as e:
            print(f"Error scanning {filepath}: {e}")

        return []
