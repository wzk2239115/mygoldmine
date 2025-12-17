"""SQL Injection Sink Detectors.

This module provides language-specific detectors for identifying SQL injection sinks
in various programming languages.
"""

from .base import SinkDetector
from .php_detector import PHPSinkDetector
from .python_detector import PythonSinkDetector
from .javascript_detector import JavaScriptSinkDetector
from .typescript_detector import TypeScriptSinkDetector
from .java_detector import JavaSinkDetector
from .c_detector import CSinkDetector
from .cpp_detector import CppSinkDetector
from .go_detector import GoSinkDetector
from .rust_detector import RustSinkDetector

__all__ = [
    'SinkDetector',
    'PHPSinkDetector',
    'PythonSinkDetector',
    'JavaScriptSinkDetector',
    'TypeScriptSinkDetector',
    'JavaSinkDetector',
    'CSinkDetector',
    'CppSinkDetector',
    'GoSinkDetector',
    'RustSinkDetector',
]
