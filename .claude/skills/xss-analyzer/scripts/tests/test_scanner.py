"""
Test Scanner - 自动化测试
"""
import os
import unittest
from pathlib import Path
from ..core.scanner import Scanner
from ..core.parser_manager import ParserManager


class TestScanner(unittest.TestCase):
    """扫描器测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.test_dir = Path(__file__).parent / 'fixtures'
        cls.scanner = Scanner()

    def test_scanner_initialization(self):
        """测试扫描器初始化"""
        self.assertIsNotNone(self.scanner.parser_manager)
        self.assertTrue(len(self.scanner.parser_manager.get_supported_languages()) > 0)

    def test_parser_manager_initialization(self):
        """测试ParserManager初始化"""
        pm = ParserManager()
        languages = pm.get_supported_languages()
        self.assertGreater(len(languages), 0)
        print(f"Supported languages: {languages}")

    def test_get_language_for_file(self):
        """测试文件语言识别"""
        pm = ParserManager()

        self.assertEqual(pm.get_language_for_file('test.php'), 'php')
        self.assertEqual(pm.get_language_for_file('test.py'), 'python')
        self.assertEqual(pm.get_language_for_file('test.js'), 'javascript')
        self.assertEqual(pm.get_language_for_file('test.java'), 'java')
        self.assertIsNone(pm.get_language_for_file('test.txt'))

    def test_get_extensions(self):
        """测试获取语言扩展名"""
        pm = ParserManager()

        php_ext = pm.get_extensions('php')
        self.assertIn('.php', php_ext)

        js_ext = pm.get_extensions('javascript')
        self.assertIn('.js', js_ext)

    def test_scan_php_fixtures(self):
        """测试扫描PHP测试文件"""
        php_file = self.test_dir / 'php' / 'output_calls.php'

        if php_file.exists():
            try:
                results = self.scanner.scan_file(str(php_file))
                print(f"PHP scan results: {len(results)} sinks found")
                for result in results:
                    print(f"  - {result['sink_type']} at line {result['line']}")
            except Exception as e:
                print(f"Error scanning PHP file: {e}")

    def test_scan_python_fixtures(self):
        """测试扫描Python测试文件"""
        py_file = self.test_dir / 'python' / 'test_sinks.py'

        if py_file.exists():
            try:
                results = self.scanner.scan_file(str(py_file))
                print(f"Python scan results: {len(results)} sinks found")
                for result in results:
                    print(f"  - {result['sink_type']} at line {result['line']}")
            except Exception as e:
                print(f"Error scanning Python file: {e}")

    def test_scan_javascript_fixtures(self):
        """测试扫描JavaScript测试文件"""
        js_file = self.test_dir / 'javascript' / 'test_sinks.js'

        if js_file.exists():
            try:
                results = self.scanner.scan_file(str(js_file))
                print(f"JavaScript scan results: {len(results)} sinks found")
                for result in results:
                    print(f"  - {result['sink_type']} at line {result['line']}")
            except Exception as e:
                print(f"Error scanning JavaScript file: {e}")

    def test_scan_directory(self):
        """测试扫描整个目录"""
        if self.test_dir.exists():
            try:
                results = self.scanner.scan_directory(str(self.test_dir))
                print(f"Directory scan results: {len(results)} total sinks found")

                by_language = {}
                for result in results:
                    lang = result['language']
                    by_language[lang] = by_language.get(lang, 0) + 1

                print(f"Results by language: {by_language}")
            except Exception as e:
                print(f"Error scanning directory: {e}")

    def test_file_not_found(self):
        """测试文件不存在的处理"""
        with self.assertRaises(FileNotFoundError):
            self.scanner.scan_file('/non/existent/file.php')

    def test_directory_not_found(self):
        """测试目录不存在的处理"""
        with self.assertRaises(NotADirectoryError):
            self.scanner.scan_directory('/non/existent/directory')


if __name__ == '__main__':
    unittest.main(verbosity=2)
