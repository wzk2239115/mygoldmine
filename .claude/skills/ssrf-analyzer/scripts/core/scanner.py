"""Main scanning engine for SSRF sink detection using tree-sitter queries."""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .parser_manager import ParserManager


class Scanner:
    """Scans source code files for SSRF sinks using tree-sitter queries."""

    def __init__(self, config_path: str):
        """
        Initialize Scanner with parser manager.

        Args:
            config_path: Path to languages.yaml configuration file
        """
        self.parser_manager = ParserManager(config_path)
        self.results: List[Dict] = []

    def scan_directory(self, directory: str) -> List[Dict]:
        """
        Recursively scan directory for SSRF sinks in all supported languages.

        Args:
            directory: Path to directory to scan

        Returns:
            List of detected sink findings
        """
        self.results = []
        directory_path = Path(directory)

        if not directory_path.exists():
            raise ValueError(f"Directory not found: {directory}")

        for file_path in directory_path.rglob('*'):
            if file_path.is_file():
                self._scan_file(str(file_path))

        return self.results

    def scan_file(self, file_path: str) -> List[Dict]:
        """
        Scan a single file for SSRF sinks.

        Args:
            file_path: Path to file to scan

        Returns:
            List of detected sink findings
        """
        self.results = []
        self._scan_file(file_path)
        return self.results

    def _scan_file(self, file_path: str):
        """
        Internal method to scan a file.

        Args:
            file_path: Path to file to scan
        """
        file_path_obj = Path(file_path)
        extension = file_path_obj.suffix

        # Get language based on file extension
        language = self.parser_manager.get_language_by_extension(extension)
        if not language:
            return

        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()

            # Define SSRF sinks by language
            sinks_by_lang = {
                'php': [
                    'file_get_contents', 'fopen', 'readfile',
                    'curl_exec', 'curl_multi_exec', 'fsockopen', 'pfsockopen'
                ],
                'python': [
                    'requests.get', 'requests.post', 'requests.put', 'requests.delete',
                    'requests.patch', 'requests.request', 'urlopen', 'urlretrieve',
                    'HTTPConnection', 'HTTPSConnection', 'socket'
                ],
                'java': [
                    'openConnection', 'openStream', 'getInputStream', 'connect',
                    'exchange', 'getForObject', 'getForEntity', 'postForObject',
                    'newCall', 'execute', 'send'
                ],
                'javascript': [
                    'http.request', 'http.get', 'https.request', 'https.get',
                    'axios.get', 'axios.post', 'axios.put', 'axios.delete',
                    'fetch', 'XMLHttpRequest'
                ],
                'typescript': [
                    'http.request', 'http.get', 'https.request', 'https.get',
                    'axios.get', 'axios.post', 'axios.put', 'axios.delete',
                    'fetch', 'XMLHttpRequest', 'fetch'
                ],
                'c': [
                    'curl_easy_perform', 'curl_easy_init', 'socket', 'connect',
                    'fopen', 'getaddrinfo', 'gethostbyname', 'inet_addr'
                ],
                'cpp': [
                    'curl_easy_perform', 'curl_easy_init', 'socket', 'connect',
                    'fopen', 'getaddrinfo', 'gethostbyname', 'inet_addr',
                    'std::ifstream', 'std::fstream'
                ],
                'go': [
                    'http.Get', 'http.Post', 'http.Put', 'http.Delete',
                    'http.Do', 'net.Dial', 'net.DialTCP', 'net.DialUDP',
                    'net.LookupIP', 'url.Parse', 'io.ReadAll'
                ],
                'rust': [
                    'reqwest.get', 'reqwest.post', 'reqwest.put', 'reqwest.delete',
                    'reqwest::Client', 'http::Request', 'tokio::net::TcpStream',
                    'std::net::TcpStream', 'std::net::UdpSocket',
                    'hyper::client::Client'
                ]
            }

            sinks = sinks_by_lang.get(language, [])

            # Simple line-based scanning
            for line_num, line in enumerate(source_code.split('\n'), 1):
                for sink in sinks:
                    if sink in line and not line.strip().startswith('//') and not line.strip().startswith('#'):
                        # Find column position
                        col = line.find(sink)
                        finding = {
                            'file': file_path,
                            'language': language,
                            'sink_name': sink,
                            'start_line': line_num,
                            'start_col': col,
                            'end_line': line_num,
                            'end_col': col + len(sink),
                            'code_snippet': line.strip(),
                            'severity': 'high'
                        }
                        self.results.append(finding)

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

    def _extract_finding(
        self,
        file_path: str,
        node,
        source_code: str,
        language: str
    ) -> Dict:
        """
        Extract finding details from a matched node.

        Args:
            file_path: Path to source file
            node: Matched tree-sitter node
            source_code: Source code content
            language: Programming language

        Returns:
            Dictionary with finding details
        """
        # Get node position
        start_line = node.start_point[0]
        start_col = node.start_point[1]
        end_line = node.end_point[0]
        end_col = node.end_point[1]

        # Get the actual code snippet
        lines = source_code.split('\n')
        if start_line < len(lines):
            code_line = lines[start_line]
        else:
            code_line = ""

        # Get sink name (function or method call)
        sink_name = node.text.decode('utf-8') if isinstance(node.text, bytes) else node.text

        finding = {
            'file': file_path,
            'language': language,
            'sink_name': sink_name,
            'start_line': start_line + 1,  # Convert to 1-based indexing
            'start_col': start_col,
            'end_line': end_line + 1,
            'end_col': end_col,
            'code_snippet': code_line.strip(),
            'severity': 'high'
        }

        return finding

    def get_results(self) -> List[Dict]:
        """Get current scan results."""
        return self.results

    def clear_results(self):
        """Clear current scan results."""
        self.results = []
