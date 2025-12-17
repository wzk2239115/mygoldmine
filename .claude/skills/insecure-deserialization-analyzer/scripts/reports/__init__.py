"""Reports module for insecure deserialization sink detector."""

from .json_reporter import JSONReporter, SARIFReporter

__all__ = ['JSONReporter', 'SARIFReporter']
