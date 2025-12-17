"""Parser manager for CSRF sink detection."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
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
                    lib_name = self.LANGUAGE_LIBS[lang]
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
        return [lang for lang, config in languages.items() if config.get('enabled', False)]

    def get_query_file(self, language: str, query_type: str = 'routes') -> Optional[Path]:
        """Get the path to a tree-sitter query file for a language."""
        script_dir = Path(__file__).parent.parent

        if language == 'php':
            return script_dir / f"languages/php/queries/actions.scm"
        elif language == 'python':
            return script_dir / f"languages/python/queries/{query_type}.scm"
        elif language == 'java':
            return script_dir / f"languages/java/queries/controllers.scm"
        elif language in ('javascript', 'typescript'):
            return script_dir / f"languages/javascript/queries/{query_type}.scm"

        return None

    def load_query(self, language: str, query_type: str = 'routes') -> Optional[str]:
        """Load a tree-sitter query file."""
        query_file = self.get_query_file(language, query_type)
        if query_file and query_file.exists():
            with open(query_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None
