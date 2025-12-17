"""Core modules for CSRF sink detection."""

from .parser_manager import ParserManager
from .scanner import (
    CSRFSinkScanner,
    PHPCSRFDetector,
    PythonCSRFDetector,
    JavaCSRFDetector,
    JavaScriptCSRFDetector,
)

__all__ = [
    'ParserManager',
    'CSRFSinkScanner',
    'PHPCSRFDetector',
    'PythonCSRFDetector',
    'JavaCSRFDetector',
    'JavaScriptCSRFDetector',
]
