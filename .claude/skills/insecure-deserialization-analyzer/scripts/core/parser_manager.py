"""
Parser Manager - Manages tree-sitter parser instances for different languages.
"""

import os
from typing import Dict, Optional
import yaml


class ParserManager:
    """Manages tree-sitter parser instances for different languages."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the parser manager.

        Args:
            config_path: Path to languages.yaml config file
        """
        self.parsers = {}
        self.languages_config = {}

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
        """Load language configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.languages_config = config.get('languages', {})
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config file: {e}")

    def _initialize_parsers(self) -> None:
        """Initialize tree-sitter parsers for supported languages."""
        for lang, config in self.languages_config.items():
            try:
                module_name = config.get('tree_sitter_module')
                if module_name:
                    self._init_parser_for_language(lang, module_name)
            except Exception as e:
                print(f"Warning: Failed to initialize {lang} parser: {e}")

    def _init_parser_for_language(self, language: str, module_name: str) -> None:
        """
        Initialize parser for a specific language.

        Args:
            language: Language name (e.g., 'php', 'python')
            module_name: Tree-sitter module name
        """
        try:
            try:
                # Use tree_sitter_languages package (unified approach)
                from tree_sitter_languages import get_parser
                parser = get_parser(language)
                self.parsers[language] = parser
            except ImportError:
                # Fallback: not available
                pass
        except Exception as e:
            print(f"Warning: Could not initialize parser for {language}: {e}")

    def get_parser(self, language: str) -> Optional[object]:
        """Get parser for a specific language."""
        return self.parsers.get(language)

    def get_language_config(self, language: str) -> Dict:
        """Get configuration for a specific language."""
        return self.languages_config.get(language, {})

    def get_supported_languages(self) -> list:
        """Get list of supported languages."""
        return list(self.languages_config.keys())

    def get_extensions_for_language(self, language: str) -> list:
        """Get file extensions for a language."""
        config = self.get_language_config(language)
        return config.get('extensions', [])
