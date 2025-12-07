"""C++ sink detector for SQL injection vulnerabilities."""

from typing import List, Dict, Any, Optional
from .c_detector import CSinkDetector


class CppSinkDetector(CSinkDetector):
    """Detects SQL injection sinks in C++ code.

    Inherits from C detector as C++ has similar AST structure for function calls.
    """
    pass
