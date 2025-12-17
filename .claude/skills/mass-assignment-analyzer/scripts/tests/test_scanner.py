"""
Automated Tests for Mass Assignment Sink Detector
Tests basic functionality of sink matching across languages
"""
import unittest
import os
from pathlib import Path

from core.scanner import Scanner


class TestMassAssignmentDetector(unittest.TestCase):
    """Test mass assignment sink detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.scanner = Scanner()
        self.fixtures_dir = os.path.join(
            os.path.dirname(__file__),
            'fixtures'
        )

    def test_parser_initialization(self):
        """Test that parsers are initialized correctly"""
        supported_langs = self.scanner.parser_manager.get_supported_languages()
        print(f"Supported languages: {supported_langs}")
        self.assertGreater(len(supported_langs), 0)

    def test_file_language_detection(self):
        """Test language detection from file extensions"""
        test_cases = [
            ('test.php', 'php'),
            ('test.py', 'python'),
            ('test.java', 'java'),
            ('test.js', 'javascript'),
            ('test.ts', 'javascript'),
        ]

        for filename, expected_lang in test_cases:
            detected_lang = self.scanner.parser_manager.get_file_language(filename)
            self.assertEqual(detected_lang, expected_lang,
                           f"Failed to detect {expected_lang} from {filename}")

    def test_php_fixture_scanning(self):
        """Test scanning PHP fixtures"""
        php_fixture = os.path.join(self.fixtures_dir, 'php', 'model_updates.php')

        if os.path.exists(php_fixture):
            findings = self.scanner.scan_file(php_fixture)
            print(f"PHP findings: {len(findings)}")

            # Should detect at least some mass assignment patterns
            self.assertGreater(len(findings), 0,
                              "Should detect mass assignment in PHP fixtures")

            # Verify finding structure
            for finding in findings:
                self.assertTrue(hasattr(finding, 'file'))
                self.assertTrue(hasattr(finding, 'line'))
                self.assertTrue(hasattr(finding, 'type'))
                self.assertEqual(finding.type, 'MASS_ASSIGNMENT')

    def test_python_fixture_scanning(self):
        """Test scanning Python fixtures"""
        py_fixture = os.path.join(self.fixtures_dir, 'python', 'django_sqlalchemy_examples.py')

        if os.path.exists(py_fixture):
            findings = self.scanner.scan_file(py_fixture)
            print(f"Python findings: {len(findings)}")

            # Should detect some patterns
            if len(findings) > 0:
                for finding in findings:
                    self.assertTrue(hasattr(finding, 'message'))
                    self.assertIn('mass assignment', finding.message.lower())

    def test_findings_export(self):
        """Test that findings can be exported to dict"""
        php_fixture = os.path.join(self.fixtures_dir, 'php', 'model_updates.php')

        if os.path.exists(php_fixture):
            findings = self.scanner.scan_file(php_fixture)

            if findings:
                finding = findings[0]
                finding_dict = finding.to_dict()

                # Verify dictionary structure
                self.assertIn('file', finding_dict)
                self.assertIn('line', finding_dict)
                self.assertIn('column', finding_dict)
                self.assertIn('type', finding_dict)
                self.assertIn('code', finding_dict)
                self.assertIn('message', finding_dict)
                self.assertIn('severity', finding_dict)

    def test_scanner_clear_findings(self):
        """Test clearing scanner findings"""
        self.scanner.findings.append("dummy")
        self.assertEqual(len(self.scanner.findings), 1)

        self.scanner.clear_findings()
        self.assertEqual(len(self.scanner.findings), 0)

    def test_unsupported_file_extension(self):
        """Test handling of unsupported file extensions"""
        unsupported_file = 'test.xyz'
        detected_lang = self.scanner.parser_manager.get_file_language(unsupported_file)
        self.assertIsNone(detected_lang)


class TestParserManager(unittest.TestCase):
    """Test parser manager functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser_manager = Scanner().parser_manager

    def test_supported_languages(self):
        """Test that required languages are supported"""
        supported = self.parser_manager.get_supported_languages()

        # At minimum, should support some languages
        # (exact list depends on installed tree-sitter modules)
        self.assertIsInstance(supported, list)

    def test_get_nonexistent_parser(self):
        """Test getting parser for unsupported language"""
        parser = self.parser_manager.get_parser('nonexistent')
        self.assertIsNone(parser)

    def test_language_config_loading(self):
        """Test that language config is loaded"""
        config = self.parser_manager.languages_config
        self.assertIsInstance(config, dict)
        # Should have configuration for known languages
        self.assertGreater(len(config), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
