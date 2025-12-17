"""
Parser Manager: Manages tree-sitter parser instances for different languages.
"""

import os
from typing import Dict, Optional
from pathlib import Path
import yaml

try:
    from tree_sitter import Language, Parser
except ImportError:
    raise ImportError("tree-sitter package is required. Install with: pip install tree-sitter")


class ParserManager:
    """Manages tree-sitter parser instances for JWT sink detection."""

    def __init__(self, config_path: str = None):
        """
        Initialize the parser manager with language configurations.

        Args:
            config_path: Path to languages.yaml config file
        """
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, Language] = {}
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load language configuration from YAML file."""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "config",
                "languages.yaml"
            )

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def get_parser(self, language: str) -> Optional[Parser]:
        """
        Get or create a parser for the specified language.

        Args:
            language: Language name (python, php, javascript, java)

        Returns:
            Parser instance or None if language not supported
        """
        if language in self.parsers:
            return self.parsers[language]

        try:
            # Dynamically import and load the tree-sitter language
            module_name = self.config['languages'][language]['tree_sitter_module']
            lang_obj = self._load_language(module_name)

            parser = Parser()
            parser.language = lang_obj

            self.parsers[language] = parser
            self.languages[language] = lang_obj
            return parser

        except (KeyError, ImportError) as e:
            print(f"Warning: Could not load parser for {language}: {e}")
            return None

    def _load_language(self, module_name: str) -> Language:
        """
        Dynamically load a tree-sitter language module.

        Args:
            module_name: Module name like 'tree_sitter_python'

        Returns:
            Language object
        """
        try:
            # Try to import the module
            module = __import__(module_name)

            # Try different language function names
            lang_capsule = None

            # Standard: language()
            if hasattr(module, 'language'):
                lang_capsule = module.language()
            # PHP variants: language_php() or language_php_only()
            elif hasattr(module, 'language_php'):
                lang_capsule = module.language_php()
            elif hasattr(module, 'language_php_only'):
                lang_capsule = module.language_php_only()
            # JavaScript variants: language() should work
            elif hasattr(module, 'language'):
                lang_capsule = module.language()
            else:
                # Fallback: try to load from compiled .so file
                return Language(module_name)

            # Wrap capsule in Language object
            return Language(lang_capsule)

        except Exception as e:
            raise ImportError(f"Failed to load tree-sitter language {module_name}: {e}")

    def get_extensions(self, language: str) -> list:
        """Get file extensions for a language."""
        if language in self.config['languages']:
            return self.config['languages'][language]['extensions']
        return []

    def get_query_file(self, language: str) -> str:
        """Get the query file name for a language."""
        if language in self.config['languages']:
            return self.config['languages'][language]['query_file']
        return "jwt_sinks.scm"

    def get_supported_languages(self) -> list:
        """Get list of supported languages."""
        return list(self.config['languages'].keys())

    def get_language_priority(self, language: str) -> int:
        """Get priority of a language (lower = higher priority)."""
        if language in self.config['languages']:
            return self.config['languages'][language].get('priority', 999)
        return 999

    def is_supported(self, language: str) -> bool:
        """Check if a language is supported."""
        return language in self.config['languages']
