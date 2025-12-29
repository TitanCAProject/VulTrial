"""
JavaScript/TypeScript search backend for VulTrial
Provides code search and analysis capabilities for JS/TS codebases
"""

from .search_backend import JSSearchBackend
from .data_structures import JSSearchResult, JSCallChainResult, JSTaintPath

__all__ = [
    'JSSearchBackend',
    'JSSearchResult',
    'JSCallChainResult',
    'JSTaintPath',
]

