"""Core module for insecure deserialization sink detector."""

from .scanner import Scanner, Sink
from .parser_manager import ParserManager

__all__ = ['Scanner', 'Sink', 'ParserManager']
