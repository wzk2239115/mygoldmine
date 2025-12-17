"""
Parser Manager - 管理各语言的tree-sitter解析器实例
"""
import os
from typing import Dict, Optional
import yaml
from tree_sitter import Parser, Language
from tree_sitter_php import language_php
from tree_sitter_python import language as py_language
from tree_sitter_javascript import language as js_language
from tree_sitter_java import language as java_language


class ParserManager:
    """管理不同编程语言的tree-sitter解析器"""

    def __init__(self, config_path: str = None):
        """
        初始化ParserManager

        Args:
            config_path: languages.yaml配置文件路径
        """
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, object] = {}
        self.language_config: Dict = {}
        self.queries: Dict[str, str] = {}

        # Language mapping for new tree-sitter API
        self.language_map = {
            'php': language_php,
            'python': py_language,
            'javascript': js_language,
            'java': java_language
        }

        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'config',
                'languages.yaml'
            )

        self._load_config(config_path)
        self._initialize_parsers()

    def _load_config(self, config_path: str) -> None:
        """加载语言配置文件"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not config or 'languages' not in config:
            raise ValueError("Invalid configuration file format")

        self.language_config = config['languages']

    def _initialize_parsers(self) -> None:
        """初始化所有配置的语言的解析器"""
        base_dir = os.path.dirname(os.path.dirname(__file__))

        for lang_name, lang_config in self.language_config.items():
            try:
                # Get language from mapping
                if lang_name not in self.language_map:
                    print(f"Warning: No language mapping for {lang_name}")
                    continue

                language_func = self.language_map[lang_name]

                # 创建解析器 - 新的tree-sitter API需要将language函数返回的capsule包装成Language对象
                language_obj = Language(language_func())
                parser = Parser()
                parser.language = language_obj

                self.parsers[lang_name] = parser
                self.languages[lang_name] = language_obj

                # 加载查询文件
                query_file = lang_config.get('query_file')
                if query_file:
                    query_path = os.path.join(base_dir, query_file)
                    if os.path.exists(query_path):
                        with open(query_path, 'r', encoding='utf-8') as f:
                            self.queries[lang_name] = f.read()

            except Exception as e:
                print(f"Warning: Error initializing parser for {lang_name}: {e}")

    def get_parser(self, language: str) -> Optional[Parser]:
        """获取指定语言的解析器"""
        return self.parsers.get(language)

    def get_language(self, language: str) -> Optional[Language]:
        """获取指定语言的Language对象"""
        return self.languages.get(language)

    def get_query(self, language: str) -> Optional[str]:
        """获取指定语言的查询文本"""
        return self.queries.get(language)

    def get_extensions(self, language: str) -> list:
        """获取指定语言的文件扩展名"""
        if language in self.language_config:
            return self.language_config[language].get('extensions', [])
        return []

    def get_supported_languages(self) -> list:
        """获取所有支持的语言"""
        return list(self.language_config.keys())

    def get_language_for_file(self, filepath: str) -> Optional[str]:
        """根据文件扩展名获取语言"""
        _, ext = os.path.splitext(filepath)

        for lang_name, lang_config in self.language_config.items():
            if ext in lang_config.get('extensions', []):
                return lang_name

        return None

    def parse(self, language: str, source_code: bytes) -> Optional:
        """
        解析源代码

        Args:
            language: 编程语言名称
            source_code: 源代码（字节形式）

        Returns:
            AST树根节点
        """
        parser = self.get_parser(language)
        if parser is None:
            raise ValueError(f"Parser not found for language: {language}")

        return parser.parse(source_code)
