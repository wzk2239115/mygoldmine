"""Manages tree-sitter parser instances for different programming languages."""

import os
import yaml
from typing import Dict, Optional
from pathlib import Path
from tree_sitter import Parser, Language


class ParserManager:
    """Manages tree-sitter parsers for multiple languages."""

    def __init__(self, config_path: str):
        """
        Initialize ParserManager with language configuration.

        Args:
            config_path: Path to languages.yaml configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.parsers: Dict[str, object] = {}
        self.queries: Dict[str, object] = {}
        self._load_parsers()
        self._load_queries()

    def _load_config(self) -> dict:
        """Load language configuration from YAML file."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get('languages', {})

    def _load_parsers(self):
        """Load tree-sitter parsers for configured languages."""
        # Mapping from language name to the actual module attribute name
        lang_attr_map = {
            'php': 'language_php',
            'python': 'language',
            'java': 'language',
            'javascript': 'language'
        }

        for lang_name, lang_config in self.config.items():
            try:
                module_name = lang_config.get('tree_sitter_module')
                if not module_name:
                    continue

                # Dynamically import the tree-sitter language module
                module = __import__(module_name)

                # Get the language function
                attr_name = lang_attr_map.get(lang_name, 'language')
                if hasattr(module, attr_name):
                    lang_func = getattr(module, attr_name)
                elif hasattr(module, 'language'):
                    lang_func = module.language
                else:
                    # Try to find any 'language' function in the module
                    lang_func = None
                    for attr in dir(module):
                        if 'language' in attr.lower() and callable(getattr(module, attr)):
                            lang_func = getattr(module, attr)
                            break
                    if not lang_func:
                        raise AttributeError(f"No language function found in {module_name}")

                # Call the language function to get the language object
                lang_obj = lang_func()

                # Create parser and set language
                parser = Parser()
                parser.language = Language(lang_obj)
                self.parsers[lang_name] = parser
            except (ImportError, AttributeError) as e:
                print(f"Warning: Could not load parser for {lang_name}: {e}")

    def _load_queries(self):
        """Load tree-sitter query files for each language."""
        base_dir = Path(self.config_path).parent.parent

        for lang_name, lang_config in self.config.items():
            query_file = lang_config.get('sink_query_file')
            if not query_file:
                continue

            query_path = base_dir / query_file
            if query_path.exists():
                try:
                    parser = self.parsers.get(lang_name)
                    if parser:
                        with open(query_path, 'r', encoding='utf-8') as f:
                            query_text = f.read()
                        # Query will be created when needed by scanner
                        self.queries[lang_name] = {
                            'path': str(query_path),
                            'text': query_text
                        }
                except Exception as e:
                    print(f"Warning: Could not load query for {lang_name}: {e}")

    def get_parser(self, language: str) -> Optional[object]:
        """
        Get parser for specified language.

        Args:
            language: Language name (php, python, java, javascript)

        Returns:
            Parser object or None if not available
        """
        return self.parsers.get(language)

    def get_query_text(self, language: str) -> Optional[str]:
        """
        Get query text for specified language.

        Args:
            language: Language name

        Returns:
            Query text or None if not available
        """
        if language in self.queries:
            return self.queries[language]['text']
        return None

    def get_supported_languages(self) -> list:
        """Get list of supported languages."""
        return list(self.config.keys())

    def get_extensions(self, language: str) -> list:
        """
        Get file extensions for specified language.

        Args:
            language: Language name

        Returns:
            List of file extensions
        """
        if language in self.config:
            return self.config[language].get('extensions', [])
        return []

    def get_language_by_extension(self, extension: str) -> Optional[str]:
        """
        Get language name by file extension.

        Args:
            extension: File extension (e.g., '.php', '.py')

        Returns:
            Language name or None
        """
        for lang, config in self.config.items():
            if extension in config.get('extensions', []):
                return lang
        return None
