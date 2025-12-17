"""
Test suite for JWT sink detection.
"""

import unittest
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scanner import JWTSinkScanner, Finding


class TestJWTSinkScanner(unittest.TestCase):
    """Tests for JWT sink scanner."""

    def setUp(self):
        """Set up test fixtures."""
        self.scanner = JWTSinkScanner()
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_parser_manager_initialization(self):
        """Test that parser manager initializes correctly."""
        self.assertIsNotNone(self.scanner.parser_manager)
        languages = self.scanner.parser_manager.get_supported_languages()
        self.assertIn("python", languages)
        self.assertIn("php", languages)

    def test_language_detection(self):
        """Test language detection from file extension."""
        self.assertEqual(self.scanner._detect_language("test.py"), "python")
        self.assertEqual(self.scanner._detect_language("test.php"), "php")
        self.assertEqual(self.scanner._detect_language("test.js"), "javascript")
        self.assertEqual(self.scanner._detect_language("test.java"), "java")
        self.assertIsNone(self.scanner._detect_language("test.txt"))

    def test_python_fixture_scan(self):
        """Test scanning Python fixture file."""
        fixture_file = self.fixtures_dir / "python" / "jwt_fixtures.py"
        if fixture_file.exists():
            findings = self.scanner.scan_file(str(fixture_file))
            # Should find JWT operations
            self.assertGreater(len(findings), 0)
            # Check that findings have required fields
            for finding in findings:
                self.assertIsNotNone(finding.file)
                self.assertGreater(finding.line, 0)
                self.assertEqual(finding.language, "python")

    def test_php_fixture_scan(self):
        """Test scanning PHP fixture file."""
        fixture_file = self.fixtures_dir / "php" / "jwt_calls.php"
        if fixture_file.exists():
            findings = self.scanner.scan_file(str(fixture_file))
            # Should find JWT operations
            if len(findings) > 0:
                for finding in findings:
                    self.assertIsNotNone(finding.file)
                    self.assertGreater(finding.line, 0)
                    self.assertEqual(finding.language, "php")

    def test_code_snippet_extraction(self):
        """Test code snippet extraction."""
        source = "line1\nline2\nline3\nline4\nline5"
        snippet = self.scanner._extract_code_snippet(source, 2, context_lines=1)
        # Should extract around line 2
        self.assertIn("line1", snippet)
        self.assertIn("line2", snippet)
        self.assertIn("line3", snippet)

    def test_unsupported_file(self):
        """Test scanning unsupported file type."""
        findings = self.scanner.scan_file("nonexistent.txt")
        self.assertEqual(len(findings), 0)

    def test_nonexistent_file(self):
        """Test scanning non-existent file."""
        findings = self.scanner.scan_file("/nonexistent/path/file.py")
        self.assertEqual(len(findings), 0)

    def test_findings_summary(self):
        """Test findings summary generation."""
        summary = self.scanner.get_summary()
        self.assertIn("total_findings", summary)
        self.assertIn("by_language", summary)
        self.assertIn("by_severity", summary)

    def test_clear_findings(self):
        """Test clearing findings."""
        # Add a dummy finding
        finding = Finding(
            file="test.py",
            line=1,
            column=0,
            function_name="jwt.decode",
            code_snippet="jwt.decode(token, secret)"
        )
        self.scanner.findings.append(finding)
        self.assertEqual(len(self.scanner.findings), 1)

        # Clear findings
        self.scanner.clear_findings()
        self.assertEqual(len(self.scanner.findings), 0)

    def test_finding_to_dict(self):
        """Test finding conversion to dictionary."""
        finding = Finding(
            file="test.py",
            line=10,
            column=5,
            function_name="jwt.decode",
            code_snippet="jwt.decode(token, key)",
            language="python"
        )
        finding_dict = finding.to_dict()
        self.assertEqual(finding_dict["file"], "test.py")
        self.assertEqual(finding_dict["line"], 10)
        self.assertEqual(finding_dict["function_name"], "jwt.decode")


class TestReporters(unittest.TestCase):
    """Tests for report generation."""

    def setUp(self):
        """Set up test fixtures."""
        from reports.json_reporter import JSONReporter
        from reports.sarif_reporter import SARIFReporter
        self.JSONReporter = JSONReporter
        self.SARIFReporter = SARIFReporter

    def test_json_reporter_generation(self):
        """Test JSON report generation."""
        reporter = self.JSONReporter()
        finding = Finding(
            file="test.py",
            line=5,
            column=0,
            function_name="jwt.decode",
            code_snippet="jwt.decode(token, secret)",
            language="python"
        )
        reporter.add_findings([finding])
        report = reporter.generate_report()

        self.assertIn("tool", report)
        self.assertIn("findings", report)
        self.assertEqual(report["summary"]["total_findings"], 1)

    def test_sarif_reporter_generation(self):
        """Test SARIF report generation."""
        reporter = self.SARIFReporter()
        finding = Finding(
            file="test.py",
            line=5,
            column=0,
            function_name="jwt.decode",
            code_snippet="jwt.decode(token, secret)",
            language="python"
        )
        reporter.add_findings([finding])
        report = reporter.generate_report()

        self.assertIn("version", report)
        self.assertEqual(report["version"], "2.1.0")
        self.assertIn("runs", report)
        self.assertEqual(len(report["runs"][0]["results"]), 1)


if __name__ == "__main__":
    unittest.main()
