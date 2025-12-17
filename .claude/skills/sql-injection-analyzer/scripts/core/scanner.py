"""Scanner module for SQL injection sink detection."""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Import detector classes from the detectors module
from .detectors import (
    SinkDetector,
    PHPSinkDetector,
    PythonSinkDetector,
    JavaScriptSinkDetector,
    TypeScriptSinkDetector,
    JavaSinkDetector,
    CSinkDetector,
    CppSinkDetector,
    GoSinkDetector,
    RustSinkDetector
)

# Make tree_sitter optional
try:
    import tree_sitter
    from tree_sitter import Language, Parser
except ImportError:
    tree_sitter = None
