"""PHP sink detector for SQL injection vulnerabilities."""

from typing import List, Dict, Any, Optional
from .base import SinkDetector

# Make tree_sitter optional
try:
    import tree_sitter
    from tree_sitter import Language, Parser
except ImportError:
    tree_sitter = None


class PHPSinkDetector(SinkDetector):
    """Detects SQL injection sinks in PHP code."""

    def detect(self, tree, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        """Detect PHP SQL sinks."""
        sinks = []
        cursor = tree_sitter.TreeCursor(tree.root_node)
        lines = source_code.split('\n')

        self._traverse_node(cursor.node, cursor, sinks, source_code, lines, file_path)
        return sinks

    def _traverse_node(self, node, cursor, sinks, source_code, lines, file_path):
        """Recursively traverse AST nodes."""
        if self._is_sink_call(node):
            sink_info = self._extract_sink_info(node, source_code, lines, file_path)
            if sink_info:
                sinks.append(sink_info)

        for child in node.children:
            self._traverse_node(child, cursor, sinks, source_code, lines, file_path)

    def _is_sink_call(self, node) -> bool:
        """Check if node is a sink function/method call."""
        if node.type == "function_call_expression":
            func_name = self._get_function_name(node)
            if func_name:
                return any(sink['name'] == func_name for sink in self.sink_config)
        elif node.type == "member_access_expression" or node.type == "method_call_expression":
            method_name = self._get_method_name(node)
            if method_name:
                return any(sink['name'] == method_name for sink in self.sink_config)
        return False

    def _get_function_name(self, node) -> Optional[str]:
        """Extract function name from function call."""
        if node.child_count > 0:
            for child in node.children:
                if child.type in ("name", "qualified_name"):
                    return child.text.decode() if isinstance(child.text, bytes) else child.text
        return None

    def _get_method_name(self, node) -> Optional[str]:
        """Extract method name from method call."""
        for child in node.children:
            if child.type == "property_name":
                return child.text.decode() if isinstance(child.text, bytes) else child.text
        return None

    def _extract_sink_info(self, node, source_code, lines, file_path) -> Optional[Dict[str, Any]]:
        """Extract detailed sink information."""
        func_name = self._get_function_name(node) or self._get_method_name(node)
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
        """Extract parameters from function/method call."""
        params = []
        for child in node.children:
            if child.type == "arguments":
                for arg in child.children:
                    if arg.type not in ("(", ")", ","):
                        arg_text = arg.text.decode() if isinstance(arg.text, bytes) else arg.text
                        params.append(arg_text)
        return params
