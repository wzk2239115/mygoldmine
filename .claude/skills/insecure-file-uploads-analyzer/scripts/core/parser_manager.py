"""Manages tree-sitter parser instances"""

class ParserManager:
    def __init__(self, config_path=None):
        self.parsers = {}
        self.config = {}

    def get_parser(self, language):
        return self.parsers.get(language.lower())

    def get_language_config(self, language):
        return self.config.get(language.lower())

    def supported_languages(self):
        return list(self.config.keys())

    def get_extensions(self, language):
        config = self.get_language_config(language)
        return config.get('extensions', []) if config else []
