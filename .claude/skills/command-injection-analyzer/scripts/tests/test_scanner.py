#!/usr/bin/env python3
"""Test suite for command injection sink detector."""

import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli import CommandInjectionSinkDetectorCLI


class TestCommandInjectionSinkDetector(unittest.TestCase):
    """Test cases for command injection sink detector."""

    def setUp(self):
        """Set up test fixtures."""
        self.cli = CommandInjectionSinkDetectorCLI()
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_php_sink_detection(self):
        """Test detection of PHP command injection sinks."""
        php_file = self.fixtures_dir / "php" / "cmd_calls.php"
        if not php_file.exists():
            self.skipTest(f"Test fixture {php_file} not found")

        sink_config = self.cli.parser_manager.get_sink_config("php")
        sinks = self.cli.scan_file(str(php_file), "php", sink_config, verbose=False)

        # Should detect system, exec, shell_exec, passthru, popen
        self.assertGreater(len(sinks), 0, "Should detect PHP command injection sinks")

        # Check for specific sinks
        sink_names = [s['sink_type'] for s in sinks]
        self.assertIn('system', sink_names)
        self.assertIn('exec', sink_names)
        self.assertIn('shell_exec', sink_names)

    def test_python_sink_detection(self):
        """Test detection of Python command injection sinks."""
        py_file = self.fixtures_dir / "python" / "cmd_calls.py"
        if not py_file.exists():
            self.skipTest(f"Test fixture {py_file} not found")

        sink_config = self.cli.parser_manager.get_sink_config("python")
        sinks = self.cli.scan_file(str(py_file), "python", sink_config, verbose=False)

        # Should detect subprocess and os calls
        self.assertGreater(len(sinks), 0, "Should detect Python command injection sinks")

        # Check for specific sinks
        sink_names = [s['sink_type'] for s in sinks]
        self.assertTrue(
            any('subprocess' in name or 'system' in name for name in sink_names),
            "Should detect subprocess or os.system calls"
        )

    def test_java_sink_detection(self):
        """Test detection of Java command injection sinks."""
        java_file = self.fixtures_dir / "java" / "CommandInjection.java"
        if not java_file.exists():
            self.skipTest(f"Test fixture {java_file} not found")

        sink_config = self.cli.parser_manager.get_sink_config("java")
        sinks = self.cli.scan_file(str(java_file), "java", sink_config, verbose=False)

        # Should detect Runtime.exec and ProcessBuilder
        self.assertGreater(len(sinks), 0, "Should detect Java command injection sinks")

        # Check for specific sinks
        sink_names = [s['sink_type'] for s in sinks]
        self.assertIn('exec', sink_names)
        self.assertIn('start', sink_names)

    def test_javascript_sink_detection(self):
        """Test detection of JavaScript command injection sinks."""
        js_file = self.fixtures_dir / "javascript" / "cmd_calls.js"
        if not js_file.exists():
            self.skipTest(f"Test fixture {js_file} not found")

        sink_config = self.cli.parser_manager.get_sink_config("javascript")
        sinks = self.cli.scan_file(str(js_file), "javascript", sink_config, verbose=False)

        # Should detect child_process calls
        self.assertGreater(len(sinks), 0, "Should detect JavaScript command injection sinks")

        # Check for specific sinks
        sink_names = [s['sink_type'] for s in sinks]
        self.assertIn('exec', sink_names)

    def test_go_sink_detection(self):
        """Test detection of Go command injection sinks."""
        go_file = self.fixtures_dir / "go" / "cmd_calls.go"
        if not go_file.exists():
            self.skipTest(f"Test fixture {go_file} not found")

        sink_config = self.cli.parser_manager.get_sink_config("go")
        sinks = self.cli.scan_file(str(go_file), "go", sink_config, verbose=False)

        # Should detect os/exec calls
        self.assertGreater(len(sinks), 0, "Should detect Go command injection sinks")

        # Check for specific sinks
        sink_names = [s['sink_type'] for s in sinks]
        self.assertIn('Command', sink_names)

    def test_rust_sink_detection(self):
        """Test detection of Rust command injection sinks."""
        rs_file = self.fixtures_dir / "rust" / "cmd_calls.rs"
        if not rs_file.exists():
            self.skipTest(f"Test fixture {rs_file} not found")

        sink_config = self.cli.parser_manager.get_sink_config("rust")
        sinks = self.cli.scan_file(str(rs_file), "rust", sink_config, verbose=False)

        # Should detect Command struct usage
        self.assertGreater(len(sinks), 0, "Should detect Rust command injection sinks")

        # Check for specific sinks
        sink_names = [s['sink_type'] for s in sinks]
        self.assertTrue(
            any('new' in name or 'Command' in name for name in sink_names),
            "Should detect Command struct usage"
        )

    def test_file_detection(self):
        """Test file pattern matching."""
        patterns = ['*.php']
        files = self.cli.find_files(str(self.fixtures_dir / "php"), patterns)

        self.assertGreater(len(files), 0, "Should find PHP files")
        self.assertTrue(any(f.endswith('.php') for f in files), "Should match .php files")

    def test_report_generation(self):
        """Test report generation."""
        sinks = [
            {
                'file': 'test.php',
                'line': 1,
                'column': 1,
                'sink_type': 'system',
                'sink_category': 'direct_execution',
                'function_name': 'system',
                'parameters': ['$cmd'],
                'vulnerable_params': [0],
                'context': 'system($cmd);',
            }
        ]

        report = self.cli.reporter.generate_report(sinks, source_path='/test')

        self.assertIn('metadata', report)
        self.assertIn('sinks', report)
        self.assertIn('summary', report)
        self.assertEqual(report['metadata']['total_sinks'], 1)
        self.assertEqual(len(report['sinks']), 1)

    def test_language_configuration(self):
        """Test language configuration loading."""
        enabled_langs = self.cli.parser_manager.get_enabled_languages()

        self.assertGreater(len(enabled_langs), 0, "Should have enabled languages")
        self.assertIn('php', enabled_langs)
        self.assertIn('python', enabled_langs)
        self.assertIn('java', enabled_langs)
        self.assertIn('javascript', enabled_langs)

    def test_sink_configuration(self):
        """Test sink configuration loading."""
        php_sinks = self.cli.parser_manager.get_sink_config('php')

        self.assertGreater(len(php_sinks), 0, "Should have PHP sink configuration")

        sink_names = [s['name'] for s in php_sinks]
        self.assertIn('system', sink_names)
        self.assertIn('exec', sink_names)


if __name__ == '__main__':
    unittest.main()
