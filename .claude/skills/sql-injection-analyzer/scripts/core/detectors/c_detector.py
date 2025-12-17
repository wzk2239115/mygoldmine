"""C/C++ sink detector for SQL injection vulnerabilities."""

from typing import List, Dict, Any, Optional
from .base import SinkDetector

# Make tree_sitter optional
try:
    import tree_sitter
    from tree_sitter import Language, Parser
except ImportError:
    tree_sitter = None


class CSinkDetector(SinkDetector):
    """Detects SQL injection sinks in C/C++ code."""

    def detect(self, tree, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        """Detect C/C++ SQL sinks."""
        sinks = []
        self._traverse_node(tree.root_node, sinks, source_code, file_path)
        return sinks

    def _traverse_node(self, node, sinks, source_code, file_path):
        """Recursively traverse AST nodes."""
        if self._is_sink_call(node):
            sink_info = self._extract_sink_info(node, source_code, file_path)
            if sink_info:
                sinks.append(sink_info)

        for child in node.children:
            self._traverse_node(child, sinks, source_code, file_path)

    def _is_sink_call(self, node) -> bool:
        """Check if node is a sink function call."""
        if node.type == "call_expression":
            func_name = self._get_function_name(node)
            if func_name:
                return any(sink['name'] == func_name for sink in self.sink_config)
        return False

    def _get_function_name(self, node) -> Optional[str]:
        """Extract function name from function call."""
        if node.child_count > 0:
            first_child = node.children[0]
            if first_child.type == "identifier":
                return first_child.text.decode() if isinstance(first_child.text, bytes) else first_child.text
        return None

    def _extract_sink_info(self, node, source_code, file_path) -> Optional[Dict[str, Any]]:
        """Extract detailed sink information."""
        func_name = self._get_function_name(node)
        if not func_name:
            return None

        sink_config = next((s for s in self.sink_config if s['name'] == func_name), None)
        if not sink_config:
            return None

        line, column = node.start_point
        context = self._get_context(source_code, node)

        return {
            "file": file_path,
            "line": line + 1,
            "column": column + 1,
            "sink_type": func_name,
            "sink_category": sink_config.get("category", "unknown"),
            "function_name": func_name,
            "parameters": self._extract_parameters(node),
            "vulnerable_params": sink_config.get("vulnerable_params", [0]),
            "context": context,
        }

    def _get_context(self, source_code: str, node, context_lines: int = 1) -> str:
        """Get source code context around the sink."""
        lines = source_code.split('\n')
        start_line = max(0, node.start_point[0] - context_lines)
        end_line = min(len(lines), node.end_point[0] + context_lines + 1)
        context = '\n'.join(lines[start_line:end_line])
        return context.strip()

    def _extract_parameters(self, node) -> List[str]:
        """Extract parameters from function call."""
        params = []
        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type not in ("(", ")", ","):
                        arg_text = arg.text.decode() if isinstance(arg.text, bytes) else arg.text
                        params.append(arg_text)
        return params
