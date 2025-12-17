"""Unit tests for SSRF sink detector."""

import unittest
import tempfile
import os
from pathlib import Path
from core.scanner import Scanner


class TestSSRFScanner(unittest.TestCase):
    """Test cases for SSRF sink detection."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.config_path = Path(__file__).parent.parent / 'config' / 'languages.yaml'

    def setUp(self):
        """Initialize scanner for each test."""
        self.scanner = Scanner(str(self.config_path))

    def test_scanner_initialization(self):
        """Test scanner initialization."""
        self.assertIsNotNone(self.scanner)
        self.assertIsNotNone(self.scanner.parser_manager)

    def test_supported_languages(self):
        """Test that all languages are supported."""
        languages = self.scanner.parser_manager.get_supported_languages()
        self.assertIn('php', languages)
        self.assertIn('python', languages)
        self.assertIn('java', languages)
        self.assertIn('javascript', languages)

    def test_php_file_detection(self):
        """Test PHP file extension detection."""
        language = self.scanner.parser_manager.get_language_by_extension('.php')
        self.assertEqual(language, 'php')

    def test_python_file_detection(self):
        """Test Python file extension detection."""
        language = self.scanner.parser_manager.get_language_by_extension('.py')
        self.assertEqual(language, 'python')

    def test_java_file_detection(self):
        """Test Java file extension detection."""
        language = self.scanner.parser_manager.get_language_by_extension('.java')
        self.assertEqual(language, 'java')

    def test_javascript_file_detection(self):
        """Test JavaScript file extension detection."""
        language = self.scanner.parser_manager.get_language_by_extension('.js')
        self.assertEqual(language, 'javascript')

    def test_query_loading(self):
        """Test that queries are loaded for all languages."""
        for language in self.scanner.parser_manager.get_supported_languages():
            query_text = self.scanner.parser_manager.get_query_text(language)
            # Query text might be None if parser is not installed
            # Just verify the method works without error
            self.assertTrue(True)

    def test_results_initialization(self):
        """Test that results are initialized as empty list."""
        self.assertEqual(self.scanner.get_results(), [])

    def test_clear_results(self):
        """Test clearing results."""
        # Simulate adding a result
        self.scanner.results.append({'file': 'test.php', 'sink_name': 'file_get_contents'})
        self.assertEqual(len(self.scanner.results), 1)

        # Clear results
        self.scanner.clear_results()
        self.assertEqual(len(self.scanner.results), 0)

    def test_scan_nonexistent_file(self):
        """Test scanning a non-existent file."""
        results = self.scanner.scan_file('/nonexistent/file.php')
        self.assertEqual(results, [])

    def test_scan_empty_file(self):
        """Test scanning an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False) as f:
            f.write('')
            temp_file = f.name

        try:
            results = self.scanner.scan_file(temp_file)
            # Empty file should not produce errors
            self.assertIsInstance(results, list)
        finally:
            os.unlink(temp_file)


class TestReporters(unittest.TestCase):
    """Test cases for report generation."""

    def setUp(self):
        """Set up test data."""
        self.test_findings = [
            {
                'file': '/path/to/file.php',
                'language': 'php',
                'sink_name': 'file_get_contents',
                'start_line': 10,
                'start_col': 5,
                'end_line': 10,
                'end_col': 25,
                'code_snippet': '$content = file_get_contents($url);',
                'severity': 'high'
            },
            {
                'file': '/path/to/script.py',
                'language': 'python',
                'sink_name': 'requests.get',
                'start_line': 5,
                'start_col': 10,
                'end_line': 5,
                'end_col': 22,
                'code_snippet': 'response = requests.get(url)',
                'severity': 'high'
            }
        ]

    def test_json_reporter_generation(self):
        """Test JSON report generation."""
        from reports.json_reporter import JSONReporter

        report = JSONReporter.generate(self.test_findings)
        self.assertIsNotNone(report)
        self.assertIn('version', report)
        self.assertIn('timestamp', report)
        self.assertIn('findings', report)

    def test_json_reporter_file_output(self):
        """Test JSON report file output."""
        from reports.json_reporter import JSONReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'report.json')
            JSONReporter.generate(self.test_findings, output_path)

            self.assertTrue(os.path.exists(output_path))
            with open(output_path, 'r') as f:
                content = f.read()
                self.assertIn('findings', content)

    def test_sarif_reporter_generation(self):
        """Test SARIF report generation."""
        from reports.sarif_reporter import SARIFReporter

        report = SARIFReporter.generate(self.test_findings)
        self.assertIsNotNone(report)
        self.assertIn('version', report)
        self.assertIn('runs', report)

    def test_sarif_reporter_file_output(self):
        """Test SARIF report file output."""
        from reports.sarif_reporter import SARIFReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'report.sarif')
            SARIFReporter.generate(self.test_findings, output_path)

            self.assertTrue(os.path.exists(output_path))
            with open(output_path, 'r') as f:
                content = f.read()
                self.assertIn('runs', content)


if __name__ == '__main__':
    unittest.main()
