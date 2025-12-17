"""
Scanner - 主扫描引擎，运行Sink查询
"""
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from tree_sitter import Query, QueryCursor
from .parser_manager import ParserManager


class Scanner:
    """XSS Sink检测扫描器"""

    def __init__(self, parser_manager: ParserManager = None):
        """
        初始化Scanner

        Args:
            parser_manager: ParserManager实例
        """
        self.parser_manager = parser_manager or ParserManager()
        self.results: List[Dict] = []

    def scan_file(self, filepath: str) -> List[Dict]:
        """
        扫描单个文件

        Args:
            filepath: 文件路径

        Returns:
            检测到的XSS Sink列表
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        # 根据文件扩展名确定语言
        language = self.parser_manager.get_language_for_file(filepath)
        if language is None:
            return []

        # 读取文件内容
        with open(filepath, 'rb') as f:
            source_code = f.read()

        return self._scan_content(filepath, language, source_code)

    def scan_directory(self, directory: str) -> List[Dict]:
        """
        扫描整个目录

        Args:
            directory: 目录路径

        Returns:
            所有检测到的XSS Sink列表
        """
        if not os.path.isdir(directory):
            raise NotADirectoryError(f"Not a directory: {directory}")

        all_results = []
        supported_extensions = set()

        # 收集所有支持的扩展名
        for lang in self.parser_manager.get_supported_languages():
            supported_extensions.update(self.parser_manager.get_extensions(lang))

        # 递归扫描所有支持的文件
        for root, dirs, files in os.walk(directory):
            # 跳过常见的忽略目录
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.venv'}]

            for file in files:
                _, ext = os.path.splitext(file)
                if ext in supported_extensions:
                    filepath = os.path.join(root, file)
                    try:
                        results = self.scan_file(filepath)
                        all_results.extend(results)
                    except Exception as e:
                        print(f"Error scanning {filepath}: {e}")

        return all_results

    def _scan_content(self, filepath: str, language: str, source_code: bytes) -> List[Dict]:
        """
        使用Sink查询扫描代码内容

        Args:
            filepath: 文件路径
            language: 编程语言
            source_code: 源代码（字节形式）

        Returns:
            检测到的Sink列表
        """
        results = []

        try:
            # 解析代码
            tree = self.parser_manager.parse(language, source_code)
            if tree is None:
                return results

            # 获取查询文本
            query_text = self.parser_manager.get_query(language)
            if not query_text:
                return results

            # 创建查询对象
            lang_obj = self.parser_manager.get_language(language)
            if lang_obj is None:
                return results

            try:
                query = Query(lang_obj, query_text)
            except Exception as e:
                print(f"Error creating query for {language}: {e}")
                return results

            # 执行查询 - 使用新的tree-sitter API
            cursor = QueryCursor(query)

            # 处理结果
            source_lines = source_code.decode('utf-8', errors='ignore').split('\n')

            for pattern_index, match_captures in cursor.matches(tree.root_node):
                # 遍历每个capture（可能有多个同名的capture）
                for capture_name, nodes in match_captures.items():
                    for node in nodes:
                        result = {
                            'file': filepath,
                            'language': language,
                            'sink_type': capture_name,
                            'line': node.start_point[0] + 1,
                            'column': node.start_point[1],
                            'end_line': node.end_point[0] + 1,
                            'end_column': node.end_point[1],
                            'code': self._get_line_content(source_lines, node.start_point[0]),
                            'node_text': node.text.decode('utf-8', errors='ignore')
                        }
                        results.append(result)

        except Exception as e:
            print(f"Error scanning file {filepath}: {e}")

        return results

    def _get_line_content(self, lines: List[str], line_index: int) -> str:
        """获取指定行的内容"""
        if 0 <= line_index < len(lines):
            return lines[line_index].strip()
        return ""
