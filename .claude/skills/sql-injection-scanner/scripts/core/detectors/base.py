"""Base class for sink detection."""

from typing import List, Dict, Any

# Make tree_sitter optional
try:
    import tree_sitter
    from tree_sitter import Language, Parser
except ImportError:
    tree_sitter = None


class SinkDetector:
    """Base class for sink detection."""

    def __init__(self, language_name: str, sink_config: Dict[str, Any]):
        self.language_name = language_name
        self.sink_config = sink_config
        self.sinks = []

    def detect(self, tree, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        """Detect sinks in AST. Must be implemented by subclasses."""
        raise NotImplementedError
