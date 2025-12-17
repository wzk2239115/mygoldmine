"""Parser manager for handling multiple language parsers."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import yaml

# Try to import tree_sitter, but make it optional
try:
    import tree_sitter
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class ParserManager:
    """Manages parsers for different programming languages."""

    # Map language names to their tree-sitter library paths
    LANGUAGE_LIBS = {
        'php': 'php',
        'python': 'python',
        'javascript': 'javascript',
        'typescript': 'javascript',
        'java': 'java',
    }

    def __init__(self, config_path: str = None):
        """Initialize parser manager."""
        self.config = self._load_config(config_path)
        self.parsers: Dict[str, Any] = {}
        self._initialized = False

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from YAML."""
        if config_path is None:
            # Find config relative to this file
            script_dir = Path(__file__).parent.parent
            config_path = script_dir / "config" / "languages.yaml"

        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def initialize_parsers(self, languages: List[str] = None):
        """Initialize tree-sitter parsers for specified languages."""
        if not HAS_TREE_SITTER:
            return

        if languages is None:
            languages = list(self.LANGUAGE_LIBS.keys())

        for lang in languages:
            if lang in self.LANGUAGE_LIBS:
                try:
                    # Try to load language
                    lib_name = self.LANGUAGE_LIBS[lang]
                    # This would require tree_sitter to be properly built
                    # For now, we'll handle this gracefully
                except Exception as e:
                    print(f"Warning: Could not initialize parser for {lang}: {e}")

    def get_sink_config(self, language: str) -> List[Dict[str, Any]]:
        """Get sink configuration for a language."""
        lang_config = self.config.get('languages', {}).get(language, {})
        return lang_config.get('sinks', [])

    def get_file_patterns(self, language: str) -> List[str]:
        """Get file patterns for a language."""
        lang_config = self.config.get('languages', {}).get(language, {})
        return lang_config.get('file_patterns', [])

    def is_language_enabled(self, language: str) -> bool:
        """Check if language is enabled."""
        lang_config = self.config.get('languages', {}).get(language, {})
        return lang_config.get('enabled', False)

    def get_enabled_languages(self) -> List[str]:
        """Get list of enabled languages."""
        languages = self.config.get('languages', {})
        return [lang for lang, cfg in languages.items() if cfg.get('enabled', False)]

    def get_parser(self, language: str) -> Optional[Any]:
        """Get parser for language."""
        if language not in self.parsers and HAS_TREE_SITTER:
            try:
                # Try to load and cache parser
                lib_name = self.LANGUAGE_LIBS.get(language)
                if lib_name:
                    # Implementation would go here
                    pass
            except Exception as e:
                print(f"Could not get parser for {language}: {e}")
                return None
        return self.parsers.get(language)
