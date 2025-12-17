"""
Parser Manager: Manages tree-sitter parser instances for different languages
"""
import os
from typing import Dict, Optional
import yaml

try:
    from tree_sitter import Language, Parser
except ImportError:
    raise ImportError("tree-sitter library not found. Install with: pip install tree-sitter")


class ParserManager:
    """Manages tree-sitter parsers for multiple languages"""

    def __init__(self, config_path: str = None):
        """Initialize parser manager with language configuration"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'config',
                'languages.yaml'
            )

        self.config_path = config_path
        self.languages_config = self._load_config()
        self.parsers: Dict[str, Parser] = {}
        self.languages: Dict[str, Language] = {}
        self._initialize_parsers()

    def _load_config(self) -> dict:
        """Load language configuration from YAML"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get('languages', {})

    def _initialize_parsers(self):
        """Initialize tree-sitter parsers for each language"""
        for lang_name, lang_config in self.languages_config.items():
            try:
                module_name = lang_config.get('tree_sitter_module')
                language_module = __import__(module_name)
                
                # Use 'language_symbol' from config, default to 'language'
                lang_symbol_name = lang_config.get('language_symbol', 'language')
                lang_getter = getattr(language_module, lang_symbol_name)
                
                if callable(lang_getter):
                    lang_capsule = lang_getter()
                else:
                    lang_capsule = lang_getter

                language = Language(lang_capsule)
                parser = Parser(language)
                
                self.parsers[lang_name] = parser
                self.languages[lang_name] = language
            except Exception as e:
                print(f"Warning: Could not initialize parser for {lang_name}: {e}")
                print(f"Install with: pip install {lang_name}_parser")

    def get_parser(self, language: str) -> Optional[Parser]:
        """Get parser for a specific language"""
        return self.parsers.get(language)

    def get_language(self, language: str) -> Optional[Language]:
        """Get language object for a specific language"""
        return self.languages.get(language)

    def get_file_language(self, file_path: str) -> Optional[str]:
        """Detect language from file extension"""
        _, ext = os.path.splitext(file_path)

        for lang_name, lang_config in self.languages_config.items():
            if ext in lang_config.get('extensions', []):
                return lang_name

        return None

    def supports_language(self, language: str) -> bool:
        """Check if a language is supported"""
        return language in self.parsers

    def get_supported_languages(self) -> list:
        """Get list of supported languages"""
        return list(self.parsers.keys())
