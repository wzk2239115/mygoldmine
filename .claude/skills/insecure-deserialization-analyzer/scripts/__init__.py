"""
Insecure Deserialization Sink Detector

A tree-sitter based tool for detecting unsafe deserialization operations
across multiple programming languages (PHP, Python, Java, JavaScript).
"""

__version__ = '1.0.0'
__author__ = 'Security Research Team'

from core.scanner import Scanner, Sink
from core.parser_manager import ParserManager
from reports.json_reporter import JSONReporter, SARIFReporter

__all__ = [
    'Scanner',
    'Sink',
    'ParserManager',
    'JSONReporter',
    'SARIFReporter',
]
